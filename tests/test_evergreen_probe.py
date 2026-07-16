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

    def test_replaces_malformed_real_page_header_and_extracts_eta(self) -> None:
        rows = [
            [
                "提单列示之船名、航次 EVER ACE 1406-019W (長範輪) "
                "预计抵达时间 : AUG-05-2026 提单货柜信息和当前动态 "
                "箱号 柜型 日期 货柜动态 地点 船名 航次 Method VGM"
            ],
            ["EGSU0180491", "40'(SH)", "JUL-02-2026", "Loaded (FCL) on vessel", "YANTIAN, CHINA (CN)", "EVER ACE 1406-019W", "2", "15638.5 KGS"],
        ]

        result = _extract_tracking_rows(rows, "EGSU0180491")

        self.assertEqual(
            result["headers"],
            ["箱号", "柜型", "日期", "货柜动态", "地点", "船名 航次", "Method", "VGM"],
        )
        self.assertEqual(result["destination_eta"], "AUG-05-2026")

    def test_rejects_page_without_tracking_table(self) -> None:
        with self.assertRaisesRegex(TrackingPageError, "未出现轨迹结果表"):
            _extract_tracking_rows([["维护通知"]], "EGHU9204414")


if __name__ == "__main__":
    unittest.main()
