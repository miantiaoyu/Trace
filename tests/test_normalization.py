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

    def test_normalizes_hmm_route_vessel_eta_and_vessel_events(self) -> None:
        raw = {
            "tables": [
                [
                    ["", "Origin", "Loading Port", "T/S Port", "Discharging Port", "Destination"],
                    ["Location", "XIAMEN, CHINA", "XIAMEN, CHINA", "BUSAN, KOREA", "SAVANNAH, GA", "SAVANNAH, GA"],
                    ["Terminal", "XIAMEN TERMINAL", "XIAMEN TERMINAL", "BUSAN TERMINAL", "GARDEN CITY", "GARDEN CITY"],
                    ["Arrival(ETB)", "", "2026-06-19 07:23", "2026-07-05 13:18", "2026-08-16 00:30", "2026-08-16 12:27"],
                ],
                [
                    ["Vessel / Voyage", "Route", "Loading Port", "Departure", "Discharging Port", "Arrival"],
                    ["GSL CHLOE 2610N", "PF1", "XIAMEN, CHINA", "2026-06-27 20:14", "BUSAN, KOREA", "2026-07-05 13:18"],
                    ["HYUNDAI MARS 0055E", "EC1", "BUSAN, KOREA", "2026-07-16 23:00", "SAVANNAH, GA", "2026-08-16 00:30"],
                ],
                [
                    ["Date", "Time", "Location", "Status Description", "Mode"],
                    ["2026-07-05", "22:56", "BUSAN, KOREA", "Vessel Discharged at T/S Port", "GSL CHLOE 2610N"],
                    ["2026-06-19", "07:23", "XIAMEN, CHINA", "Export Truck Gate In", "Truck"],
                ],
            ]
        }

        result = normalize_tracking(Carrier.HMM, "HMMU0000001", raw)

        self.assertEqual(result["origin"], "XIAMEN, CHINA - XIAMEN TERMINAL")
        self.assertEqual(result["destination"], "SAVANNAH, GA - GARDEN CITY")
        self.assertEqual(result["destination_eta"], "2026-08-16 12:27")
        self.assertEqual(result["events"][0]["mode"], "Vessel")
        self.assertEqual(result["events"][0]["vessel"], "GSL CHLOE")
        self.assertEqual(result["events"][0]["voyage"], "2610N")
        self.assertEqual(result["vessel"]["name"], "GSL CHLOE")
        self.assertTrue(result["coverage"]["vessel"])
        self.assertTrue(result["coverage"]["eta"])

    def test_normalizes_hmm_combined_datetime_as_event_fallback(self) -> None:
        raw = {
            "tables": [
                [
                    ["Location", "Date / Time", "Status Description"],
                    ["QINGDAO, CHINA", "2026-07-11 04:11", "Export Empty Container Released"],
                ],
                [
                    ["Vessel / Voyage", "Route"],
                    ["HMM JUNIPER 0004W", "FIL"],
                ],
            ]
        }

        result = normalize_tracking(Carrier.HMM, "HMMU0000002", raw)

        self.assertEqual(result["current"]["time"], "2026-07-11 04:11")
        self.assertEqual(result["vessel"]["name"], "HMM JUNIPER")
        self.assertEqual(result["vessel"]["voyage"], "0004W")

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

    def test_maersk_selects_latest_actual_and_next_expected_from_shuffled_events(self) -> None:
        raw = {
            "containers": [
                {
                    "locations": [
                        {
                            "city": "QINGDAO",
                            "events": [
                                {"event_time": "2026-08-24T18:00:00.000", "activity": "ARRIVAL", "event_time_type": "EXPECTED"},
                                {"event_time": "2026-07-11T10:05:00.000", "activity": "GATE-OUT", "event_time_type": "ACTUAL"},
                                {"event_time": "2026-07-18T17:00:00.000", "activity": "DEPARTURE", "event_time_type": "EXPECTED"},
                                {"event_time": "2026-07-09T08:00:00.000", "activity": "RELEASE", "event_time_type": "ACTUAL"},
                            ],
                        }
                    ]
                }
            ]
        }

        result = normalize_tracking(Carrier.MAERSK, "MSKU0000001", raw)

        self.assertEqual(result["current"]["status"], "GATE-OUT")
        self.assertEqual(result["current"]["time"], "2026-07-11T10:05:00.000")
        self.assertEqual(result["next_expected"]["status"], "DEPARTURE")
        self.assertEqual(result["events"][0]["time_type"], "EXPECTED")

    def test_normalizes_sm_line_actual_and_expected_events(self) -> None:
        raw = {
            "sailing": {"list": [{"polNm": "NINGBO, CHINA", "podNm": "LONG BEACH, US", "eta": "2026-07-28 04:00"}]},
            "detail": {
                "list": [
                    {"eventDt": "2026-07-14 08:58", "statusNm": "Gate In", "placeNm": "NINGBO", "yardNm": "TERMINAL", "actTpCd": "A"},
                    {"eventDt": "2026-07-16 20:00", "statusNm": "Loaded", "placeNm": "NINGBO", "vslEngNm": "SM SHANGHAI", "skdVoyNo": "2605", "skdDirCd": "E", "actTpCd": "E"},
                ]
            },
        }

        result = normalize_tracking(Carrier.SM_LINE, "SMCU0000001", raw)

        self.assertEqual(result["current"]["status"], "Gate In")
        self.assertEqual(result["next_expected"]["status"], "Loaded")
        self.assertEqual(result["vessel"]["name"], "SM SHANGHAI")
        self.assertEqual(result["vessel"]["voyage"], "2605E")
        self.assertEqual(result["destination_eta"], "2026-07-28 04:00")

    def test_normalizes_evergreen_latest_row(self) -> None:
        raw = {
            "headers": ["箱号", "柜型", "日期", "货柜动态", "地点", "船名 航次", "Method", "VGM"],
            "rows": [["EGHU0000001", "40'(SH)", "JUL-10-2026", "Empty container returned", "CORK (IE)", "", "Truck", ""]],
        }

        result = normalize_tracking(Carrier.EVERGREEN, "EGHU0000001", raw)

        self.assertEqual(result["current"]["status"], "Empty container returned")
        self.assertEqual(result["current"]["location"], "CORK (IE)")

    def test_normalizes_msc_actual_expected_vessel_and_eta(self) -> None:
        raw = {
            "Data": {
                "BillOfLadings": [
                    {
                        "GeneralTrackingInfo": {"ShippedFrom": "SHANGHAI, CN", "ShippedTo": "SAVANNAH, US"},
                        "ContainersInfo": [
                            {
                                "ContainerNumber": "TLLU0000001",
                                "PodEtaDate": "10/08/2026",
                                "Events": [
                                    {"Date": "10/08/2026", "Location": "SAVANNAH, US", "Description": "Estimated Time of Arrival", "Detail": ["ZIM AMBER", "14W"], "Vessel": {"IMO": "9967952"}},
                                    {"Date": "14/07/2026", "Location": "SHANGHAI, CN", "Description": "Estimated Time of Departure", "Detail": ["ZIM AMBER", "14E"], "Vessel": {"IMO": "9967952"}},
                                    {"Date": "09/07/2026", "Location": "SHANGHAI, CN", "Description": "Export received at CY", "Detail": ["LADEN"], "Vessel": {"IMO": ""}},
                                ],
                            }
                        ],
                    }
                ]
            }
        }

        result = normalize_tracking(Carrier.MSC, "TLLU0000001", raw)

        self.assertEqual(result["current"]["status"], "Export received at CY")
        self.assertEqual(result["next_expected"]["status"], "Estimated Time of Departure")
        self.assertEqual(result["vessel"], {"name": "ZIM AMBER", "voyage": "14E", "imo": "9967952"})
        self.assertEqual(result["destination_eta"], "10/08/2026")

    def test_normalizes_wan_hai_latest_status_and_booking_vessel(self) -> None:
        raw = {
            "headers": ["Ctnr No.", "Ctnr Date", "Status Name", "Ctnr Depot Name", "Voyage", "Vessel Name", "More detail"],
            "rows": [["WHSU0000001", "20260710 16:14", "Full Container Withdrawn", "YUSEN TERMINAL", "", "", "REF"]],
            "booking_summary": {
                "headers": ["", "BL no.", "Oboard Date", "Voyage", "Vessel Name", "More detail"],
                "rows": [["1", "REF", "2026/06/21", "E016", "WAN HAI A03", ""]],
            },
        }

        result = normalize_tracking(Carrier.WAN_HAI, "WHSU0000001", raw)

        self.assertEqual(result["current"]["status"], "Full Container Withdrawn")
        self.assertEqual(result["vessel"]["name"], "WAN HAI A03")
        self.assertEqual(result["vessel"]["voyage"], "E016")

    def test_keeps_fixed_shape_when_a_provider_has_no_mapping(self) -> None:
        result = normalize_tracking(Carrier.ONE, "BEAU5347896", {"rows": [["unknown"]]})

        self.assertEqual(result["carrier"], "ONE")
        self.assertEqual(result["events"], [])
        self.assertIsNone(result["current"]["status"])
        self.assertIn("events", result["coverage"])


if __name__ == "__main__":
    unittest.main()
