import unittest

from trace_api_probe.providers.hmm_probe import TRACKING_RESPONSE_TIMEOUT_MS, HmmTrackingError, _build_result


class HmmProbeTests(unittest.TestCase):
    def test_waits_two_minutes_for_tracking_response(self) -> None:
        self.assertEqual(TRACKING_RESPONSE_TIMEOUT_MS, 120_000)

    def test_builds_result_from_tracking_html(self) -> None:
        html = """
        <div>Tracking Result</div>
        <input id="thisCntr" value="HMMU4706485" />
        <div>Shipment Progress</div>
        <table>
          <tr><th>Container No.</th><th>Movement</th></tr>
          <tr><td>HMMU4706485</td><td>Export Truck Gate In to Terminal</td></tr>
        </table>
        """

        result = _build_result(html, "HMMU4706485")

        self.assertEqual(result["carrier"], "HMM")
        self.assertEqual(result["container"], "HMMU4706485")
        self.assertEqual(result["tables"][0][1], ["HMMU4706485", "Export Truck Gate In to Terminal"])
        self.assertEqual(result["parse_diagnostics"]["table_count"], 1)
        self.assertEqual(result["parse_diagnostics"]["table_headers"][0], ["Container No.", "Movement"])
        self.assertTrue(result["parse_diagnostics"]["sections"]["container_summary"])
        self.assertFalse(result["parse_diagnostics"]["sections"]["route"])

    def test_rejects_response_without_requested_container(self) -> None:
        with self.assertRaisesRegex(HmmTrackingError, "未回显柜号"):
            _build_result("<div>Tracking Result</div><div>Shipment Progress</div>", "HMMU4706485")

    def test_rejects_response_without_tracking_contract(self) -> None:
        with self.assertRaisesRegex(HmmTrackingError, "缺少 Tracking Result"):
            _build_result("<div>HMMU4706485</div>", "HMMU4706485")

    def test_rejects_response_when_container_table_contract_changes(self) -> None:
        html = """
        <div>Tracking Result</div>
        <div>HMMU4706485</div>
        <div>Shipment Progress</div>
        <table><tr><th>Unknown</th></tr><tr><td>value</td></tr></table>
        """

        with self.assertRaisesRegex(HmmTrackingError, "未识别到柜信息表"):
            _build_result(html, "HMMU4706485")


if __name__ == "__main__":
    unittest.main()
