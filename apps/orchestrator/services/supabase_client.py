# ╔══════════════════════════════════════════════════════════════╗
# ║  Supabase Client — Orchestrator                             ║
# ║                                                             ║
# ║  Reutiliza el cliente cacheado del tracker para evitar      ║
# ║  crear instancias duplicadas (Fix Issue K).                 ║
# ║  El sys.path se centraliza en main.py.                      ║
# ╚══════════════════════════════════════════════════════════════╝

from supabase_service import get_client

# Singleton — misma instancia cacheada que usa el tracker
supabase = get_client()

__all__ = ["supabase", "get_client"]
