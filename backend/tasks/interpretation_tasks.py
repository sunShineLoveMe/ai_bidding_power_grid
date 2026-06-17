"""AI 深度招标解读 Celery 任务。

同步 HTTP 生成在大文件场景下会持续数分钟，用户刷新或网络中断时容易误判失败。
本模块把长耗时的分段解读和最终融合放入 Celery worker，状态写入
`bid_interpretation_tasks`，前端通过轮询接口读取进度。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from backend.core.logging_config import log_context
from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@celery_app.task(name="bid.interpretation.generate_report", bind=True, max_retries=0)
def run_ai_interpretation_report(self, project_id: str, task_id: str) -> dict[str, Any]:
    from backend.ai.interpreter import generate_ai_interpretation_report
    from backend.db.supabase_repo import update_bid_interpretation_task

    metadata: dict[str, Any] = {"events": []}

    def update_progress(patch: dict[str, Any]) -> None:
        nonlocal metadata
        stage = patch.get("stage")
        if stage == "segmenting":
            total = int(patch.get("segment_total") or 0)
            done = int(patch.get("segment_done") or 0)
            progress = 10 + int((done / total) * 70) if total else 15
        elif stage == "merging":
            progress = 88
        elif stage == "single":
            progress = 35
        elif stage == "completed":
            progress = 100
        else:
            progress = int(patch.get("progress") or 20)

        metadata = {
            **metadata,
            "stage": stage,
            "segment_total": patch.get("segment_total", metadata.get("segment_total")),
            "segment_done": patch.get("segment_done", metadata.get("segment_done")),
            "segment_index": patch.get("segment_index", metadata.get("segment_index")),
            "failure_count": patch.get("failure_count", metadata.get("failure_count", 0)),
        }
        metadata["events"] = (metadata.get("events") or [])[-20:] + [{
            "stage": stage,
            "message": patch.get("message"),
            "at": _now_iso(),
        }]

        update_bid_interpretation_task(project_id, task_id, {
            "status": "running",
            "progress": progress,
            "message": patch.get("message") or "AI 深度解读生成中。",
            "metadata": metadata,
        })

    with log_context(project_id=project_id, task_id=task_id):
        try:
            update_bid_interpretation_task(project_id, task_id, {
                "status": "running",
                "progress": 5,
                "message": "正在准备 AI 深度解读任务。",
                "started_at": _now_iso(),
                "metadata": metadata,
            })
            report = generate_ai_interpretation_report(project_id, progress_callback=update_progress)
            generation = {}
            if isinstance(report, dict):
                generation = report.get("_segmented_interpretation") or {}
            metadata = {
                **metadata,
                "stage": "completed",
                "report_keys": sorted(report.keys()) if isinstance(report, dict) else [],
                "segmented_interpretation": generation,
            }
            update_bid_interpretation_task(project_id, task_id, {
                "status": "completed",
                "progress": 100,
                "message": "AI 深度解读报告已生成。",
                "metadata": metadata,
                "finished_at": _now_iso(),
            })
            return {"status": "completed", "project_id": project_id, "task_id": task_id}
        except Exception as exc:
            logger.exception("后台 AI 深度解读任务失败")
            try:
                update_bid_interpretation_task(project_id, task_id, {
                    "status": "failed",
                    "progress": 100,
                    "message": "AI 深度解读生成失败，请查看错误信息。",
                    "error_message": str(exc)[:1000],
                    "metadata": {**metadata, "stage": "failed"},
                    "finished_at": _now_iso(),
                })
            except Exception:
                logger.exception("写入 AI 深度解读任务失败状态失败")
            return {"status": "failed", "project_id": project_id, "task_id": task_id, "error": str(exc)[:200]}
