#!/usr/bin/env python3
"""Rebuild the Taichang bid with verified facts and supply-only boundaries."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = PROJECT_ROOT / "docs/development/runs"
STAGING_DIR = PROJECT_ROOT / "parsed_outputs/power_grid_customer_corpus/customer_taichang_supplement_20260611/staging/taichang_bid_fact_pack"
PROJECT_ID = "4bc3ee73-9ec5-4184-aafd-eaede9f90798"
PRODUCT_ROWS_PATH = PROJECT_ROOT / "parsed_outputs/power_grid_customer_corpus/customer_liaoning_taichang_20260606_p0/staging/taichang_product_parameters/taichang_product_parameter_rows.json"
PERFORMANCE_ROWS_PATH = PROJECT_ROOT / "parsed_outputs/power_grid_customer_corpus/customer_taichang_supplement_20260611/staging/taichang_project_performance/taichang_project_performance_rows.json"

sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

TITLE_REPLACEMENTS = {
    "工程概况": "项目概况",
    "施工部署与资源配置": "供货部署与资源配置",
    "发包人要求响应": "招标人要求响应",
    "承包人建议书": "投标人建议书",
    "施工组织设计/实施方案": "供货组织设计/实施方案",
    "进度计划与节点控制": "供货进度计划与节点控制",
    "环保与文明施工措施": "环保与文明生产措施",
    "报价文件及工程量清单": "报价文件及货物清单",
}
TEXT_REPLACEMENTS = {
    "工程量清单": "货物清单",
    "发包人": "招标人",
    "承包人": "投标人",
    "施工组织": "供货组织",
    "施工部署": "供货部署",
    "工程概况": "项目概况",
    "施工进度": "供货进度",
    "文明施工": "文明生产与绿色交付",
}
FORBIDDEN_TOPICS = [
    "水利施工",
    "桩基",
    "防渗墙",
    "BIM",
    "建造师",
    "安全生产许可证",
    "电力工程施工总承包",
    "输变电工程专业承包",
    "承装（修、试）电力设施许可证",
]
ALLOWED_PLACEHOLDERS = [
    "本次实际投标的分标、包号、包名称和物资范围",
    "最终投标总价、分项单价、数量和税率",
    "交货期、备货周期、质保期和投标有效期",
    "本项目投标保证金和履约保证金信息",
    "授权代理人、签署人、投标日期、签章和装订页码",
    "本项目履约负责人及各岗位的最终指派",
    "售后响应、到场时间、服务网点和量化产能承诺",
]
REQUIRED_SCOPE = (
    "本项目按河北泰昌电力器材科技有限公司电缆保护管 MPP/CPVC 物资供货标书编写，"
    "范围包括生产、检验、包装、运输、交付和售后服务；除招标文件明确要求外，不扩写工程施工、安装总承包或水利业务。"
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _sha(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def _normalized_text(value: Any) -> Any:
    if isinstance(value, str):
        result = value
        for old, new in TEXT_REPLACEMENTS.items():
            result = result.replace(old, new)
        return result
    if isinstance(value, list):
        return [_normalized_text(item) for item in value]
    return value


def _normalized_title(title: str) -> str:
    result = title
    for old, new in TITLE_REPLACEMENTS.items():
        result = result.replace(old, new)
    return result


def _build_fact_pack() -> dict[str, Any]:
    product_rows = _read_json(PRODUCT_ROWS_PATH)
    performance_rows = _read_json(PERFORMANCE_ROWS_PATH)
    report_rows: dict[str, list[dict[str, Any]]] = {}
    for row in product_rows:
        report_rows.setdefault(row["product_family"], []).append(row)

    def parameter(product: str, name: str) -> dict[str, Any]:
        row = next(item for item in report_rows[product] if item.get("parameter_name") == name)
        return {
            "parameter": name,
            "standard_requirement": row.get("standard_requirement"),
            "inspection_result": row.get("inspection_result"),
            "unit": row.get("unit"),
        }

    supply_contract = next(row for row in performance_rows if row.get("evidence_type") == "supply_contract")
    fact_pack = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "enterprise": {
            "full_name": "河北泰昌电力器材科技有限公司",
            "unified_social_credit_code": "91130607056539515C",
            "legal_representative": "晁坤琳",
            "company_type": "有限责任公司（自然人投资或控股）",
            "registered_capital": "10000万元人民币",
            "established_date": "2012年11月14日",
            "registered_address": "河北省保定市满城区陉阳驿村",
            "evidence": "泰昌营业执照副本及企业信用报告",
        },
        "certifications": [
            {
                "name": "质量管理体系认证证书",
                "certificate_no": "06925Q10172R4",
                "standard": "GB/T 19001-2016/ISO 9001:2015",
                "valid_until": "2028年2月15日",
                "issuer": "凯新认证（北京）有限公司",
            },
            {
                "name": "环境管理体系认证证书",
                "certificate_no": "17424E20980R0M",
                "standard": "GB/T 24001-2016/ISO 14001:2015",
                "valid_until": "需结合证书监督审核页人工确认",
                "issuer": "华信创认证",
            },
            {
                "name": "职业健康安全管理体系认证证书",
                "certificate_no": "626023S10219R0",
                "standard": "GB/T 45001-2020/ISO 45001:2018",
                "valid_until": "2026年6月18日",
                "issuer": "凯新认证（北京）有限公司",
            },
        ],
        "personnel_evidence": {
            "roster_count": 65,
            "candidates": [
                "晁坤琳：董事长、试验员",
                "杨贺：总经理",
                "晁猛：项目经理（厂长）",
                "陈仙瑞：高压试验员",
                "赵称心：技术总监",
                "王强、陈国华、黄文清、林乌金：技术售后",
                "赵伟、刘合钦、杨华、巩超、于诗兰、莫文清：质检员",
            ],
            "boundary": "花名册证明人员在册情况，但本项目具体岗位指派仍须客户确认。",
        },
        "product_inspection": {
            "CPVC电缆保护管": {
                "report_no": report_rows["CPVC电缆保护管"][0]["report_no"],
                "specification_model": report_rows["CPVC电缆保护管"][0]["specification_model"],
                "parameters": [parameter("CPVC电缆保护管", "尺寸-平均内径"), parameter("CPVC电缆保护管", "尺寸-壁厚")],
            },
            "MPP电缆保护管": {
                "report_no": report_rows["MPP电缆保护管"][0]["report_no"],
                "specification_model": report_rows["MPP电缆保护管"][0]["specification_model"],
                "parameters": [parameter("MPP电缆保护管", "环刚度")],
            },
        },
        "project_performance": {
            "project_name": supply_contract["project_name"],
            "tender_no": supply_contract["tender_no"],
            "package_no": supply_contract["package_no"],
            "product_summary": supply_contract["product_summary"],
            "total_quantity": f"{supply_contract['total_quantity']:,.0f}米",
            "amount_tax_included": f"{supply_contract['amount_tax_included_yuan']:,.2f}元",
            "buyer": supply_contract["buyer"],
            "award_date": supply_contract["award_date"],
            "contract_no": supply_contract["contract_no_buyer"],
            "contract_sign_date": "原件为空，不得推断",
        },
        "equipment_evidence": [
            "CPVC生产线、MPP生产线现场资料",
            "微机控制电子万能试验机",
            "热变形/维卡软化点温度测定仪",
            "电子天平、锤击试验装置、熔体流动速率仪、电子拉力试验机",
            "设备型号、数量、精度和检定周期仍须按设备台账人工复核",
        ],
        "known_not_applicable": FORBIDDEN_TOPICS,
        "unresolved_for_current_tender": ALLOWED_PLACEHOLDERS,
        "source_files": [
            "泰昌营业执照副本及企业信用报告",
            "质量/环境/职业健康安全管理体系认证证书",
            "公司人员花名册及人员证书",
            "CPVC/MPP电缆保护管检验报告",
            "TJ20220002363合同协议书及0322AB中标通知书",
            "生产线、生产设备和试验设备原始资料",
        ],
    }
    assert fact_pack["enterprise"]["unified_social_credit_code"] == "91130607056539515C"
    assert fact_pack["product_inspection"]["CPVC电缆保护管"]["report_no"] == "2024100312005501713"
    assert fact_pack["project_performance"]["tender_no"] == "0322AB"
    return fact_pack


def _fact_context(facts: dict[str, Any]) -> str:
    enterprise = facts["enterprise"]
    rows = [
        f"- 企业：{enterprise['full_name']}；统一社会信用代码：{enterprise['unified_social_credit_code']}；法定代表人：{enterprise['legal_representative']}。",
        f"- 企业类型：{enterprise['company_type']}；注册资本：{enterprise['registered_capital']}；成立日期：{enterprise['established_date']}；注册地址：{enterprise['registered_address']}。",
    ]
    for cert in facts["certifications"]:
        rows.append(
            f"- {cert['name']}：编号 {cert['certificate_no']}，标准 {cert['standard']}，有效期 {cert['valid_until']}，机构 {cert['issuer']}。"
        )
    for product, report in facts["product_inspection"].items():
        params = "；".join(
            f"{item['parameter']} {item['inspection_result']}{item['unit'] or ''}（要求 {item['standard_requirement']}）"
            for item in report["parameters"]
        )
        rows.append(f"- {product}检验报告：报告编号 {report['report_no']}，型号 {report['specification_model']}；{params}。")
    performance = facts["project_performance"]
    rows.append(
        f"- 真实业绩：{performance['project_name']}，招标编号 {performance['tender_no']}，{performance['package_no']}，"
        f"产品 {performance['product_summary']}，数量 {performance['total_quantity']}，含税金额 {performance['amount_tax_included']}，"
        f"买方 {performance['buyer']}，中标日期 {performance['award_date']}，合同编号 {performance['contract_no']}；合同签署日期原件为空。"
    )
    rows.append("- 人员证据：" + "；".join(facts["personnel_evidence"]["candidates"]) + "。具体项目岗位不得自动指定。")
    rows.append("- 设备证据：" + "；".join(facts["equipment_evidence"]) + "。")
    return "\n".join(rows)


def _extract_response_text(response: dict[str, Any]) -> str:
    return str(response["output"]["choices"][0]["message"]["content"] or "").strip()


def _repair_content(project_id: str, section: dict[str, Any], content: str, factual_context: str) -> str:
    from backend.ai.qwen_client import call_dashscope_api
    from backend.core.config import get_stage_model

    prompt = f"""
你是投标文件终审编辑。请重写下面章节正文，只输出完整正文，不输出解释或 Markdown 一级标题。

章节：{section['title']}
业务边界：{REQUIRED_SCOPE}

已核验事实：
{factual_context}

硬性要求：
1. 删除以下不适用内容及相关资质要求：{'、'.join(FORBIDDEN_TOPICS)}。
2. 已核验事实必须直接填写，不能再次写成待补充。
3. 仅这些本项目未确认事项允许待补充：{'、'.join(ALLOWED_PLACEHOLDERS)}。
4. 不得编造供应商、品牌、人员项目任命、产能、金额、日期或承诺时限。
5. 保持电缆保护管 MPP/CPVC 生产供货、检验、包装运输、交付和售后服务口径。

待修订正文：
{content}
""".strip()
    response = call_dashscope_api(
        [{"role": "user", "content": prompt}],
        model=get_stage_model("section_writing"),
        json_mode=False,
        usage_context={"project_id": project_id, "section_id": section["id"], "stage": "taichang_fact_grounded_repair"},
    )
    return _extract_response_text(response)


def _write_summary(path: Path, report: dict[str, Any]) -> None:
    lines = [
        f"# 泰昌企业事实约束全量重写记录 - {report['run_id']}",
        "",
        f"- 状态：{report['status']}",
        f"- 模型：`{report['model']}`",
        f"- 目标/成功/失败：{report['target_sections']} / {report['success_count']} / {report['failure_count']}",
        f"- 标题修正：{report['renamed_count']}",
        f"- 修复后二次 DeepSeek 清理：{report['repair_count']}",
        f"- 占位符：{report['before_placeholders']} -> {report['after_placeholders']}",
        f"- 禁止主题命中：{report['forbidden_hit_count']}",
        f"- 耗时：{report['elapsed_seconds']} 秒",
        f"- 事实包：`{report['fact_pack_path']}`",
        f"- 旧正文备份：`{report['backup_path']}`",
        "",
        "## 失败章节",
        "",
    ]
    lines.extend([f"- {item['order_index']} {item['title']}：{item['error']}" for item in report["failures"]] or ["- 无"])
    lines.extend(["", "## 章节结果", "", "| 序号 | 章节 | 状态 | 占位 | 禁止主题 |", "| ---: | --- | --- | ---: | --- |"])
    for item in report["sections"]:
        forbidden_text = "、".join(item.get("forbidden_hits") or []) or "-"
        lines.append(
            f"| {item['order_index']} | {item['title']} | {item['status']} | {item.get('placeholders', 0)} | "
            f"{forbidden_text} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", default=PROJECT_ID)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    os.environ["APP_AUTH_ENABLED"] = "false"
    os.environ["APP_LOGIN_ENABLED"] = "false"
    os.environ.setdefault("APP_ENV", "testing")
    if os.getenv("AI_PROVIDER") != "deepseek" or not os.getenv("DEEPSEEK_API_KEY"):
        raise RuntimeError("This run requires AI_PROVIDER=deepseek and DEEPSEEK_API_KEY")

    import main as flask_main
    from backend.core.config import get_stage_model
    from backend.db.supabase_repo import get_supabase_client, list_bid_sections, update_bid_section_content
    from backend.services.section_generation import generate_and_save_bid_section

    started = time.time()
    facts = _build_fact_pack()
    fact_pack_path = STAGING_DIR / f"{args.run_id}_fact_pack.json"
    _write_json(fact_pack_path, facts)
    factual_context = _fact_context(facts)
    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    repair_count = 0
    renamed_count = 0

    with flask_main.app.app_context():
        sections = list_bid_sections(args.project_id)
        if args.limit:
            sections = sections[: args.limit]
        backup = [{**row, "content_sha256": _sha(str(row.get("content") or ""))} for row in sections]
        backup_path = RUNS_DIR / f"{args.run_id}_before_sections_backup.json"
        _write_json(backup_path, backup)
        before_placeholders = sum(str(row.get("content") or "").count("【待补充") for row in sections)
        client = get_supabase_client()

        for index, original in enumerate(sections, 1):
            section = dict(original)
            old_title = str(section.get("title") or "")
            section["title"] = _normalized_title(old_title)
            section["purpose"] = _normalized_text(section.get("purpose"))
            for field in ("response_points", "mapped_requirements", "mapped_scoring_items", "mapped_risks", "required_materials", "writing_notes"):
                section[field] = _normalized_text(section.get(field) or [])
            if section["title"] != old_title:
                renamed_count += 1
            metadata = dict(section.get("metadata") or {})
            options = dict(metadata.get("generation_options") or {})
            options.update({
                "force_fresh": True,
                "disable_continuation": True,
                "skip_length_supplement": True,
                "run_id": args.run_id,
                "factual_context": factual_context,
                "required_scope": REQUIRED_SCOPE,
                "forbidden_topics": FORBIDDEN_TOPICS,
                "allowed_placeholders": ALLOWED_PLACEHOLDERS,
                "generated_by": "scripts/rag/regenerate_taichang_fact_grounded_bid.py",
            })
            metadata.update({
                "generation_options": options,
                "generation_status": "regenerating",
                "writing_status": "regenerating",
                "fact_grounding_run_id": args.run_id,
                "fact_pack_path": str(fact_pack_path.relative_to(PROJECT_ROOT)),
            })
            section["metadata"] = metadata
            update_payload = {
                "title": section["title"],
                "purpose": section.get("purpose"),
                "response_points": section.get("response_points"),
                "mapped_requirements": section.get("mapped_requirements"),
                "mapped_scoring_items": section.get("mapped_scoring_items"),
                "mapped_risks": section.get("mapped_risks"),
                "required_materials": section.get("required_materials"),
                "writing_notes": section.get("writing_notes"),
                "metadata": metadata,
                "content": "",
                "status": "regenerating",
            }
            client.table("bid_sections").update(update_payload).eq("id", section["id"]).eq("project_id", args.project_id).execute()
            section["content"] = ""
            section["status"] = "regenerating"
            print(json.dumps({"event": "section_start", "index": index, "total": len(sections), "title": section["title"]}, ensure_ascii=False), flush=True)
            try:
                summary = generate_and_save_bid_section(args.project_id, section, with_images=False)
                row = client.table("bid_sections").select("content").eq("id", section["id"]).limit(1).execute().data[0]
                content = str(row.get("content") or "")
                forbidden_hits = [term for term in FORBIDDEN_TOPICS if term in content]
                if forbidden_hits:
                    repaired = _repair_content(args.project_id, section, content, factual_context)
                    content = f"## {section['title']}\n\n{repaired.strip()}"
                    update_bid_section_content(args.project_id, section["id"], content, "generated", section, metadata_patch={"fact_grounding_repaired": True})
                    repair_count += 1
                    forbidden_hits = [term for term in FORBIDDEN_TOPICS if term in content]
                result = {
                    "order_index": section.get("order_index"),
                    "title": section["title"],
                    "status": "generated" if not forbidden_hits else "needs_review",
                    "placeholders": content.count("【待补充"),
                    "forbidden_hits": forbidden_hits,
                    **summary,
                }
                results.append(result)
                print(json.dumps({"event": "section_done", **result}, ensure_ascii=False), flush=True)
            except Exception as exc:
                client.table("bid_sections").update({
                    "title": original.get("title"),
                    "purpose": original.get("purpose"),
                    "content": original.get("content"),
                    "metadata": original.get("metadata"),
                    "status": original.get("status"),
                }).eq("id", original["id"]).eq("project_id", args.project_id).execute()
                failure = {"order_index": section.get("order_index"), "title": section["title"], "error": str(exc)}
                failures.append(failure)
                results.append({**failure, "status": "failed", "placeholders": 0, "forbidden_hits": []})
                print(json.dumps({"event": "section_failed", **failure}, ensure_ascii=False), flush=True)

        final_sections = list_bid_sections(args.project_id)
    after_placeholders = sum(str(row.get("content") or "").count("【待补充") for row in final_sections)
    forbidden_hit_count = sum(len(item.get("forbidden_hits") or []) for item in results)
    report = {
        "run_id": args.run_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "project_id": args.project_id,
        "model": get_stage_model("section_writing"),
        "status": "PASS" if not failures and not forbidden_hit_count else "FAIL",
        "target_sections": len(sections),
        "success_count": sum(item["status"] == "generated" for item in results),
        "failure_count": len(failures),
        "renamed_count": renamed_count,
        "repair_count": repair_count,
        "before_placeholders": before_placeholders,
        "after_placeholders": after_placeholders,
        "forbidden_hit_count": forbidden_hit_count,
        "elapsed_seconds": round(time.time() - started, 2),
        "fact_pack_path": str(fact_pack_path.relative_to(PROJECT_ROOT)),
        "backup_path": str(backup_path.relative_to(PROJECT_ROOT)),
        "sections": results,
        "failures": failures,
    }
    report_json = RUNS_DIR / f"{args.run_id}.json"
    report_md = RUNS_DIR / f"{args.run_id}.md"
    _write_json(report_json, report)
    _write_summary(report_md, report)
    print(json.dumps({"report": str(report_md.relative_to(PROJECT_ROOT)), "status": report["status"]}, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
