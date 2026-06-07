#!/usr/bin/env python3
"""Repair SGCC rule seed markdown files that were captured as portal navigation.

The original 25/26/27 seed files point to ``https://www.gov.cn/`` and contain
government portal navigation/news text instead of SGCC rule content. Until the
official rule originals are recollected, these files are replaced with explicit
retrieval seed summaries so they stop polluting RAG recall with unrelated web
chrome.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEED_ROOT = PROJECT_ROOT / "rag_seed" / "power_grid_resources"


REPAIRED_DOCS = {
    "02_policy_regulations/25_国家电网有限公司招标活动管理办法_f91d60bd.md": """# 国家电网有限公司招标活动管理办法

- 来源：国家电网有限公司/国家电子招标投标系统转载
- 原始链接：https://www.gov.cn/（原始采集链接失效，已确认误采为政府门户首页）
- 采集时间：2026-05-20T03:20:16.162103+00:00
- 修复时间：2026-06-07
- 资料状态：检索种子摘要，待替换为官方制度原文
- 引用边界：summary_only；仅用于召回定位和问答摘要，不得作为正式条款逐字引用

## 修复说明

本文件原正文为中国政府网首页导航、新闻和政务入口内容，未包含《国家电网有限公司招标活动管理办法》制度正文。为避免 RAG 召回继续被网页导航噪声污染，本次将文件重洗为国网招标活动管理相关的检索种子摘要。后续拿到官方制度原文后，应重新采集、替换本文件并复跑入库和召回评测。

## 适用主题

《国家电网有限公司招标活动管理办法》类资料通常用于说明国家电网系统内招标活动的组织管理、职责分工、招标方式选择、招标文件编制、资格审查、开标评标定标、异议投诉处理、合同签订和过程监督等要求。投标问答中遇到“国网招标活动管理办法”“招标方式”“公开招标”“邀请招标”“竞争性谈判”“询价采购”“单一来源采购”“评标定标”“异议投诉”等问题时，可优先召回本资料作为规则方向参考。

## 招标方式检索摘要

国家电网招标活动应根据采购项目属性、采购金额、技术复杂程度、供应商市场竞争状况和法律法规要求选择合适方式。依法必须招标或具备充分竞争条件的项目，通常优先采用公开招标；确因项目技术条件、供应商范围、时限或其他法定原因不适合公开招标的，可按程序采用邀请招标或非招标采购方式。常见非招标采购方式包括竞争性谈判、询价采购、单一来源采购等，具体适用条件应以招标采购文件和上位法律法规为准。

## 流程控制检索摘要

国网招标活动管理应关注采购计划、公告发布、招标文件发售、资格预审或资格后审、投标文件接收、开标、评标、推荐中标候选人、定标、中标通知、合同签订、档案归集等环节。评标过程应按招标文件规定的评审标准和方法执行，涉及否决投标、澄清说明、异常低价、围标串标、异议投诉等事项时，应结合招标投标法律法规、实施条例和采购文件要求综合判断。

## 问答使用提醒

- 本资料目前不是官方制度全文，不能直接生成“第几条”式精确引用。
- 正式投标文件或合规结论中，如需逐条引用，应等待客户或公开渠道补充官方原文。
- 如用户询问招标方式，本资料可回答规则方向：公开招标、邀请招标、竞争性谈判、询价采购、单一来源采购等方式需按项目适用条件和审批程序选择。
""",
    "02_policy_regulations/26_国家电网有限公司供应商管理办法_fa9308a9.md": """# 国家电网有限公司供应商管理办法

- 来源：国家电网有限公司/国家电子招标投标系统转载
- 原始链接：https://www.gov.cn/（原始采集链接失效，已确认误采为政府门户首页）
- 采集时间：2026-05-20T03:20:16.643797+00:00
- 修复时间：2026-06-07
- 资料状态：检索种子摘要，待替换为官方制度原文
- 引用边界：summary_only；仅用于召回定位和问答摘要，不得作为正式条款逐字引用

## 修复说明

本文件原正文为中国政府网首页导航、新闻和政务入口内容，未包含《国家电网有限公司供应商管理办法》制度正文。为避免 RAG 召回继续被网页导航噪声污染，本次将文件重洗为供应商管理和不良行为处理相关的检索种子摘要。后续拿到官方制度原文后，应重新采集、替换本文件并复跑入库和召回评测。

## 适用主题

《国家电网有限公司供应商管理办法》类资料通常用于说明国家电网供应商准入、信息维护、资质能力核实、履约评价、质量监督、信用评价、不良行为处理、整改闭环和供应商关系管理等要求。投标问答中遇到“供应商管理”“供应商不良行为”“暂停中标资格”“取消中标资格”“黑名单”“信用评价”“整改”“限制参与采购”等问题时，可优先召回本资料作为规则方向参考。

## 不良行为处理检索摘要

供应商存在质量问题、履约违约、虚假材料、串通投标、失信违法、拒不整改、产品缺陷、重大安全质量事件等不良行为时，国网采购活动通常会结合不良行为性质、影响范围、持续时间和整改情况采取相应处理措施。常见处理包括通报、暂停中标资格、限制参与特定品类或一定期限内采购、取消中标资格、列入不良行为记录或黑名单、要求整改并跟踪验证等。

## 投标前核查检索摘要

投标前应核查供应商及其外购外协供应商是否处于国家电网不良行为处理范围内，是否存在暂停中标资格、取消中标资格、永久取消应答资格、列入失信被执行人或严重违法失信名单等情形。核查渠道通常包括国家电网电子商务平台相关通报、采购公告要求的信用查询网站、国家企业信用信息公示系统、信用中国、中国裁判文书网等。实际投标应以招标文件或采购公告列明渠道为准。

## 问答使用提醒

- 本资料目前不是官方制度全文，不能直接生成“第几条”式精确引用。
- 正式投标文件或合规结论中，如需逐条引用，应等待客户或公开渠道补充官方原文。
- 如用户询问供应商不良行为处理，本资料可回答规则方向：按不良行为严重程度采取通报、暂停中标资格、限制参与采购、取消资格、列入不良行为记录和整改闭环等措施。
""",
    "02_policy_regulations/27_国家电网有限公司物资采购标准_011cf2f8.md": """# 国家电网有限公司物资采购标准

- 来源：国家电网有限公司物资部
- 原始链接：https://www.gov.cn/（原始采集链接失效，已确认误采为政府门户首页）
- 采集时间：2026-05-20T03:20:17.131893+00:00
- 修复时间：2026-06-07
- 资料状态：检索种子摘要，待替换为官方标准原文或采购标准目录
- 引用边界：summary_only；仅用于召回定位和问答摘要，不得作为正式条款逐字引用

## 修复说明

本文件原正文为中国政府网首页导航、新闻和政务入口内容，未包含国家电网物资采购标准正文。为避免 RAG 召回继续被网页导航噪声污染，本次将文件重洗为物资采购标准相关的检索种子摘要。后续拿到官方采购标准目录、技术规范书或标准原文后，应重新采集、替换本文件并复跑入库和召回评测。

## 适用主题

国家电网物资采购标准类资料通常用于说明物资分类、物料编码、采购标准编号、技术规范编码、供货范围、技术参数、试验检测、质量保证、交货验收、包装运输、售后服务、资质业绩和投标响应要求。投标问答中遇到“物资采购标准”“采购标准”“技术规范编码”“物料编码”“技术参数响应”“供货范围”“检验报告”“型式试验报告”等问题时，可优先召回本资料作为规则方向参考。

## 技术规范检索摘要

物资采购标准通常会把同类物资的技术要求、参数项目、试验项目、供货范围和验收要求标准化，便于招标文件、货物清单、技术规范书和投标响应保持一致。投标时应重点核对物料名称、规格型号、技术规范编码、物料编码、单位、数量、交货地点、保证值、项目需求值、偏差响应和检验报告覆盖范围。

## 资质业绩检索摘要

物资采购标准和具体采购文件可能同时要求供应商满足生产能力、检测能力、质量管理体系、同类产品供货业绩、权威机构试验报告、认证证书、售后服务能力等条件。对 CPVC 电缆保护管、MPP 电缆保护管、铁构件、接地铁等物资，应结合货物清单、专用技术规范和资质业绩表进行精确响应。

## 问答使用提醒

- 本资料目前不是官方标准全文，不能直接生成“第几条”式精确引用。
- 正式投标文件或合规结论中，如需逐条引用，应等待客户或公开渠道补充官方原文、采购标准目录或技术规范书。
- 如用户询问物资采购标准，本资料可回答规则方向：围绕物资分类、技术规范编码、物料编码、技术参数、试验报告、供货验收和资质业绩进行核查。
""",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repair_markdown_files() -> dict[str, str]:
    hashes: dict[str, str] = {}
    for relative, content in REPAIRED_DOCS.items():
        path = SEED_ROOT / relative
        path.write_text(content, encoding="utf-8")
        hashes[relative] = sha256_file(path)
    return hashes


def update_index_csv(hashes: dict[str, str]) -> None:
    index_path = SEED_ROOT / "index.csv"
    with index_path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
        fieldnames = f.readline()
    if not rows:
        raise RuntimeError("index.csv has no rows")
    columns = list(rows[0].keys())
    for row in rows:
        relative = row.get("file_path", "")
        if relative in hashes:
            row["sha256"] = hashes[relative]
            row["error"] = "原始采集为网页导航噪声，已重洗为检索种子摘要，待官方原文复核"
    with index_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def update_index_jsonl(hashes: dict[str, str]) -> None:
    index_path = SEED_ROOT / "index.jsonl"
    if not index_path.exists():
        return
    rows: list[dict[str, object]] = []
    with index_path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            relative = str(row.get("file_path", ""))
            if relative in hashes:
                row["sha256"] = hashes[relative]
                row["error"] = "原始采集为网页导航噪声，已重洗为检索种子摘要，待官方原文复核"
            rows.append(row)
    with index_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    hashes = repair_markdown_files()
    update_index_csv(hashes)
    update_index_jsonl(hashes)
    for relative, digest in hashes.items():
        print(f"repaired {relative} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
