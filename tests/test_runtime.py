import json
import tempfile
import unittest
from pathlib import Path

from trace_api_probe.runtime import RunAlreadyActiveError, RunLock, RunRecorder


def report(status: str = "query_failed") -> dict[str, object]:
    return {
        "query": {"source": "table", "read_only": True, "days": 7, "limit": 1, "carrier": "HMM", "count": 1},
        "summary": {"total": 1, "success": int(status == "success"), "partial": 0, "failed": int(status != "success")},
        "results": [
            {
                "carrier": "HMM",
                "container": "HMMU0000001",
                "status": status,
                "execution": {"attempts": 2, "elapsed_seconds": 12.5},
            }
        ],
    }


class RuntimeTests(unittest.TestCase):
    def test_lock_rejects_overlapping_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.lock"
            with RunLock(path):
                with self.assertRaises(RunAlreadyActiveError):
                    with RunLock(path):
                        pass

    def test_log_is_sanitized_and_health_alerts_after_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "runs.jsonl"
            state_path = Path(directory) / "health.json"
            recorder = RunRecorder(log_path=log_path, health_state_path=state_path, alert_threshold=2)

            self.assertEqual(recorder.record(report()), [])
            alerts = recorder.record(report())

            self.assertEqual(alerts[0]["carrier"], "HMM")
            log_text = log_path.read_text(encoding="utf-8")
            self.assertNotIn("HMMU0000001", log_text)
            entries = [json.loads(line) for line in log_text.splitlines()]
            self.assertEqual(entries[-1]["carriers"]["HMM"]["retries"], 1)

    def test_success_resets_failure_streak(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "health.json"
            recorder = RunRecorder(health_state_path=state_path, alert_threshold=2)

            recorder.record(report())
            recorder.record(report("success"))
            recorder.record(report())

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["carriers"]["HMM"]["consecutive_failed_runs"], 1)


if __name__ == "__main__":
    unittest.main()
