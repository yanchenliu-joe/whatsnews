"""
Ingest -> assemble -> generate -> notify pipeline orchestration + the
daily/interval scheduler loop that drives it.

Public API:
  run_scheduled_pipeline(regenerate=False) -> dict
  run_scheduled_preparation() -> dict
  run_generation_pipeline_for_topic(conn, cur, topic_id, topic_name, trigger_type) -> dict
  seconds_until_next_run(daily_times, timezone) -> tuple
  scheduler_loop() -> None (async loop)
"""

from app.pipeline.orchestrator import (
    _notify_after_pipeline,
    run_generation_for_topic,
    run_generation_pipeline_for_topic,
    run_scheduled_pipeline,
    run_scheduled_preparation,
)
from app.pipeline.scheduler import scheduler_loop, seconds_until_next_run

__all__ = [
    "_notify_after_pipeline",
    "run_generation_for_topic",
    "run_generation_pipeline_for_topic",
    "run_scheduled_pipeline",
    "run_scheduled_preparation",
    "scheduler_loop",
    "seconds_until_next_run",
]
