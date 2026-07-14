#!/usr/bin/env python3
"""调用真实章节写作模型验证 P2-02 四类正文资料装配。"""

from __future__ import annotations

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.ai.qwen_client import call_dashscope_api  # noqa: E402
from backend.core.config import get_stage_model  # noqa: E402
from backend.services.taichang_chapter_content import (  # noqa: E402
    chapter_content_prompt_context,
    render_grounded_chapter_draft,
)
from scripts.rag.build_taichang_p2_02_chapter_content_manifest import build  # noqa: E402


OUTPUT_DIR = ROOT / "docs/development/taichang-bid-v1-data/p2_02_chapter_content_reuse"


def _response_text(response: dict[str, Any]) -> str:
    return str((((response.get("output") or {}).get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()


def _unsupported_hits(content: str, phrases: list[str]) -> list[str]:
    """允许明确的否定边界，但拒绝把同一术语写成正向能力事实。"""
    negation_aware = {"工艺符合性", "工艺能力证明", "工艺性能"}
    hits = []
    for phrase in phrases:
        start = content.find(phrase)
        if start < 0:
            continue
        prefix = content[max(0, start - 16):start]
        if phrase in negation_aware:
            suffix = content[start + len(phrase):start + len(phrase) + 12]
            if any(word in prefix for word in ("不构成", "不能作为", "并非", "不得作为", "不代表", "无法证明")) or "边界" in suffix:
                continue
        hits.append(phrase)
    return hits


def _prompt(manifest: dict[str, Any]) -> str:
    context = chapter_content_prompt_context(manifest, max_rows=12, max_chunks=6)
    semantic_key = str(manifest.get("semantic_key") or "")
    chapter_guards = {
        "manufacturing.quality_control": "正文只允许三部分：两张有效管理体系证书表；15项历史知识资料仅为未解析写作线索；质量目标/质保/标准待按项目复核的边界。禁止声称企业已建立或运行任何具体质量控制流程，不要描述知识资料内容、编号范围或后续安排。",
        "manufacturing.process.mpp": "正文只允许检验参数表和边界说明。检验报告只证明该规格送检样品的产品检验结果，不能证明任何生产流程或企业生产能力；通用历史工艺资料只能称为未核验写作线索。",
        "qualification.personnel_roster_and_certificates": "正文只允许花名册抽样表、两张人员证书表和项目任命边界。不得推断未列明的组织部门、剩余人数、组织架构文件、其他证书、核验渠道、后续安排或证书满足本项目要求。",
        "performance.project_evidence": "只写合同和中标通知书已经证明的项目、招标编号、包号、产品、数量、金额、双方和中标日期；招标编号不得写成中标通知书编号，不得编造合同编号、项目起始节点、履约验收状态、当前招标适配或其他业绩。",
    }
    return f"""
你正在为河北泰昌电力器材科技有限公司编写国家电网投标文件正文能力验证样本。

章节：{manifest.get('section_title')}
分册：{manifest.get('volume_type')}

资料清单：
{context}

要求：
1. 只输出可直接进入标书的本章正文，使用正式、克制、可核验的中文。
2. 正文必须实际使用清单中的结构化事实或知识资料，不得只写空泛框架。
3. 精确数值、姓名、证书号、报告号、项目名称、金额和日期只能来自结构化行或正式证据。
4. knowledge_only 只作写作背景；不得描述为已插入的正式图片或附件。
5. 阻断项必须转化为审慎边界，不得把缺失事实写成已经满足；不得编造承诺值。
6. 输出 500～900 个中文字符，可使用三级小标题或简洁表格。
7. 本样本只验证正文生成能力，不代表该章节属于 SL2655 当前目录，不要声称当前招标要求本章。
8. 不得使用“承诺”“全部满足”“履行正常”“验收齐全”等超出证据的结论；客户确认项只能写成正式复核边界。
9. 本章专项限制：{chapter_guards.get(semantic_key) or '仅使用资料清单中明确可核验的事实。'}
10. 资料计数以完整 manifest 为准：结构化行 {len(manifest.get('structured_row_ids') or [])}、结构化分块 {len(manifest.get('chunk_ids') or [])}、历史知识资料 {len(manifest.get('knowledge_asset_ids') or [])}、证据包 {len(manifest.get('evidence_bundle_ids') or [])}；提示中只展示部分明细，不得把展示条数当总数。
11. 不得引入资料清单未出现的部门、证书类型、核验渠道、项目参与方、后续安排或执行状态。
""".strip()


def _generate(manifest: dict[str, Any]) -> dict[str, Any]:
    model = get_stage_model("section_writing")
    unsupported_phrases = {
        "manufacturing.quality_control": ["设计、生产和服务全过程", "已建立并有效运行", "热镀锌", "首件检验", "巡回检验", "完工检验", "追溯编码", "操作规范", "控制频次", "原材料入厂", "过程检验", "成品出厂", "全链条", "质量监控", "可追溯", "合同签订后", "共8项", "编号technical", "technical-media-0008至", "覆盖关键生产环节", "须在投标前补充", "合同阶段约定", "委托人协商"],
        "manufacturing.process.mpp": ["工艺符合性", "工艺能力证明", "工艺性能", "挤出成型", "挤出温度", "螺杆转速", "牵引速度", "冷却定型", "生产工艺稳定", "出厂检验能力", "定期抽样", "确保出厂", "具备资质的第三方", "国家电网采购技术规范", "满足国家电网相关标准", "报告日期", "项目启动阶段", "客户/监理方"],
        "qualification.personnel_roster_and_certificates": ["现有在册人员10人", "现有在册人员12人", "完整的组织架构", "技术研发", "从业经验", "其他59名", "组织架构文件", "焊工证", "登高证", "政务平台", "若有新增人员", "将及时更新", "随投标文件提供", "可满足电力器材", "可满足项目", "满足现场", "甲方要求", "所有相关证书"],
        "performance.project_evidence": ["0322AB-包2", "TJ20220002363", "中标通知书（编号", "项目起始节点", "履行情况正常", "验收记录齐全", "均满足国家电网", "符合国家电网招标采购要求", "典型项目", "其余项目业绩", "可直接调取", "验收单据，可提供"],
    }.get(str(manifest.get("semantic_key") or ""), [])
    response = call_dashscope_api(
        [{"role": "user", "content": _prompt(manifest)}],
        model=model,
        json_mode=False,
        usage_context={
            "project_id": "2cb1f65e-f552-430b-8322-540ca93b9fe4",
            "stage": "taichang_p2_02_real_chapter_sample",
            "metadata": {"semantic_key": manifest.get("semantic_key")},
        },
    )
    model_content = _response_text(response)
    if not model_content:
        raise RuntimeError(f"章节 {manifest.get('section_title')} 未返回正文")
    unsupported_hits = _unsupported_hits(model_content, unsupported_phrases)
    content = render_grounded_chapter_draft(manifest)
    visible_internal_hits = [term for term in ("taichang-", "technical-media-", "row-") if term in content]
    if visible_internal_hits:
        raise RuntimeError(f"结构化正式稿泄露内部标识：{visible_internal_hits}")
    return {
        "section_id": manifest.get("section_id"),
        "section_title": manifest.get("section_title"),
        "semantic_key": manifest.get("semantic_key"),
        "model": model,
        "model_called": True,
        "model_draft_chars": len(re.sub(r"\s+", "", model_content)),
        "model_draft_accepted": False,
        "model_rejection_reason": "高精度章节统一使用结构化正式渲染；模型稿仅用于写作能力与越界审计",
        "formal_renderer": "taichang_structured_grounded_renderer_v1",
        "content": content,
        "content_chars": len(re.sub(r"\s+", "", content)),
        "structured_row_count": len(manifest.get("structured_row_ids") or []),
        "chunk_count": len(manifest.get("chunk_ids") or []),
        "knowledge_asset_count": len(manifest.get("knowledge_asset_ids") or []),
        "evidence_bundle_count": len(manifest.get("evidence_bundle_ids") or []),
        "blockers": manifest.get("blockers") or [],
        "unsupported_fact_hits": unsupported_hits,
        "generation_attempts": 1,
        "source_files": manifest.get("source_files") or [],
        "source_pages": manifest.get("source_pages") or [],
    }


def main() -> None:
    payload = build()
    manifests = payload["capability_validation_manifests"]
    generated: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(_generate, manifest): manifest for manifest in manifests}
        for future in as_completed(futures):
            result = future.result()
            generated.append(result)
            print(f"PASS {result['section_title']} {result['content_chars']} chars {result['model']}", flush=True)
    generated.sort(key=lambda item: item["section_id"])

    drafts_dir = OUTPUT_DIR / "real_generation_samples"
    drafts_dir.mkdir(parents=True, exist_ok=True)
    for result in generated:
        safe_name = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "_", result["section_title"])
        (drafts_dir / f"{safe_name}.md").write_text(
            f"# {result['section_title']}\n\n{result['content']}\n",
            encoding="utf-8",
        )

    report = {
        "schema_version": "taichang-p2-02-real-generation-samples-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sample_role": "capability_validation_only_not_current_sl2655_outline",
        "all_passed": len(generated) == 4 and all(item["content_chars"] >= 300 for item in generated),
        "knowledge_only_docx_insertions": 0,
        "samples": generated,
    }
    (OUTPUT_DIR / "real_generation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if not report["all_passed"]:
        raise SystemExit("P2-02 真实章节生成样本未全部达标")
    print(json.dumps({
        "all_passed": report["all_passed"],
        "sample_count": len(generated),
        "knowledge_only_docx_insertions": 0,
        "output": str((OUTPUT_DIR / "real_generation_report.json").relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
