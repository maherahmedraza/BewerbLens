# ╔══════════════════════════════════════════════════════════════╗
# ║  Worker — Task execution logic                              ║
# ║                                                             ║
# ║  Fixes applied:                                             ║
# ║  #D  — task_type check: "sync" instead of "tracker"         ║
# ║  #L  — Only use columns that exist in pipeline_tasks schema ║
# ║  #M  — Status "done"/"failed" to match schema constraint    ║
# ║  #7  — Atomic task claiming via 'claim_next_task' SQL RPC   ║
# ║  #14 — Heartbeat on pipeline_runs (not pipeline_tasks)      ║
# ╚══════════════════════════════════════════════════════════════╝

import threading
import time
from datetime import datetime, timezone

from loguru import logger

from .supabase_client import supabase
from .tracker import PipelineCancelledError, run_tracker_task


class SupabaseLogHandler:
    """
    Sinks Loguru logs directly into the pipeline_run_logs table for real-time dashboard viewing.
    """
    def __init__(self, run_id: str):
        self.run_id = run_id

    def write(self, message):
        # El mensaje viene formateado de Loguru
        try:
            # Quitamos el newline final
            clean_msg = message.strip()
            if not clean_msg:
                return

            # Extraemos el nivel [INFO], [ERROR], etc.
            level = "INFO"
            if "ERROR" in message: level = "ERROR"
            elif "WARNING" in message: level = "WARNING"
            elif "DEBUG" in message: level = "DEBUG"

            supabase.table("pipeline_run_logs").insert({
                "run_id": self.run_id,
                "level": level,
                "message": clean_msg,
                "step_name": "worker"
            }).execute()
        except Exception:
            # Fail silently to not crash the main loop
            pass


def worker_loop(worker_id: str):
    """
    Bucle continuo: reclama y ejecuta tareas de la cola pipeline_tasks.
    """
    logger.info(f"Worker {worker_id} started.")

    while True:
        try:
            # Reclama la siguiente tarea pendiente de forma atómica (Fix #7)
            res = supabase.rpc("claim_next_task", {"worker_val": worker_id}).execute()

            if not res.data:
                time.sleep(10)
                continue

            task = res.data[0]
            task_id = task["id"]
            run_id = task.get("run_id")

            logger.info(f"Worker {worker_id} claimed task {task_id}")

            # Marcar como "running" para visibilidad en el dashboard
            _update_task_status(task_id, "running")

            # Heartbeat en pipeline_runs (no en pipeline_tasks que no tiene esa columna)
            stop_heartbeat = threading.Event()
            if run_id:
                hb_thread = threading.Thread(
                    target=_heartbeat_loop,
                    args=(run_id, stop_heartbeat),
                    daemon=True,
                )
                hb_thread.start()
            else:
                hb_thread = None

            # Configurar log sink para este run
            handler = SupabaseLogHandler(run_id) if run_id else None
            handler_id = None
            if handler:
                handler_id = logger.add(handler.write, level="INFO")

            started_at = datetime.now(timezone.utc)

            try:
                success, result_stats = _execute_task(task)

                # Calcular duración
                ended_at = datetime.now(timezone.utc)
                duration_ms = int((ended_at - started_at).total_seconds() * 1000)

                # Fix #M: "done"/"failed" — no "completed"
                status = "done" if success else "failed"
                _update_task_status(task_id, status)

                # Actualizar también pipeline_runs si hay run_id asociado
                if run_id:
                    _finalize_run(run_id, status, result_stats, started_at, ended_at, duration_ms)

                logger.info(f"Task {task_id} {status} in {duration_ms}ms")

            finally:
                if handler_id is not None:
                    logger.remove(handler_id)
                stop_heartbeat.set()
                if hb_thread:
                    hb_thread.join(timeout=2)

        except Exception as e:
            logger.error(f"Worker loop error: {str(e)}")
            time.sleep(5)


def _update_task_status(task_id: str, status: str):
    """Actualiza el status de una tarea en pipeline_tasks."""
    try:
        supabase.table("pipeline_tasks").update({"status": status}).eq("id", task_id).execute()
    except Exception as e:
        logger.warning(f"Failed to update task {task_id} status: {e}")


def _finalize_run(
    run_id: str,
    status: str,
    result_stats: dict,
    started_at: datetime,
    ended_at: datetime,
    duration_ms: int,
):
    """Finaliza el registro en pipeline_runs con estadísticas y duración."""
    try:
        if result_stats.get("cancelled"):
            run_status = "cancelled"
        else:
            run_status = "success" if status == "done" else "failed"
        data = {
            "status": run_status,
            "ended_at": ended_at.isoformat(),
            "duration_ms": duration_ms,
            "summary_stats": result_stats or {},
        }
        if result_stats.get("error"):
            data["error_message"] = str(result_stats["error"])[:500]

        supabase.table("pipeline_runs").update(data).eq("id", run_id).execute()

        # Mark failed step if pipeline crashed
        if run_status == "failed":
            _mark_failed_steps(run_id, result_stats.get("error", ""))
        elif run_status == "cancelled":
            _mark_cancelled_steps(run_id, result_stats.get("error", "Cancelled by user"))
    except Exception as e:
        logger.warning(f"Failed to finalize run {run_id}: {e}")


def _mark_failed_steps(run_id: str, error_msg: str):
    """Mark any still-running steps as failed when the run fails."""
    try:
        from supabase_service import update_pipeline_step
        res = supabase.table("pipeline_run_steps").select("step_name, status").eq("run_id", run_id).execute()
        for step in (res.data or []):
            if step["status"] in ("running", "pending"):
                new_status = "failed" if step["status"] == "running" else "skipped"
                msg = error_msg[:200] if step["status"] == "running" else "Skipped due to earlier failure"
                update_pipeline_step(supabase, run_id, step["step_name"], new_status, message=msg)
    except Exception as e:
        logger.warning(f"Failed to mark steps for run {run_id}: {e}")


def _mark_cancelled_steps(run_id: str, message: str):
    """Mark pending steps as skipped when a run is cancelled."""
    try:
        from supabase_service import update_pipeline_step

        res = supabase.table("pipeline_run_steps").select("step_name, status").eq("run_id", run_id).execute()
        for step in (res.data or []):
            if step["status"] == "pending":
                update_pipeline_step(supabase, run_id, step["step_name"], "skipped", message="Skipped after cancellation")
            elif step["status"] == "running":
                update_pipeline_step(supabase, run_id, step["step_name"], "failed", message=message[:200])
    except Exception as e:
        logger.warning(f"Failed to mark cancelled steps for run {run_id}: {e}")


def _heartbeat_loop(run_id: str, stop_event: threading.Event):
    """
    Actualiza heartbeat_at en pipeline_runs cada 30s.
    Fix #14: heartbeat en la tabla correcta (pipeline_runs, no pipeline_tasks).
    """
    while not stop_event.is_set():
        try:
            supabase.table("pipeline_runs").update({
                "heartbeat_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", run_id).execute()
        except Exception:
            pass
        stop_event.wait(timeout=30)


def _execute_task(task: dict) -> tuple[bool, dict]:
    """Enruta al runner correcto según task_type."""
    task_type = task.get("task_type")

    try:
        # Fix #D: el task_type insertado es "sync", no "tracker"
        if task_type == "sync":
            payload = task.get("parameters", {})
            stats = run_tracker_task(payload)
            return True, stats
        else:
            logger.error(f"Unknown task type: {task_type}")
            return False, {"error": f"unknown_task_type: {task_type}"}
    except PipelineCancelledError as e:
        logger.warning(f"Execution cancelled: {str(e)}")
        return False, {"cancelled": True, "error": str(e)}
    except Exception as e:
        logger.error(f"Execution error: {str(e)}")
        return False, {"error": str(e)}
