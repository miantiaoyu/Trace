import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch

from trace_api_probe.__main__ import _build_report, main
from trace_api_probe.db import ShipmentSample
from trace_api_probe.tracking import TrackingOptions


class MainReportTests(unittest.TestCase):
    def test_main_returns_success_when_every_result_is_skipped(self) -> None:
        samples = [ShipmentSample(1, "HMM", "INVALID", None, None)]
        with TemporaryDirectory() as directory:
            lock_path = Path(directory) / "trace.lock"
            with (
                patch("trace_api_probe.__main__._resolve_samples", return_value=samples),
                patch(
                    "trace_api_probe.__main__.query_samples",
                    return_value=[{"status": "source_data_error"}],
                ),
                patch("trace_api_probe.__main__._print_json"),
            ):
                exit_code = main(["--lock-file", str(lock_path), "--summary-only"])

        self.assertEqual(exit_code, 0)

    def test_reports_success_partial_and_failed_separately(self) -> None:
        samples = [
            ShipmentSample(1, "MSK 马士基", "MSKU0000001", None, None),
            ShipmentSample(2, "HMM", "HMMU0000001", None, None),
            ShipmentSample(3, "MSC 地中海", "MSCU0000001", None, None),
            ShipmentSample(4, "HMM", "INVALID", None, None),
        ]
        results = [
            {"status": "success"},
            {"status": "partial_success"},
            {"status": "query_failed"},
            {"status": "source_data_error"},
        ]

        with patch("trace_api_probe.__main__.query_samples", return_value=results):
            report = _build_report(
                samples=samples,
                days=7,
                limit=4,
                carrier=None,
                options=TrackingOptions(),
            )

        self.assertEqual(
            report["summary"],
            {"total": 4, "success": 1, "partial": 1, "skipped": 1, "failed": 1},
        )


if __name__ == "__main__":
    unittest.main()
