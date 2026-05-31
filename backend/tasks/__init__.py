"""Celery 任务包。

本包承载从裸线程迁移到 Celery 的后台任务，包括 DOCX 异步导出、
MinerU 解析、知识库入库和大纲精炼。

对外只暴露 celery_app 与各任务模块，应用入口（main.py / worker 启动命令）
通过 `backend.tasks.celery_app:celery_app` 共享同一个 Celery 实例。
"""

from backend.tasks.celery_app import celery_app

__all__ = ["celery_app"]
