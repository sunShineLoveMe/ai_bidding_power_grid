#!/usr/bin/env python3
"""Run the minimal bidding workflow smoke test against a live backend.

This script is intentionally HTTP-level instead of Flask test-client level so it
can be reused after Docker or Aliyun deployment. It checks the path that matters
before customer testing:

1. optional login
2. tender upload
3. parse status polling
4. interpretation query / AI report generation
5. outline SSE generation
6. one section SSE generation
7. DOCX export task creation and polling
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import requests


DEFAULT_SAMPLE_MD = """# 国网配电自动化终端采购项目招标文件

## 项目概况

本项目采购配电自动化终端、通信模块、安装调试和运维服务。

## 技术要求

投标人应响应设备供货、现场安装、调试验收、质量保证、售后服务、
安全生产和资料移交要求。

## 评分办法

技术方案、项目实施组织、质量保证、售后服务、企业业绩和人员能力
为主要评分项。
"""


class SmokeFailure(RuntimeError):
    pass


@dataclass
class StepResult:
    name: str
    ok: bool
    detail: str = ""
    elapsed_ms: int = 0


@dataclass
class SmokeContext:
    base_url: str
    timeout: int
    session: requests.Session = field(default_factory=requests.Session)
    results: list[StepResult] = field(default_factory=list)

    def url(self, path: str) -> str:
        return f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"

    def record(self, name: str, started_at: float, detail: str = "", ok: bool = True) -> None:
        self.results.append(
            StepResult(
                name=name,
                ok=ok,
                detail=detail,
                elapsed_ms=int((time.time() - started_at) * 1000),
            )
        )


def _short_json(value: Any, *, limit: int = 500) -> str:
    text = json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= limit else text[:limit] + "..."


def _response_json(response: requests.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise SmokeFailure(f"响应不是 JSON: status={response.status_code} body={response.text[:300]}") from exc
    if response.status_code >= 400:
        raise SmokeFailure(f"HTTP {response.status_code}: {_short_json(payload)}")
    if not isinstance(payload, dict):
        raise SmokeFailure(f"响应 JSON 不是对象: {_short_json(payload)}")
    return payload


def _require_keys(payload: dict[str, Any], keys: Iterable[str], step: str) -> None:
    missing = [key for key in keys if not payload.get(key)]
    if missing:
        raise SmokeFailure(f"{step} 缺少字段: {', '.join(missing)}; payload={_short_json(payload)}")


def _parse_sse(text: str) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    event_type = "message"
    data_lines: list[str] = []

    def flush() -> None:
        nonlocal event_type, data_lines
        if not data_lines:
            event_type = "message"
            return
        raw = "\n".join(data_lines)
        try:
            data = json.loads(raw)
        except ValueError:
            data = {"raw": raw}
        events.append((event_type, data))
        event_type = "message"
        data_lines = []

    for line in text.splitlines():
        if not line:
            flush()
        elif line.startswith("event:"):
            event_type = line.split(":", 1)[1].strip() or "message"
        elif line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].lstrip())
    flush()
    return events


def _request_sse(ctx: SmokeContext, method: str, path: str, **kwargs: Any) -> list[tuple[str, dict[str, Any]]]:
    response = ctx.session.request(method, ctx.url(path), timeout=ctx.timeout, **kwargs)
    if response.status_code >= 400:
        raise SmokeFailure(f"HTTP {response.status_code}: {response.text[:500]}")
    events = _parse_sse(response.text)
    if not events:
        raise SmokeFailure("SSE 响应没有事件")
    error_events = [data for event, data in events if event == "error"]
    if error_events:
        raise SmokeFailure(f"SSE 返回 error: {_short_json(error_events[-1])}")
    return events


def _ensure_sample_file(path: str | None) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    if path:
        sample = Path(path).expanduser().resolve()
        if not sample.exists():
            raise SmokeFailure(f"样例文件不存在: {sample}")
        return sample, None
    tmp = tempfile.TemporaryDirectory(prefix="ai-bidding-smoke-")
    sample = Path(tmp.name) / "power-grid-smoke-tender.md"
    sample.write_text(DEFAULT_SAMPLE_MD, encoding="utf-8")
    return sample, tmp


def login_if_needed(ctx: SmokeContext, username: str | None, password: str | None) -> None:
    if not username and not password:
        return
    if not username or not password:
        raise SmokeFailure("--username 和 --password 必须同时提供")

    started = time.time()
    response = ctx.session.post(
        ctx.url("/api/users/login"),
        json={"username": username, "password": password},
        timeout=ctx.timeout,
    )
    payload = _response_json(response)
    token = payload.get("token")
    if token:
        ctx.session.headers.update({"Authorization": f"Bearer {token}"})
    ctx.record("login", started, f"user={username}")


def identify_user(ctx: SmokeContext, fallback_user_id: str) -> str:
    started = time.time()
    response = ctx.session.post(
        ctx.url("/api/users/identify"),
        json={"fingerprintId": f"smoke-{int(time.time())}"},
        timeout=ctx.timeout,
    )
    if response.status_code >= 400:
        ctx.record("identify_user", started, f"fallback={fallback_user_id}; status={response.status_code}", ok=True)
        return fallback_user_id
    payload = _response_json(response)
    user_id = payload.get("userId") or fallback_user_id
    ctx.record("identify_user", started, f"userId={user_id}")
    return str(user_id)


def upload_tender(ctx: SmokeContext, sample_file: Path, user_id: str) -> dict[str, Any]:
    started = time.time()
    mime = mimetypes.guess_type(sample_file.name)[0] or "application/octet-stream"
    with sample_file.open("rb") as fh:
        response = ctx.session.post(
            ctx.url("/api/bidding/upload"),
            data={"userId": user_id},
            files={"file": (sample_file.name, fh, mime)},
            timeout=ctx.timeout,
        )
    payload = _response_json(response)
    _require_keys(payload, ["projectId", "fileId"], "upload_tender")
    ctx.record(
        "upload_tender",
        started,
        f"projectId={payload.get('projectId')} fileId={payload.get('fileId')} supabaseFileId={payload.get('supabaseFileId')}",
    )
    return payload


def wait_parse_completed(ctx: SmokeContext, file_id: str, project_id: str, supabase_file_id: str | None) -> dict[str, Any]:
    started = time.time()
    deadline = time.time() + ctx.timeout
    last_payload: dict[str, Any] = {}
    query = f"projectId={project_id}"
    if supabase_file_id:
        query += f"&supabaseFileId={supabase_file_id}"
    while time.time() < deadline:
        response = ctx.session.get(ctx.url(f"/api/bidding/parse-status/{file_id}?{query}"), timeout=ctx.timeout)
        payload = _response_json(response)
        last_payload = payload
        if payload.get("parseCompleted") or payload.get("parseStatus") == "indexed":
            ctx.record("wait_parse_completed", started, f"parseStatus={payload.get('parseStatus')}")
            return payload
        if payload.get("error") and not payload.get("retryable"):
            raise SmokeFailure(f"解析失败且不可重试: {_short_json(payload)}")
        time.sleep(2)
    raise SmokeFailure(f"等待解析完成超时，最后状态: {_short_json(last_payload)}")


def query_interpretation(ctx: SmokeContext, project_id: str) -> dict[str, Any]:
    started = time.time()
    response = ctx.session.get(ctx.url(f"/api/bidding/interpretations/{project_id}"), timeout=ctx.timeout)
    payload = _response_json(response)
    ctx.record("query_interpretation", started, f"hasAnalysis={bool(payload.get('analysis'))}")
    return payload


def generate_ai_report(ctx: SmokeContext, project_id: str) -> dict[str, Any]:
    started = time.time()
    response = ctx.session.post(ctx.url(f"/api/bidding/interpretations/{project_id}/ai-report"), timeout=ctx.timeout)
    payload = _response_json(response)
    _require_keys(payload, ["aiReport"], "generate_ai_report")
    ctx.record("generate_ai_report", started, "ok")
    return payload


def generate_outline(ctx: SmokeContext, project_id: str) -> dict[str, Any]:
    started = time.time()
    events = _request_sse(ctx, "GET", f"/api/bidding/interpretations/{project_id}/bid-outline/stream")
    done = next((data for event, data in reversed(events) if event == "done"), None)
    if not done:
        raise SmokeFailure("大纲 SSE 没有 done 事件")
    outline = done.get("outline") or {}
    chapters = outline.get("chapters") or []
    if not chapters:
        raise SmokeFailure(f"大纲 done 事件没有章节: {_short_json(done)}")
    ctx.record("generate_outline", started, f"chapters={len(chapters)}")
    return outline


def list_sections(ctx: SmokeContext, project_id: str) -> list[dict[str, Any]]:
    started = time.time()
    response = ctx.session.get(ctx.url(f"/api/bidding/interpretations/{project_id}/sections"), timeout=ctx.timeout)
    payload = _response_json(response)
    sections = payload.get("sections")
    if not isinstance(sections, list) or not sections:
        raise SmokeFailure(f"章节列表为空: {_short_json(payload)}")
    ctx.record("list_sections", started, f"sections={len(sections)}")
    return sections


def generate_one_section(ctx: SmokeContext, project_id: str, section: dict[str, Any]) -> None:
    started = time.time()
    chapter = {
        "id": section.get("id"),
        "title": section.get("title") or "施工组织设计",
        "order": section.get("order") or "1",
        "level": section.get("level") or 1,
        "parent_id": section.get("parent_id"),
        "metadata": section.get("metadata") if isinstance(section.get("metadata"), dict) else {},
    }
    events = _request_sse(
        ctx,
        "POST",
        f"/api/bidding/interpretations/{project_id}/sections/stream",
        json=chapter,
    )
    done = any(event == "done" for event, _data in events)
    chunks = [data for event, data in events if event == "chunk" and data.get("content")]
    if not done:
        raise SmokeFailure("章节正文 SSE 没有 done 事件")
    if not chunks:
        raise SmokeFailure("章节正文 SSE 没有正文 chunk")
    ctx.record("generate_one_section", started, f"sectionId={chapter.get('id')} chunks={len(chunks)}")


def create_docx_export(ctx: SmokeContext, project_id: str) -> str:
    started = time.time()
    response = ctx.session.post(ctx.url(f"/api/bidding/interpretations/{project_id}/download-docx"), json={}, timeout=ctx.timeout)
    payload = _response_json(response)
    task_id = payload.get("taskId")
    if not task_id:
        raise SmokeFailure(f"DOCX 导出响应缺 taskId: {_short_json(payload)}")
    ctx.record("create_docx_export", started, f"taskId={task_id}")
    return str(task_id)


def wait_docx_export(ctx: SmokeContext, project_id: str, task_id: str) -> dict[str, Any]:
    started = time.time()
    deadline = time.time() + ctx.timeout
    last_task: dict[str, Any] = {}
    while time.time() < deadline:
        response = ctx.session.get(
            ctx.url(f"/api/bidding/interpretations/{project_id}/export-tasks/{task_id}"),
            timeout=ctx.timeout,
        )
        payload = _response_json(response)
        task = payload.get("task") or {}
        last_task = task
        if task.get("status") == "completed":
            ctx.record("wait_docx_export", started, f"status=completed path={task.get('file_path') or task.get('download_url')}")
            return task
        if task.get("status") == "failed":
            raise SmokeFailure(f"DOCX 导出失败: {_short_json(task)}")
        time.sleep(2)
    raise SmokeFailure(f"等待 DOCX 导出超时，最后状态: {_short_json(last_task)}")


def run_smoke(args: argparse.Namespace) -> SmokeContext:
    ctx = SmokeContext(base_url=args.base_url, timeout=args.timeout)
    tmp: tempfile.TemporaryDirectory[str] | None = None
    try:
        login_if_needed(ctx, args.username, args.password)
        project_id = args.project_id
        file_id = args.file_id
        supabase_file_id = args.supabase_file_id
        if not project_id:
            sample_file, tmp = _ensure_sample_file(args.sample_file)
            user_id = args.user_id or identify_user(ctx, "smoke-user")
            uploaded = upload_tender(ctx, sample_file, user_id)
            project_id = uploaded["projectId"]
            file_id = uploaded["fileId"]
            supabase_file_id = uploaded.get("supabaseFileId")
        if file_id and not args.skip_parse_wait:
            wait_parse_completed(ctx, file_id, project_id, supabase_file_id)
        query_interpretation(ctx, project_id)
        if not args.skip_ai_report:
            generate_ai_report(ctx, project_id)
        outline = generate_outline(ctx, project_id)
        sections = list_sections(ctx, project_id)
        generate_one_section(ctx, project_id, sections[0] if sections else (outline.get("chapters") or [{}])[0])
        task_id = create_docx_export(ctx, project_id)
        wait_docx_export(ctx, project_id, task_id)
        return ctx
    finally:
        if tmp is not None:
            tmp.cleanup()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run minimal AI bidding workflow smoke test against a live backend.")
    parser.add_argument("--base-url", default=os.getenv("SMOKE_BASE_URL", "http://127.0.0.1:3012"))
    parser.add_argument("--timeout", type=int, default=int(os.getenv("SMOKE_TIMEOUT_SECONDS", "300")))
    parser.add_argument("--username", default=os.getenv("SMOKE_USERNAME"))
    parser.add_argument("--password", default=os.getenv("SMOKE_PASSWORD"))
    parser.add_argument("--user-id", default=os.getenv("SMOKE_USER_ID"))
    parser.add_argument("--sample-file", default=os.getenv("SMOKE_SAMPLE_FILE"))
    parser.add_argument("--project-id", default=os.getenv("SMOKE_PROJECT_ID"))
    parser.add_argument("--file-id", default=os.getenv("SMOKE_FILE_ID"))
    parser.add_argument("--supabase-file-id", default=os.getenv("SMOKE_SUPABASE_FILE_ID"))
    parser.add_argument("--skip-parse-wait", action="store_true")
    parser.add_argument("--skip-ai-report", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        ctx = run_smoke(args)
    except Exception as exc:
        print(f"SMOKE FAILED: {exc}", file=sys.stderr)
        return 1

    print("SMOKE PASSED")
    for result in ctx.results:
        marker = "ok" if result.ok else "fail"
        print(f"[{marker}] {result.name} ({result.elapsed_ms} ms) {result.detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
