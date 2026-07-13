import unittest

from crawler_lab.evergreen_probe import TrackingPageError, _extract_tracking_rows


class EvergreenProbeTests(unittest.TestCase):
    def test_extracts_row_after_tracking_headers(self) -> None:
        rows = [
            ["其他内容"],
            ["箱号", "柜型", "日期", "货柜动态", "地点", "船名 航次", "Method", "VGM"],
            ["EGHU9204414", "40'(SH)", "JUL-10-2026", "Empty container returned", "CORK (IE)", "", "", ""],
        ]

        result = _extract_tracking_rows(rows, "EGHU9204414")

        self.assertEqual(result["carrier"], "EVERGREEN")
        self.assertEqual(result["rows"], [rows[2]])

    def test_rejects_page_without_tracking_table(self) -> None:
        with self.assertRaisesRegex(TrackingPageError, "未出现轨迹结果表"):
            _extract_tracking_rows([["维护通知"]], "EGHU9204414")


if __name__ == "__main__":
    unittest.main()
