import sys
import types
import unittest
from unittest.mock import patch

from trace_api_probe.carriers import Carrier
from trace_api_probe.config import DbConfig
from trace_api_probe.db import _group_samples, fetch_pending_shipments, fetch_recent_shipments


def _sample(consolidation_no: str) -> types.SimpleNamespace:
    return types.SimpleNamespace(
        id=1,
        shipping_company="HMM",
        container_no=f"{consolidation_no}U",
        update_time=None,
        create_time=None,
        consolidation_no=consolidation_no,
        erp_order_count=1,
        source_error=None,
    )


class FakeCursor:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.query = ""
        self.params: list[object] = []

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, query: str, params: list[object]) -> None:
        self.query = query
        self.params = params

    def fetchall(self) -> list[dict[str, object]]:
        return self.rows


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self.fake_cursor = cursor

    def cursor(self) -> FakeCursor:
        return self.fake_cursor

    def close(self) -> None:
        return None


class DbTests(unittest.TestCase):
    def test_marks_conflicting_containers_in_same_consolidation_as_source_error(self) -> None:
        samples = _group_samples(
            [
                {"id": 2, "shipping_company": "HMM", "cabinet_no": "HMMU0000001", "cabinet_combination_number": "PG20260713001", "update_time": "2026-07-13", "create_time": None},
                {"id": 1, "shipping_company": "HMM", "cabinet_no": "HMMU0000002", "cabinet_combination_number": "PG20260713001", "update_time": "2026-07-12", "create_time": None},
            ]
        )

        self.assertEqual(len(samples), 1)
        self.assertIn("多个柜号", samples[0].source_error or "")

    def test_fetches_recent_rows_and_groups_by_consolidation_number(self) -> None:
        cursor = FakeCursor(
            [
                {"id": 2, "shipping_company": "YML阳明", "cabinet_no": "YMMU0000002", "cabinet_combination_number": "PG20260713001", "update_time": "2026-07-13", "create_time": None},
                {"id": 1, "shipping_company": "YML阳明", "cabinet_no": "YMMU0000002", "cabinet_combination_number": "PG20260713001", "update_time": "2026-07-12", "create_time": None},
            ]
        )
        fake_module = types.SimpleNamespace(
            cursors=types.SimpleNamespace(DictCursor=object),
            connect=lambda **kwargs: FakeConnection(cursor),
        )

        with patch.dict(sys.modules, {"pymysql": fake_module}):
            result = fetch_recent_shipments(
                DbConfig("db.example", 3306, "reader", "secret"),
                days=7,
                carrier=Carrier.YANG_MING,
                limit=20,
            )

        self.assertEqual([item.container_no for item in result], ["YMMU0000002"])
        self.assertEqual(result[0].consolidation_no, "PG20260713001")
        self.assertEqual(result[0].erp_order_count, 2)
        self.assertIn("INTERVAL 7 DAY", cursor.query)
        self.assertIn("ORDER BY update_time DESC, id DESC", cursor.query)
        self.assertEqual(cursor.params, ["YML", "YML阳明", "YML 阳明", "阳明", "YANGMING", "YANG MING"])

    def test_hmm_query_has_prefix_fallback_for_mojibake_company_name(self) -> None:
        cursor = FakeCursor(
            [
                {"id": 3, "shipping_company": "HMM ş«ĐÂ BCO", "cabinet_no": "HMMU4706485", "cabinet_combination_number": "PG20260713002", "update_time": "2026-07-13", "create_time": None},
            ]
        )
        fake_module = types.SimpleNamespace(
            cursors=types.SimpleNamespace(DictCursor=object),
            connect=lambda **kwargs: FakeConnection(cursor),
        )

        with patch.dict(sys.modules, {"pymysql": fake_module}):
            result = fetch_recent_shipments(
                DbConfig("db.example", 3306, "reader", "secret"),
                days=7,
                carrier=Carrier.HMM,
                limit=1,
            )

        self.assertEqual([item.container_no for item in result], ["HMMU4706485"])
        self.assertIn("UPPER(TRIM(shipping_company)) LIKE %s", cursor.query)
        self.assertIn("HMM%", cursor.params)

    def test_removes_internal_whitespace_from_container_number(self) -> None:
        cursor = FakeCursor(
            [
                {
                    "id": 4,
                    "shipping_company": "EMC 长荣",
                    "cabinet_no": " EGHU 9204414 ",
                    "shipping_order": "BOOKING123",
                    "cabinet_combination_number": "PG20260713003",
                    "update_time": "2026-07-13",
                    "create_time": None,
                }
            ]
        )
        fake_module = types.SimpleNamespace(
            cursors=types.SimpleNamespace(DictCursor=object),
            connect=lambda **kwargs: FakeConnection(cursor),
        )

        with patch.dict(sys.modules, {"pymysql": fake_module}):
            result = fetch_recent_shipments(
                DbConfig("db.example", 3306, "reader", "secret"),
                days=7,
                limit=1,
            )

        self.assertEqual(result[0].container_no, "EGHU9204414")
        self.assertNotEqual(result[0].container_no, "BOOKING123")

    def test_pending_shipments_only_take_recent_rows_missing_from_headway(self) -> None:
        source_config = DbConfig("aliyun.example", 3306, "reader", "source-secret")
        target_config = DbConfig("172.16.48.10", 3306, "writer", "target-secret")
        new_sample = _sample("PG_NEW")
        existing_recent = _sample("PG_EXISTING_RECENT")
        due_sample = _sample("PG_DUE")

        with (
            patch(
                "trace_api_probe.db.fetch_recent_shipments",
                return_value=[new_sample, existing_recent],
            ) as fetch_recent,
            patch("trace_api_probe.db._fetch_due_headway_keys", return_value=["PG_DUE"]) as fetch_due,
            patch(
                "trace_api_probe.db._fetch_shipments_by_consolidation_numbers",
                return_value=[due_sample],
            ) as fetch_historical,
            patch(
                "trace_api_probe.db._fetch_headway_states",
                return_value={
                    "PG_EXISTING_RECENT": {"is_arrived_destination": 0, "next_query_at": None},
                    "PG_DUE": {"is_arrived_destination": 0, "next_query_at": None},
                },
            ) as fetch_states,
        ):
            result = fetch_pending_shipments(
                source_config,
                target_config,
                environment="test",
                days=60,
                limit=0,
            )

        self.assertEqual([item.consolidation_no for item in result], ["PG_DUE", "PG_NEW"])
        fetch_recent.assert_called_once_with(source_config, days=60, carrier=None, limit=0)
        fetch_due.assert_called_once_with(target_config, "test")
        fetch_historical.assert_called_once_with(source_config, ["PG_DUE"], carrier=None)
        fetch_states.assert_called_once_with(
            target_config,
            "test",
            ["PG_DUE", "PG_NEW", "PG_EXISTING_RECENT"],
        )

    def test_pending_shipments_retries_due_query_failure(self) -> None:
        source_config = DbConfig("aliyun.example", 3306, "reader", "source-secret")
        target_config = DbConfig("172.16.48.10", 3306, "writer", "target-secret")
        failed_sample = _sample("PG_FAILED")

        with (
            patch("trace_api_probe.db.fetch_recent_shipments", return_value=[failed_sample]),
            patch("trace_api_probe.db._fetch_due_headway_keys", return_value=["PG_FAILED"]),
            patch("trace_api_probe.db._fetch_shipments_by_consolidation_numbers", return_value=[]),
            patch(
                "trace_api_probe.db._fetch_headway_states",
                return_value={
                    "PG_FAILED": {
                        "query_status": "query_failed",
                        "is_arrived_destination": 0,
                        "next_query_at": "2000-01-01 00:00:00",
                    }
                },
            ),
        ):
            result = fetch_pending_shipments(
                source_config,
                target_config,
                environment="test",
                days=60,
                limit=0,
            )

        self.assertEqual([item.consolidation_no for item in result], ["PG_FAILED"])

    def test_due_query_failure_has_priority_over_new_rows_when_limited(self) -> None:
        source_config = DbConfig("aliyun.example", 3306, "reader", "source-secret")
        target_config = DbConfig("172.16.48.10", 3306, "writer", "target-secret")
        new_samples = [_sample("PG_NEW_1"), _sample("PG_NEW_2")]
        failed_sample = _sample("PG_FAILED")

        with (
            patch("trace_api_probe.db.fetch_recent_shipments", return_value=new_samples),
            patch("trace_api_probe.db._fetch_due_headway_keys", return_value=["PG_FAILED"]),
            patch(
                "trace_api_probe.db._fetch_shipments_by_consolidation_numbers",
                return_value=[failed_sample],
            ),
            patch(
                "trace_api_probe.db._fetch_headway_states",
                return_value={
                    "PG_FAILED": {
                        "query_status": "query_failed",
                        "is_arrived_destination": 0,
                        "next_query_at": "2000-01-01 00:00:00",
                    }
                },
            ),
        ):
            result = fetch_pending_shipments(
                source_config,
                target_config,
                environment="test",
                days=60,
                limit=1,
            )

        self.assertEqual([item.consolidation_no for item in result], ["PG_FAILED"])


if __name__ == "__main__":
    unittest.main()
