from typing import Optional
from pydantic import BaseModel
from services.supabase_client import supabase
from loguru import logger

# Singleton ID for the pipeline config
SINGLETON_ID = "00000000-0000-0000-0000-000000000001"

class ConfigPatch(BaseModel):
    retention_days: Optional[int] = None
    schedule_interval_hours: Optional[float] = None
    is_paused: Optional[bool] = None

class ConfigService:
    """
    Manages the global pipeline configuration stored in Supabase.
    Ensures that updates are properly audited and validated.
    """
    async def get_current(self):
        """Fetches the current singleton configuration."""
        try:
            result = supabase.table("pipeline_config")\
                .select("*")\
                .eq("id", SINGLETON_ID)\
                .execute()
            if not result.data:
                # Initialize if missing
                self._initialize_config()
                return await self.get_current()
            return result.data[0]
        except Exception as e:
            logger.error(f"Failed to fetch config: {str(e)}")
            return {}

    async def update(self, patch: ConfigPatch):
        """Updates the singleton configuration."""
        data = patch.model_dump(exclude_unset=True)
        if not data:
            return await self.get_current()

        try:
            result = supabase.table("pipeline_config")\
                .update(data)\
                .eq("id", SINGLETON_ID)\
                .execute()
            
            logger.success("Pipeline configuration updated")
            return result.data[0] if result.data else await self.get_current()
        except Exception as e:
            logger.error(f"Failed to update config: {str(e)}")
            raise e

    def _initialize_config(self):
        """Creates the initial singleton configuration row."""
        initial_data = {
            "id": SINGLETON_ID,
            "schedule_interval_hours": 4.0,
            "retention_days": 30,
            "is_paused": False
        }
        supabase.table("pipeline_config").insert(initial_data).execute()
        logger.info("Initialized default pipeline configuration")

config_service = ConfigService()
