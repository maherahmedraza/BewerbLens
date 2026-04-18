import asyncio
import datetime
import os
import sys

# Ensure we can import from the tracker app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tracker")))

from tracker import run_pipeline
from supabase_service import get_client

async def simulate_test_run():
    """
    Manually triggers a pipeline run to verify the 
    orchestration and real-time pulse indicators.
    """
    print("🚀 Starting Simulation: Orchestration Test Run")
    run_id = f"TEST-{datetime.datetime.now().strftime('%H%M%S')}"
    
    try:
        # We pass since_date far in the past to ensure some activity if possible,
        # or just today to keep it quick.
        stats = run_pipeline(
            since_date=datetime.date.today(), 
            run_id=run_id, 
            triggered_by="manual"
        )
        print(f"✅ Simulation Complete: {stats}")
    except Exception as e:
        print(f"❌ Simulation Failed: {str(e)}")

if __name__ == "__main__":
    asyncio.run(simulate_test_run())
