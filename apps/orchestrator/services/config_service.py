from typing import Optional

from loguru import logger
from pydantic import BaseModel, Field
from services.supabase_client import supabase

# Singleton ID for the pipeline config
SINGLETON_ID = "00000000-0000-0000-0000-000000000001"

class ConfigPatch(BaseModel):
    retention_days: Optional[int] = Field(default=None, ge=1, le=365)
    schedule_interval_hours: Optional[float] = Field(default=None, ge=0.5, le=168.0)
    is_paused: Optional[bool] = None
    max_emails_per_run: Optional[int] = Field(default=None, ge=25, le=5000)

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
            "is_paused": False,
            "max_emails_per_run": 250,
        }
        supabase.table("pipeline_config").insert(initial_data).execute()
        logger.info("Initialized default pipeline configuration")

config_service = ConfigService()
