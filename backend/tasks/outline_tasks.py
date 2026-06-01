"""Bid outline Celery tasks.

The quick outline still streams synchronously so the UI can show progress
immediately. The slower AI refinement runs in Celery, avoiding the old
daemon-thread path that could be lost on process restart.
"""

from __future__ import annotations

import logging

from backend.tasks.celery_app import celery_app
from backend.core.logging_config import log_context

logger = logging.getLogger(__name__)


@celery_app.task(name="bid.outline.refine", bind=True, max_retries=0)
def refine_bid_outline(self, project_id: str, payload: dict, analysis: dict) -> dict:
    from backend.ai.chapter_planner import _refine_bid_outline_in_background

    with log_context(project_id=project_id):
        logger.info("outline_refine_task_started")
        _refine_bid_outline_in_background(project_id, payload, analysis)
        logger.info("outline_refine_task_completed")
    return {"project_id": project_id, "status": "completed"}
