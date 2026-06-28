from backend.services.formal_placeholders import (
    apply_confirmed_values_to_export_text,
    collect_formal_placeholders,
    finalize_confirmed_formal_export_text,
    replace_formal_placeholders_with_confirmation_text,
)


def test_collect_formal_placeholders_covers_legacy_plain_tokens():
    text = "\n".join([
        "报告编号：待补充",
        "检测设备：【设备型号待补充】",
        "参数客户确认后填写（技术参数见原图，此处待补充）",
        "请在最终提交前清理本章节中用于占位的“待补充”标记。",
    ])

    placeholders = collect_formal_placeholders(text)

    assert "：待补充" in placeholders
    assert "【设备型号待补充】" in placeholders
    assert "此处待补充" in placeholders
    assert len(placeholders) == 3


def test_replace_formal_placeholders_removes_visible_pending_tokens():
    text = "\n".join([
        "报告编号：待补充",
        "检测设备：【设备型号待补充】",
        "参数客户确认后填写（技术参数见原图，此处待补充）",
        "**待补充事项**",
    ])

    rewritten, count = replace_formal_placeholders_with_confirmation_text(text)

    assert count == 4
    assert "待补充" not in rewritten
    assert "客户最终确认后填写" in rewritten
    assert "待客户最终确认" in rewritten
    assert "客户最终确认事项" in rewritten


def test_apply_confirmed_values_to_export_text_renders_legacy_customer_placeholders():
    text = "\n".join([
        "投标报价为客户最终确认后填写（投标总价），税率客户确认后填写（税率）。",
        "交货期为合同签订后客户确认后填写日内，质保期客户确认后填写个月。",
        "授权代表：客户最终确认后填写（授权代表姓名）；日期：客户确认后填写（签署日期）。",
        "设备型号：客户最终确认后填写（具体型号）。",
    ])
    values = {
        "total_bid_price": "¥1,286,000.00",
        "tax_rate": "13%",
        "delivery_period": "自合同签订之日起30日内完成供货",
        "warranty_period": "货物验收合格后12个月",
        "authorized_representative": "李明",
        "signature_date": "2026年06月26日",
    }

    rewritten, count = apply_confirmed_values_to_export_text(text, values)

    assert count >= 7
    assert "客户最终确认后填写" not in rewritten
    assert "客户确认后填写" not in rewritten
    assert "¥1,286,000.00" in rewritten
    assert "13%" in rewritten
    assert "合同签订后30日内" in rewritten
    assert "质保期12个月" in rewritten
    assert "授权代表：李明" in rewritten
    assert "日期：2026年06月26日" in rewritten
    assert "设备型号：按招标文件、本投标文件及附件资料执行" in rewritten


def test_finalize_confirmed_formal_export_text_removes_workflow_language_without_fake_values():
    text = "投标保证金：【待补充：人工复核】\n授权代表：客户确认后填写（授权代表姓名）\n本节用户确认后提交。"
    rewritten, count = finalize_confirmed_formal_export_text(text, {"authorized_representative": "晁坤琳"})

    assert count >= 3
    assert "晁坤琳" in rewritten
    for forbidden in ("待补充", "人工复核", "客户确认后填写", "用户确认", "占位符"):
        assert forbidden not in rewritten
    assert "1280000" not in rewritten
    assert "内部测试模拟" not in rewritten


def test_finalize_confirmed_formal_export_text_normalizes_supply_bid_terms_only_for_supply_context():
    text = "本施工组织设计及技术方案依据招标文件编制。专职项目经理负责关键工序及施工方案。"
    rewritten, count = finalize_confirmed_formal_export_text(text, {"package_name": "电缆保护管CPVC包1"})

    assert count >= 3
    assert "施工组织" not in rewritten
    assert "施工方案" not in rewritten
    assert "项目经理" not in rewritten
    assert "供货组织方案" in rewritten
    assert "项目负责人" in rewritten

    construction_text, construction_count = finalize_confirmed_formal_export_text(text, {"package_name": "土建施工项目"})
    assert construction_count == 0
    assert "施工组织设计" in construction_text
