import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from PyPDF2 import PdfReader, PdfWriter

from backend.parsing.bid_interpreter import ingest_mineru_artifacts_to_supabase
from backend.db.supabase_repo import update_bid_file_parse_status
from backend.rag.vector_store import EmptyDocumentContentError, file_to_chroma
from backend.parsing.mineru_client import (
    MinerUDownloadError,
    MinerUConfigError,
    create_local_file_batch_task,
    download_and_extract_zip,
    extract_zip_artifacts,
    get_batch_result,
    has_mineru_token,
    wait_for_batch_file_result,
)

PARSED_OUTPUT_ROOT = Path("parsed_outputs")
MINERU_MAX_PDF_PAGES = int(os.getenv("MINERU_MAX_PDF_PAGES", "200"))

FAILED_PARSE_STATUSES = {
    "mineru_failed",
    "index_failed",
    "ocr_required",
    "mineru_download_failed",
    "mineru_import_failed",
    "supabase_sync_failed",
}


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _mineru_user_message(status: str, error: str | None = None) -> str:
    if status == "mineru_download_failed":
        return "MinerU 已完成解析，但结果 zip 下载失败；系统会保留断点文件并自动重试，也可在历史记录中手动重试。"
    if status == "mineru_import_failed":
        return "MinerU 结果 zip 导入失败，请确认 zip 文件完整且包含 full.md 或 content_list 产物。"
    if status == "mineru_failed":
        return "MinerU 解析失败，请检查文件是否加密、损坏、页数过多或内容无法识别。"
    if status == "ocr_required":
        return "当前文件无法直接抽取文本，需要配置 MinerU/OCR 后重新解析。"
    if status == "index_failed":
        return "原始文件文本抽取或向量化失败，请检查文件内容是否可读。"
    return error or "解析失败，请查看错误详情。"


def _failure_payload(status: str, error: Exception | str, *, stage: str, retryable: bool = False, **extra: Any) -> dict[str, Any]:
    error_text = str(error)
    return {
        "parse_status": status,
        "failure_stage": stage,
        "error": error_text,
        "error_type": error.__class__.__name__ if isinstance(error, Exception) else "RuntimeError",
        "user_message": _mineru_user_message(status, error_text),
        "retryable": retryable,
        "failed_at": _now_iso(),
        **extra,
    }


def _has_completed_mineru_ingest(parse_id: str) -> bool:
    status = read_parse_status(parse_id) or {}
    return bool(status.get("artifacts")) and status.get("supabase_ingest_status") == "done"


def _status_file(file_id: str) -> Path:
    return PARSED_OUTPUT_ROOT / file_id / "mineru_status.json"


def write_parse_status(file_id: str, payload: dict[str, Any]) -> None:
    status_path = _status_file(file_id)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {}
    if status_path.exists():
        try:
            existing = json.loads(status_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
    existing.update(payload)
    existing["updated_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    status_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


def read_parse_status(file_id: str) -> dict[str, Any] | None:
    status_path = _status_file(file_id)
    if not status_path.exists():
        return None
    return json.loads(status_path.read_text(encoding="utf-8"))


def _update_supabase_status(file_id: str | None, parse_status: str) -> None:
    if not file_id:
        return
    try:
        update_bid_file_parse_status(file_id, parse_status)
    except Exception:
        logging.exception("更新 Supabase parse_status=%s 失败: %s", parse_status, file_id)


def _vectorize_markdown(markdown_path: str | None, parse_id: str, supabase_file_id: str | None) -> None:
    if not markdown_path:
        raise RuntimeError("MinerU result does not include full.md")
    file_to_chroma(markdown_path)
    _update_supabase_status(supabase_file_id, "indexed")
    write_parse_status(parse_id, {"parse_status": "indexed", "indexed_source": markdown_path})


def ingest_artifacts(parse_id: str, artifacts: dict[str, Any]) -> None:
    status = read_parse_status(parse_id) or {}
    project_id = status.get("project_id")
    bid_file_id = status.get("supabase_file_id")
    if not project_id:
        write_parse_status(parse_id, {
            "supabase_ingest_status": "skipped",
            "supabase_ingest_reason": "project_id is missing",
        })
        return

    write_parse_status(parse_id, {"supabase_ingest_status": "running"})
    try:
        result = ingest_mineru_artifacts_to_supabase(
            parse_id=parse_id,
            project_id=project_id,
            bid_file_id=bid_file_id,
            artifacts=artifacts,
        )
        write_parse_status(parse_id, {
            "supabase_ingest_status": "done",
            "supabase_ingest_result": result,
        })
    except Exception as e:
        logging.exception("MinerU 解析产物写入 Supabase 失败: %s", parse_id)
        write_parse_status(parse_id, {
            "supabase_ingest_status": "failed",
            "supabase_ingest_error": str(e),
            "supabase_ingest_failed_at": _now_iso(),
        })


def _extract_done_result(batch_data: dict[str, Any], parse_id: str) -> dict[str, Any] | None:
    extract_result = batch_data.get("extract_result") or []
    if isinstance(extract_result, dict):
        extract_result = [extract_result]
    for item in extract_result:
        if not isinstance(item, dict):
            continue
        if item.get("data_id") == parse_id or len(extract_result) == 1:
            return item
    return None


def _is_pdf_input(file_path: str | Path, original_filename: str | None = None) -> bool:
    if Path(file_path).suffix.lower() == ".pdf":
        return True
    if original_filename and Path(original_filename).suffix.lower() == ".pdf":
        return True
    try:
        with open(file_path, "rb") as f:
            return f.read(5) == b"%PDF-"
    except Exception:
        return False


def _should_use_mineru_first(file_path: str, original_filename: str | None = None) -> bool:
    if not _is_pdf_input(file_path, original_filename):
        return False
    return os.getenv("MINERU_PARSE_PDF_FIRST", "true").lower() not in {"false", "0", "no"}


def _pdf_page_count(file_path: str | Path) -> int | None:
    try:
        reader = PdfReader(str(file_path))
        return len(reader.pages)
    except Exception:
        logging.exception("读取 PDF 页数失败: %s", file_path)
        return None


def _split_pdf_for_mineru(file_path: str | Path, parse_id: str, max_pages: int = MINERU_MAX_PDF_PAGES) -> list[dict[str, Any]]:
    reader = PdfReader(str(file_path))
    total_pages = len(reader.pages)
    split_dir = PARSED_OUTPUT_ROOT / parse_id / "split_inputs"
    split_dir.mkdir(parents=True, exist_ok=True)

    parts: list[dict[str, Any]] = []
    for index, start in enumerate(range(0, total_pages, max_pages), 1):
        end = min(start + max_pages, total_pages)
        writer = PdfWriter()
        for page_index in range(start, end):
            writer.add_page(reader.pages[page_index])

        part_path = split_dir / f"part_{index:03d}_pages_{start + 1}_{end}.pdf"
        with open(part_path, "wb") as f:
            writer.write(f)
        parts.append({
            "index": index,
            "path": str(part_path),
            "start_page": start + 1,
            "end_page": end,
            "page_count": end - start,
        })
    return parts


def _read_json_list(path: str | None) -> list[dict[str, Any]]:
    if not path:
        return []
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        logging.exception("读取 MinerU content_list 失败: %s", path)
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _merge_split_artifacts(parse_id: str, parts: list[dict[str, Any]]) -> dict[str, Any]:
    combined_dir = PARSED_OUTPUT_ROOT / parse_id / "combined"
    combined_dir.mkdir(parents=True, exist_ok=True)
    markdown_parts: list[str] = []
    content_list: list[dict[str, Any]] = []
    artifacts_parts: list[dict[str, Any]] = []

    for part in parts:
        artifacts = part["artifacts"]
        artifacts_parts.append({
            "index": part["index"],
            "start_page": part["start_page"],
            "end_page": part["end_page"],
            "artifacts": artifacts,
        })
        markdown_path = artifacts.get("markdown_path")
        if markdown_path:
            markdown = Path(markdown_path).read_text(encoding="utf-8")
            markdown_parts.append(
                f"\n\n<!-- MinerU split part {part['index']}, pages {part['start_page']}-{part['end_page']} -->\n\n{markdown.strip()}\n"
            )

        page_offset = int(part["start_page"]) - 1
        for item in _read_json_list(artifacts.get("content_list_path")):
            next_item = dict(item)
            page_idx = next_item.get("page_idx")
            if isinstance(page_idx, int):
                next_item["page_idx"] = page_idx + page_offset
            next_item.setdefault("split_part", part["index"])
            content_list.append(next_item)

    markdown_path = combined_dir / "full.md"
    content_list_path = combined_dir / "combined_content_list.json"
    markdown_path.write_text("\n".join(markdown_parts).strip() + "\n", encoding="utf-8")
    content_list_path.write_text(json.dumps(content_list, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "extract_dir": str(combined_dir),
        "markdown_path": str(markdown_path),
        "content_list_path": str(content_list_path),
        "model_path": None,
        "middle_path": None,
        "zip_path": None,
        "split": True,
        "split_parts": artifacts_parts,
    }


def _run_mineru_parse_and_index(
    *,
    file_path: str,
    original_filename: str,
    parse_id: str,
    supabase_file_id: str | None,
) -> None:
    output_dir = PARSED_OUTPUT_ROOT / parse_id
    _update_supabase_status(supabase_file_id, "mineru_submitted")
    write_parse_status(
        parse_id,
        {
            "parse_status": "mineru_submitted",
            "parser": "mineru",
            "source_file": file_path,
            "data_id": parse_id,
            "file_name": original_filename,
            "supabase_file_id": supabase_file_id,
        },
    )
    task = create_local_file_batch_task(
        local_file_path=file_path,
        file_name=original_filename,
        data_id=parse_id,
    )
    write_parse_status(
        parse_id,
        {
            "batch_id": task.batch_id,
            "data_id": task.data_id,
            "file_name": task.file_name,
        },
    )

    def on_progress(result: dict[str, Any]) -> None:
        state = result.get("state") or "mineru_running"
        status = "mineru_running" if state in {"waiting-file", "pending", "running", "converting"} else state
        _update_supabase_status(supabase_file_id, status)
        write_parse_status(
            parse_id,
            {
                "parse_status": status,
                "mineru_state": state,
                "extract_progress": result.get("extract_progress"),
                "err_msg": result.get("err_msg"),
            },
        )

    result = wait_for_batch_file_result(batch_id=task.batch_id, data_id=parse_id, on_progress=on_progress)
    full_zip_url = result.get("full_zip_url")
    if not full_zip_url:
        raise RuntimeError(f"MinerU finished without full_zip_url: {result}")

    _update_supabase_status(supabase_file_id, "mineru_done")
    write_parse_status(
        parse_id,
        {
            "parse_status": "mineru_downloading",
            "mineru_state": "done",
            "full_zip_url": full_zip_url,
            "download_started_at": _now_iso(),
        },
    )
    artifacts = download_and_extract_zip(full_zip_url, output_dir)
    write_parse_status(parse_id, {
        "parse_status": "mineru_done",
        "artifacts": artifacts,
        "download_finished_at": _now_iso(),
        "download_info": artifacts.get("download_info"),
    })
    ingest_artifacts(parse_id, artifacts)
    _vectorize_markdown(artifacts.get("markdown_path"), parse_id, supabase_file_id)


def _run_mineru_split_parse_and_index(
    *,
    file_path: str,
    original_filename: str,
    parse_id: str,
    supabase_file_id: str | None,
    total_pages: int,
) -> None:
    parts = _split_pdf_for_mineru(file_path, parse_id)
    _update_supabase_status(supabase_file_id, "mineru_split_submitted")
    write_parse_status(parse_id, {
        "parse_status": "mineru_split_submitted",
        "parser": "mineru",
        "split": True,
        "total_pages": total_pages,
        "max_pages_per_part": MINERU_MAX_PDF_PAGES,
        "part_count": len(parts),
        "parts": [
            {
                "index": part["index"],
                "start_page": part["start_page"],
                "end_page": part["end_page"],
                "page_count": part["page_count"],
            }
            for part in parts
        ],
        "supabase_file_id": supabase_file_id,
    })

    parsed_parts: list[dict[str, Any]] = []
    original_path = Path(original_filename)
    for part in parts:
        part_parse_id = f"{parse_id}_part{part['index']:03d}"
        part_name = f"{original_path.stem}_part{part['index']:03d}_p{part['start_page']}-{part['end_page']}.pdf"
        output_dir = PARSED_OUTPUT_ROOT / parse_id / "parts" / f"part_{part['index']:03d}"
        _update_supabase_status(supabase_file_id, "mineru_split_running")
        write_parse_status(parse_id, {
            "parse_status": "mineru_split_running",
            "current_part": part["index"],
            "current_part_pages": f"{part['start_page']}-{part['end_page']}",
        })

        task = create_local_file_batch_task(
            local_file_path=part["path"],
            file_name=part_name,
            data_id=part_parse_id,
        )
        write_parse_status(part_parse_id, {
            "parse_status": "mineru_submitted",
            "parser": "mineru",
            "parent_parse_id": parse_id,
            "batch_id": task.batch_id,
            "data_id": task.data_id,
            "file_name": task.file_name,
            "start_page": part["start_page"],
            "end_page": part["end_page"],
            "supabase_file_id": supabase_file_id,
        })

        def on_progress(result: dict[str, Any], *, current_part: dict[str, Any] = part) -> None:
            state = result.get("state") or "mineru_running"
            status = "mineru_running" if state in {"waiting-file", "pending", "running", "converting"} else state
            _update_supabase_status(supabase_file_id, "mineru_split_running")
            progress_payload = {
                "parse_status": "mineru_split_running",
                "current_part": current_part["index"],
                "current_part_pages": f"{current_part['start_page']}-{current_part['end_page']}",
                "current_part_state": state,
                "extract_progress": result.get("extract_progress"),
                "err_msg": result.get("err_msg"),
            }
            write_parse_status(parse_id, progress_payload)
            write_parse_status(part_parse_id, {
                "parse_status": status,
                "mineru_state": state,
                "extract_progress": result.get("extract_progress"),
                "err_msg": result.get("err_msg"),
            })

        result = wait_for_batch_file_result(batch_id=task.batch_id, data_id=part_parse_id, on_progress=on_progress)
        full_zip_url = result.get("full_zip_url")
        if not full_zip_url:
            raise RuntimeError(f"MinerU split part finished without full_zip_url: {result}")

        write_parse_status(part_parse_id, {
            "parse_status": "mineru_downloading",
            "mineru_state": "done",
            "full_zip_url": full_zip_url,
            "download_started_at": _now_iso(),
        })
        artifacts = download_and_extract_zip(full_zip_url, output_dir)
        part["artifacts"] = artifacts
        parsed_parts.append(part)
        write_parse_status(part_parse_id, {
            "parse_status": "mineru_done",
            "artifacts": artifacts,
            "download_finished_at": _now_iso(),
            "download_info": artifacts.get("download_info"),
        })

    artifacts = _merge_split_artifacts(parse_id, parsed_parts)
    _update_supabase_status(supabase_file_id, "mineru_done")
    write_parse_status(parse_id, {
        "parse_status": "mineru_done",
        "mineru_state": "done",
        "artifacts": artifacts,
        "current_part": None,
    })
    ingest_artifacts(parse_id, artifacts)
    _vectorize_markdown(artifacts.get("markdown_path"), parse_id, supabase_file_id)


def retry_mineru_result_download(parse_id: str) -> None:
    status = read_parse_status(parse_id) or {}
    supabase_file_id = status.get("supabase_file_id")
    full_zip_url = status.get("full_zip_url")
    batch_id = status.get("batch_id")
    retry_count = int(status.get("download_retry_count") or 0) + 1

    try:
        write_parse_status(
            parse_id,
            {
                "parse_status": "mineru_download_retrying",
                "download_retry_count": retry_count,
                "download_retry_started_at": _now_iso(),
                "retryable": True,
                "user_message": "正在重试下载 MinerU 解析结果，已保留可能存在的断点文件。",
            },
        )
        if not full_zip_url and batch_id:
            batch_data = get_batch_result(batch_id)
            result = _extract_done_result(batch_data, parse_id)
            if not result or result.get("state") != "done":
                raise RuntimeError(f"MinerU batch result is not done yet: {result}")
            full_zip_url = result.get("full_zip_url")
            if not full_zip_url:
                raise RuntimeError(f"MinerU done result has no full_zip_url: {result}")
            write_parse_status(parse_id, {"full_zip_url": full_zip_url, "mineru_state": "done"})
        if not full_zip_url:
            raise RuntimeError("No full_zip_url or batch_id found for MinerU retry")

        artifacts = download_and_extract_zip(full_zip_url, PARSED_OUTPUT_ROOT / parse_id)
        write_parse_status(parse_id, {
            "parse_status": "mineru_done",
            "artifacts": artifacts,
            "download_retry_finished_at": _now_iso(),
            "download_info": artifacts.get("download_info"),
        })
        ingest_artifacts(parse_id, artifacts)
        _vectorize_markdown(artifacts.get("markdown_path"), parse_id, supabase_file_id)
    except Exception as e:
        logging.exception("MinerU 结果下载重试失败: %s", parse_id)
        _update_supabase_status(supabase_file_id, "mineru_download_failed")
        write_parse_status(parse_id, _failure_payload(
            "mineru_download_failed",
            e,
            stage="download_retry",
            retryable=True,
            download_retry_count=retry_count,
        ))


def import_mineru_result_zip(parse_id: str, zip_file_path: str | Path) -> dict[str, str | None]:
    status = read_parse_status(parse_id) or {}
    supabase_file_id = status.get("supabase_file_id")
    output_dir = PARSED_OUTPUT_ROOT / parse_id
    try:
        write_parse_status(parse_id, {"parse_status": "mineru_importing_zip", "import_started_at": _now_iso()})
        artifacts = extract_zip_artifacts(zip_file_path, output_dir)
        write_parse_status(parse_id, {"parse_status": "mineru_done", "artifacts": artifacts, "import_finished_at": _now_iso()})
        ingest_artifacts(parse_id, artifacts)
        _vectorize_markdown(artifacts.get("markdown_path"), parse_id, supabase_file_id)
        return artifacts
    except Exception as e:
        write_parse_status(parse_id, _failure_payload("mineru_import_failed", e, stage="manual_import", retryable=True))
        raise


def parse_and_index_tender_file(
    *,
    file_path: str,
    original_filename: str,
    parse_id: str,
    supabase_file_id: str | None = None,
) -> None:
    """Use MinerU first for PDFs when configured, otherwise index native text."""
    if has_mineru_token() and _should_use_mineru_first(file_path, original_filename):
        try:
            page_count = _pdf_page_count(file_path)
            if page_count and page_count > MINERU_MAX_PDF_PAGES:
                _run_mineru_split_parse_and_index(
                    file_path=file_path,
                    original_filename=original_filename,
                    parse_id=parse_id,
                    supabase_file_id=supabase_file_id,
                    total_pages=page_count,
                )
            else:
                _run_mineru_parse_and_index(
                    file_path=file_path,
                    original_filename=original_filename,
                    parse_id=parse_id,
                    supabase_file_id=supabase_file_id,
                )
            return
        except MinerUDownloadError as e:
            logging.exception("MinerU 结果 zip 下载失败，保留解析任务等待重试: %s", file_path)
            if _has_completed_mineru_ingest(parse_id):
                _update_supabase_status(supabase_file_id, "mineru_done")
                write_parse_status(
                    parse_id,
                    {
                        "parse_status": "mineru_done",
                        "retryable": False,
                        "user_message": None,
                    },
                )
                return
            _update_supabase_status(supabase_file_id, "mineru_download_failed")
            write_parse_status(
                parse_id,
                _failure_payload("mineru_download_failed", e, stage="download", retryable=True, parser="mineru"),
            )
            return
        except Exception as e:
            logging.exception("MinerU 优先解析失败，回退原生文本抽取: %s", file_path)
            _update_supabase_status(supabase_file_id, "mineru_fallback_native")
            write_parse_status(
                parse_id,
                {
                    "parse_status": "mineru_fallback_native",
                    "parser": "mineru",
                    "error": str(e),
                    "error_type": e.__class__.__name__,
                    "user_message": "MinerU 解析失败，系统正在尝试原生文本抽取兜底。",
                    "failed_at": _now_iso(),
                    "fallback": "native_text",
                },
            )

    try:
        file_to_chroma(file_path)
        _update_supabase_status(supabase_file_id, "indexed")
        write_parse_status(
            parse_id,
            {
                "parse_status": "indexed",
                "parser": "native_text",
                "source_file": file_path,
                "file_name": original_filename,
                "supabase_file_id": supabase_file_id,
            },
        )
        return
    except EmptyDocumentContentError as e:
        logging.warning("文件需要 OCR/MinerU 解析: %s, reason=%s", file_path, e)
        _update_supabase_status(supabase_file_id, "ocr_required")
        write_parse_status(
            parse_id,
            _failure_payload(
                "ocr_required",
                e,
                stage="native_text_extract",
                retryable=has_mineru_token(),
                parser="mineru",
                source_file=file_path,
                file_name=original_filename,
                reason=str(e),
                supabase_file_id=supabase_file_id,
            ),
        )
    except Exception:
        logging.exception("原始文件向量化处理失败: %s", file_path)
        error_text = "原始文件向量化处理失败"
        _update_supabase_status(supabase_file_id, "index_failed")
        write_parse_status(
            parse_id,
            _failure_payload(
                "index_failed",
                error_text,
                stage="native_vectorize",
                retryable=False,
                parser="native_text",
                source_file=file_path,
                file_name=original_filename,
                supabase_file_id=supabase_file_id,
            ),
        )
        return

    if not has_mineru_token():
        write_parse_status(
            parse_id,
            {
                "parse_status": "ocr_required",
                "parser": "mineru",
                "error": "MINERU_API_TOKEN is not configured",
                "user_message": "未配置 MINERU_API_TOKEN，扫描版或图片型 PDF 无法自动 OCR，请配置后重试或手动导入解析结果。",
                "failure_stage": "config",
                "retryable": True,
                "supabase_file_id": supabase_file_id,
            },
        )
        return

    try:
        _run_mineru_parse_and_index(
            file_path=file_path,
            original_filename=original_filename,
            parse_id=parse_id,
            supabase_file_id=supabase_file_id,
        )
    except MinerUConfigError as e:
        _update_supabase_status(supabase_file_id, "ocr_required")
        write_parse_status(parse_id, _failure_payload("ocr_required", e, stage="config", retryable=True, supabase_file_id=supabase_file_id))
    except MinerUDownloadError as e:
        logging.exception("MinerU 结果 zip 下载失败，等待重试: %s", file_path)
        if _has_completed_mineru_ingest(parse_id):
            _update_supabase_status(supabase_file_id, "mineru_done")
            write_parse_status(
                parse_id,
                {
                    "parse_status": "mineru_done",
                    "retryable": False,
                    "user_message": None,
                },
            )
            return
        _update_supabase_status(supabase_file_id, "mineru_download_failed")
        write_parse_status(parse_id, _failure_payload("mineru_download_failed", e, stage="download", retryable=True, supabase_file_id=supabase_file_id))
    except Exception as e:
        logging.exception("MinerU 解析或解析结果向量化失败: %s", file_path)
        _update_supabase_status(supabase_file_id, "mineru_failed")
        write_parse_status(parse_id, _failure_payload("mineru_failed", e, stage="parse_or_vectorize", retryable=True, supabase_file_id=supabase_file_id))
