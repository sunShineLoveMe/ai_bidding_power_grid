import json
import re
from typing import Any


def strip_llm_json(content: str) -> dict[str, Any]:
    """Parse JSON returned by LLMs, tolerating think blocks and fenced code."""
    clean = re.sub(r"<think>.*?</think>", "", content or "", flags=re.DOTALL).strip()
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", clean, flags=re.DOTALL)
    if match:
        clean = match.group(1).strip()
    return json.loads(clean)
