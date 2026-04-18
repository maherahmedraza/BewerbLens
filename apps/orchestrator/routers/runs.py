from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import date
from typing import Optional

from models import PipelineStage
from services.tracker import tracker_service
from services.supabase_client import supabase

router = APIRouter()

class TriggerRequest(BaseModel):
    user_id: str
    since_date: Optional[date] = None
    triggered_by: str = "manual"  # "manual" | "backfill"

class RunResponse(BaseModel):
    run_id: str
    id: str
    status: str
    current_phase: Optional[str] = None


class StageRerunRequest(BaseModel):
    stage: PipelineStage

@router.post("/trigger", response_model=RunResponse)
async def trigger_run(payload: TriggerRequest):
    """
    Manually triggers a pipeline execution.
    Returns the run identifiers immediately while execution continues in background.
    """
    if payload.triggered_by not in ["manual", "backfill"]:
        raise HTTPException(status_code=400, detail="Invalid triggered_by. Must be 'manual' or 'backfill'.")
    
    try:
        run = await tracker_service.start_run(
            user_id=payload.user_id,
            triggered_by=payload.triggered_by,
            since_date=payload.since_date,
        )
        return run
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history")
async def get_history(limit: int = 20, offset: int = 0):
    """
    Fetches the execution history from Supabase.
    Ordered by start time (descending).
    """
    try:
        result = supabase.table("pipeline_runs")\
            .select("*")\
            .order("started_at", desc=True)\
            .limit(limit)\
            .offset(offset)\
            .execute()
        return result.data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{run_id}")
async def get_run_details(run_id: str):
    """
    Fetches detailed metadata and log summaries for a specific run.
    """
    try:
        import uuid
        try:
            uuid.UUID(run_id)
            query = supabase.table("pipeline_runs").select("*").eq("id", run_id)
        except ValueError:
            query = supabase.table("pipeline_runs").select("*").eq("run_id", run_id)
            
        result = query.single().execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Run not found")
        return result.data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{run_id}/cancel", response_model=RunResponse)
async def cancel_run(run_id: str):
    """Request cancellation of a pending or active run."""
    try:
        return await tracker_service.cancel_run(run_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{run_id}/resume", response_model=RunResponse)
async def resume_run(run_id: str):
    """Resume a failed or cancelled run from the first incomplete stage."""
    try:
        return await tracker_service.resume_run(run_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{run_id}/rerun-stage", response_model=RunResponse)
async def rerun_stage(run_id: str, payload: StageRerunRequest):
    """Rerun a specific stage and all downstream stages for an existing run."""
    try:
        return await tracker_service.rerun_stage(run_id, payload.stage)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
