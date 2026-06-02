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
7. compliance coverage check
8. DOCX export task creation and polling
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
from datetime import datetime, timezone
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
    artifacts: dict[str, Any] = field(default_factory=dict)
    quiet: bool = False

    def url(self, path: str) -> str:
        return f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"

    def progress(self, message: str) -> None:
        if not self.quiet:
            print(f"[smoke] {message}", file=sys.stderr, flush=True)

    def record(self, name: str, started_at: float, detail: str = "", ok: bool = True) -> None:
        result = StepResult(
            name=name,
            ok=ok,
            detail=detail,
            elapsed_ms=int((time.time() - started_at) * 1000),
        )
        self.results.append(result)
        self.progress(f"{name} ok elapsed_ms={result.elapsed_ms} {detail}".strip())


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


def _now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


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


def check_ready(ctx: SmokeContext) -> dict[str, Any]:
    started = time.time()
    response = ctx.session.get(ctx.url("/api/ready"), timeout=ctx.timeout)
    payload = _response_json(response)
    checks = payload.get("checks") or {}
    failed_checks = [
        name
        for name, check in checks.items()
        if isinstance(check, dict) and check.get("status") in {"fail", "failed", "error"}
    ]
    if failed_checks:
        raise SmokeFailure(f"/api/ready 存在失败检查: {', '.join(failed_checks)}; payload={_short_json(payload)}")
    status = payload.get("status") or payload.get("ready") or "unknown"
    ctx.artifacts["ready"] = payload
    ctx.record("check_ready", started, f"status={status} checks={len(checks) if isinstance(checks, dict) else '-'}")
    return payload


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
    ctx.artifacts.update(
        {
            "project_id": payload.get("projectId"),
            "file_id": payload.get("fileId"),
            "supabase_file_id": payload.get("supabaseFileId"),
            "sample_file": str(sample_file),
        }
    )
    return payload


def wait_parse_completed(
    ctx: SmokeContext,
    file_id: str,
    project_id: str,
    supabase_file_id: str | None,
    *,
    require_mineru: bool = False,
) -> dict[str, Any]:
    started = time.time()
    deadline = time.time() + ctx.timeout
    last_payload: dict[str, Any] = {}
    last_status: str | None = None
    query = f"projectId={project_id}"
    if supabase_file_id:
        query += f"&supabaseFileId={supabase_file_id}"
    while time.time() < deadline:
        response = ctx.session.get(ctx.url(f"/api/bidding/parse-status/{file_id}?{query}"), timeout=ctx.timeout)
        payload = _response_json(response)
        last_payload = payload
        current_status = str(payload.get("parseStatus") or "unknown")
        if current_status != last_status:
            mineru = payload.get("mineru") if isinstance(payload.get("mineru"), dict) else {}
            ctx.progress(
                "wait_parse_completed "
                f"parseStatus={current_status} parser={mineru.get('parser')} "
                f"retryable={payload.get('retryable')}"
            )
            last_status = current_status
        if payload.get("parseCompleted") or payload.get("parseStatus") == "indexed":
            mineru = payload.get("mineru") if isinstance(payload.get("mineru"), dict) else {}
            if require_mineru and mineru.get("parser") != "mineru":
                raise SmokeFailure(f"解析已完成但未确认走 MinerU: {_short_json(payload)}")
            ctx.artifacts["parse_status"] = payload
            ctx.record(
                "wait_parse_completed",
                started,
                f"parseStatus={payload.get('parseStatus')} parser={mineru.get('parser')}",
            )
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
    ctx.artifacts["outline_chapters"] = len(chapters)
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
    ctx.artifacts["section_id"] = chapter.get("id")
    ctx.artifacts["section_chunks"] = len(chunks)
    ctx.record("generate_one_section", started, f"sectionId={chapter.get('id')} chunks={len(chunks)}")


def run_compliance_check(ctx: SmokeContext, project_id: str) -> dict[str, Any]:
    started = time.time()
    response = ctx.session.get(ctx.url(f"/api/bidding/interpretations/{project_id}/compliance-check"), timeout=ctx.timeout)
    payload = _response_json(response)
    rows = payload.get("rows")
    summary = payload.get("summary") or {}
    if not isinstance(rows, list):
        raise SmokeFailure(f"合规检查响应缺 rows: {_short_json(payload)}")
    ctx.record(
        "run_compliance_check",
        started,
        f"rows={len(rows)} coverage={summary.get('coverageRate') or summary.get('coverage_rate')}",
    )
    ctx.artifacts["compliance_rows"] = len(rows)
    ctx.artifacts["compliance_summary"] = summary
    return payload


def create_docx_export(ctx: SmokeContext, project_id: str) -> str:
    started = time.time()
    response = ctx.session.post(ctx.url(f"/api/bidding/interpretations/{project_id}/download-docx"), json={}, timeout=ctx.timeout)
    payload = _response_json(response)
    task_id = payload.get("taskId")
    if not task_id:
        raise SmokeFailure(f"DOCX 导出响应缺 taskId: {_short_json(payload)}")
    ctx.artifacts["docx_task_id"] = task_id
    ctx.record("create_docx_export", started, f"taskId={task_id}")
    return str(task_id)


def wait_docx_export(ctx: SmokeContext, project_id: str, task_id: str) -> dict[str, Any]:
    started = time.time()
    deadline = time.time() + ctx.timeout
    last_task: dict[str, Any] = {}
    last_status: str | None = None
    while time.time() < deadline:
        response = ctx.session.get(
            ctx.url(f"/api/bidding/interpretations/{project_id}/export-tasks/{task_id}"),
            timeout=ctx.timeout,
        )
        payload = _response_json(response)
        task = payload.get("task") or {}
        last_task = task
        current_status = str(task.get("status") or "unknown")
        if current_status != last_status:
            ctx.progress(f"wait_docx_export status={current_status}")
            last_status = current_status
        if task.get("status") == "completed":
            ctx.artifacts["docx_export"] = task
            ctx.record("wait_docx_export", started, f"status=completed path={task.get('file_path') or task.get('download_url')}")
            return task
        if task.get("status") == "failed":
            raise SmokeFailure(f"DOCX 导出失败: {_short_json(task)}")
        time.sleep(2)
    raise SmokeFailure(f"等待 DOCX 导出超时，最后状态: {_short_json(last_task)}")


def run_smoke(args: argparse.Namespace) -> SmokeContext:
    ctx = SmokeContext(base_url=args.base_url, timeout=args.timeout, quiet=args.quiet)
    tmp: tempfile.TemporaryDirectory[str] | None = None
    try:
        if not args.skip_ready:
            check_ready(ctx)
        login_if_needed(ctx, args.username, args.password)
        project_id = args.project_id
        file_id = args.file_id
        supabase_file_id = args.supabase_file_id
        if not project_id:
            sample_file, tmp = _ensure_sample_file(args.sample_file)
            if args.require_mineru and sample_file.suffix.lower() != ".pdf":
                raise SmokeFailure("--require-mineru 需要通过 --sample-file 传入 PDF 文件")
            user_id = args.user_id or identify_user(ctx, "smoke-user")
            uploaded = upload_tender(ctx, sample_file, user_id)
            project_id = uploaded["projectId"]
            file_id = uploaded["fileId"]
            supabase_file_id = uploaded.get("supabaseFileId")
        ctx.artifacts["project_id"] = project_id
        if file_id:
            ctx.artifacts["file_id"] = file_id
        if supabase_file_id:
            ctx.artifacts["supabase_file_id"] = supabase_file_id
        if file_id and not args.skip_parse_wait:
            wait_parse_completed(ctx, file_id, project_id, supabase_file_id, require_mineru=args.require_mineru)
        query_interpretation(ctx, project_id)
        if not args.skip_ai_report:
            generate_ai_report(ctx, project_id)
        outline = generate_outline(ctx, project_id)
        sections = list_sections(ctx, project_id)
        generate_one_section(ctx, project_id, sections[0] if sections else (outline.get("chapters") or [{}])[0])
        if not args.skip_compliance:
            run_compliance_check(ctx, project_id)
        task_id = create_docx_export(ctx, project_id)
        wait_docx_export(ctx, project_id, task_id)
        return ctx
    except Exception as exc:
        setattr(exc, "smoke_context", ctx)
        raise
    finally:
        if tmp is not None:
            tmp.cleanup()


def _report_payload(ctx: SmokeContext, *, ok: bool, error: str | None = None) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ok": ok,
        "base_url": ctx.base_url,
        "timeout": ctx.timeout,
        "error": error,
        "artifacts": ctx.artifacts,
        "steps": [
            {
                "name": result.name,
                "ok": result.ok,
                "detail": result.detail,
                "elapsed_ms": result.elapsed_ms,
            }
            for result in ctx.results
        ],
    }


def write_report(ctx: SmokeContext, report_path: str | None, *, ok: bool, error: str | None = None) -> Path | None:
    if not report_path:
        return None
    output = Path(report_path)
    if output.is_dir() or not output.suffix:
        output.mkdir(parents=True, exist_ok=True)
        status = "passed" if ok else "failed"
        output = output / f"run_{_now_tag()}_http_smoke_{status}.md"
    output.parent.mkdir(parents=True, exist_ok=True)

    payload = _report_payload(ctx, ok=ok, error=error)
    json_path = output.with_suffix(".json")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# HTTP 全链路冒烟报告",
        "",
        f"> 生成时间：{payload['generated_at']}",
        f"> 结果：{'PASS' if ok else 'FAIL'}",
        f"> 后端：`{ctx.base_url}`",
        f"> JSON：`{json_path}`",
        "",
        "## 关键 ID",
        "",
        f"- project_id：`{ctx.artifacts.get('project_id') or '-'}`",
        f"- file_id：`{ctx.artifacts.get('file_id') or '-'}`",
        f"- supabase_file_id：`{ctx.artifacts.get('supabase_file_id') or '-'}`",
        f"- docx_task_id：`{ctx.artifacts.get('docx_task_id') or '-'}`",
        "",
        "## 步骤",
        "",
        "| 状态 | 步骤 | 耗时(ms) | 详情 |",
        "| --- | --- | ---: | --- |",
    ]
    for result in ctx.results:
        lines.append(
            f"| {'ok' if result.ok else 'fail'} | `{result.name}` | {result.elapsed_ms} | {result.detail or '-'} |"
        )
    if error:
        lines.extend(["", "## 错误", "", error])
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


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
    parser.add_argument("--skip-compliance", action="store_true")
    parser.add_argument("--skip-ready", action="store_true")
    parser.add_argument("--require-mineru", action="store_true", help="Require parse-status to confirm parser=mineru; use with a PDF sample file.")
    parser.add_argument("--quiet", action="store_true", help="Do not print per-step progress to stderr.")
    parser.add_argument(
        "--report",
        default=os.getenv("SMOKE_REPORT_PATH", "docs/development/runs"),
        help="Markdown report file or directory. A sibling JSON report is also written.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    ctx: SmokeContext | None = None
    try:
        ctx = run_smoke(args)
    except Exception as exc:
        ctx = getattr(exc, "smoke_context", None) or SmokeContext(base_url=args.base_url, timeout=args.timeout)
        report = write_report(ctx, args.report, ok=False, error=str(exc))
        if report:
            print(f"SMOKE REPORT: {report}", file=sys.stderr)
        print(f"SMOKE FAILED: {exc}", file=sys.stderr)
        return 1

    report = write_report(ctx, args.report, ok=True)
    print("SMOKE PASSED")
    if report:
        print(f"SMOKE REPORT: {report}")
    for result in ctx.results:
        marker = "ok" if result.ok else "fail"
        print(f"[{marker}] {result.name} ({result.elapsed_ms} ms) {result.detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
