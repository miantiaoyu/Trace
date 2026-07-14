import unittest

from trace_api_probe.carriers import Carrier
from trace_api_probe.normalization import normalize_tracking


class NormalizationTests(unittest.TestCase):
    def test_normalizes_yang_ming_events_and_current_location(self) -> None:
        raw = {
            "containerList": [
                {
                    "ctStatusInfo": [
                        {
                            "moveDate": "2026/07/13 04:09",
                            "eventDesc": "Received at Origin",
                            "atFacility": "SHEKOU",
                            "vesselVoyage": "V001",
                            "dportETA": "2026/08/01",
                            "nowStatus": "Y",
                        }
                    ]
                }
            ]
        }

        result = normalize_tracking(Carrier.YANG_MING, "YMMU6799822", raw)

        self.assertEqual(result["current"]["status"], "Received at Origin")
        self.assertEqual(result["current"]["location"], "SHEKOU")
        self.assertEqual(result["events"][0]["time"], "2026/07/13 04:09")
        self.assertEqual(result["destination_eta"], "2026/08/01")

    def test_normalizes_hmm_shipment_progress_table(self) -> None:
        raw = {
            "tables": [
                [
                    ["Date", "Time", "Location", "Status Description", "Mode"],
                    ["2026-07-13", "16:52", "XIAMEN", "Export Truck Gate In", "Truck"],
                ]
            ]
        }

        result = normalize_tracking(Carrier.HMM, "HMMU4706485", raw)

        self.assertEqual(result["current"]["location"], "XIAMEN")
        self.assertEqual(result["events"][0]["status"], "Export Truck Gate In")
        self.assertEqual(result["events"][0]["time"], "2026-07-13 16:52")

    def test_normalizes_cosco_rows(self) -> None:
        raw = {
            "rows": [
                ["动态节点", "时间", "位置", "运输方式"],
                ["重箱进场", "2026-07-10 20:32:00", "QINGDAO", "Truck"],
            ]
        }

        result = normalize_tracking(Carrier.COSCO, "CSLU6335149", raw)

        self.assertEqual(result["current"]["status"], "重箱进场")
        self.assertEqual(result["events"][0]["location"], "QINGDAO")

    def test_normalizes_one_rows(self) -> None:
        raw = {
            "rows": [
                ["Gate In to Outbound Terminal", "2026-07-12", "01:03"],
                ["Loaded on Vessel at Port of Loading", "ZEAL LUMOS 017E", "2026-07-19", "06:00"],
            ]
        }

        result = normalize_tracking(Carrier.ONE, "BEAU5347896", raw)

        self.assertEqual(result["current"]["status"], "Gate In to Outbound Terminal")
        self.assertEqual(result["events"][1]["vessel"], "ZEAL LUMOS")
        self.assertEqual(result["events"][1]["voyage"], "017E")
        self.assertEqual(result["vessel"]["name"], "ZEAL LUMOS")

    def test_normalizes_maersk_locations_and_eta(self) -> None:
        raw = {
            "origin": {"city": "QINGDAO", "terminal": "QINGDAO TERMINAL"},
            "destination": {"city": "NEWARK", "terminal": "APM TERMINAL"},
            "containers": [
                {
                    "eta_final_delivery": "2026-08-24T18:00:00.000",
                    "locations": [
                        {
                            "city": "QINGDAO",
                            "events": [
                                {
                                    "activity": "CONTAINER DEPARTURE",
                                    "event_time": "2026-07-18T17:00:00.000",
                                    "transport_mode": "MVS",
                                    "vessel_name": "MAERSK ELBA",
                                    "voyage_num": "629W",
                                }
                            ],
                        }
                    ],
                }
            ],
        }

        result = normalize_tracking(Carrier.MAERSK, "MRSU2197338", raw)

        self.assertEqual(result["origin"], "QINGDAO - QINGDAO TERMINAL")
        self.assertEqual(result["destination"], "NEWARK - APM TERMINAL")
        self.assertEqual(result["vessel"]["name"], "MAERSK ELBA")
        self.assertEqual(result["destination_eta"], "2026-08-24T18:00:00.000")

    def test_keeps_fixed_shape_when_a_provider_has_no_mapping(self) -> None:
        result = normalize_tracking(Carrier.ONE, "BEAU5347896", {"rows": [["unknown"]]})

        self.assertEqual(result["carrier"], "ONE")
        self.assertEqual(result["events"], [])
        self.assertIsNone(result["current"]["status"])
        self.assertIn("events", result["coverage"])


if __name__ == "__main__":
    unittest.main()
