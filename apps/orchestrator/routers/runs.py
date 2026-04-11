from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import date
from typing import Optional
from services.tracker import tracker_service
from services.supabase_client import supabase

router = APIRouter()

class TriggerRequest(BaseModel):
    since_date: Optional[date] = None
    triggered_by: str = "manual"  # "manual" | "backfill"

class RunResponse(BaseModel):
    run_id: str
    id: str
    status: str

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
            triggered_by=payload.triggered_by,
            since_date=payload.since_date,
        )
        return run
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{run_id}")
async def get_run_details(run_id: str):
    """
    Fetches detailed metadata and log summaries for a specific run.
    """
    try:
        # Check both by run_id (string label) and id (UUID)
        query = supabase.table("pipeline_runs").select("*")
        
        # If it looks like a UUID, search by id, else search by run_id
        if "-" in run_id and len(run_id) > 20: 
            query = query.eq("id", run_id)
        else:
            query = query.eq("run_id", run_id)
            
        result = query.single().execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Run not found")
        return result.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
