import json
import tempfile
import unittest
from pathlib import Path

from trace_api_probe.runtime import DetailRecorder, RunAlreadyActiveError, RunLock, RunRecorder


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

    def test_detail_log_records_per_sample_failure_without_raw_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "detail.jsonl"
            sample = type(
                "Sample",
                (),
                {
                    "id": 7,
                    "consolidation_no": "PG20260713001",
                    "container_no": "HMMU0000001",
                    "shipping_company": "HMM",
                    "erp_order_count": 2,
                    "source_error": None,
                },
            )()
            detail_report = report()
            detail_report["results"][0]["route"] = "hmm_browser_html"
            detail_report["results"][0]["error"] = {"type": "TimeoutError", "message": "timeout"}
            detail_report["results"][0]["raw"] = {"html": "<secret raw>"}

            DetailRecorder(log_path=log_path).record(detail_report, samples=[sample], persist=True)

            entry = json.loads(log_path.read_text(encoding="utf-8").strip())
            row = entry["rows"][0]
            self.assertEqual(row["sample"]["consolidation_no"], "PG20260713001")
            self.assertEqual(row["result"]["error_type"], "TimeoutError")
            self.assertTrue(row["result"]["raw_present"])
            self.assertNotIn("<secret raw>", log_path.read_text(encoding="utf-8"))
            self.assertEqual(row["persistence"]["action"], "upsert")


if __name__ == "__main__":
    unittest.main()
