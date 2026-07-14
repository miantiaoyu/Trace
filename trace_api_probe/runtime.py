from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from filelock import FileLock, Timeout


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
            streak = 0 if int(metrics.get("success", 0)) > 0 else streak + 1
            carrier_state[str(carrier)] = {
                "consecutive_failed_runs": streak,
                "updated_at": _utc_now(),
            }
            if streak >= self._alert_threshold:
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
            "success": statuses.get("success", 0),
            "partial": statuses.get("partial_success", 0),
            "failed": len(rows) - statuses.get("success", 0) - statuses.get("partial_success", 0),
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
