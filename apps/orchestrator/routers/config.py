
from fastapi import APIRouter, HTTPException
from services.config_service import ConfigPatch, config_service
from services.scheduler import scheduler_service

router = APIRouter()

@router.get("/")
async def get_config():
    """
    Retrieves the global pipeline configuration.
    This is used by the dashboard on mount to reflect the current state.
    """
    try:
        return await config_service.get_current()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/")
async def patch_config(patch: ConfigPatch):
    """
    Updates specific configuration fields (e.g. Pause, Interval, Retention).
    The dashboard uses this with optimistic UI updates.
    """
    # Validation: Ensure at least one field is provided
    if all(v is None for v in patch.model_dump().values()):
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        result = await config_service.update(patch)
        await scheduler_service.reschedule_from_db(result)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
