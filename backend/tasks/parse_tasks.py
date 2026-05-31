"""招标文件解析 / 知识库入库 Celery 任务（P1-1 第二批）。

迁移前：解析链路跑在 backend/api/projects.py、mineru.py、knowledge.py 的
`threading.Thread(daemon=True)` 上，进程重启即丢任务、且状态写本地文件不跨进程可见。
迁移后：这些后台动作改为 Celery 任务，状态写 DB（见 parse_status_store），
worker 被杀后任务由 broker 重投递（acks_late）。

本模块只做"线程目标函数 → Celery 任务"的薄包装，解析与入库的核心逻辑仍在
document_parser / rag.ingestion 中，不改业务行为，降低主链路改造风险。
"""

from __future__ import annotations

import logging

from backend.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="bid.parse.sync_and_parse_tender", bind=True, max_retries=0)
def sync_and_parse_tender(
    self,
    file_path: str,
    original_filename: str,
    parse_id: str,
    supabase_sync: dict | None = None,
) -> dict:
    """同步 Supabase 并触发 MinerU/OCR 解析（原 projects._sync_and_parse_tender_in_background）。"""
    from backend.api.projects import _sync_and_parse_tender_in_background

    _sync_and_parse_tender_in_background(file_path, original_filename, parse_id, supabase_sync)
    return {"parse_id": parse_id, "status": "dispatched"}


@celery_app.task(name="bid.parse.parse_and_index_tender", bind=True, max_retries=0)
def parse_and_index_tender(
    self,
    file_path: str,
    original_filename: str,
    parse_id: str,
    supabase_file_id: str | None = None,
) -> dict:
    """直接解析并入库（原 retry-parse 线程目标 parse_and_index_tender_file）。"""
    from backend.parsing.document_parser import parse_and_index_tender_file

    parse_and_index_tender_file(
        file_path=file_path,
        original_filename=original_filename,
        parse_id=parse_id,
        supabase_file_id=supabase_file_id,
    )
    return {"parse_id": parse_id, "status": "dispatched"}


@celery_app.task(name="bid.parse.retry_download", bind=True, max_retries=0)
def retry_mineru_download(self, parse_id: str) -> dict:
    """重试 MinerU 结果下载（原 get_parse_status 内的恢复线程）。"""
    from backend.parsing.document_parser import retry_mineru_result_download

    retry_mineru_result_download(parse_id)
    return {"parse_id": parse_id, "status": "dispatched"}


@celery_app.task(name="bid.parse.ingest_artifacts", bind=True, max_retries=0)
def ingest_artifacts(self, parse_id: str, artifacts: dict) -> dict:
    """将 MinerU 产物写入业务表（原 ingest 线程目标 ingest_artifacts）。"""
    from backend.parsing.document_parser import ingest_artifacts as _ingest

    _ingest(parse_id, artifacts)
    return {"parse_id": parse_id, "status": "dispatched"}


@celery_app.task(name="bid.knowledge.sync_and_parse", bind=True, max_retries=0)
def sync_and_parse_knowledge(
    self,
    file_path: str,
    original_filename: str,
    parse_id: str,
    document_id: str,
) -> dict:
    """知识库文件解析入库（原 knowledge.sync_and_parse_knowledge_in_background）。"""
    from backend.api.knowledge import sync_and_parse_knowledge_in_background

    sync_and_parse_knowledge_in_background(file_path, original_filename, parse_id, document_id)
    return {"document_id": document_id, "status": "dispatched"}
