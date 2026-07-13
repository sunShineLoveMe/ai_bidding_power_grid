"""投标项目运行模式的稳定契约。

模式只决定项目使用哪套编排规则，不改变招标文件解析、编辑、检查和导出的
公共能力。历史项目未保存模式时一律按 ``general`` 处理，保证升级兼容。
"""

from __future__ import annotations

import os
from typing import Any, Literal


ProjectMode = Literal["general", "taichang_reuse"]

GENERAL_PROJECT_MODE: ProjectMode = "general"
TAICHANG_REUSE_PROJECT_MODE: ProjectMode = "taichang_reuse"
SUPPORTED_PROJECT_MODES = frozenset({GENERAL_PROJECT_MODE, TAICHANG_REUSE_PROJECT_MODE})
PROJECT_MODE_CONTRACT_VERSION = "project_mode_contract.v1"


class InvalidProjectModeError(ValueError):
    """客户端提交了系统不支持的项目模式。"""


class ProjectModeUnavailableError(RuntimeError):
    """可选模式当前被关闭，但通用模式仍可正常使用。"""


def normalize_project_mode(value: Any, *, strict: bool = False) -> ProjectMode:
    """规范化项目模式；旧数据缺失或异常时默认回退到通用模式。"""
    normalized = str(value or "").strip().lower()
    if not normalized:
        return GENERAL_PROJECT_MODE
    if normalized in SUPPORTED_PROJECT_MODES:
        return normalized  # type: ignore[return-value]
    if strict:
        raise InvalidProjectModeError(
            f"不支持的项目模式：{normalized}。可选值为 general、taichang_reuse。"
        )
    return GENERAL_PROJECT_MODE


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def ensure_project_mode_available(mode: ProjectMode) -> None:
    """只在创建项目时检查可选入口开关，绝不阻断通用模式。"""
    if mode == TAICHANG_REUSE_PROJECT_MODE and not _env_flag("TAICHANG_REUSE_ENABLED", True):
        raise ProjectModeUnavailableError("泰昌历史标书复用模式当前未启用，请使用通用标书流程。")


def project_mode_context(value: Any) -> dict[str, Any]:
    """生成可写入任务 metadata 的服务器权威模式上下文。"""
    mode = normalize_project_mode(value)
    return {
        "project_mode": mode,
        "project_mode_contract_version": PROJECT_MODE_CONTRACT_VERSION,
        "orchestration_profile": "taichang_reuse_v1" if mode == TAICHANG_REUSE_PROJECT_MODE else "general_v1",
        "historical_bid_reuse_enabled": mode == TAICHANG_REUSE_PROJECT_MODE,
    }


def merge_project_mode_metadata(value: Any, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """合并任务 metadata，模式字段始终以项目服务端记录为准。"""
    return {
        **(metadata if isinstance(metadata, dict) else {}),
        **project_mode_context(value),
    }
