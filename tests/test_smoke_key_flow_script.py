import unittest

from scripts.smoke_key_flow import _parse_sse


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


if __name__ == "__main__":
    unittest.main()
