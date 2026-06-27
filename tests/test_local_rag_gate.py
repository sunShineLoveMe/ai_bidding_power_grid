import unittest


class LocalRagGateTest(unittest.TestCase):
    def test_parse_sse_events_ignores_non_json_lines(self):
        from scripts.rag.run_local_rag_gate import parse_sse_events

        events = parse_sse_events(
            "data: {\"type\":\"start\"}\n"
            "\n"
            "event: ping\n"
            "data: not-json\n"
            "data: {\"type\":\"done\"}\n"
        )

        self.assertEqual([event["type"] for event in events], ["start", "done"])

    def test_summarize_stream_events_counts_retrieved_and_chunks(self):
        from scripts.rag.run_local_rag_gate import summarize_stream_events

        summary = summarize_stream_events([
            {"type": "retrieved", "contexts_count": 2, "assets_count": 3, "images": [{}, {}]},
            {"type": "chunk", "content": "A"},
            {"type": "chunk", "content": "B"},
            {"type": "done"},
        ])

        self.assertTrue(summary["done"])
        self.assertEqual(summary["contexts_count"], 2)
        self.assertEqual(summary["assets_count"], 3)
        self.assertEqual(summary["images_count"], 2)
        self.assertEqual(summary["chunks"], 2)


if __name__ == "__main__":
    unittest.main()
