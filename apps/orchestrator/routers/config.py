
from fastapi import APIRouter, HTTPException
from services.config_service import ConfigPatch, config_service
from services.scheduler import scheduler_service

router = APIRouter()


def _augment_config(config: dict):
    return {
        **config,
        "scheduler_status": scheduler_service.get_schedule_status(
            configured_interval_hours=config.get("schedule_interval_hours"),
            is_paused=config.get("is_paused"),
        ),
    }

@router.get("/")
async def get_config():
    """
    Retrieves the global pipeline configuration.
    This is used by the dashboard on mount to reflect the current state.
    """
    try:
        config = await config_service.get_current()
        return _augment_config(config)
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
        return _augment_config(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
