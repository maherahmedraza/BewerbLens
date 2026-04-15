# ╔══════════════════════════════════════════════════════════════╗
# ║  Failure Handler — Retry Logic & State Management           ║
# ║                                                             ║
# ║  Implements Airflow-style retry patterns:                   ║
# ║  • Exponential backoff                                      ║
# ║  • Max retry limits                                         ║
# ║  • Zombie detection via heartbeats                          ║
# ║  • Graceful degradation                                     ║
# ╚══════════════════════════════════════════════════════════════╝

import time
from typing import Optional, Callable, Any, Dict
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from functools import wraps
from loguru import logger
from supabase import Client


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    retry_on_exceptions: tuple = (Exception,)


class RetryableError(Exception):
    """Error that should trigger a retry."""
    pass


class FatalError(Exception):
    """Error that should NOT retry (e.g., authentication failure)."""
    pass


def with_retry(config: RetryConfig = RetryConfig()):
    """
    Decorator for automatic retry with exponential backoff.
    
    Usage:
        @with_retry(RetryConfig(max_attempts=3))
        def fetch_emails():
            # ... code that might fail
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 1
            delay = config.initial_delay
            
            while attempt <= config.max_attempts:
                try:
                    return func(*args, **kwargs)
                
                except FatalError:
                    # Don't retry fatal errors
                    logger.error(f"Fatal error in {func.__name__}, no retry")
                    raise
                
                except config.retry_on_exceptions as e:
                    if attempt == config.max_attempts:
                        logger.error(
                            f"{func.__name__} failed after {attempt} attempts: {str(e)}"
                        )
                        raise
                    
                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt}/{config.max_attempts}), "
                        f"retrying in {delay:.1f}s: {str(e)}"
                    )
                    
                    time.sleep(delay)
                    delay = min(delay * config.exponential_base, config.max_delay)
                    attempt += 1
            
        return wrapper
    return decorator


# ── Zombie Detection System ────────────────────────────────────

class HeartbeatMonitor:
    """
    Detects and handles "zombie" pipeline runs.
    
    A run is considered a zombie if:
    - Status is "running"
    - No heartbeat update in the last 10 minutes
    
    This handles edge cases like:
    - Worker crashes (out of memory)
    - Network disconnections
    - Infinite loops
    """
    
    def __init__(self, client: Client, zombie_threshold_minutes: int = 10):
        self.client = client
        self.zombie_threshold = timedelta(minutes=zombie_threshold_minutes)
    
    def detect_zombies(self) -> list[Dict]:
        """
        Find all zombie runs in the database.
        Returns list of zombie run dictionaries.
        """
        threshold_time = datetime.now(timezone.utc) - self.zombie_threshold
        
        result = self.client.table("pipeline_runs").select("*").eq(
            "status", "running"
        ).execute()
        
        zombies = []
        for run in result.data:
            heartbeat_at = run.get('heartbeat_at')
            if not heartbeat_at:
                continue
            
            heartbeat_time = datetime.fromisoformat(heartbeat_at.replace("Z", "+00:00"))
            if heartbeat_time < threshold_time:
                zombies.append(run)
                logger.warning(
                    f"Detected zombie run: {run['run_id']} "
                    f"(last heartbeat: {heartbeat_time})"
                )
        
        return zombies
    
    def kill_zombie(self, run_id: str, reason: str = "Zombie detected"):
        """
        Mark a zombie run as failed and clean up.
        """
        self.client.table("pipeline_runs").update({
            "status": "failed",
            "error_message": f"Pipeline zombie-killed: {reason}",
            "ended_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", run_id).execute()
        
        logger.info(f"Killed zombie run: {run_id}")
    
    def cleanup_zombies(self):
        """
        Automatically detect and kill all zombies.
        Should be run by the scheduler periodically.
        """
        zombies = self.detect_zombies()
        for zombie in zombies:
            self.kill_zombie(zombie['id'])
        
        return len(zombies)


# ── Pipeline Step Executor with Rollback ───────────────────────

class StepExecutor:
    """
    Executes pipeline steps with automatic rollback on failure.
    Ensures database consistency even when steps fail.
    """
    
    def __init__(self, client: Client, run_id: str):
        self.client = client
        self.run_id = run_id
        self.completed_steps = []
    
    def execute_step(
        self,
        step_name: str,
        step_function: Callable,
        rollback_function: Optional[Callable] = None
    ) -> Any:
        """
        Execute a pipeline step with automatic state management.
        
        Args:
            step_name: Name of the step (ingestion, analysis, persistence)
            step_function: The actual work to perform
            rollback_function: Optional cleanup function if step fails
        
        Returns:
            The result of step_function
        """
        # Mark step as running
        self._update_step_status(step_name, "running", progress=0)
        
        try:
            result = step_function()
            
            # Mark step as success
            self._update_step_status(step_name, "success", progress=100)
            self.completed_steps.append(step_name)
            
            return result
        
        except Exception as e:
            logger.error(f"Step '{step_name}' failed: {str(e)}")
            
            # Mark step as failed
            self._update_step_status(
                step_name, 
                "failed", 
                message=str(e)[:500]
            )
            
            # Attempt rollback
            if rollback_function:
                try:
                    logger.info(f"Rolling back step '{step_name}'")
                    rollback_function()
                except Exception as rollback_error:
                    logger.error(f"Rollback failed: {str(rollback_error)}")
            
            raise
    
    def _update_step_status(
        self,
        step_name: str,
        status: str,
        progress: int = 0,
        message: str = ""
    ):
        """Update step status in database."""
        from supabase_service import update_pipeline_step
        update_pipeline_step(
            self.client,
            self.run_id,
            step_name,
            status,
            progress=progress,
            message=message
        )


# ── Graceful Degradation Pattern ───────────────────────────────

class PartialSuccessHandler:
    """
    Handles scenarios where some emails succeed and others fail.
    Ensures partial progress is saved, not lost.
    
    Example: 
    - Fetched 50 emails
    - 45 classified successfully 
    - 5 failed (Gemini timeout)
    - Should save the 45 successful ones, not discard everything
    """
    
    def __init__(self, client: Client):
        self.client = client
        self.successes = []
        self.failures = []
    
    def process_batch(
        self,
        items: list,
        processor: Callable,
        on_success: Callable,
        on_failure: Callable
    ):
        """
        Process items individually, tracking successes and failures.
        
        Args:
            items: List of items to process
            processor: Function that processes each item
            on_success: Callback for successful items
            on_failure: Callback for failed items
        """
        for item in items:
            try:
                result = processor(item)
                on_success(item, result)
                self.successes.append((item, result))
            
            except Exception as e:
                logger.warning(f"Failed to process item: {str(e)}")
                on_failure(item, e)
                self.failures.append((item, e))
        
        logger.info(
            f"Batch complete: {len(self.successes)} succeeded, "
            f"{len(self.failures)} failed"
        )
    
    def get_stats(self) -> Dict[str, int]:
        """Get processing statistics."""
        return {
            "total": len(self.successes) + len(self.failures),
            "succeeded": len(self.successes),
            "failed": len(self.failures),
            "success_rate": (
                len(self.successes) / (len(self.successes) + len(self.failures))
                if (len(self.successes) + len(self.failures)) > 0
                else 0.0
            )
        }


# ── Usage Example ──────────────────────────────────────────────

"""
def run_pipeline_with_failure_handling(run_id: str):
    client = get_client()
    executor = StepExecutor(client, run_id)
    
    try:
        # Step 1: Ingestion with retry
        @with_retry(RetryConfig(max_attempts=3))
        def fetch_with_retry():
            return fetch_emails()
        
        emails = executor.execute_step(
            "ingestion",
            fetch_with_retry,
            rollback_function=lambda: cleanup_temp_files()
        )
        
        # Step 2: Classification with partial success handling
        def classify_batch():
            handler = PartialSuccessHandler(client)
            
            def on_success(email, classification):
                # Save to DB immediately
                upsert_application(client, email, classification)
            
            def on_failure(email, error):
                # Log failure for manual review
                client.table("failed_emails").insert({
                    "email_id": email.email_id,
                    "error": str(error)
                }).execute()
            
            handler.process_batch(
                emails,
                classifier.classify_single,
                on_success,
                on_failure
            )
            
            return handler.get_stats()
        
        stats = executor.execute_step("analysis", classify_batch)
        
        return stats
        
    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}")
        raise
"""
