# ╔══════════════════════════════════════════════════════════════╗
# ║  Scheduler — APScheduler async para pipeline periódica      ║
# ║                                                             ║
# ║  Soporta reconfiguración dinámica desde pipeline_config     ║
# ║  y pausa/reanudación remota desde el dashboard.             ║
# ╚══════════════════════════════════════════════════════════════╝

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from config import settings
from failure_handler import HeartbeatMonitor
from loguru import logger
from services.supabase_client import get_client, supabase
from services.tracker import tracker_service
from supabase_service import (
    cleanup_pipeline_logs,
    cleanup_usage_metrics,
    get_due_follow_up_applications,
    get_pipeline_config,
    get_telegram_enabled_users,
    mark_follow_up_reminders_sent,
)
from telegram_notifier import send_follow_up_reminder_for_user

# UUID fijo de la fila singleton en pipeline_config
SINGLETON_ID = "00000000-0000-0000-0000-000000000001"


class SchedulerService:
    """
    Scheduler de producción. Lee la configuración desde Supabase
    y permite reconfiguración dinámica sin reiniciar.
    """

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.current_interval_hours = 4.0
        self.job_id = "main_pipeline_sync"
        self.zombie_job_id = "zombie_cleanup"
        self.retention_job_id = "pipeline_retention_cleanup"
        self.follow_up_job_id = "follow_up_reminders"
        self.is_running = False
        self.last_schedule_error: str | None = None

    async def start(self):
        """Arranca el scheduler y carga la configuración inicial."""
        if not self.scheduler.running:
            self.scheduler.start()
            self.is_running = True

            await self.reschedule_from_db()

            # Zombie detection: runs every 5 minutes
            self.scheduler.add_job(
                self._run_zombie_cleanup,
                trigger=IntervalTrigger(minutes=5),
                id=self.zombie_job_id,
                replace_existing=True,
            )
            self.scheduler.add_job(
                self._run_retention_cleanup,
                trigger=IntervalTrigger(hours=6),
                id=self.retention_job_id,
                replace_existing=True,
            )
            self.scheduler.add_job(
                self._run_follow_up_reminders,
                trigger=IntervalTrigger(hours=24),
                id=self.follow_up_job_id,
                replace_existing=True,
            )

            logger.info("Scheduler service started (sync, zombie cleanup, retention cleanup, reminders)")

    async def stop(self):
        """Para el scheduler de forma limpia."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("Scheduler service stopped")

    async def reschedule_from_db(self, config_payload: dict = None):
        """
        Reconfigura dinámicamente el scheduler según pipeline_config.
        Puede ser invocado por un listener de Realtime para actualizaciones
        con latencia cero.
        """
        try:
            if not config_payload:
                result = supabase.table("pipeline_config").select("*").eq("id", SINGLETON_ID).execute()
                if not result.data:
                    raise RuntimeError("No configuration found in DB for rescheduling.")
                config_payload = result.data[0]

            interval_hours = float(config_payload.get("schedule_interval_hours", 4.0))
            is_paused = bool(config_payload.get("is_paused", False))
            job = self.scheduler.get_job(self.job_id) if self.scheduler.running else None

            if is_paused:
                if job:
                    self.scheduler.remove_job(self.job_id)
                    logger.warning("Pipeline PAUSED via remote config.")
                self.current_interval_hours = interval_hours
                self.last_schedule_error = None
                return self.get_schedule_status(interval_hours, is_paused)

            self.scheduler.add_job(
                tracker_service.trigger_scheduled_run,
                trigger=IntervalTrigger(hours=interval_hours),
                id=self.job_id,
                replace_existing=True,
            )
            self.current_interval_hours = interval_hours
            self.last_schedule_error = None
            logger.success(f"Rescheduled: Pipeline will run every {interval_hours} hours.")
            return self.get_schedule_status(interval_hours, is_paused)
        except Exception as e:
            self.last_schedule_error = str(e)
            logger.error(f"Failed to reschedule from database: {str(e)}")
            raise

    def get_schedule_status(
        self,
        configured_interval_hours: float | None = None,
        is_paused: bool | None = None,
    ) -> dict:
        job = self.scheduler.get_job(self.job_id) if self.scheduler.running else None
        next_run_at = job.next_run_time.isoformat() if job and job.next_run_time else None
        effective_interval_hours = None
        if job and getattr(job.trigger, "interval", None):
            effective_interval_hours = round(job.trigger.interval.total_seconds() / 3600, 2)

        return {
            "scheduler_running": self.scheduler.running,
            "scheduled_sync_active": job is not None,
            "configured_interval_hours": configured_interval_hours,
            "effective_interval_hours": effective_interval_hours,
            "next_run_at": next_run_at,
            "is_paused": is_paused,
            "last_schedule_error": self.last_schedule_error,
        }

    async def trigger_now(self, parameters: dict = None):
        """Ejecución inmediata disparada por la API."""
        await tracker_service.start_run(
            triggered_by="manual",
            since_date=parameters.get("since_date") if parameters else None,
        )
        logger.info("Manual synchronization triggered via Scheduler")

    def _run_zombie_cleanup(self):
        """Detect and kill zombie pipeline runs."""
        try:
            client = get_client()
            monitor = HeartbeatMonitor(client)
            killed = monitor.cleanup_zombies()
            if killed > 0:
                logger.warning(f"Zombie cleanup: killed {killed} stale run(s)")
        except Exception as e:
            logger.error(f"Zombie cleanup failed: {e}")

    def _run_retention_cleanup(self):
        try:
            client = get_client()
            config = get_pipeline_config(client)
            retention_days = int(config.get("retention_days") or 30)
            deleted_logs = cleanup_pipeline_logs(client, retention_days)
            deleted_usage = cleanup_usage_metrics(client, retention_days)
            if deleted_logs or deleted_usage:
                logger.info(
                    "Retention cleanup removed "
                    f"{deleted_logs} pipeline logs and {deleted_usage} usage rows"
                )
        except Exception as error:
            logger.error(f"Retention cleanup failed: {error}")

    def _run_follow_up_reminders(self):
        try:
            client = get_client()
            users = get_telegram_enabled_users(client)
            if not users:
                return

            sent_count = 0
            for user in users:
                reminders = get_due_follow_up_applications(
                    client,
                    user_id=user["id"],
                    reminder_after_days=settings.follow_up_reminder_days,
                    repeat_interval_days=settings.follow_up_reminder_repeat_days,
                )
                if not reminders:
                    continue

                sent, error = send_follow_up_reminder_for_user(
                    user,
                    reminders,
                    reminder_days=settings.follow_up_reminder_days,
                )
                if sent:
                    mark_follow_up_reminders_sent(
                        client,
                        [reminder.application_id for reminder in reminders],
                    )
                    sent_count += 1
                elif error:
                    logger.warning(
                        f"Follow-up reminder failed for user {user.get('email') or user['id']}: {error}"
                    )

            if sent_count:
                logger.info(f"Sent follow-up reminders to {sent_count} user(s)")
        except Exception as error:
            logger.error(f"Follow-up reminder job failed: {error}")


# Instancia global
scheduler_service = SchedulerService()
