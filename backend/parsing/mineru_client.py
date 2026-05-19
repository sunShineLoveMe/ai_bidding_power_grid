import json
import os
import socket
import subprocess
import time
from urllib.parse import urlparse
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()

MINERU_API_BASE_URL = os.getenv("MINERU_API_BASE_URL", "https://mineru.net").rstrip("/")


class MinerUConfigError(RuntimeError):
    pass


class MinerUApiError(RuntimeError):
    pass


class MinerUDownloadError(RuntimeError):
    pass


@dataclass
class MinerULocalTask:
    batch_id: str
    upload_url: str
    data_id: str
    file_name: str


def get_mineru_token() -> str:
    token = os.getenv("MINERU_API_TOKEN") or os.getenv("MINERU_TOKEN")
    if not token:
        raise MinerUConfigError("MINERU_API_TOKEN is required to call MinerU precise parsing API")
    return token


def has_mineru_token() -> bool:
    return bool(os.getenv("MINERU_API_TOKEN") or os.getenv("MINERU_TOKEN"))


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {get_mineru_token()}",
        "Content-Type": "application/json",
        "Accept": "*/*",
    }


def _raise_for_mineru_error(payload: dict[str, Any]) -> None:
    if payload.get("code") == 0:
        return
    raise MinerUApiError(f"MinerU API failed: code={payload.get('code')}, msg={payload.get('msg')}")


def create_local_file_batch_task(
    *,
    local_file_path: str | Path,
    file_name: str,
    data_id: str,
    model_version: str = "vlm",
    language: str = "ch",
    enable_table: bool = True,
    enable_formula: bool = False,
    is_ocr: bool = True,
    timeout: int = 300,
) -> MinerULocalTask:
    """Create a MinerU signed upload task and upload the local file."""
    local_path = Path(local_file_path)
    if not local_path.exists():
        raise FileNotFoundError(f"Local file not found: {local_path}")

    payload = {
        "files": [
            {
                "name": file_name,
                "data_id": data_id,
                "is_ocr": is_ocr,
            }
        ],
        "model_version": model_version,
        "language": language,
        "enable_table": enable_table,
        "enable_formula": enable_formula,
    }
    response = requests.post(
        f"{MINERU_API_BASE_URL}/api/v4/file-urls/batch",
        headers=_headers(),
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    result = response.json()
    _raise_for_mineru_error(result)

    data = result.get("data") or {}
    file_urls = data.get("file_urls") or []
    if not data.get("batch_id") or not file_urls:
        raise MinerUApiError(f"MinerU upload URL response is incomplete: {json.dumps(result, ensure_ascii=False)}")

    upload_url_item = file_urls[0]
    upload_url = upload_url_item.get("url") if isinstance(upload_url_item, dict) else upload_url_item
    if not upload_url:
        raise MinerUApiError(f"MinerU upload URL is empty: {json.dumps(result, ensure_ascii=False)}")
    with open(local_path, "rb") as f:
        upload_response = requests.put(upload_url, data=f, timeout=timeout)
    upload_response.raise_for_status()

    return MinerULocalTask(
        batch_id=data["batch_id"],
        upload_url=upload_url,
        data_id=data_id,
        file_name=file_name,
    )


def get_batch_result(batch_id: str, timeout: int = 60) -> dict[str, Any]:
    response = requests.get(
        f"{MINERU_API_BASE_URL}/api/v4/extract-results/batch/{batch_id}",
        headers=_headers(),
        timeout=timeout,
    )
    response.raise_for_status()
    result = response.json()
    _raise_for_mineru_error(result)
    return result.get("data") or {}


def _normalize_extract_results(batch_data: dict[str, Any]) -> list[dict[str, Any]]:
    extract_result = batch_data.get("extract_result") or []
    if isinstance(extract_result, dict):
        return [extract_result]
    return [item for item in extract_result if isinstance(item, dict)]


def wait_for_batch_file_result(
    *,
    batch_id: str,
    data_id: str,
    timeout_seconds: int = 1800,
    poll_interval_seconds: int = 8,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_result: dict[str, Any] = {}

    while time.time() < deadline:
        batch_data = get_batch_result(batch_id)
        results = _normalize_extract_results(batch_data)
        matched = next((item for item in results if item.get("data_id") == data_id), None)
        if matched is None and len(results) == 1:
            matched = results[0]
        if matched:
            last_result = matched
            if on_progress:
                on_progress(matched)
            state = matched.get("state")
            if state == "done":
                return matched
            if state == "failed":
                raise MinerUApiError(matched.get("err_msg") or "MinerU parsing failed")
        time.sleep(poll_interval_seconds)

    raise TimeoutError(f"MinerU parsing timeout after {timeout_seconds}s, last_result={last_result}")


def _download_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=int(os.getenv("MINERU_DOWNLOAD_RETRIES", "5")),
        connect=5,
        read=5,
        status=5,
        backoff_factor=float(os.getenv("MINERU_DOWNLOAD_BACKOFF", "1.5")),
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _download_with_curl(zip_url: str, tmp_zip_path: Path, timeout: int, verify_ssl: bool) -> None:
    curl_path = os.getenv("MINERU_CURL_PATH", "/usr/bin/curl")
    parsed_url = urlparse(zip_url)
    host = parsed_url.hostname
    resolve_ips = _resolve_download_host(host) if host else []
    resume_enabled = os.getenv("MINERU_DOWNLOAD_RESUME", "true").lower() not in {"false", "0", "no"}

    errors: list[str] = []
    resolve_attempts: list[str | None] = [None, *resolve_ips]
    for resolve_ip in resolve_attempts:
        mode = f"resolve={resolve_ip}" if resolve_ip else "system-dns"
        resume_from = tmp_zip_path.stat().st_size if resume_enabled and tmp_zip_path.exists() else 0
        if tmp_zip_path.exists() and not resume_enabled:
            tmp_zip_path.unlink()
        command = [
            curl_path,
            "-L",
            "--fail",
            "--silent",
            "--show-error",
            "--retry",
            os.getenv("MINERU_CURL_RETRIES", "5"),
            "--retry-delay",
            os.getenv("MINERU_CURL_RETRY_DELAY", "2"),
            "--connect-timeout",
            os.getenv("MINERU_CURL_CONNECT_TIMEOUT", "30"),
            "--max-time",
            str(timeout),
            "-A",
            "Mozilla/5.0 ai-bidding-mineru-downloader",
            "-o",
            str(tmp_zip_path),
        ]
        if resume_from > 0:
            command.extend(["--continue-at", "-"])
        if resolve_ip and host:
            command.extend(["--resolve", f"{host}:443:{resolve_ip}"])
        command.append(zip_url)
        if not verify_ssl:
            command.insert(1, "-k")

        result = subprocess.run(command, check=False, capture_output=True, text=True)
        if result.returncode == 0:
            if tmp_zip_path.exists() and tmp_zip_path.stat().st_size > 0:
                return
            errors.append(
                f"{mode}: code=0, stderr={result.stderr.strip()}, but output file was not created or is empty"
            )
            continue
        errors.append(f"{mode}: code={result.returncode}, stderr={result.stderr.strip()}")

    raise MinerUDownloadError("curl fallback failed: " + " | ".join(errors))


def _resolve_download_host(host: str | None) -> list[str]:
    if not host:
        return []
    env_ips = os.getenv("MINERU_CDN_RESOLVE_IPS")
    if env_ips:
        return [ip.strip() for ip in env_ips.split(",") if ip.strip()]

    if os.getenv("MINERU_DOWNLOAD_DOH_RESOLVE", "true").lower() in {"false", "0", "no"}:
        return []

    try:
        response = requests.get(
            "https://dns.google/resolve",
            params={"name": host, "type": "A"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        ips: list[str] = []
        for answer in payload.get("Answer") or []:
            if answer.get("type") == 1 and answer.get("data"):
                ips.append(answer["data"])
        return ips
    except Exception:
        return []


def _host_uses_fake_ip(host: str | None) -> bool:
    if not host:
        return False
    try:
        addresses = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except Exception:
        return False
    for item in addresses:
        ip = item[4][0]
        if ip.startswith("198.18.") or ip.startswith("198.19."):
            return True
    return False


def extract_zip_artifacts(zip_path: str | Path, output_dir: str | Path) -> dict[str, str | None]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    zip_path = Path(zip_path)
    if not zip_path.exists() or zip_path.stat().st_size == 0:
        raise MinerUDownloadError(f"MinerU result zip is empty or missing: {zip_path}")

    extract_dir = output_path / "extract"
    extract_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)
    except zipfile.BadZipFile as e:
        raise MinerUDownloadError(f"MinerU result zip is invalid: {zip_path}") from e

    markdown_path = next(extract_dir.rglob("full.md"), None)
    content_list_path = next(extract_dir.rglob("*_content_list.json"), None)
    model_path = next(extract_dir.rglob("*_model.json"), None)
    middle_path = next(extract_dir.rglob("*_middle.json"), None) or next(extract_dir.rglob("layout.json"), None)

    return {
        "zip_path": str(zip_path),
        "extract_dir": str(extract_dir),
        "markdown_path": str(markdown_path) if markdown_path else None,
        "content_list_path": str(content_list_path) if content_list_path else None,
        "model_path": str(model_path) if model_path else None,
        "middle_path": str(middle_path) if middle_path else None,
    }


def download_and_extract_zip(zip_url: str, output_dir: str | Path, timeout: int = 300) -> dict[str, str | None]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    zip_path = output_path / "mineru_result.zip"
    tmp_zip_path = output_path / "mineru_result.zip.part"
    verify_ssl = os.getenv("MINERU_DOWNLOAD_VERIFY_SSL", "true").lower() not in {"false", "0", "no"}
    resume_enabled = os.getenv("MINERU_DOWNLOAD_RESUME", "true").lower() not in {"false", "0", "no"}
    keep_partial = os.getenv("MINERU_DOWNLOAD_KEEP_PARTIAL", "true").lower() not in {"false", "0", "no"}
    parsed_url = urlparse(zip_url)
    skip_requests = _host_uses_fake_ip(parsed_url.hostname)
    download_info: dict[str, Any] = {
        "url_host": parsed_url.hostname,
        "resume_enabled": resume_enabled,
        "used_curl_fallback": False,
        "resumed_from_bytes": 0,
        "downloaded_bytes": 0,
    }

    try:
        if tmp_zip_path.exists() and not resume_enabled:
            tmp_zip_path.unlink()
        try:
            if skip_requests:
                raise MinerUDownloadError("System DNS resolved MinerU CDN to fake-ip; using curl --resolve")
            else:
                resume_from = tmp_zip_path.stat().st_size if resume_enabled and tmp_zip_path.exists() else 0
                headers = {"User-Agent": "Mozilla/5.0 ai-bidding-mineru-downloader"}
                if resume_from > 0:
                    headers["Range"] = f"bytes={resume_from}-"
                response = _download_session().get(
                    zip_url,
                    stream=True,
                    timeout=timeout,
                    verify=verify_ssl,
                    headers=headers,
                )
                response.raise_for_status()
                mode = "ab" if resume_from > 0 and response.status_code == 206 else "wb"
                if resume_from > 0 and response.status_code != 206:
                    resume_from = 0
                download_info["resumed_from_bytes"] = resume_from
                downloaded_bytes = 0
                with open(tmp_zip_path, mode) as f:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            downloaded_bytes += len(chunk)
                            f.write(chunk)
                download_info["downloaded_bytes"] = downloaded_bytes
        except Exception as requests_error:
            if tmp_zip_path.exists() and not keep_partial:
                tmp_zip_path.unlink()
            if os.getenv("MINERU_DOWNLOAD_USE_CURL_FALLBACK", "true").lower() in {"false", "0", "no"}:
                raise
            download_info["used_curl_fallback"] = True
            _download_with_curl(zip_url, tmp_zip_path, timeout, verify_ssl)
        if not tmp_zip_path.exists():
            raise MinerUDownloadError("MinerU result zip download did not create a temporary file")
        if tmp_zip_path.stat().st_size == 0:
            raise MinerUDownloadError("MinerU result zip download returned empty file")
        download_info["zip_size"] = tmp_zip_path.stat().st_size
        tmp_zip_path.replace(zip_path)
    except Exception as e:
        if tmp_zip_path.exists() and not keep_partial:
            tmp_zip_path.unlink()
        if tmp_zip_path.exists():
            download_info["partial_path"] = str(tmp_zip_path)
            download_info["partial_size"] = tmp_zip_path.stat().st_size
        raise MinerUDownloadError(f"MinerU result zip download failed: {e}") from e

    artifacts = extract_zip_artifacts(zip_path, output_dir)
    artifacts["download_info"] = download_info
    return artifacts
