#!/usr/bin/env python3
"""构建泰昌 P1-04 章节—事实—证据语义映射。

本脚本只读复用 P1-01 知识资产、P1-02 文件级证据包、P1-03 安全业务台账及
泰昌原始检验报告参数，不写数据库、不复制资产。映射使用语义章节键和标题关键词，
由后续项目动态骨架进行匹配，禁止绑定历史标书章节号。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "docs/development/taichang-bid-v1-data"
DEFAULT_OUTPUT_DIR = DATA_ROOT / "p1_04_chapter_evidence_mapping"
P1_01_ASSETS = DATA_ROOT / "p1_01_ingestion/taichang_historical_bid_asset_ingestion.json"
P1_02_BUNDLES = DATA_ROOT / "p1_02_evidence_bundles/taichang_evidence_bundles.json"
P1_03_LEDGER = DATA_ROOT / "p1_03_business_ledgers/taichang_p1_03_manifest.json"
PARAMETER_ROWS = (
    PROJECT_ROOT
    / "parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/"
    "staging/taichang_product_parameters/taichang_product_parameter_rows.json"
)
ENTERPRISE_FACT_SOURCE = "backend/rag/enterprise_facts.py"

ENTERPRISE = "河北泰昌电力器材科技有限公司"
STATUS_LABELS = {
    "existing": "已有资料",
    "partial": "部分可用",
    "missing_evidence": "缺原件",
    "manual_confirmation": "人工确认",
}


def _load_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _fact_ref(source: str, selector: dict[str, Any], usage: str) -> dict[str, Any]:
    return {"source": source, "selector": selector, "usage": usage}


def _chapter(
    *,
    mapping_id: str,
    volume: str,
    semantic_key: str,
    name: str,
    aliases: list[str],
    status: str,
    fact_refs: list[dict[str, Any]] | None = None,
    bundle_keys: list[str] | None = None,
    asset_selector: dict[str, Any] | None = None,
    blockers: list[str] | None = None,
    confirmations: list[str] | None = None,
    generation_policy: str = "仅在当前招标动态骨架命中后按来源引用，不复制资产记录。",
) -> dict[str, Any]:
    return {
        "mapping_id": mapping_id,
        "bid_volume": volume,
        "semantic_chapter_key": semantic_key,
        "chapter_display_name": name,
        "chapter_match": {
            "mode": "semantic_title_keywords",
            "aliases": aliases,
            "exclude_keywords": ["招标人", "其他投标人", "河北豪乾"],
            "fixed_chapter_number": None,
        },
        "material_status": status,
        "material_status_label": STATUS_LABELS[status],
        "existing_material": status == "existing",
        "fact_refs": fact_refs or [],
        "requested_evidence_business_keys": bundle_keys or [],
        "evidence_bundle_ids": [],
        "knowledge_asset_selector": asset_selector,
        "resolved_knowledge_asset_candidate_ids": [],
        "blockers": blockers or [],
        "customer_confirmation_fields": confirmations or [],
        "generation_policy": generation_policy,
        "source_boundary": {
            "enterprise_fact_owner": ENTERPRISE,
            "tender_requirement_role": "仅用于确定本项目要求、年度、评分项和格式，不作为泰昌企业事实",
            "reference_template_role": "仅参考写法和结构，不作为泰昌企业事实",
        },
    }


def _definitions() -> list[dict[str, Any]]:
    param_source = str(PARAMETER_ROWS.relative_to(PROJECT_ROOT))
    ledger_source = str(P1_03_LEDGER.relative_to(PROJECT_ROOT))
    asset_source = str(P1_01_ASSETS.relative_to(PROJECT_ROOT))
    return [
        _chapter(
            mapping_id="TECH-PARAM-CPVC",
            volume="technical",
            semantic_key="technical_characteristics.cpvc",
            name="CPVC技术特性参数表",
            aliases=["CPVC技术特性", "CPVC技术参数", "PVC-C技术参数", "CPVC技术响应"],
            status="existing",
            fact_refs=[_fact_ref(param_source, {"product_family": "CPVC电缆保护管", "report_no": "2024100312005501713"}, "逐行参数及来源页码")],
            bundle_keys=["report:2024100312005501713"],
        ),
        _chapter(
            mapping_id="TECH-PARAM-MPP",
            volume="technical",
            semantic_key="technical_characteristics.mpp",
            name="MPP技术特性参数表",
            aliases=["MPP技术特性", "MPP技术参数", "改性聚丙烯技术参数", "MPP技术响应"],
            status="existing",
            fact_refs=[_fact_ref(param_source, {"product_family": "MPP电缆保护管", "report_no": "2024100312005501712"}, "逐行参数及来源页码")],
            bundle_keys=["report:2024100312005501712"],
        ),
        _chapter(
            mapping_id="TECH-QUALITY-CONTROL",
            volume="technical",
            semantic_key="manufacturing.quality_control",
            name="产品制造质量控制",
            aliases=["产品制造质量控制", "质量管控体系", "工序质量控制", "制造质量保证"],
            status="partial",
            fact_refs=[_fact_ref(ledger_source, {"ledger_type": "management_certificate", "validity_status": "valid"}, "有效质量/环境体系事实")],
            bundle_keys=["management-system:quality", "management-system:environment"],
            asset_selector={
                "source": asset_source,
                "ready_for_database_ingestion": True,
                "evidence_types": ["production_capacity"],
                "source_group_keywords": ["工序控制点工艺文件"],
                "required_quality_tier": "knowledge_only",
                "formal_evidence": False,
            },
            blockers=["历史 Word 工艺资料仅为 knowledge_only，不能单独证明当前项目正式质量承诺。"],
            confirmations=["项目质量目标", "质量保证期", "当前招标适用标准"],
        ),
        _chapter(
            mapping_id="TECH-PROCESS-CPVC",
            volume="technical",
            semantic_key="manufacturing.process.cpvc",
            name="CPVC生产工艺",
            aliases=["CPVC生产工艺", "PVC-C工艺流程", "CPVC制造工艺"],
            status="partial",
            fact_refs=[_fact_ref(param_source, {"product_family": "CPVC电缆保护管"}, "检验结果仅用于验证成品特性")],
            bundle_keys=["report:2024100312005501713"],
            asset_selector={"source": asset_source, "ready_for_database_ingestion": True, "evidence_types": ["production_capacity"], "source_group_keywords": ["工序控制点工艺文件"], "required_quality_tier": "knowledge_only", "formal_evidence": False},
            blockers=["现有可入库历史工艺资料为电缆保护管通用资料，缺少经核验的 CPVC 专属完整工艺文件。"],
        ),
        _chapter(
            mapping_id="TECH-PROCESS-MPP",
            volume="technical",
            semantic_key="manufacturing.process.mpp",
            name="MPP生产工艺",
            aliases=["MPP生产工艺", "改性聚丙烯工艺流程", "MPP制造工艺"],
            status="partial",
            fact_refs=[_fact_ref(param_source, {"product_family": "MPP电缆保护管"}, "检验结果仅用于验证成品特性")],
            bundle_keys=["report:2024100312005501712"],
            asset_selector={"source": asset_source, "ready_for_database_ingestion": True, "evidence_types": ["production_capacity"], "source_group_keywords": ["工序控制点工艺文件"], "required_quality_tier": "knowledge_only", "formal_evidence": False},
            blockers=["现有可入库历史工艺资料为电缆保护管通用资料，缺少经核验的 MPP 专属完整工艺文件。"],
        ),
        _chapter(
            mapping_id="TECH-PROCESS-NHAP",
            volume="technical",
            semantic_key="manufacturing.process.nhap",
            name="N-HAP生产工艺",
            aliases=["N-HAP生产工艺", "涂塑钢制电缆导管工艺", "涂塑钢管制造工艺"],
            status="missing_evidence",
            fact_refs=[_fact_ref(ledger_source, {"business_key": "report:2024400312005505333"}, "仅作待补原件登记，不得生成正式参数或能力结论")],
            blockers=["仅有历史报告编号，无原始检验报告；不得生成正式参数或覆盖结论。", "缺少经核验的 N-HAP 专属工艺文件。"],
        ),
        _chapter(
            mapping_id="TECH-PROCESS-UPVC",
            volume="technical",
            semantic_key="manufacturing.process.upvc",
            name="UPVC生产工艺",
            aliases=["UPVC生产工艺", "硬聚氯乙烯电缆导管工艺", "UPVC制造工艺"],
            status="missing_evidence",
            fact_refs=[_fact_ref(ledger_source, {"business_key": "report:2025200312005503479"}, "仅作待补原件登记，不得生成正式参数或能力结论")],
            blockers=["仅有历史报告编号，无原始检验报告；不得生成正式参数或覆盖结论。", "缺少经核验的 UPVC 专属工艺文件。"],
        ),
        _chapter(
            mapping_id="TECH-TEST-EQUIPMENT",
            volume="technical",
            semantic_key="testing.equipment_and_calibration",
            name="试验检测设备及校准资料",
            aliases=["试验检测设备", "检测设备一览表", "计量校准", "检验设备"],
            status="partial",
            fact_refs=[_fact_ref(ledger_source, {"ledger_type": "equipment_calibration", "validity_status": "valid"}, "设备台账、校准编号、有效期和来源页")],
            bundle_keys=[
                "equipment:微机控制电子万能试验机", "equipment:热变形、维卡软化点温度测定仪", "equipment:熔体流动速率仪",
                "equipment:电子天平", "equipment:电子拉力试验机", "equipment:锤击试验装置",
            ],
            blockers=["证据包需按投标日复核校准有效期；不得随机抽取单页替代完整设备证据包。"],
        ),
        _chapter(
            mapping_id="TECH-INSPECTION-REPORTS",
            volume="technical",
            semantic_key="testing.inspection_reports",
            name="产品检验报告",
            aliases=["检验报告", "型式试验报告", "检测报告", "产品检验"],
            status="existing",
            fact_refs=[_fact_ref(ledger_source, {"ledger_type": "inspection_report_registry", "fact_status": "verified_existing_report"}, "报告登记、产品和规格")],
            bundle_keys=["report:2024100312005501712", "report:2024100312005501713"],
            generation_policy="只引用 CPVC/MPP 完整 evidence_bundle_id；N-HAP/UPVC 待补原件，不得随机插入单页。",
        ),
        _chapter(
            mapping_id="TECH-SERVICE-AFTERSALES",
            volume="technical",
            semantic_key="service.after_sales_and_quality_plan",
            name="技术服务、售后服务与质量方案",
            aliases=["技术服务", "售后服务", "质量保证方案", "服务承诺", "质量承诺"],
            status="partial",
            blockers=["尚无独立核验的泰昌技术服务/售后制度事实；P1-05 只能接入经批准的企业知识。", "交货响应、到场时限、质保期限、违约责任等承诺值必须以当前招标要求和客户确认为准。"],
            confirmations=["质保期限", "售后响应时限", "现场服务范围", "备品备件承诺", "违约责任"],
        ),
        _chapter(
            mapping_id="TECH-GREEN-LOW-CARBON",
            volume="technical",
            semantic_key="enterprise.green_low_carbon",
            name="绿色低碳与环境管理",
            aliases=["绿色低碳", "绿色工厂", "环境保护", "碳足迹", "绿色制造"],
            status="partial",
            fact_refs=[_fact_ref(ledger_source, {"ledger_type": "management_certificate", "business_key": "certificate:17424E20980R0M"}, "环境管理体系有效事实")],
            bundle_keys=["management-system:environment"],
            asset_selector={"source": asset_source, "ready_for_database_ingestion": True, "evidence_types": ["green_low_carbon"], "source_group_keywords": ["环境影响评估报告"], "required_quality_tier": "knowledge_only", "formal_evidence": False},
            blockers=["历史绿色低碳图片为 knowledge_only，正式评分材料须按当前评分项核验。"],
        ),
        _chapter(
            mapping_id="TECH-MANUFACTURING-CAPACITY",
            volume="technical",
            semantic_key="manufacturing.capacity",
            name="生产制造能力",
            aliases=["生产制造能力", "生产设备", "生产线", "厂房及生产环境"],
            status="partial",
            asset_selector={"source": asset_source, "ready_for_database_ingestion": True, "evidence_types": ["enterprise_evidence"], "source_group_keywords": ["生产制造环境", "试组装环境"], "required_quality_tier": "knowledge_only", "formal_evidence": False},
            blockers=["历史环境图片只作知识资料；正式配图必须另行通过 formal_bid_ready 门禁。"],
        ),
        _chapter(
            mapping_id="BUS-ENTERPRISE-PROFILE",
            volume="business",
            semantic_key="enterprise.basic_profile",
            name="企业基本情况",
            aliases=["企业基本情况", "投标人基本信息", "法人营业执照", "企业概况"],
            status="existing",
            fact_refs=[_fact_ref(ENTERPRISE_FACT_SOURCE, {"profile": "taichang_verified_enterprise_profile"}, "核验后的企业工商基础事实")],
            bundle_keys=["uscc:91130607056539515C"],
        ),
        _chapter(
            mapping_id="BUS-PREQUALIFICATION",
            volume="business",
            semantic_key="qualification.prequalification_result",
            name="资格预审结果",
            aliases=["资格预审", "资格预审结果通知书", "预审合格通知", "资格能力核实"],
            status="missing_evidence",
            blockers=["当前无独立资格预审结果通知书原件。", "适用批次、物料类别和有效范围必须从原件及当前招标要求确认。"],
            confirmations=["适用批次", "适用物料", "有效期"],
        ),
        _chapter(
            mapping_id="BUS-MANAGEMENT-CERTS",
            volume="business",
            semantic_key="qualification.management_system_certificates",
            name="管理体系认证证书",
            aliases=["管理体系认证", "质量体系证书", "环境体系证书", "职业健康安全体系"],
            status="partial",
            fact_refs=[_fact_ref(ledger_source, {"ledger_type": "management_certificate", "validity_status": "valid"}, "仅引用当前有效证书")],
            bundle_keys=["management-system:quality", "management-system:environment"],
            blockers=["职业健康安全管理体系认证证书已于 2026-06-18 到期，禁止进入正式材料。"],
        ),
        _chapter(
            mapping_id="BUS-FINANCIAL",
            volume="business",
            semantic_key="finance.audit_reports",
            name="财务状况与审计报告",
            aliases=["财务状况", "审计报告", "财务报表", "经审计财务资料"],
            status="partial",
            fact_refs=[_fact_ref(ledger_source, {"ledger_type": "audit_report"}, "按当前招标要求年度选择完整报告")],
            bundle_keys=["audit-year:2023", "audit-year:2024", "audit-year:2025"],
            blockers=["必须先解析当前招标要求年度；不得默认堆叠全部年度。", "2024 年审计报告编号未在原件封面确认，保持人工复核。"],
            confirmations=["当前招标要求的审计年度范围"],
        ),
        _chapter(
            mapping_id="BUS-PERFORMANCE",
            volume="business",
            semantic_key="performance.project_evidence",
            name="项目业绩",
            aliases=["项目业绩", "供货业绩", "合同业绩", "中标业绩"],
            status="existing",
            fact_refs=[_fact_ref("parsed_outputs/power_grid_customer_corpus/customer_taichang_supplement_20260611/staging/taichang_project_performance/taichang_project_performance_rows.json", {"project_id": "taichang-tianjin-2022-0322AB-package-2"}, "合同与中标通知书分别保留来源")],
            bundle_keys=["project:taichang-tianjin-2022-0322AB-package-2"],
            blockers=["合同签署日期原件为空，不得用中标时间或交货日期推断。"],
        ),
        _chapter(
            mapping_id="BUS-REVIEW-SUPPLEMENT",
            volume="business",
            semantic_key="qualification.review_supplement",
            name="评审补充材料",
            aliases=["评审补充材料", "评分证明材料", "综合实力证明", "技术商务评分"],
            status="partial",
            fact_refs=[_fact_ref(P1_02_BUNDLES.relative_to(PROJECT_ROOT).as_posix(), {"selection": "current_scoring_item_only"}, "按当前评分项选择证书或报告")],
            blockers=["未解析当前评分项前不得堆叠全部证书、报告或历史材料。", "知识产权资料无可信原件，不得生成相关得分证明。"],
            confirmations=["当前评分项", "对应证明材料要求", "材料有效期基准日"],
        ),
        _chapter(
            mapping_id="BUS-PERSONNEL",
            volume="business",
            semantic_key="qualification.personnel_roster_and_certificates",
            name="人员组织与人员证书",
            aliases=["人员组织", "人员配置", "人员花名册", "项目人员", "试验检测人员", "人员证书", "社保证明", "劳动合同"],
            status="existing",
            fact_refs=[
                _fact_ref(
                    ledger_source,
                    {"ledger_types": ["personnel_roster", "personnel_certificate", "personnel_summary"]},
                    "私有项目完整人员台账，包含姓名、岗位、学历、社保/劳动合同记录、证书编号、准操项目、有效期和来源页",
                )
            ],
            blockers=["正式投标时仍需按当前项目岗位要求、证书有效期和实际项目分工复核，不得把花名册自动等同于项目任命。"],
            generation_policy="可引用客户确认的完整人员台账；按当前招标岗位要求筛选，不复制人员记录，不虚构项目任命。",
        ),
        _chapter(
            mapping_id="BUS-AUTHORIZATION-SIGNATURE",
            volume="business",
            semantic_key="authorization.signature_and_seal",
            name="授权委托与签章",
            aliases=["授权委托书", "法定代表人授权", "签字盖章", "电子签章", "法定代表人身份证明"],
            status="manual_confirmation",
            blockers=["不得自动生成或执行签字盖章。", "授权范围、被授权人和签署日期必须由客户确认。"],
            confirmations=["法定代表人签署方式", "被授权人", "授权范围", "授权期限", "盖章位置", "签署日期"],
            generation_policy="可从完整人员台账预填候选人信息，但只生成模板占位和确认清单；不得自动签字、盖章。",
        ),
    ]


def _resolve(mapping: list[dict[str, Any]], bundles: list[dict[str, Any]], assets: list[dict[str, Any]]) -> None:
    bundle_by_key = {str(item.get("business_key")): item for item in bundles}
    for item in mapping:
        resolved_bundles = []
        for key in item.pop("requested_evidence_business_keys"):
            bundle = bundle_by_key.get(key)
            if bundle:
                resolved_bundles.append(bundle["evidence_bundle_id"])
        item["evidence_bundle_ids"] = sorted(set(resolved_bundles))

        selector = item.get("knowledge_asset_selector")
        if not selector:
            continue
        accepted = []
        for asset in assets:
            if asset.get("ready_for_database_ingestion") is not selector.get("ready_for_database_ingestion"):
                continue
            if asset.get("evidence_type") not in selector.get("evidence_types", []):
                continue
            group_title = str(asset.get("source_group_title") or "")
            if selector.get("source_group_keywords") and not any(word in group_title for word in selector["source_group_keywords"]):
                continue
            if asset.get("quality_tier_after_review") != selector.get("required_quality_tier"):
                continue
            accepted.append(str(asset.get("candidate_id")))
        item["resolved_knowledge_asset_candidate_ids"] = sorted(set(accepted))


def _validate(mapping: list[dict[str, Any]], bundle_ids: set[str]) -> None:
    ids = [item["mapping_id"] for item in mapping]
    if len(ids) != len(set(ids)):
        raise ValueError("mapping_id 重复")
    for item in mapping:
        if item["chapter_match"]["fixed_chapter_number"] is not None:
            raise ValueError(f"{item['mapping_id']} 绑定了固定章节号")
        if re.search(r"(^|\D)\d+(?:\.\d+)+(?=\D|$)", " ".join(item["chapter_match"]["aliases"])):
            raise ValueError(f"{item['mapping_id']} 的章节别名包含固定编号")
        unknown = set(item["evidence_bundle_ids"]) - bundle_ids
        if unknown:
            raise ValueError(f"{item['mapping_id']} 引用了不存在的证据包: {sorted(unknown)}")
        if item["existing_material"] and not (
            item["fact_refs"] or item["evidence_bundle_ids"] or item["resolved_knowledge_asset_candidate_ids"]
        ):
            raise ValueError(f"{item['mapping_id']} 标记已有资料但无法定位事实或证据")
        if item["material_status"] in {"missing_evidence", "manual_confirmation"} and item["existing_material"]:
            raise ValueError(f"{item['mapping_id']} 缺证/人工确认章节不得标记已有资料")

    serialized = json.dumps(mapping, ensure_ascii=False)
    if "management-system:ohs" in serialized or "taichang-evidence-68219d67c5feb3ed96a4" in serialized:
        raise ValueError("过期职业健康安全证书不得进入映射引用")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = ["映射ID", "语义章节键", "章节名称", "材料状态", "匹配别名", "事实引用数", "证据包数", "知识资产数", "证据包ID", "缺口或门禁", "客户确认项"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for item in rows:
            writer.writerow({
                "映射ID": item["mapping_id"],
                "语义章节键": item["semantic_chapter_key"],
                "章节名称": item["chapter_display_name"],
                "材料状态": item["material_status_label"],
                "匹配别名": "；".join(item["chapter_match"]["aliases"]),
                "事实引用数": len(item["fact_refs"]),
                "证据包数": len(item["evidence_bundle_ids"]),
                "知识资产数": len(item["resolved_knowledge_asset_candidate_ids"]),
                "证据包ID": "；".join(item["evidence_bundle_ids"]),
                "缺口或门禁": "；".join(item["blockers"]),
                "客户确认项": "；".join(item["customer_confirmation_fields"]),
            })


def _write_markdown(path: Path, title: str, rows: list[dict[str, Any]]) -> None:
    lines = [f"# {title}", "", "> 按当前项目动态骨架的标题语义匹配，不绑定历史章节号；同一资产只引用 ID，不复制记录。", "", "| 语义章节 | 状态 | 事实 | 证据包 | 知识资产 | 缺口/门禁 |", "| --- | --- | ---: | ---: | ---: | --- |"]
    for item in rows:
        blockers = "；".join(item["blockers"]) or "—"
        lines.append(f"| {item['chapter_display_name']} (`{item['semantic_chapter_key']}`) | {item['material_status_label']} | {len(item['fact_refs'])} | {len(item['evidence_bundle_ids'])} | {len(item['resolved_knowledge_asset_candidate_ids'])} | {blockers} |")
    lines.extend(["", "## 使用门禁", "", "- 只有“已有资料”可作为自动引用候选；“部分可用”仍需项目适配或有效期复核。", "- “缺原件”不得生成正式事实；“人工确认”只生成占位和确认清单。", "- 辽宁招标资料只定义本项目要求，河北豪乾只参考结构和写法。", "- 人员完整信息已获客户确认，可在泰昌私有项目中使用；项目任命、授权签字和盖章仍须按当前投标确认。", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def build(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    p1_01 = _load_json(P1_01_ASSETS, {"records": []})
    p1_02 = _load_json(P1_02_BUNDLES, {"bundles": []})
    p1_03 = _load_json(P1_03_LEDGER, {"summary": {}})
    parameter_rows = _load_json(PARAMETER_ROWS, [])
    bundles = p1_02.get("bundles", [])
    assets = p1_01.get("records", [])

    mapping = _definitions()
    _resolve(mapping, bundles, assets)
    _validate(mapping, {str(item.get("evidence_bundle_id")) for item in bundles})

    status_counts = Counter(item["material_status"] for item in mapping)
    volume_counts = Counter(item["bid_volume"] for item in mapping)
    payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "enterprise": ENTERPRISE,
        "mapping_mode": "semantic_dynamic_project_skeleton",
        "fixed_chapter_numbers": False,
        "project_skeleton_contract": "project_bid_skeleton.json",
        "historical_skeleton_role": "reference_only",
        "source_policy": {
            "enterprise_fact": "仅泰昌原始资料、核验事实、结构化台账和证据包",
            "tender_requirement": "仅用于当前项目要求、评分项、年度和格式",
            "reference_template": "仅用于结构和写法，不得生成泰昌事实",
            "asset_reuse": "只复用事实/证据/资产 ID，不创建副本",
            "private_project_personnel": "客户已确认可在私有项目内使用完整人员花名册和证书信息；保留来源、有效期和项目适用性校验",
        },
        "privacy_override_basis": "客户已确认该项目为私有项目，人员及证书完整数据可进入版本化台账、私有知识库问答和章节映射",
        "source_snapshot": {
            "p1_01_ready_knowledge_assets": sum(1 for item in assets if item.get("ready_for_database_ingestion") is True),
            "p1_02_evidence_bundles": len(bundles),
            "p1_03_business_ledger_rows": p1_03.get("summary", {}).get("business_ledger_rows", 0),
            "p1_03_published_rows": p1_03.get("summary", {}).get("published_rows", 0),
            "p1_03_personnel_rows": sum(
                int((p1_03.get("summary", {}).get("by_ledger_type") or {}).get(key, 0))
                for key in ("personnel_roster", "personnel_certificate")
            ),
            "p1_03_privacy_blocked_rows": p1_03.get("summary", {}).get("privacy_blocked_rows", 0),
            "verified_parameter_rows": len(parameter_rows),
        },
        "summary": {
            "mapping_count": len(mapping),
            "technical_mapping_count": volume_counts["technical"],
            "business_mapping_count": volume_counts["business"],
            "existing_count": status_counts["existing"],
            "partial_count": status_counts["partial"],
            "missing_evidence_count": status_counts["missing_evidence"],
            "manual_confirmation_count": status_counts["manual_confirmation"],
            "unique_evidence_bundle_count": len({bundle_id for item in mapping for bundle_id in item["evidence_bundle_ids"]}),
            "database_writes": 0,
            "asset_copies": 0,
        },
        "mappings": mapping,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "taichang_bid_evidence_mapping.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    technical = [item for item in mapping if item["bid_volume"] == "technical"]
    business = [item for item in mapping if item["bid_volume"] == "business"]
    _write_csv(output_dir / "泰昌资料—技术标章节映射表.csv", technical)
    _write_csv(output_dir / "泰昌资料—商务标章节映射表.csv", business)
    _write_markdown(output_dir / "泰昌资料—技术标章节映射表.md", "泰昌资料—技术标章节映射表", technical)
    _write_markdown(output_dir / "泰昌资料—商务标章节映射表.md", "泰昌资料—商务标章节映射表", business)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    payload = build(args.output_dir)
    print(json.dumps({"output_dir": str(args.output_dir), "summary": payload["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
