from __future__ import annotations

import re
from typing import Iterable


BRACKETED_FORMAL_PLACEHOLDER_RE = re.compile(r"【[^】]*(?:待补充|待填写|待确认|待核对)[^】]*】")
PLAIN_FORMAL_PLACEHOLDER_RE = re.compile(
    r"(?:[:：]\s*待补充(?:具体)?[\u4e00-\u9fa5A-Za-z0-9/（）()、]{0,18})"
    r"|(?:此处待补充)"
    r"|(?:待补充具体[\u4e00-\u9fa5A-Za-z0-9/（）()、]{0,18})"
    r"|(?:待补充事项)"
)


def collect_formal_placeholders(text: str | None) -> list[str]:
    """Collect explicit formal bid placeholders that must not remain in final DOCX.

    The project has old generated text with both bracketed placeholders and plain
    fragments such as "报告编号：待补充" or "此处待补充".  We intentionally avoid
    matching every standalone "待补充" in explanatory prose, because those can be
    audit notes rather than an actual field placeholder.
    """
    value = str(text or "")
    matches: list[tuple[int, str]] = []
    for pattern in (BRACKETED_FORMAL_PLACEHOLDER_RE, PLAIN_FORMAL_PLACEHOLDER_RE):
        matches.extend((match.start(), match.group(0)) for match in pattern.finditer(value))
    return [item for _, item in sorted(matches, key=lambda pair: pair[0])]


def count_formal_placeholders(texts: Iterable[str | None]) -> int:
    return sum(len(collect_formal_placeholders(text)) for text in texts)


def replace_formal_placeholders_with_confirmation_text(text: str | None) -> tuple[str, int]:
    """Rewrite visible placeholder tokens into non-final customer-confirmation wording.

    This is for draft cleanup only; it removes embarrassing "待补充" markers from
    generated prose while keeping the text honest that the value needs customer
    confirmation.  Customer-decision fields are still blocked by the formal gate.
    """
    result = str(text or "")
    replacements = 0

    def replace_bracketed(match: re.Match[str]) -> str:
        nonlocal replacements
        token = match.group(0).strip("【】")
        token = re.sub(r"\s+", "", token)
        token = re.sub(r"^(?:待补充|待填写|待确认|待核对)[：:]?", "", token)
        token = re.sub(r"(?:待补充|待填写|待确认|待核对)$", "", token)
        replacements += 1
        return f"客户最终确认后填写（{token or '相关信息'}）"

    result = BRACKETED_FORMAL_PLACEHOLDER_RE.sub(replace_bracketed, result)

    plain_patterns = [
        (re.compile(r"客户确认后填写（([^）]{0,60})此处待补充）"), r"客户确认后填写（\1待客户最终确认）"),
        (re.compile(r"（待补充具体([^）]{0,40})）"), r"（客户最终确认后填写具体\1）"),
        (re.compile(r"（待补充([^）]{0,40})）"), r"（客户最终确认后填写\1）"),
        (re.compile(r"([：:]\s*)待补充具体([\u4e00-\u9fa5A-Za-z0-9/（）()、]{0,18})"), r"\1客户最终确认后填写具体\2"),
        (re.compile(r"([：:]\s*)待补充([\u4e00-\u9fa5A-Za-z0-9/（）()、]{0,18})"), r"\1客户最终确认后填写\2"),
        (re.compile(r"此处待补充"), "待客户最终确认"),
        (re.compile(r"待补充具体([\u4e00-\u9fa5A-Za-z0-9/（）()、]{0,18})"), r"客户最终确认后填写具体\1"),
        (re.compile(r"待补充事项"), "客户最终确认事项"),
        (re.compile(r"“待补充”标记"), "“客户确认后填写”标记"),
    ]
    for pattern, replacement in plain_patterns:
        result, count = pattern.subn(replacement, result)
        replacements += count
    return result, replacements
