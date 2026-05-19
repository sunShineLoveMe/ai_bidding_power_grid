"""
API 层共享对象集中地。

本模块是 `backend/api/routes.py` 拆分的第一站：只承载所有业务路由模块都需要共享的
**零依赖模块级对象**——蓝图实例、不可变常量、进程内状态字典与其互斥锁。

拆分原则：
- 蓝图实例（`bp`、`knowledge_bp`）必须全局唯一，一旦在多个位置定义会导致
  Flask 抛 `AssertionError: A name collision occurred` 或路由丢失。
- 进程内状态（`temp_analysis_store`、`_temp_store_lock`）是旧版标书链路的
  内存态，后续路由模块与 `routes.py` 之间必须共享同一个实例，不能各复制一份。
- DOCX 导出限制常量（`DOCX_VOLUME_IMAGE_LIMITS`、`DOCX_TOTAL_ASSET_IMAGE_LIMIT`）
  在多处辅助函数中被引用，为避免不同模块读到不同的值，统一在此处完成一次 env 解析。
- ONLYOFFICE / Backend URL 相关常量同样集中于此，方便后续只改一处即可影响全部路由。

本文件**不含任何路由装饰器，也不含任何辅助函数**；路由与辅助逻辑仍保留在
`routes.py`，在后续 commit 中逐步搬入独立业务模块。
"""

from __future__ import annotations

import os
import threading

from flask import Blueprint


# ---- Blueprints ----------------------------------------------------------
# 这两个蓝图由 `main.py` 通过 `routes.bp` / `routes.knowledge_bp` 注册；
# `routes.py` 会 re-export 它们以保持原有导入路径不变。
bp = Blueprint("bidding", __name__)
knowledge_bp = Blueprint("knowledge", __name__)


# ---- 进程内临时状态 -------------------------------------------------------
# 旧版标书链路（pre-analysis_bid / chapter-analysis_bid / chapter-design /
# generate-bid-document）依赖的共享字典。新链路不再写入此结构，但为了
# 不改坏已被用户确认的旧功能，保留原语义与可见性。
# 结构: { bidding_id: { 'biddingId': int, 'analysisData': dict|None,
#                      'directoryStructure': dict|None } }
temp_analysis_store: dict = {}
_temp_store_lock = threading.Lock()


# ---- 环境依赖常量 ---------------------------------------------------------
ONLYOFFICE_JWT_SECRET: str = os.getenv("ONLYOFFICE_JWT_SECRET", "")
BACKEND_URL_FOR_DOCKER: str = os.getenv(
    "BACKEND_URL_FOR_DOCKER", "host.docker.internal:3012"
)
APP_HOST: str = os.getenv("APP_HOST", "localhost:3012")


# ---- DOCX 导出限制 --------------------------------------------------------
# 各分册单章自动插图上限，与 DOCX_TOTAL_ASSET_IMAGE_LIMIT 共同约束生成文档时
# 自动匹配企业资信库/产品库图片的规模，避免 Word 超大或排版失控。
DOCX_VOLUME_IMAGE_LIMITS: dict[str, int] = {
    "technical": int(os.getenv("DOCX_TECHNICAL_SECTION_IMAGE_LIMIT", "2")),
    "qualification": int(os.getenv("DOCX_QUALIFICATION_SECTION_IMAGE_LIMIT", "2")),
    "business": int(os.getenv("DOCX_BUSINESS_SECTION_IMAGE_LIMIT", "1")),
    "attachment": int(os.getenv("DOCX_ATTACHMENT_SECTION_IMAGE_LIMIT", "2")),
    "other": int(os.getenv("DOCX_OTHER_SECTION_IMAGE_LIMIT", "1")),
    "price": 0,
}
DOCX_TOTAL_ASSET_IMAGE_LIMIT: int = int(os.getenv("DOCX_TOTAL_ASSET_IMAGE_LIMIT", "36"))


__all__ = [
    "bp",
    "knowledge_bp",
    "temp_analysis_store",
    "_temp_store_lock",
    "ONLYOFFICE_JWT_SECRET",
    "BACKEND_URL_FOR_DOCKER",
    "APP_HOST",
    "DOCX_VOLUME_IMAGE_LIMITS",
    "DOCX_TOTAL_ASSET_IMAGE_LIMIT",
]
