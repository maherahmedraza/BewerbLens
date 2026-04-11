# ╔══════════════════════════════════════════════════════════════╗
# ║  Scheduler — APScheduler async para pipeline periódica      ║
# ║                                                             ║
# ║  Soporta reconfiguración dinámica desde pipeline_config     ║
# ║  y pausa/reanudación remota desde el dashboard.             ║
# ╚══════════════════════════════════════════════════════════════╝

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from services.supabase_client import supabase
from services.tracker import tracker_service

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
        self.is_running = False

    async def start(self):
        """Arranca el scheduler y carga la configuración inicial."""
        if not self.scheduler.running:
            self.scheduler.start()
            self.is_running = True

            await self.reschedule_from_db()
            logger.info("Scheduler service started")

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
            # 1. Obtener configuración si no fue proporcionada
            if not config_payload:
                result = supabase.table("pipeline_config").select("*").eq("id", SINGLETON_ID).execute()
                if not result.data:
                    logger.warning("No configuration found in DB for rescheduling.")
                    return
                config_payload = result.data[0]

            interval_hours = float(config_payload.get("schedule_interval_hours", 4.0))
            is_paused = config_payload.get("is_paused", False)

            # 2. Manejar estado de pausa
            job = self.scheduler.get_job(self.job_id)

            if is_paused:
                if job:
                    self.scheduler.remove_job(self.job_id)
                    logger.warning("Pipeline PAUSED via remote config.")
                return

            # 3. Crear o actualizar el job si cambió el intervalo
            if not job or interval_hours != self.current_interval_hours:
                self.scheduler.add_job(
                    tracker_service.trigger_scheduled_run,
                    trigger=IntervalTrigger(hours=interval_hours),
                    id=self.job_id,
                    replace_existing=True,
                )
                self.current_interval_hours = interval_hours
                logger.success(f"Rescheduled: Pipeline will run every {interval_hours} hours.")

        except Exception as e:
            logger.error(f"Failed to reschedule from database: {str(e)}")

    async def trigger_now(self, parameters: dict = None):
        """Ejecución inmediata disparada por la API."""
        await tracker_service.start_run(
            triggered_by="manual",
            since_date=parameters.get("since_date") if parameters else None,
        )
        logger.info("Manual synchronization triggered via Scheduler")


# Instancia global
scheduler_service = SchedulerService()
