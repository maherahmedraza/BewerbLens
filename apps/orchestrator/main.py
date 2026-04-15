# ╔══════════════════════════════════════════════════════════════╗
# ║  Orchestrator Main — FastAPI entry point                    ║
# ║                                                             ║
# ║  Punto de entrada único del orquestador. Centraliza:        ║
# ║  - sys.path para que todos los servicios accedan al tracker ║
# ║  - Worker loop en hilo de fondo                             ║
# ║  - Scheduler APScheduler para ejecuciones periódicas        ║
# ║  - Routers REST para config y runs                          ║
# ╚══════════════════════════════════════════════════════════════╝

import os
import sys
import threading
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

# ── sys.path centralizado (Fix #N) ───────────────────────────
# Todas las rutas al tracker se configuran AQUÍ y solo aquí.
# Permite que services/tracker.py, services/supabase_client.py, etc.
# importen módulos del tracker sin manipular sys.path ellos mismos.
TRACKER_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "tracker")
)
if TRACKER_DIR not in sys.path:
    sys.path.insert(0, TRACKER_DIR)

# Después de configurar sys.path, importar los servicios
from services.worker import worker_loop  # noqa: E402
from services.scheduler import scheduler_service  # noqa: E402
from routers import config as config_router  # noqa: E402
from routers import runs as runs_router  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona el ciclo de vida: startup y shutdown."""
    logger.info("Starting BewerbLens Orchestrator...")

    # 1. Worker thread — reclama y ejecuta tareas de la cola
    worker_thread = threading.Thread(
        target=worker_loop,
        args=("main_worker",),
        daemon=True,
    )
    worker_thread.start()

    # 2. Scheduler — ejecuta la pipeline periódicamente
    try:
        await scheduler_service.start()
    except Exception as e:
        logger.error(f"Scheduler failed to start: {e}")

    yield

    # Shutdown
    try:
        await scheduler_service.stop()
    except Exception:
        pass
    logger.info("Shutting down Orchestrator...")


app = FastAPI(title="BewerbLens Orchestrator", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount Routers ──────────────────────────────────────────────
app.include_router(config_router.router, prefix="/config", tags=["config"])
app.include_router(runs_router.router, prefix="/runs", tags=["runs"])


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "worker": "active",
        "scheduler": scheduler_service.is_running,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
