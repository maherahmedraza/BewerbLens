import pytest
from datetime import date
from supabase_service import _should_update_status

def test_status_precedence():
    """Verifica que los estados de mayor importancia no sean sobreescritos por menores."""
    # applied -> rejection (YES)
    assert _should_update_status("Applied", "Rejected") is True
    
    # rejection -> applied (NO)
    assert _should_update_status("Rejected", "Applied") is False
    
    # rejection -> positive response (YES - maybe a mistake before or new update)
    assert _should_update_status("Rejected", "Positive Response") is True
    
    # interview -> rejection (YES)
    assert _should_update_status("Interview", "Rejected") is True

def test_status_stability():
    """Verifica que el mismo estado no dispare una actualización."""
    assert _should_update_status("Applied", "Applied") is False
    assert _should_update_status("Interview", "Interview") is False

def test_unknown_status():
    """Verifica el comportamiento con estados desconocidos."""
    # El default de la lógica es True para permitir actualizaciones si el estado es nuevo
    assert _should_update_status("Unknown", "Interview") is True
