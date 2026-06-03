"""Celery 应用初始化。

设计要点（对应 P1-1 需求）：

- Web 进程（gunicorn）与 Celery worker 进程通过同一模块路径
  `backend.tasks.celery_app:celery_app` 导入同一个实例，保证任务注册一致。
- broker / result backend 均从环境变量 `REDIS_URL` 读取，仅靠该变量即可在
  本地 redis 与阿里云 Redis 间切换，无需改代码。
- `task_acks_late=True` + `task_reject_on_worker_lost=True`：worker 进程被杀时
  未确认的任务会被重新投递，避免进程重启后任务无痕丢失。
- 测试环境通过 `CELERY_TASK_ALWAYS_EAGER=true` 切换为同步执行（eager 模式），
  使集成冒烟测试无需独立运行 worker 进程。
- 任务体往往依赖 Flask `current_app`（读取配置、拼下载 URL 等），因此提供
  `FlaskTask` 基类，在任务执行时自动推入应用上下文。
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

from celery import Celery, Task

logger = logging.getLogger(__name__)

# 确保项目根目录在 import 路径上：Celery worker 可能不以项目根为 CWD 启动，
# 否则任务执行时 `from main import app` 会 ModuleNotFoundError。
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# 防御性加载 .env：celery_app 在 import 期即读取 REDIS_URL 等变量。
# 即使未经 dev_worker.sh（未提前 source .env）直接 `celery -A ...` 启动，
# 也能从项目根 .env 读到 broker、模型、数据库等配置，避免"连不上 Redis/DB"。
try:
    from dotenv import load_dotenv

    load_dotenv(_PROJECT_ROOT / ".env")
except Exception:  # pragma: no cover - dotenv 缺失时不阻断
    pass

_TRUE_VALUES = {"1", "true", "yes", "on"}


def _is_eager() -> bool:
    return (os.getenv("CELERY_TASK_ALWAYS_EAGER", "false") or "").lower() in _TRUE_VALUES


def _resolve_broker_url() -> str:
    """解析 broker 地址。

    eager 模式（测试）下允许 REDIS_URL 缺失，使用内存 broker 占位即可；
    非 eager 模式下 REDIS_URL 必须配置，否则视为致命错误。
    """
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        return redis_url
    if _is_eager():
        return "memory://"
    logger.error("REDIS_URL 未配置，Celery 无法连接消息代理（broker）。请在环境变量中配置 REDIS_URL。")
    raise RuntimeError("REDIS_URL is not configured; Celery broker cannot start")


def _build_celery() -> Celery:
    broker_url = _resolve_broker_url()
    # result backend 复用同一 Redis；eager 模式下用内存 backend 占位。
    backend_url = os.getenv("CELERY_RESULT_BACKEND") or (
        broker_url if broker_url != "memory://" else "cache+memory://"
    )

    app = Celery("ai_bidding", broker=broker_url, backend=backend_url)

    # worker 并发度可按 RDS 最大连接数设置上限，避免数据库连接来源失控。
    worker_concurrency = int(os.getenv("CELERY_WORKER_CONCURRENCY", "4"))

    app.conf.update(
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        task_track_started=True,
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone=os.getenv("TZ", "Asia/Shanghai"),
        enable_utc=True,
        worker_concurrency=worker_concurrency,
        worker_max_tasks_per_child=int(os.getenv("CELERY_WORKER_MAX_TASKS_PER_CHILD", "100")),
        broker_connection_retry_on_startup=True,
        task_always_eager=_is_eager(),
        task_eager_propagates=_is_eager(),
    )

    # 任务模块列表：每迁移一类任务，在此登记一个模块。
    app.conf.imports = (
        "backend.tasks.export_tasks",
        "backend.tasks.parse_tasks",
        "backend.tasks.outline_tasks",
        "backend.tasks.section_tasks",
    )

    return app


celery_app = _build_celery()


class FlaskTask(Task):
    """在 Flask 应用上下文中执行任务。

    任务体大量依赖 current_app（GENERATED_FOLDER 配置、下载 URL 拼接等），
    worker 进程没有请求上下文，需要显式推入应用上下文。
    """

    abstract = True
    _flask_app = None

    @classmethod
    def _get_flask_app(cls):
        if cls._flask_app is None:
            # 优先按常规导入；worker 若不以项目根为 CWD、且 main 不在 sys.path 时，
            # 退回按绝对文件路径加载 main.py，保证跨 CWD/容器稳定可用。
            try:
                from main import app as flask_app
            except ModuleNotFoundError:
                import importlib.util

                main_path = _PROJECT_ROOT / "main.py"
                spec = importlib.util.spec_from_file_location("main", main_path)
                if spec is None or spec.loader is None:
                    raise
                module = importlib.util.module_from_spec(spec)
                sys.modules.setdefault("main", module)
                spec.loader.exec_module(module)
                flask_app = module.app
            cls._flask_app = flask_app
        return cls._flask_app

    def __call__(self, *args, **kwargs):
        from backend.core.logging_config import log_context

        celery_task_id = getattr(getattr(self, "request", None), "id", None)
        started_at = time.perf_counter()
        with self._get_flask_app().app_context():
            with log_context(
                app_module="celery",
                stage="task",
                celery_task_id=celery_task_id,
                celery_task_name=self.name,
            ):
                logger.info("celery_task_started")
                try:
                    result = super().__call__(*args, **kwargs)
                except Exception:
                    logger.exception(
                        "celery_task_failed",
                        extra={"duration_ms": int((time.perf_counter() - started_at) * 1000)},
                    )
                    raise
                logger.info(
                    "celery_task_completed",
                    extra={"duration_ms": int((time.perf_counter() - started_at) * 1000)},
                )
                return result


celery_app.Task = FlaskTask
