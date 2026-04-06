#!/usr/bin/env python3
# ╔══════════════════════════════════════════════════════════════╗
# ║  Scheduler — Orquestador de ejecución del pipeline          ║
# ║                                                             ║
# ║  Tres modos de ejecución:                                   ║
# ║  1. `python scheduler.py`         → cron loop cada 4 horas  ║
# ║  2. `python scheduler.py --once`  → ejecución única         ║
# ║  3. GitHub Actions cron            → ver tracker.yml         ║
# ║                                                             ║
# ║  Este módulo reemplaza la necesidad de crontab del sistema   ║
# ║  proporcionando un scheduler Python nativo con:              ║
# ║  - Logging de cada ciclo                                     ║
# ║  - Telegram alerts en caso de fallo                          ║
# ║  - Jitter aleatorio para evitar rate limits                  ║
# ║  - Manejo limpio de señales (SIGINT/SIGTERM)                 ║
# ╚══════════════════════════════════════════════════════════════╝

import argparse
import random
import signal
import sys
import time
from datetime import datetime

from loguru import logger

from telegram_notifier import send_notification

# ── Configurar logging del scheduler ─────────────────────────
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan> <dim>{extra}</dim>",
    level="INFO",
)
logger.add(
    "scheduler.log",
    rotation="10 MB",
    retention="30 days",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message} {extra}",
    level="DEBUG",
)

# ── Constantes ────────────────────────────────────────────────
DEFAULT_INTERVAL_HOURS = 4
MAX_JITTER_MINUTES = 10

# ── Control de señales para shutdown limpio ───────────────────
_shutdown_requested = False


def _handle_signal(signum, frame):
    """Maneja SIGINT/SIGTERM para un apagado limpio."""
    global _shutdown_requested
    signal_name = signal.Signals(signum).name
    logger.info(f"Received {signal_name} — shutting down after current cycle")
    _shutdown_requested = True


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


def _run_pipeline_safe() -> dict:
    """
    Ejecuta el pipeline con captura completa de errores.
    Importa tracker aquí para evitar dependencias circulares en el arranque.
    """
    # Importar aquí para mantener aislamiento y evitar side effects en import
    from tracker import run_pipeline

    try:
        return run_pipeline()
    except Exception as error:
        logger.bind(error=str(error)).critical("Pipeline crashed during scheduled run")
        # Intentar notificar por Telegram
        send_notification(
            action="added",
            company_name="⚠️ PIPELINE ERROR",
            job_title=str(error)[:100],
            platform="Scheduler",
            status="Applied",
            email_subject="Pipeline crashed — check logs",
        )
        return {"errors": 1, "crash": True}


def run_loop(interval_hours: float = DEFAULT_INTERVAL_HOURS) -> None:
    """
    Bucle principal del scheduler. Ejecuta el pipeline cada N horas
    con jitter aleatorio para evitar rate limits de APIs.
    """
    cycle = 0

    logger.info("=" * 60)
    logger.info("BewerbLens — Scheduler started")
    logger.bind(
        interval_hours=interval_hours,
        jitter_max_min=MAX_JITTER_MINUTES
    ).info("Configuration loaded")
    logger.info("=" * 60)

    while not _shutdown_requested:
        cycle += 1
        run_start = datetime.now()

        logger.info(f"── Cycle {cycle} starting at {run_start.strftime('%Y-%m-%d %H:%M:%S')} ──")

        # Ejecutar pipeline
        stats = _run_pipeline_safe()

        run_duration = (datetime.now() - run_start).total_seconds()

        logger.bind(
            cycle=cycle,
            duration_seconds=round(run_duration, 1),
            added=stats.get("added", 0),
            errors=stats.get("errors", 0),
        ).info("Cycle complete")

        if _shutdown_requested:
            break

        # Calcular siguiente ejecución con jitter
        jitter_minutes = random.uniform(0, MAX_JITTER_MINUTES)
        sleep_seconds = (interval_hours * 3600) + (jitter_minutes * 60)
        next_run = datetime.now().timestamp() + sleep_seconds
        next_run_str = datetime.fromtimestamp(next_run).strftime("%H:%M:%S")

        logger.bind(
            next_run=next_run_str,
            jitter_min=round(jitter_minutes, 1)
        ).info("Sleeping until next cycle")

        # Dormir en intervalos pequeños para responder rápido a señales
        slept = 0.0
        while slept < sleep_seconds and not _shutdown_requested:
            chunk = min(30.0, sleep_seconds - slept)
            time.sleep(chunk)
            slept += chunk

    logger.info("Scheduler stopped cleanly")


def run_once() -> int:
    """Ejecuta el pipeline una sola vez y retorna el exit code."""
    logger.info("Running pipeline (single execution mode)")
    stats = _run_pipeline_safe()

    if stats.get("crash"):
        return 2
    return 0 if stats.get("errors", 0) == 0 else 1


def main():
    """Punto de entrada del scheduler con argumentos CLI."""
    parser = argparse.ArgumentParser(
        description="BewerbLens — Scheduler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python scheduler.py              # Ejecutar loop cada 4 horas
  python scheduler.py --once       # Ejecutar una sola vez
  python scheduler.py --interval 2 # Ejecutar cada 2 horas
        """,
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Ejecutar el pipeline una sola vez y salir",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL_HOURS,
        help=f"Intervalo entre ejecuciones en horas (default: {DEFAULT_INTERVAL_HOURS})",
    )

    args = parser.parse_args()

    if args.once:
        exit_code = run_once()
        sys.exit(exit_code)
    else:
        run_loop(interval_hours=args.interval)


if __name__ == "__main__":
    main()
