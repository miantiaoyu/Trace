import unittest
from unittest.mock import patch

from trace_api_probe.carriers import Carrier
from trace_api_probe.db import ShipmentSample
from trace_api_probe.tracking import CarrierRoute, TrackingOptions, TrackingRouter, query_samples


def sample(company: str = "YML阳明", container: str = "YMMU7349033") -> ShipmentSample:
    return ShipmentSample(7, company, container, "2026-07-13 10:00:00", "2026-07-12 10:00:00")


class TrackingRouterTests(unittest.TestCase):
    def test_rejects_invalid_container_before_calling_carrier_adapter(self) -> None:
        calls = []
        routes = {
            Carrier.YANG_MING: CarrierRoute(
                "fake",
                "测试路线",
                lambda container, options: calls.append(container),
            )
        }

        result = TrackingRouter(routes).query(sample(container="YMMU7349034"), TrackingOptions())

        self.assertEqual(result["status"], "source_data_error")
        self.assertEqual(result["route"], "source_validation")
        self.assertEqual(calls, [])

    def test_invalid_container_takes_precedence_over_unknown_carrier(self) -> None:
        result = TrackingRouter().query(sample("未知船司", "INVALID"))

        self.assertEqual(result["status"], "source_data_error")
        self.assertEqual(result["route"], "source_validation")

    def test_routes_sample_and_keeps_raw_payload(self) -> None:
        routes = {
            Carrier.YANG_MING: CarrierRoute("fake", "测试路线", lambda container, options: {"events": [container]})
        }

        result = TrackingRouter(routes).query(sample(), TrackingOptions())

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["carrier"], "YANG_MING")
        self.assertEqual(result["raw"], {"events": ["YMMU7349033"]})

    def test_keeps_query_failure_and_does_not_raise(self) -> None:
        routes = {
            Carrier.YANG_MING: CarrierRoute("fake", "测试路线", lambda container, options: (_ for _ in ()).throw(RuntimeError("站点超时")))
        }

        result = TrackingRouter(routes).query(sample(), TrackingOptions())

        self.assertEqual(result["status"], "query_failed")
        self.assertEqual(result["error"], {"type": "RuntimeError", "message": "站点超时"})

    def test_identifies_known_but_unavailable_carrier(self) -> None:
        result = TrackingRouter().query(sample("OOCL 东方海外", "OOLU1234567"))

        self.assertEqual(result["carrier"], "OOCL")
        self.assertEqual(result["status"], "route_unavailable")

    def test_cma_without_web_route_is_unavailable(self) -> None:
        result = TrackingRouter().query(sample("CMA 达飞", "CMAU4616180"))

        self.assertEqual(result["carrier"], "CMA_CGM")
        self.assertEqual(result["status"], "route_unavailable")

    def test_unknown_carrier_is_reported_as_data(self) -> None:
        result = TrackingRouter().query(sample("未知船司", "EGHU9204414"))

        self.assertEqual(result["status"], "unsupported_carrier")
        self.assertIsNone(result["carrier"])

    def test_batch_preserves_order(self) -> None:
        routes = {
            Carrier.YANG_MING: CarrierRoute("fake", "测试路线", lambda container, options: {"container": container})
        }
        results = query_samples([sample(container="YMMU0000001"), sample(container="YMMU0000002")], router=TrackingRouter(routes))

        self.assertEqual([result["container"] for result in results], ["YMMU0000001", "YMMU0000002"])

    def test_routes_hmm_mojibake_company_name(self) -> None:
        routes = {
            Carrier.HMM: CarrierRoute("fake_hmm", "测试 HMM 路线", lambda container, options: {"container": container})
        }

        result = TrackingRouter(routes).query(sample("HMM ş«ĐÂ BCO", "HMMU4706485"))

        self.assertEqual(result["carrier"], "HMM")
        self.assertEqual(result["status"], "success")

    def test_normalization_failure_keeps_raw_and_does_not_raise(self) -> None:
        routes = {
            Carrier.YANG_MING: CarrierRoute("fake", "测试路线", lambda container, options: {"payload": container})
        }

        with patch("trace_api_probe.tracking.normalize_tracking", side_effect=ValueError("字段结构变化")):
            result = TrackingRouter(routes).query(sample(), TrackingOptions())

        self.assertEqual(result["status"], "partial_success")
        self.assertEqual(result["raw"], {"payload": "YMMU7349033"})
        self.assertEqual(result["error"]["stage"], "normalization")

    def test_batch_isolates_unexpected_router_exception(self) -> None:
        class BrokenRouter:
            def query(self, shipment, options):
                if shipment.container_no.endswith("1"):
                    raise AssertionError("意外异常")
                return {"container": shipment.container_no, "status": "success"}

        results = query_samples(
            [sample(container="YMMU0000001"), sample(container="YMMU0000002")],
            router=BrokenRouter(),
        )

        self.assertEqual(results[0]["status"], "internal_error")
        self.assertEqual(results[1]["status"], "success")


if __name__ == "__main__":
    unittest.main()
