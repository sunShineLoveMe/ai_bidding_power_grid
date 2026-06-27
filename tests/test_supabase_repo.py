from unittest.mock import MagicMock, patch

from backend.db.supabase_repo import update_bid_analysis_project_meta


def test_update_bid_analysis_project_meta_reselects_when_update_returns_empty_data():
    project_id = "4390e1ff-2d62-4230-802a-b5dc829145f2"
    project_meta = {"ai_report": {"executive_summary": ["摘要"]}}

    update_query = MagicMock()
    update_query.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    select_query = MagicMock()
    select_query.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "analysis-1", "project_id": project_id, "project_meta": project_meta}]
    )

    client = MagicMock()
    client.table.side_effect = [update_query, select_query]

    with patch("backend.db.supabase_repo.get_supabase_client", return_value=client):
        result = update_bid_analysis_project_meta(project_id, project_meta)

    assert result == {"id": "analysis-1", "project_id": project_id, "project_meta": project_meta}
    update_query.update.assert_called_once_with({"project_meta": project_meta})
    select_query.select.assert_called_once_with("id,project_id,project_meta")


def test_update_bid_analysis_project_meta_returns_none_when_reselect_does_not_match():
    project_id = "4390e1ff-2d62-4230-802a-b5dc829145f2"
    project_meta = {"ai_report": {"executive_summary": ["新摘要"]}}

    update_query = MagicMock()
    update_query.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    select_query = MagicMock()
    select_query.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "analysis-1", "project_id": project_id, "project_meta": {"ai_report": {"executive_summary": ["旧摘要"]}}}]
    )

    client = MagicMock()
    client.table.side_effect = [update_query, select_query]

    with patch("backend.db.supabase_repo.get_supabase_client", return_value=client):
        result = update_bid_analysis_project_meta(project_id, project_meta)

    assert result is None
