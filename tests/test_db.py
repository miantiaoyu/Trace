import sys
import types
import unittest
from unittest.mock import patch

from trace_api_probe.carriers import Carrier
from trace_api_probe.config import DbConfig
from trace_api_probe.db import _group_samples, fetch_recent_shipments


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


if __name__ == "__main__":
    unittest.main()
