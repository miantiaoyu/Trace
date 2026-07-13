import unittest

from crawler_lab.wan_hai_probe import (
    WanHaiTrackingError,
    _extract_booking_summary_rows,
    _extract_reference_numbers,
    _extract_tracking_rows,
)


class WanHaiProbeTests(unittest.TestCase):
    def test_extracts_row_after_tracking_headers(self) -> None:
        rows = [
            ["Other content"],
            ["Ctnr No.", "Ctnr Date", "Status Name", "Ctnr Depot Name", "Voyage", "Vessel Name", "More detail"],
            ["WHSU6376250", "20260710 16:14", "Full Container Withdrawn By Consignee From Pier/Terminal", "YUSEN TERMINAL LLC", "", "", "026G533793 Booking Data B/L Data"],
        ]

        result = _extract_tracking_rows(rows, "WHSU6376250")

        self.assertEqual(result["carrier"], "WAN_HAI")
        self.assertEqual(result["rows"], [rows[2]])

    def test_rejects_page_without_tracking_table(self) -> None:
        with self.assertRaisesRegex(WanHaiTrackingError, "未出现集装箱列表表头"):
            _extract_tracking_rows([["Maintenance notice"]], "WHSU6376250")

    def test_extracts_booking_reference_from_more_detail(self) -> None:
        rows = [
            ["WHSU6376250", "20260710 16:14", "Status", "Depot", "", "", "026G533793 Booking Data B/L Data"],
        ]

        self.assertEqual(_extract_reference_numbers(rows), ["026G533793"])

    def test_extracts_booking_summary_rows(self) -> None:
        rows = [
            ["Other content"],
            ["?", "BL no.", "Oboard Date", "Voyage", "Vessel Name", "More detail"],
            ["1", "026G533793", "2026/06/21", "E016", "WAN HAI A03", "Booking Data B/L Data"],
        ]

        result = _extract_booking_summary_rows(rows, "026G533793")

        self.assertEqual(result["reference"], "026G533793")
        self.assertEqual(result["rows"], [rows[2]])


if __name__ == "__main__":
    unittest.main()
