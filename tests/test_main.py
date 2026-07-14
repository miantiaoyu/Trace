import unittest
from unittest.mock import patch

from trace_api_probe.__main__ import _build_report
from trace_api_probe.db import ShipmentSample
from trace_api_probe.tracking import TrackingOptions


class MainReportTests(unittest.TestCase):
    def test_reports_success_partial_and_failed_separately(self) -> None:
        samples = [
            ShipmentSample(1, "MSK 马士基", "MSKU0000001", None, None),
            ShipmentSample(2, "HMM", "HMMU0000001", None, None),
            ShipmentSample(3, "MSC 地中海", "MSCU0000001", None, None),
        ]
        results = [
            {"status": "success"},
            {"status": "partial_success"},
            {"status": "query_failed"},
        ]

        with patch("trace_api_probe.__main__.query_samples", return_value=results):
            report = _build_report(
                samples=samples,
                days=7,
                limit=3,
                carrier=None,
                options=TrackingOptions(),
            )

        self.assertEqual(
            report["summary"],
            {"total": 3, "success": 1, "partial": 1, "failed": 1},
        )


if __name__ == "__main__":
    unittest.main()
