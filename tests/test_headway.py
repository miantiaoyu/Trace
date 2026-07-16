import sys
import types
import unittest
from unittest.mock import patch

from trace_api_probe.config import DbConfig
from trace_api_probe.db import ShipmentSample
from trace_api_probe.headway import _build_row, persist_headway


class FakeCursor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, query: str, params: tuple[object, ...]) -> None:
        self.calls.append((query, params))


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self.cursor_value = cursor
        self.committed = False
        self.rolled_back = False

    def cursor(self) -> FakeCursor:
        return self.cursor_value

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        return None


class HeadwayTests(unittest.TestCase):
    def test_build_row_keeps_raw_and_arrival_fields(self) -> None:
        sample = ShipmentSample(1, "HMM", "HMMU0000001", "2026-07-13", None, "PG20260713001", 2)
        result = {
            "status": "success",
            "carrier": "HMM",
            "route": "hmm_browser_html",
            "execution": {"attempts": 1},
            "normalized": {
                "schema_version": "1.2",
                "origin_port": "XIAMEN",
                "destination_port": "SAVANNAH",
                "departure_time": "2026-07-14 10:00",
                "destination_eta": "2026-08-01 10:00",
                "current": {"time": "2026-07-14 10:00", "status": "Vessel Discharged", "location": "SAVANNAH", "mode": "Vessel"},
                "vessel": {"name": "TEST VESSEL", "voyage": "001E", "imo": "123"},
                "is_arrived_destination": True,
                "destination_arrived_at": "2026-08-01 10:00",
                "destination_arrival_evidence": "Vessel Discharged",
                "coverage": {"current": True},
            },
            "raw": {"provider": "hmm", "html": "<table>...</table>"},
        }

        row = _build_row("test", sample, result)

        self.assertEqual(row["consolidation_no"], "PG20260713001")
        self.assertEqual(row["erp_order_count"], 2)
        self.assertTrue(row["is_arrived_destination"])
        self.assertIn('"provider":"hmm"', str(row["raw_response_json"]))

    def test_persist_headway_executes_upsert_and_commits(self) -> None:
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        fake_module = types.SimpleNamespace(
            cursors=types.SimpleNamespace(DictCursor=object),
            connect=lambda **kwargs: connection,
        )
        sample = ShipmentSample(1, "HMM", "HMMU0000001", None, None, "PG20260713001", 1)
        result = {"status": "query_failed", "carrier": "HMM", "route": "hmm_browser_html", "error": {"type": "TimeoutError", "message": "timeout"}}

        with patch.dict(sys.modules, {"pymysql": fake_module}):
            summary = persist_headway(
                DbConfig("db.example", 3306, "writer", "secret"),
                environment="test",
                samples=[sample],
                results=[result],
            )

        self.assertEqual(summary, {"attempted": 1, "persisted": 1, "skipped": 0})
        self.assertTrue(connection.committed)
        self.assertEqual(len(cursor.calls), 1)
        self.assertIn("oms`.`headway", cursor.calls[0][0])
        self.assertEqual(cursor.calls[0][1][1], "PG20260713001")

    def test_persist_headway_skips_unavailable_routes(self) -> None:
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        fake_module = types.SimpleNamespace(
            cursors=types.SimpleNamespace(DictCursor=object),
            connect=lambda **kwargs: connection,
        )
        sample = ShipmentSample(1, "APL 美总", "APLU0000001", None, None, "PG20260713002", 1)
        result = {"status": "route_unavailable", "carrier": "APL", "route": "apl_unavailable", "error": "APL 当前没有稳定的直接查询路线"}

        with patch.dict(sys.modules, {"pymysql": fake_module}):
            summary = persist_headway(
                DbConfig("db.example", 3306, "writer", "secret"),
                environment="test",
                samples=[sample],
                results=[result],
            )

        self.assertEqual(summary, {"attempted": 0, "persisted": 0, "skipped": 1})
        self.assertFalse(connection.committed)
        self.assertEqual(cursor.calls, [])

    def test_persist_headway_skips_unsupported_carriers(self) -> None:
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        fake_module = types.SimpleNamespace(
            cursors=types.SimpleNamespace(DictCursor=object),
            connect=lambda **kwargs: connection,
        )
        sample = ShipmentSample(1, "未知船司", "TEST0000001", None, None, "PG20260713003", 1)
        result = {"status": "unsupported_carrier", "carrier": "UNKNOWN", "error": "无法识别船司"}

        with patch.dict(sys.modules, {"pymysql": fake_module}):
            summary = persist_headway(
                DbConfig("db.example", 3306, "writer", "secret"),
                environment="test",
                samples=[sample],
                results=[result],
            )

        self.assertEqual(summary, {"attempted": 0, "persisted": 0, "skipped": 1})
        self.assertFalse(connection.committed)
        self.assertEqual(cursor.calls, [])


if __name__ == "__main__":
    unittest.main()
