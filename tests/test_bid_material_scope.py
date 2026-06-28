from backend.services.bid_material_scope import (
    filter_sections_by_material_scope,
    material_scope_from_context,
    prune_outline_by_material_scope,
)


def test_material_scope_filters_out_non_package_material_sections():
    scope = material_scope_from_context({
        "confirmed_values": {
            "package_name": "电缆保护管CPVC、电缆保护管MPP包1",
            "material_category": "电缆保护管CPVC、电缆保护管MPP",
        }
    })
    sections = [
        {"id": "root", "title": "投标保证保险", "order_index": 1},
        {"id": "cpvc", "title": "投标保证保险（电缆保护管 CPVC）", "order_index": 2},
        {"id": "nhap", "title": "投标保证保险（电缆保护管 NHAP）", "order_index": 3},
        {"id": "nhap-child", "parent_id": "nhap", "title": "保险购买凭证", "order_index": 4},
        {"id": "mpp", "title": "投标保证保险（电缆保护管 MPP）", "order_index": 5},
    ]

    filtered = filter_sections_by_material_scope(sections, scope)
    titles = [item["title"] for item in filtered]

    assert scope == {"CPVC", "MPP"}
    assert "投标保证保险（电缆保护管 NHAP）" not in titles
    assert "保险购买凭证" not in titles
    assert "投标保证保险（电缆保护管 CPVC）" in titles
    assert "投标保证保险（电缆保护管 MPP）" in titles


def test_prune_outline_by_material_scope_removes_non_package_nodes():
    outline = {
        "chapters": [
            {"title": "商务响应文件", "children": [
                {"title": "保险购买凭证-电缆保护管 CPVC"},
                {"title": "保险购买凭证-电缆保护管 NHAP"},
            ]}
        ]
    }

    pruned = prune_outline_by_material_scope(outline, {"CPVC", "MPP"})
    children = pruned["chapters"][0]["children"]

    assert [item["title"] for item in children] == ["保险购买凭证-电缆保护管 CPVC"]
