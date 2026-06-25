from backend.services.formal_placeholders import (
    collect_formal_placeholders,
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
