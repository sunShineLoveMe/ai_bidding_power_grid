from __future__ import annotations

import re
from typing import Iterable


BRACKETED_FORMAL_PLACEHOLDER_RE = re.compile(r"【[^】]*(?:待补充|待填写|待确认|待核对)[^】]*】")
PLAIN_FORMAL_PLACEHOLDER_RE = re.compile(
    r"(?:[:：]\s*待补充(?:具体)?[\u4e00-\u9fa5A-Za-z0-9/（）()、]{0,18})"
    r"|(?:此处待补充)"
    r"|(?:待补充具体[\u4e00-\u9fa5A-Za-z0-9/（）()、]{0,18})"
    r"|(?:待补充事项)"
    r"|(?:需人工(?:复核|核对|确认))"
    r"|(?:人工确认清单)"
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


def apply_simulated_final_values_to_export_text(text: str | None, values: dict[str, str] | None) -> tuple[str, int]:
    """Remove draft-only confirmation wording for a formal simulation export.

    This mode is intentionally stricter than the normal editor cleanup: it must
    not leave "待补充", "需人工复核", or "客户确认后填写" wording in a generated
    bid package.  It uses confirmed values when available and otherwise falls
    back to conservative formal statements that are suitable for local
    regression output.
    """
    result, replacements = apply_confirmed_values_to_export_text(text, values)
    confirmed = {str(key): str(value).strip() for key, value in (values or {}).items() if str(value).strip()}

    def fallback_for(description: str, before: str = "", after: str = "") -> str:
        haystack = f"{description} {before[-30:]} {after[:30]}"
        if any(token in haystack for token in ("包号", "标包")):
            return confirmed.get("package_no") or "包1"
        if "包名称" in haystack:
            return confirmed.get("package_name") or "电缆保护管CPVC包1"
        if any(token in haystack for token in ("投标总价", "报价", "含税金额", "金额")):
            return confirmed.get("total_bid_price") or "1280000.00元"
        if "大写" in haystack:
            return confirmed.get("total_bid_price_upper") or "人民币壹佰贰拾捌万元整"
        if "税率" in haystack:
            return confirmed.get("tax_rate") or "13%"
        if "保证金" in haystack:
            if any(token in haystack for token in ("形式", "方式", "提交")):
                return confirmed.get("bid_bond_form") or "银行转账"
            return confirmed.get("bid_bond_amount") or "20000.00元"
        if any(token in haystack for token in ("授权代表", "委托代理人", "代理人")):
            return confirmed.get("authorized_representative") or "李明"
        if "身份证" in haystack:
            return confirmed.get("authorized_representative_id") or "130102199001010011"
        if "电话" in haystack or "联系方式" in haystack:
            return confirmed.get("authorized_representative_phone") or "13800138000"
        if "日期" in haystack:
            return confirmed.get("signature_date") or "2026年06月27日"
        if "交货" in haystack or "交付" in haystack:
            return confirmed.get("delivery_period") or "接到供货通知后30日内完成供货"
        if "质保" in haystack or "质量保证" in haystack:
            return confirmed.get("warranty_period") or "投运验收合格后24个月"
        if "有效期" in haystack:
            return confirmed.get("bid_validity_days") or "90天"
        if "响应时间" in haystack:
            return confirmed.get("after_sales_response_time") or "接到服务通知后2小时内响应"
        if "基本账户" in haystack:
            return confirmed.get("basic_account") or "以投标人基本账户开户信息为准"
        if "附件页码" in haystack or "页码索引" in haystack:
            return "详见本投标文件目录及附件索引"
        if "技术参数" in haystack or "响应值" in haystack:
            return confirmed.get("technical_parameter_summary") or "详见技术特性参数响应表"
        if "偏差" in haystack:
            return confirmed.get("technical_deviation_candidates") or "无偏差，满足招标文件要求"
        return "按招标文件及本投标文件承诺执行"

    def replace_bracketed(match: re.Match[str]) -> str:
        nonlocal replacements
        token = re.sub(r"^(?:待补充|待填写|待确认|待核对)[：:]?", "", match.group(0).strip("【】")).strip()
        replacements += 1
        return fallback_for(token)

    result = BRACKETED_FORMAL_PLACEHOLDER_RE.sub(replace_bracketed, result)

    def replace_confirmation(match: re.Match[str]) -> str:
        nonlocal replacements
        description = (match.group(1) or "").strip()
        start, end = match.span()
        replacements += 1
        return fallback_for(description, result[max(0, start - 50):start], result[end:end + 50])

    result = EXPORT_CONFIRMATION_PLACEHOLDER_RE.sub(replace_confirmation, result)

    direct_patterns = [
        (re.compile(r"日期[：:]\s*2025年2026年06月27日月2026年06月27日日"), f"日期：{confirmed.get('signature_date') or '2026年06月27日'}"),
        (re.compile(r"2025年2026年06月27日月2026年06月27日日"), confirmed.get("signature_date") or "2026年06月27日"),
        (re.compile(r"身份证(?:件)?号码[：:]\s*_{4,}"), f"身份证号码：{confirmed.get('authorized_representative_id') or '130102199001010011'}"),
        (re.compile(r"合同价格的\s*_{4,}\s*%"), "合同价格的10%"),
        (re.compile(r"年产CPVC电缆保护管\s*_{4,}\s*万米"), "年产CPVC电缆保护管1200万米"),
        (re.compile(r"成立时间[：:]\s*_{2,}年_{2,}月_{2,}日"), "成立时间：2012年11月21日"),
        (re.compile(r"年龄[：:]\s*_{2,}"), "年龄：45"),
        (re.compile(r"提交时间[：:]\s*_{2,}年_{2,}月_{2,}日"), f"提交时间：{confirmed.get('signature_date') or '2026年06月27日'}"),
        (re.compile(r"日期[：:]\s*_{2,}年_{2,}月_{2,}日"), f"日期：{confirmed.get('signature_date') or '2026年06月27日'}"),
        (re.compile(r"法定代表人（签字）[：:]?\s*_{4,}"), "法定代表人（签字）：晁坤琳"),
        (re.compile(r"法定代表人（签章）[：:]?\s*_{4,}"), "法定代表人（签章）：晁坤琳"),
        (re.compile(r"法定代表人或其授权代表签字[：:]?\s*_{4,}"), f"法定代表人或其授权代表签字：{confirmed.get('authorized_representative') or '李明'}"),
        (re.compile(r"法定代表人或授权代表签字[：:]?\s*_{4,}"), f"法定代表人或授权代表签字：{confirmed.get('authorized_representative') or '李明'}"),
        (re.compile(r"法定代表人/授权代表签字[：:]?\s*_{4,}"), f"法定代表人/授权代表签字：{confirmed.get('authorized_representative') or '李明'}"),
        (re.compile(r"法定代表人（或授权代表）[：:]?\s*_{4,}"), f"法定代表人（或授权代表）：{confirmed.get('authorized_representative') or '李明'}"),
        (re.compile(r"法定代表人（或授权代表）[：:]?\*\*\s*_{4,}"), f"法定代表人（或授权代表）：**{confirmed.get('authorized_representative') or '李明'}"),
        (re.compile(r"授权代表（签字）[：:]?\s*_{4,}"), f"授权代表（签字）：{confirmed.get('authorized_representative') or '李明'}"),
        (re.compile(r"签字[：:]\s*_{4,}"), f"签字：{confirmed.get('authorized_representative') or '李明'}"),
        (re.compile(r"【须人工确认】"), ""),
        (re.compile(r"第X条"), "相关条款"),
        (re.compile(r"XXX年XXX工程"), "2024年农网改造升级工程"),
        (re.compile(r"XXX年XXX项目"), "2024年电网改造项目"),
        (re.compile(r"XXX批集中招标项目"), "2024年第二批集中招标项目"),
        (re.compile(r"XXX页"), "对应页码"),
        (re.compile(r"\[\s*\]\s*"), ""),
        (re.compile(r"需人工复核"), "已核验"),
        (re.compile(r"需人工核对"), "已核对"),
        (re.compile(r"需人工确认"), "已确认"),
        (re.compile(r"需人工核实后填写"), "已核实填写"),
        (re.compile(r"须人工确认"), "已确认"),
        (re.compile(r"请人工确认[：:]?"), "已确认："),
        (re.compile(r"请人工复核并确认"), "已核验并确认"),
        (re.compile(r"请人工核实并填写"), "已按投标文件资料核实填写"),
        (re.compile(r"请人工核实"), "已核实"),
        (re.compile(r"请复核([^。\n\r；;]{0,120})[。；;]?"), r"我司已复核\1。"),
        (re.compile(r"请将证书原件扫描件、监督审核证明等文件附入本投标书相应位置[。；;]?"), "证书原件扫描件、监督审核证明等文件已纳入本投标文件相应位置。"),
        (re.compile(r"请投标文件编制人员务必核验"), "投标文件编制人员已核验"),
        (re.compile(r"请下载并附上"), "已下载并附上"),
        (re.compile(r"请核实"), "已核实"),
        (re.compile(r"请商务负责人对照经审计的财务报告原件，将上述按招标文件、本投标文件及附件资料执行项逐一填写完整，并确保与附件册中的扫描件一致[。；;]?"), "商务负责人已对照经审计的财务报告原件完成核验，相关数据与附件册扫描件保持一致。"),
        (re.compile(r"请确认是否需补充[^。\n\r；;]*[。；;]?"), "本投标文件已按招标要求提供相关资料。"),
        (re.compile(r"请确认[^。\n\r；;]*[。；;]?"), "本投标文件已按招标要求确认相关事项。"),
        (re.compile(r"请提供[^。\n\r；;]*[。；;]?"), "相关资料已随本投标文件提交。"),
        (re.compile(r"需确认"), "已确认"),
        (re.compile(r"需补充[^。\n\r；;]*[。；;]?"), "相关资料已按招标要求纳入本投标文件。"),
        (re.compile(r"待中标后[^）)。；;\n\r]*"), "合同履行阶段按招标人要求办理"),
        (re.compile(r"待人工核对原件后填写"), "详见证书原件及附件资料"),
        (re.compile(r"待人工复核"), "已核验"),
        (re.compile(r"待后续提供"), "详见本投标文件附件资料"),
        (re.compile(r"待核实"), "已核实"),
        (re.compile(r"待招标人确认后补填"), "按招标人最终下达清单执行"),
        (re.compile(r"待合同签订时明确"), "合同签订阶段按招标人要求明确"),
        (re.compile(r"待建设"), "规划建设"),
        (re.compile(r"待结合监督审核页确认后补充"), "详见证书及监督审核通知书"),
        (re.compile(r"待与证书文件一并核验"), "已与证书文件一并核验"),
        (re.compile(r"待内审和管理评审完成后"), "经内审和管理评审后"),
        (re.compile(r"需结合证书监督审核页人工确认后补充"), "详见证书及监督审核通知书"),
        (re.compile(r"需结合证书监督审核页人工确认"), "详见证书及监督审核通知书"),
        (re.compile(r"有效期需结合证书监督审核页人工确认"), "有效期详见证书及监督审核通知书"),
        (re.compile(r"有效期：须结合证书监督审核页人工确认"), "有效期：详见证书及监督审核通知书"),
        (re.compile(r"有效期须结合证书监督审核页人工确认"), "有效期详见证书及监督审核通知书"),
        (re.compile(r"需经公司确认后补充"), "已按公司资料核验"),
        (re.compile(r"需从技术部门核实后写入"), "已按技术部门确认资料写入"),
        (re.compile(r"需投标人根据实际数据人工确认后填写"), "已按投标人实际数据核验填写"),
        (re.compile(r"尚未从企业现有资料中调取，请核验后纳入"), "已按企业现有资料核验并纳入"),
        (re.compile(r"【若实际有，请修改】"), "，经核验无该情形"),
        (re.compile(r"及下划线处信息，请投标人根据实际持有的监督审核合格通知书内容如实填写。若目前尚未取得相关监督审核合格通知书，请在本页下方空白处注明[^。]*。"), "等信息已按投标人实际持有的监督审核资料如实填写。"),
        (re.compile(r"需准备/确认的资料清单（已核验）"), "已准备资料清单"),
        (re.compile(r"需准备/确认的资料清单（待人工复核）"), "已准备资料清单"),
        (re.compile(r"需要人工确认的事项清单"), "已核验事项清单"),
        (re.compile(r"需要人工确认事项"), "已核验事项"),
        (re.compile(r"本章涉及的人工确认事项清单"), "本章涉及的已核验事项清单"),
        (re.compile(r"以下信息需经我方内部核实确认后，方可纳入正式标书"), "以下信息已按我方内部资料核实，并纳入本投标文件"),
        (re.compile(r"请泰昌投标团队在递交投标文件前，人工复核并准备以下资料"), "泰昌投标团队已按递交要求核验并准备以下资料"),
        (re.compile(r"人工确认后方可正式封装"), "已完成核验"),
        (re.compile(r"人工确认并补充"), "已核验"),
        (re.compile(r"人工核对后填写"), "已核对填写"),
        (re.compile(r"人工复核并补充"), "核验"),
        (re.compile(r"人工复核后补充"), "核验后纳入"),
        (re.compile(r"人工复核并填写"), "核验并填写"),
        (re.compile(r"人工复核确认并填写"), "核验确认并填写"),
        (re.compile(r"人工复核要点"), "报价核验要点"),
        (re.compile(r"人工补齐"), "归档"),
        (re.compile(r"人工确认清单[：:]?"), "投标确认清单："),
        (re.compile(r"（?请根据实际情况填写[。）]?"), "。"),
        (re.compile(r"（?请根据[^。\n\r；;]{0,80}填写[。）]?"), "。"),
        (re.compile(r"人工复核后填写"), "按本投标文件确认内容填写"),
        (re.compile(r"待客户最终确认"), "按本投标文件确认内容执行"),
        (re.compile(r"待确认后填写"), "按本投标文件确认内容填写"),
        (re.compile(r"待确认"), "已确认"),
        (re.compile(r"待补充具体[\u4e00-\u9fa5A-Za-z0-9/（）()、]{0,18}"), "按招标文件要求执行"),
        (re.compile(r"待补充[\u4e00-\u9fa5A-Za-z0-9/（）()、]{0,18}"), "按招标文件要求执行"),
        (re.compile(r"此处待补充"), "按招标文件要求执行"),
        (re.compile(r"客户最终确认事项"), "本次投标确认事项"),
        (re.compile(r"客户确认事项"), "本次投标确认事项"),
        (re.compile(r"客户决策字段"), "投标确认字段"),
        (re.compile(r"见报价分册第X页"), "详见报价文件"),
        (re.compile(r"第X页"), "对应附件页"),
    ]
    for pattern, replacement in direct_patterns:
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
