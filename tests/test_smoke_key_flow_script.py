import unittest

from scripts.smoke_key_flow import SmokeContext, _parse_sse, build_parser, run_compliance_check


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

    def test_run_compliance_check_records_rows(self):
        session = _FakeSession({"rows": [{"id": "r1"}], "summary": {"coverageRate": 0.5}})
        ctx = SmokeContext(base_url="http://backend", timeout=10, session=session)

        payload = run_compliance_check(ctx, "11111111-1111-4111-8111-111111111111")

        self.assertEqual(1, len(payload["rows"]))
        self.assertIn("/api/bidding/interpretations/11111111-1111-4111-8111-111111111111/compliance-check", session.requested[0][0])
        self.assertEqual("run_compliance_check", ctx.results[0].name)


if __name__ == "__main__":
    unittest.main()
