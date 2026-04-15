# ╔══════════════════════════════════════════════════════════════╗
# ║  Tracker Service (Orchestrator Wrapper)                     ║
# ║                                                             ║
# ║  Punto de entrada único para ejecutar la pipeline.          ║
# ║  Provee tanto ejecución directa (run_tracker_task) como     ║
# ║  la clase TrackerService que usa el scheduler y los routers.║
# ╚══════════════════════════════════════════════════════════════╝

import uuid
from datetime import datetime, date

from loguru import logger

# Importaciones del tracker — el sys.path se centraliza en main.py
from supabase_service import (
    create_pipeline_run,
    get_client,
    get_last_checkpoint,
    init_pipeline_steps,
)
from tracker import run_pipeline_multiuser


def run_tracker_task(payload: dict) -> dict:
    """
    Punto de entrada para el worker: ejecuta una tarea de tipo 'sync'.
    Recibe el payload de pipeline_tasks.parameters y delega a run_pipeline.
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
    )


class TrackerService:
    """
    Servicio de alto nivel usado por el scheduler y los routers REST.
    Crea registros de pipeline_run, inicializa steps, y delega al worker
    a través de la cola de tareas (pipeline_tasks).
    """

    async def start_run(
        self,
        user_id: str,
        triggered_by: str = "manual",
        since_date: date | None = None,
    ) -> dict:
        """
        Crea un run en la DB y encola una tarea para que el worker la ejecute.
        Retorna inmediatamente con los identificadores del run.
        """
        client = get_client()

        # Determinar fecha de inicio
        if since_date is None:
            since_date = get_last_checkpoint(client)

        # Generar ID legible
        run_id = f"RUN-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"

        # Crear registro en pipeline_runs (con user_id)
        internal_id, started_at = create_pipeline_run(
            client, run_id, user_id=user_id, triggered_by=triggered_by, since_date=since_date
        )

        if not internal_id:
            raise RuntimeError("No se pudo crear el registro de pipeline_run")

        # Inicializar los 3 steps (ingestion, analysis, persistence)
        init_pipeline_steps(client, internal_id)

        # Encolar tarea para el worker
        task_data = {
            "task_type": "sync",
            "status": "pending",
            "user_id": user_id,
            "parameters": {
                "user_id": user_id,
                "since_date": since_date.isoformat() if since_date else None,
                "run_id": run_id,
                "internal_id": internal_id,
                "triggered_by": triggered_by,
            },
            "run_id": internal_id,
        }
        client.table("pipeline_tasks").insert(task_data).execute()

        logger.info(f"Pipeline run enqueued: {run_id} (id={internal_id})")

        return {
            "run_id": run_id,
            "id": internal_id,
            "status": "running",
        }

    async def trigger_scheduled_run(self):
        """
        Ejecuta un run programado para cada usuario activo.
        """
        try:
            client = get_client()
            users = client.table("user_profiles").select("id").not_.is_("gmail_credentials", "null").execute()
            
            if not users.data:
                logger.info("No users with active gmail_credentials found for scheduling.")
                return

            for user in users.data:
                user_id = user["id"]
                try:
                    result = await self.start_run(user_id=user_id, triggered_by="scheduler")
                    logger.info(f"Scheduled run started for user {user_id}: {result['run_id']}")
                except Exception as e:
                    logger.error(f"Scheduled run failed for user {user_id}: {str(e)}")
        except Exception as e:
            logger.error(f"Scheduled batch run failed to start: {str(e)}")


# Instancia global usada por scheduler.py y routers/runs.py
tracker_service = TrackerService()
