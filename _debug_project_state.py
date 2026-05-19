"""Check the actual database state of the problem project."""
from dotenv import load_dotenv
load_dotenv()

from backend.db.supabase_repo import (
    get_project_interpretation,
    list_bid_sections,
    get_supabase_client,
)

project_id = "fc5e18a2-613a-433a-944f-e58ed781a3c3"

print(f"=== 项目 {project_id} 的真实状态 ===\n")

client = get_supabase_client()

# 1. bid_projects
proj = client.table("bid_projects").select("*").eq("id", project_id).execute()
print(f"bid_projects: {'存在' if proj.data else '不存在'}")
if proj.data:
    print(f"  project_name: {proj.data[0].get('project_name')}")

# 2. bid_analysis
ana = client.table("bid_analysis").select("*").eq("project_id", project_id).execute()
print(f"\nbid_analysis 行数: {len(ana.data)}")
if ana.data:
    pm = ana.data[0].get("project_meta") or {}
    print(f"  project_meta 有字段: {list(pm.keys())}")
    print(f"  has bid_outline: {'bid_outline' in pm}")
    print(f"  has ai_report: {'ai_report' in pm}")
    if "bid_outline" in pm:
        bo = pm["bid_outline"]
        print(f"  bid_outline chapters: {len(bo.get('chapters', []))}")

# 3. bid_sections
sections = list_bid_sections(project_id)
print(f"\nbid_sections 条数: {len(sections)}")
if sections:
    with_content = [s for s in sections if (s.get('content') or '').strip()]
    print(f"  其中有正文的: {len(with_content)}")
    print(f"  前 5 条：")
    for s in sections[:5]:
        print(f"    [{s.get('order_index')}] L{s.get('level')} {s.get('title')}")

# 4. 模拟 get_project_interpretation 返回
print("\n=== 模拟 get_project_interpretation() 返回 ===")
payload = get_project_interpretation(project_id)
print(f"  project: {'有' if payload.get('project') else '无'}")
print(f"  analysis: {'有' if payload.get('analysis') else '无'}")
print(f"  sections: {len(payload.get('sections') or [])} 条")
print(f"  documentChunks: {len(payload.get('documentChunks') or [])} 条")
