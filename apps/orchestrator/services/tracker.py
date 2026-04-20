# ╔══════════════════════════════════════════════════════════════╗
# ║  Tracker Service (Orchestrator Wrapper)                     ║
# ║                                                             ║
# ║  Punto de entrada único para ejecutar la pipeline.          ║
# ║  Provee tanto ejecución directa (run_tracker_task) como     ║
# ║  la clase TrackerService que usa el scheduler y los routers.║
# ╚══════════════════════════════════════════════════════════════╝

import uuid
from datetime import date, datetime, timezone

from loguru import logger

from models import PIPELINE_STAGE_ORDER, PipelineStage, SyncMode
from supabase_service import create_pipeline_run, get_client, get_last_checkpoint_for_user, init_pipeline_steps
from tracker import PipelineCancelledError, run_pipeline_multiuser


def run_tracker_task(payload: dict) -> dict:
    """
    Punto de entrada para el worker: ejecuta una tarea de pipeline desde
    la etapa indicada en pipeline_tasks.parameters.start_stage.
    """
    since_date_str = payload.get("since_date")
    since_date = None
    if since_date_str:
        since_date = datetime.fromisoformat(since_date_str).date()

    user_id = payload.get("user_id")
    if not user_id:
        raise ValueError("Missing user_id in task payload")

    return run_pipeline_multiuser(
        user_id=user_id,
        since_date=since_date,
        run_id=payload.get("run_id", "orchestrated"),
        internal_id=payload.get("internal_id"),
        start_stage=payload.get("start_stage", PipelineStage.INGESTION.value),
        sync_mode=payload.get("sync_mode", SyncMode.BACKFILL.value),
    )


class TrackerService:
    """
    Servicio de alto nivel usado por el scheduler y los routers REST.
    Crea y controla pipeline_runs, administra reruns por etapa y delega
    la ejecución al worker mediante pipeline_tasks.
    """

    async def start_run(
        self,
        user_id: str,
        triggered_by: str = "manual",
        since_date: date | None = None,
    ) -> dict:
        client = get_client()
        user_profile = self._load_user_profile(client, user_id)
        sync_mode = self._resolve_sync_mode(user_profile, triggered_by)

        if since_date is None:
            since_date = self._resolve_since_date(client, user_id, user_profile, sync_mode)

        self._mark_sync_running(client, user_id, sync_mode, since_date if sync_mode == SyncMode.BACKFILL else None)

        run_label = f"RUN-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        internal_id, _started_at = create_pipeline_run(
            client,
            run_label,
            user_id=user_id,
            triggered_by=triggered_by,
            since_date=since_date,
        )
        if not internal_id:
            raise RuntimeError("No se pudo crear el registro de pipeline_run")

        init_pipeline_steps(client, internal_id)
        self._enqueue_run_task(
            client=client,
            user_id=user_id,
            run_id=internal_id,
            run_label=run_label,
            since_date=since_date,
            triggered_by=triggered_by,
            start_stage=PipelineStage.INGESTION,
            sync_mode=sync_mode,
        )

        logger.info(f"Pipeline run enqueued: {run_label} (id={internal_id})")
        return {"run_id": run_label, "id": internal_id, "status": "running", "current_phase": "ingestion"}

    async def cancel_run(self, run_identifier: str) -> dict:
        client = get_client()
        run = self._resolve_run(client, run_identifier)
        current_status = run.get("status")

        if current_status in {"success", "failed", "cancelled"}:
            return run

        tasks = client.table("pipeline_tasks").select("id, status").eq("run_id", run["id"]).execute().data or []
        pending_tasks = [task for task in tasks if task.get("status") == "pending"]

        if pending_tasks:
            for task in pending_tasks:
                client.table("pipeline_tasks").update({"status": "failed"}).eq("id", task["id"]).execute()
            self._mark_steps_from(client, run["id"], self._detect_resume_stage(client, run["id"]), "skipped", "Cancelled by user before execution.")
            update_data = {
                "status": "cancelled",
                "error_message": "Cancelled by user.",
                "ended_at": datetime.now(timezone.utc).isoformat(),
            }
        else:
            update_data = {
                "status": "cancelling",
                "error_message": "Cancellation requested by user.",
            }

        client.table("pipeline_runs").update(update_data).eq("id", run["id"]).execute()
        self._insert_control_log(client, run["id"], "WARNING", update_data["error_message"])

        run.update(update_data)
        return run

    async def resume_run(self, run_identifier: str) -> dict:
        client = get_client()
        run = self._resolve_run(client, run_identifier)

        if run.get("status") == "running":
            raise RuntimeError("Run is already active.")

        start_stage = self._detect_resume_stage(client, run["id"])
        return self._requeue_existing_run(client, run, start_stage, triggered_by="resume")

    async def rerun_stage(self, run_identifier: str, stage: str | PipelineStage) -> dict:
        client = get_client()
        run = self._resolve_run(client, run_identifier)

        if run.get("status") in {"running", "pending", "cancelling"}:
            raise RuntimeError("Cannot rerun a stage while the run is active.")

        stage_to_rerun = stage if isinstance(stage, PipelineStage) else PipelineStage(stage)
        return self._requeue_existing_run(
            client,
            run,
            stage_to_rerun,
            triggered_by=f"rerun:{stage_to_rerun.value}",
        )

    async def trigger_scheduled_run(self):
        try:
            client = get_client()
            users = (
                client.table("user_profiles")
                .select("id")
                .or_("gmail_credentials.not.is.null,gmail_connected_via.eq.env_fallback")
                .eq("sync_mode", SyncMode.INCREMENTAL.value)
                .execute()
            )

            if not users.data:
                logger.info("No users with active gmail_credentials found for scheduling.")
                return

            for user in users.data:
                user_id = user["id"]
                try:
                    result = await self.start_run(user_id=user_id, triggered_by="scheduler")
                    logger.info(f"Scheduled run started for user {user_id}: {result['run_id']}")
                except Exception as error:
                    logger.error(f"Scheduled run failed for user {user_id}: {str(error)}")
        except Exception as error:
            logger.error(f"Scheduled batch run failed to start: {str(error)}")

    def _enqueue_run_task(
        self,
        client,
        user_id: str,
        run_id: str,
        run_label: str,
        since_date: date | None,
        triggered_by: str,
        start_stage: PipelineStage,
        sync_mode: SyncMode,
    ) -> None:
        task_data = {
            "task_type": "sync",
            "status": "pending",
            "user_id": user_id,
            "parameters": {
                "user_id": user_id,
                "since_date": since_date.isoformat() if since_date else None,
                "run_id": run_label,
                "internal_id": run_id,
                "triggered_by": triggered_by,
                "start_stage": start_stage.value,
                "sync_mode": sync_mode.value,
            },
            "run_id": run_id,
        }
        client.table("pipeline_tasks").insert(task_data).execute()

    def _load_user_profile(self, client, user_id: str) -> dict:
        result = client.table("user_profiles").select("*").eq("id", user_id).limit(1).execute()
        if not result.data:
            raise RuntimeError("User profile not found.")
        return result.data[0]

    def _resolve_sync_mode(self, user_profile: dict, triggered_by: str) -> SyncMode:
        if triggered_by == "backfill":
            return SyncMode.BACKFILL
        if triggered_by in {"incremental", "scheduler"}:
            return SyncMode.INCREMENTAL

        stored_mode = user_profile.get("sync_mode") or SyncMode.BACKFILL.value
        try:
            return SyncMode(stored_mode)
        except ValueError:
            return SyncMode.BACKFILL

    def _resolve_since_date(self, client, user_id: str, user_profile: dict, sync_mode: SyncMode) -> date:
        if sync_mode == SyncMode.BACKFILL:
            backfill_start = user_profile.get("backfill_start_date")
            if backfill_start:
                return date.fromisoformat(str(backfill_start))
            return get_last_checkpoint_for_user(client, user_id)

        last_synced_at = user_profile.get("last_synced_at")
        if last_synced_at:
            return datetime.fromisoformat(str(last_synced_at).replace("Z", "+00:00")).date()
        return get_last_checkpoint_for_user(client, user_id)

    def _mark_sync_running(self, client, user_id: str, sync_mode: SyncMode, backfill_start_date: date | None) -> None:
        update_data = {
            "sync_mode": sync_mode.value,
            "sync_status": "running",
            "sync_error": None,
        }
        if backfill_start_date is not None:
            update_data["backfill_start_date"] = backfill_start_date.isoformat()
        client.table("user_profiles").update(update_data).eq("id", user_id).execute()

    def _resolve_run(self, client, run_identifier: str) -> dict:
        try:
            uuid.UUID(run_identifier)
            query = client.table("pipeline_runs").select("*").eq("id", run_identifier)
        except ValueError:
            query = client.table("pipeline_runs").select("*").eq("run_id", run_identifier)

        result = query.limit(1).execute()
        if not result.data:
            raise RuntimeError("Run not found.")
        return result.data[0]

    def _detect_resume_stage(self, client, run_id: str) -> PipelineStage:
        result = client.table("pipeline_run_steps").select("step_name, status").eq("run_id", run_id).execute()
        step_status = {row["step_name"]: row.get("status") for row in result.data or []}

        for stage in PIPELINE_STAGE_ORDER:
            if step_status.get(stage.value) != "success":
                return stage

        raise RuntimeError("All stages are already successful; choose a specific stage to rerun.")

    def _requeue_existing_run(
        self,
        client,
        run: dict,
        start_stage: PipelineStage,
        triggered_by: str,
    ) -> dict:
        parameters = dict(run.get("parameters") or {})
        since_date = None
        since_date_str = parameters.get("since_date")
        if since_date_str:
            since_date = datetime.fromisoformat(since_date_str).date()

        self._reset_steps_from(client, run["id"], start_stage)

        updated_parameters = {
            **parameters,
            "start_stage": start_stage.value,
            "requested_action": triggered_by,
        }
        update_data = {
            "status": "running",
            "error_message": None,
            "duration_ms": None,
            "ended_at": None,
            "current_phase": start_stage.value,
            "summary_stats": {},
            "parameters": updated_parameters,
            "triggered_by": triggered_by,
        }
        client.table("pipeline_runs").update(update_data).eq("id", run["id"]).execute()

        self._enqueue_run_task(
            client=client,
            user_id=run["user_id"],
            run_id=run["id"],
            run_label=run["run_id"],
            since_date=since_date,
            triggered_by=triggered_by,
            start_stage=start_stage,
        )
        self._insert_control_log(client, run["id"], "INFO", f"Queued {triggered_by} from {start_stage.value}.")

        return {
            "run_id": run["run_id"],
            "id": run["id"],
            "status": "running",
            "current_phase": start_stage.value,
        }

    def _reset_steps_from(self, client, run_id: str, start_stage: PipelineStage) -> None:
        start_index = PIPELINE_STAGE_ORDER.index(start_stage)
        for stage in PIPELINE_STAGE_ORDER[start_index:]:
            client.table("pipeline_run_steps").update(
                {
                    "status": "pending",
                    "progress_pct": 0,
                    "message": "",
                    "stats": {},
                    "started_at": None,
                    "ended_at": None,
                }
            ).match({"run_id": run_id, "step_name": stage.value}).execute()

    def _mark_steps_from(self, client, run_id: str, start_stage: PipelineStage, status: str, message: str) -> None:
        start_index = PIPELINE_STAGE_ORDER.index(start_stage)
        for stage in PIPELINE_STAGE_ORDER[start_index:]:
            client.table("pipeline_run_steps").update(
                {
                    "status": status,
                    "message": message,
                }
            ).match({"run_id": run_id, "step_name": stage.value}).execute()

    def _insert_control_log(self, client, run_id: str, level: str, message: str) -> None:
        client.table("pipeline_run_logs").insert(
            {
                "run_id": run_id,
                "level": level,
                "message": message,
                "step_name": "control",
            }
        ).execute()


tracker_service = TrackerService()

__all__ = ["PipelineCancelledError", "run_tracker_task", "tracker_service"]
