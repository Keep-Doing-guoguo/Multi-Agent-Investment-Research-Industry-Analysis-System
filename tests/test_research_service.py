from __future__ import annotations

import json
import unittest

from app.services.research_service import format_sse_event


class ResearchServiceTest(unittest.TestCase):
    def test_format_sse_event(self) -> None:
        event = {
            "event_id": 1,
            "run_id": "run_1",
            "event_type": "run_created",
            "payload": {"message": "开始"},
        }

        frame = format_sse_event(
            event_type="run_created",
            event_id=1,
            data=event,
        )

        self.assertTrue(frame.startswith("id: 1\n"))
        self.assertIn("event: run_created\n", frame)
        self.assertIn("data: ", frame)
        self.assertTrue(frame.endswith("\n\n"))

        data_line = [
            line.removeprefix("data: ")
            for line in frame.splitlines()
            if line.startswith("data: ")
        ][0]
        self.assertEqual(json.loads(data_line), event)


if __name__ == "__main__":
    unittest.main()
