from backend.ai.section_writer import compact_formal_placeholders, strip_generated_section_heading_noise


def test_compact_formal_placeholders_collapses_generic_repetition():
    content = "\n".join(
        [
            "| 序号 | 附件 | 页码 |",
            "| --- | --- | --- |",
            "| 1 | 营业执照 | 【待补充】 |",
            "| 2 | 认证证书 | 【待补充】 |",
            "| 3 | 授权文件 | 【待补充】 |",
            "| 4 | 业绩证明 | 【待补充】 |",
        ]
    )

    rewritten, report = compact_formal_placeholders({"title": "附件清单及页码索引"}, content)

    assert report["compacted"] is True
    assert report["before_placeholders"] == 4
    assert report["placeholders"] == 1
    assert "【待补充：附件页码索引待最终目录页码生成后填写】" in rewritten
    assert rewritten.count("客户确认后填写") == 3


def test_compact_formal_placeholders_keeps_specific_confirmations():
    content = "\n".join(
        [
            "项目：【待补充：包号/包名称】",
            "金额：【待补充：金额】",
            "日期：【待补充：签署日期】",
            "代表：【待补充：授权代表姓名】",
            "复核：【待补充：人工复核】",
        ]
    )

    rewritten, report = compact_formal_placeholders({"title": "投标保证金及基本账户资料"}, content)

    assert report["placeholders"] == 3
    assert "客户确认后填写（授权代表姓名）" in rewritten
    assert "客户确认后填写" in rewritten


def test_strip_generated_section_heading_noise_removes_duplicate_heading_and_normalizes_brackets():
    content = "\n".join(
        [
            "## 技术评分支撑材料",
            "",
            "【5.1 概述】",
            "本章旨在响应技术评分要求。",
            "",
            "【5.2 技术方案与产品性能响应】",
            "投标人按招标文件要求提供电缆保护管产品。",
        ]
    )

    cleaned, report = strip_generated_section_heading_noise(content, {"title": "技术评分支撑材料"})

    assert "## 技术评分支撑材料" not in cleaned
    assert "【5.1 概述】" not in cleaned
    assert "5.1 概述" in cleaned
    assert "5.2 技术方案与产品性能响应" in cleaned
    assert report["heading_noise_removed"] == 1
    assert report["heading_brackets_normalized"] == 2
