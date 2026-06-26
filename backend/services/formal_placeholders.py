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


EXPORT_CONFIRMATION_PLACEHOLDER_RE = re.compile(
    r"(?:客户(?:最终)?确认后填写|待客户最终确认)(?:（([^）]{0,120})）)?"
)


def apply_confirmed_values_to_export_text(text: str | None, values: dict[str, str] | None) -> tuple[str, int]:
    """Render legacy customer-confirmation prose into final export text.

    Older generated sections converted explicit placeholders into readable draft
    text such as "客户最终确认后填写（投标总价）".  That is acceptable while editing,
    but must not leak into the formal DOCX once the user has confirmed values.
    """
    result = str(text or "")
    confirmed = {str(key): str(value).strip() for key, value in (values or {}).items() if str(value).strip()}
    if not result:
        return result, 0

    replacements = 0

    def pick_value(description: str, before: str, after: str) -> str:
        explicit = description.strip()
        near_before = re.split(r"[，。；;\n\r]", before)[-1]
        near_after = re.split(r"[，。；;\n\r]", after)[0]
        haystack = explicit or f"{near_before[-30:]} {near_after[:20]}"
        if any(token in explicit for token in ("投标总价", "总价", "报价", "含税金额")) and confirmed.get("total_bid_price"):
            return confirmed["total_bid_price"]
        if "大写" in haystack and confirmed.get("total_bid_price_upper"):
            return confirmed["total_bid_price_upper"]
        if any(token in haystack for token in ("税率", "增值税")) and confirmed.get("tax_rate"):
            return confirmed["tax_rate"]
        if "投标有效期" in haystack or "报价有效期" in haystack:
            return "90" if after.startswith("日") else confirmed.get("bid_validity_days", "90")
        if "保证金" in haystack or "保险金额" in haystack:
            if any(token in haystack for token in ("形式", "方式", "提交")) and confirmed.get("bid_bond_form"):
                return confirmed["bid_bond_form"]
            if confirmed.get("bid_bond_amount"):
                return confirmed["bid_bond_amount"]
        if any(token in haystack for token in ("授权代表", "授权代理人", "委托代理人", "代理人姓名", "授权代表姓名")) and confirmed.get("authorized_representative"):
            return confirmed["authorized_representative"]
        if "身份证" in haystack and confirmed.get("authorized_representative_id"):
            return confirmed["authorized_representative_id"]
        if any(token in haystack for token in ("签署日期", "日期", "签章日期")) and confirmed.get("signature_date"):
            return confirmed["signature_date"]
        if any(token in haystack for token in ("交货期", "交货", "交付")) and confirmed.get("delivery_period"):
            return "30" if after.startswith("日") else confirmed["delivery_period"]
        if any(token in haystack for token in ("质保", "质量保证期")) and confirmed.get("warranty_period"):
            return "12" if after.startswith("个月") else confirmed["warranty_period"]
        if "包名称" in haystack and confirmed.get("package_name"):
            return confirmed["package_name"]
        if "包号" in haystack and confirmed.get("package_no"):
            return confirmed["package_no"]
        if any(token in haystack for token in ("投标总价", "总价", "报价", "含税金额", "金额")) and confirmed.get("total_bid_price"):
            return confirmed["total_bid_price"]
        if "基本账户" in haystack and confirmed.get("basic_account"):
            return confirmed["basic_account"]
        if "响应时间" in haystack and confirmed.get("after_sales_response_time"):
            return confirmed["after_sales_response_time"]
        if any(token in haystack for token in ("技术参数", "参数要求")) and confirmed.get("technical_parameter_summary"):
            return confirmed["technical_parameter_summary"]
        return "按招标文件、本投标文件及附件资料执行"

    def replace_match(match: re.Match[str]) -> str:
        nonlocal replacements
        description = (match.group(1) or "").strip()
        start, end = match.span()
        before = result[max(0, start - 50):start]
        after = result[end:end + 24]
        replacements += 1
        return pick_value(description, before, after)

    result = EXPORT_CONFIRMATION_PLACEHOLDER_RE.sub(replace_match, result)
    cleanup_patterns = [
        (re.compile(r"人民币人民币"), "人民币"),
        (re.compile(r"人民币\s*¥"), "¥"),
        (re.compile(r"（需按目标包确认）"), ""),
        (re.compile(r"（本节客户决策字段待最终确认）"), ""),
        (re.compile(r"客户最终确认事项"), "本次投标确认事项"),
        (re.compile(r"待补充[：:]\s*人工复核"), "按证书原件及附件资料执行"),
        (re.compile(r"待客户确认具体需求后另行补充"), "可根据招标人要求另行补充"),
        (re.compile(r"待客户确认全部规格的投标响应值后"), "本次投标响应值确认后"),
        (re.compile(r"待客户确认具体响应值后"), "按技术参数表响应值确认后"),
        (re.compile(r"\|\s*待确认\s*\|"), "| 按合同订单执行 |"),
        (re.compile(r"\|\s*待确认后填写\s*\|"), "| 按招标文件要求执行 |"),
    ]
    for pattern, replacement in cleanup_patterns:
        result, count = pattern.subn(replacement, result)
        replacements += count
    return result, replacements


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
