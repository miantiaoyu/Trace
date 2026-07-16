from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

from filelock import FileLock, Timeout

from trace_api_probe.result_status import PARTIAL_STATUSES, SKIPPED_STATUSES, SUCCESS_STATUSES


class RunAlreadyActiveError(RuntimeError):
    pass


class RunLock:
    """Prevent overlapping scheduled runs with a cross-platform file lock."""

    def __init__(self, path: Path, *, timeout_seconds: float = 0) -> None:
        self._path = path
        self._lock = FileLock(path, timeout=timeout_seconds)

    def __enter__(self) -> "RunLock":
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._lock.acquire()
        except Timeout as exc:
            raise RunAlreadyActiveError(f"已有 Trace 任务正在运行，锁文件: {self._path}") from exc
        return self

    def __exit__(self, *args: object) -> None:
        self._lock.release()


class RunRecorder:
    """Persist sanitized run metrics and carrier failure streaks."""

    def __init__(
        self,
        *,
        log_path: Path | None = None,
        health_state_path: Path | None = None,
        alert_threshold: int = 3,
    ) -> None:
        if alert_threshold <= 0:
            raise ValueError("连续失败告警阈值必须大于 0")
        self._log_path = log_path
        self._health_state_path = health_state_path
        self._alert_threshold = alert_threshold

    def record(self, report: Mapping[str, object]) -> list[dict[str, object]]:
        entry = _sanitized_entry(report)
        alerts = self._update_health(entry["carriers"])
        entry["alerts"] = alerts
        if self._log_path is not None:
            _append_json_line(self._log_path, entry)
        return alerts

    def _update_health(self, carriers: object) -> list[dict[str, object]]:
        if self._health_state_path is None or not isinstance(carriers, Mapping):
            return []
        state = _read_state(self._health_state_path)
        carrier_state = state.setdefault("carriers", {})
        if not isinstance(carrier_state, dict):
            carrier_state = {}
            state["carriers"] = carrier_state

        alerts = []
        for carrier, metrics in carriers.items():
            if not isinstance(metrics, Mapping):
                continue
            previous = carrier_state.get(carrier, {})
            streak = int(previous.get("consecutive_failed_runs", 0)) if isinstance(previous, Mapping) else 0
            has_success = int(metrics.get("success", 0)) > 0
            has_failure = int(metrics.get("failed", 0)) > 0 or int(metrics.get("partial", 0)) > 0
            if has_success:
                streak = 0
            elif has_failure:
                streak += 1
            carrier_state[str(carrier)] = {
                "consecutive_failed_runs": streak,
                "updated_at": _utc_now(),
            }
            if has_failure and streak >= self._alert_threshold:
                alerts.append(
                    {
                        "carrier": str(carrier),
                        "type": "consecutive_failed_runs",
                        "count": streak,
                        "message": f"{carrier} 已连续 {streak} 轮没有成功结果",
                    }
                )

        _write_state(self._health_state_path, state)
        return alerts


class DetailRecorder:
    """Persist per-sample diagnostics without storing raw carrier responses."""

    def __init__(self, *, log_path: Path | None = None) -> None:
        self._log_path = log_path

    def record(
        self,
        report: Mapping[str, object],
        *,
        samples: Sequence[object],
        persist: bool,
    ) -> None:
        if self._log_path is None:
            return
        results = report.get("results")
        result_rows = results if isinstance(results, list) else []
        rows = [
            _detail_row(sample, result, persist=persist)
            for sample, result in zip(samples, result_rows, strict=False)
            if isinstance(result, Mapping)
        ]
        entry = {
            "recorded_at": _utc_now(),
            "query": report.get("query", {}),
            "summary": report.get("summary", {}),
            "persistence": report.get("persistence", {}),
            "rows": rows,
        }
        _append_json_line(self._log_path, entry)


def _sanitized_entry(report: Mapping[str, object]) -> dict[str, object]:
    query = report.get("query")
    summary = report.get("summary")
    results = report.get("results")
    carrier_rows: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    if isinstance(results, list):
        for result in results:
            if not isinstance(result, Mapping):
                continue
            carrier = str(result.get("carrier") or "UNKNOWN")
            carrier_rows[carrier].append(result)

    carriers = {}
    for carrier, rows in carrier_rows.items():
        elapsed = []
        attempts = 0
        statuses: dict[str, int] = defaultdict(int)
        for row in rows:
            status = str(row.get("status") or "unknown")
            statuses[status] += 1
            execution = row.get("execution")
            if isinstance(execution, Mapping):
                attempts += int(execution.get("attempts") or 0)
                value = execution.get("elapsed_seconds")
                if isinstance(value, (int, float)):
                    elapsed.append(float(value))
        carriers[carrier] = {
            "total": len(rows),
            "success": sum(statuses.get(status, 0) for status in SUCCESS_STATUSES),
            "partial": sum(statuses.get(status, 0) for status in PARTIAL_STATUSES),
            "skipped": sum(statuses.get(status, 0) for status in SKIPPED_STATUSES),
            "failed": len(rows)
            - sum(statuses.get(status, 0) for status in SUCCESS_STATUSES)
            - sum(statuses.get(status, 0) for status in PARTIAL_STATUSES)
            - sum(statuses.get(status, 0) for status in SKIPPED_STATUSES),
            "attempts": attempts,
            "retries": max(0, attempts - len(rows)),
            "average_elapsed_seconds": round(sum(elapsed) / len(elapsed), 3) if elapsed else None,
            "statuses": dict(statuses),
        }

    query_summary = {}
    if isinstance(query, Mapping):
        query_summary = {
            key: query.get(key)
            for key in ("source", "read_only", "days", "limit", "carrier", "count")
        }
    return {
        "recorded_at": _utc_now(),
        "query": query_summary,
        "summary": dict(summary) if isinstance(summary, Mapping) else {},
        "carriers": carriers,
    }


def _detail_row(sample: object, result: Mapping[str, object], *, persist: bool) -> dict[str, object]:
    normalized = result.get("normalized")
    normalized = normalized if isinstance(normalized, Mapping) else {}
    current = normalized.get("current")
    current = current if isinstance(current, Mapping) else {}
    vessel = normalized.get("vessel")
    vessel = vessel if isinstance(vessel, Mapping) else {}
    execution = result.get("execution")
    execution = execution if isinstance(execution, Mapping) else {}
    status = str(result.get("status") or "internal_error")
    fields = {
        "departure_time": normalized.get("departure_time") is not None,
        "origin_port": (normalized.get("origin_port") or normalized.get("origin")) is not None,
        "destination_port": (normalized.get("destination_port") or normalized.get("destination")) is not None,
        "destination_eta": normalized.get("destination_eta") is not None,
        "current_status": current.get("status") is not None,
        "current_location": current.get("location") is not None,
        "vessel_name": vessel.get("name") is not None,
        "voyage": vessel.get("voyage") is not None,
    }
    error = result.get("error")
    return {
        "sample": {
            "id": getattr(sample, "id", None),
            "consolidation_no": getattr(sample, "consolidation_no", None),
            "container_no": getattr(sample, "container_no", None),
            "shipping_company": getattr(sample, "shipping_company", None),
            "erp_order_count": getattr(sample, "erp_order_count", None),
            "source_error": getattr(sample, "source_error", None),
        },
        "result": {
            "carrier": result.get("carrier"),
            "status": status,
            "route": result.get("route"),
            "route_description": result.get("route_description"),
            "error_type": _error_type(error),
            "error_message": _error_message(error),
            "attempts": execution.get("attempts"),
            "elapsed_seconds": execution.get("elapsed_seconds"),
            "raw_present": result.get("raw") is not None,
            "normalized_present": bool(normalized),
            "fields": fields,
            "missing_core_fields": [key for key, present in fields.items() if not present],
        },
        "persistence": _persistence_decision(sample, status, persist=persist),
    }


def _persistence_decision(sample: object, status: str, *, persist: bool) -> dict[str, object]:
    if not persist:
        return {"action": "not_requested"}
    if not getattr(sample, "consolidation_no", None):
        return {"action": "skipped", "reason": "missing_consolidation_no"}
    if status in SKIPPED_STATUSES:
        return {"action": "skipped", "reason": status}
    return {"action": "upsert"}


def _error_type(value: object) -> str | None:
    if isinstance(value, Mapping):
        error_type = value.get("type")
        return str(error_type) if error_type else None
    return type(value).__name__ if value else None


def _error_message(value: object) -> str | None:
    if isinstance(value, Mapping):
        message = value.get("message")
        return str(message)[:500] if message else None
    return str(value)[:500] if value else None


def _append_json_line(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")


def _read_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"carriers": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"carriers": {}}
    return value if isinstance(value, dict) else {"carriers": {}}


def _write_state(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
