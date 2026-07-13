"""从项目记录构建生成、续编与导出任务的模式上下文。"""

from __future__ import annotations

from typing import Any

from backend.core.project_modes import merge_project_mode_metadata, normalize_project_mode
from backend.db.supabase_repo import get_bid_project


def project_mode_from_project(project: dict[str, Any] | None) -> str:
    return normalize_project_mode((project or {}).get("project_mode"))


def build_project_task_metadata_from_project(
    project: dict[str, Any] | None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not project:
        raise RuntimeError("投标项目不存在，无法创建后续任务。")
    return merge_project_mode_metadata(project_mode_from_project(project), metadata)


def build_project_task_metadata(
    project_id: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_project_task_metadata_from_project(get_bid_project(project_id), metadata)
