import unittest
import tempfile
from pathlib import Path

from scripts.smoke_key_flow import SmokeContext, SmokeFailure, _parse_sse, _select_generation_sections, build_parser, check_ready, run_compliance_check, write_report


class _FakeResponse:
    status_code = 200
    text = ""

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.requested = []

    def get(self, url, timeout):
        self.requested.append((url, timeout))
        return _FakeResponse(self.payload)

class SmokeKeyFlowScriptTest(unittest.TestCase):
    def test_parse_sse_collects_named_events(self):
        raw = (
            'event: chapter\n'
            'data: {"title": "施工组织设计"}\n\n'
            'event: done\n'
            'data: {"outline": {"chapters": [{"title": "施工组织设计"}]}}\n\n'
        )

        events = _parse_sse(raw)

        self.assertEqual("chapter", events[0][0])
        self.assertEqual("施工组织设计", events[0][1]["title"])
        self.assertEqual("done", events[1][0])
        self.assertEqual("施工组织设计", events[1][1]["outline"]["chapters"][0]["title"])

    def test_parse_sse_keeps_raw_non_json_payload(self):
        events = _parse_sse("event: message\ndata: plain text\n\n")

        self.assertEqual([("message", {"raw": "plain text"})], events)

    def test_parser_supports_skip_compliance(self):
        args = build_parser().parse_args(["--skip-compliance"])

        self.assertTrue(args.skip_compliance)

    def test_parser_supports_ready_mineru_and_report_options(self):
        args = build_parser().parse_args(["--skip-ready", "--require-mineru", "--quiet", "--report", "out.md"])

        self.assertTrue(args.skip_ready)
        self.assertTrue(args.require_mineru)
        self.assertTrue(args.quiet)
        self.assertEqual("out.md", args.report)

    def test_parser_supports_section_count_for_long_task_smoke(self):
        args = build_parser().parse_args(["--section-count", "30"])

        self.assertEqual(30, args.section_count)

    def test_select_generation_sections_prefers_leaf_sections(self):
        sections = [
            {"id": "parent", "title": "质量措施", "metadata": {"section_role": "container"}},
            {"id": "leaf-1", "parent_id": "parent", "title": "质量控制"},
            {"id": "leaf-2", "parent_id": "parent", "title": "安全生产"},
            {"id": "leaf-3", "title": "商务响应"},
        ]

        selected = _select_generation_sections(sections, 2)

        self.assertEqual(["leaf-1", "leaf-2"], [section["id"] for section in selected])

    def test_check_ready_records_success(self):
        session = _FakeSession({"status": "ready", "checks": {"db": {"status": "ok"}}})
        ctx = SmokeContext(base_url="http://backend", timeout=10, session=session)

        payload = check_ready(ctx)

        self.assertEqual("ready", payload["status"])
        self.assertEqual("check_ready", ctx.results[0].name)
        self.assertIn("/api/ready", session.requested[0][0])

    def test_check_ready_fails_on_failed_dependency(self):
        session = _FakeSession({"status": "not_ready", "checks": {"redis": {"status": "fail"}}})
        ctx = SmokeContext(base_url="http://backend", timeout=10, session=session)

        with self.assertRaises(SmokeFailure):
            check_ready(ctx)

    def test_write_report_writes_markdown_and_json(self):
        ctx = SmokeContext(base_url="http://backend", timeout=10)
        ctx.artifacts["project_id"] = "p1"
        ctx.record("step_one", 0, "ok")
        with tempfile.TemporaryDirectory() as tmp:
            report = write_report(ctx, str(Path(tmp) / "smoke.md"), ok=True)

            self.assertIsNotNone(report)
            assert report is not None
            self.assertTrue(report.exists())
            self.assertTrue(report.with_suffix(".json").exists())
            self.assertIn("HTTP 全链路冒烟报告", report.read_text(encoding="utf-8"))

    def test_run_compliance_check_records_rows(self):
        session = _FakeSession({"rows": [{"id": "r1"}], "summary": {"coverageRate": 0.5}})
        ctx = SmokeContext(base_url="http://backend", timeout=10, session=session)

        payload = run_compliance_check(ctx, "11111111-1111-4111-8111-111111111111")

        self.assertEqual(1, len(payload["rows"]))
        self.assertIn("/api/bidding/interpretations/11111111-1111-4111-8111-111111111111/compliance-check", session.requested[0][0])
        self.assertEqual("run_compliance_check", ctx.results[0].name)


if __name__ == "__main__":
    unittest.main()
