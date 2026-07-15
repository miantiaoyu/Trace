from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Mapping, Sequence

from trace_api_probe.config import DbConfig
from trace_api_probe.db import ShipmentSample


HEADWAY_TABLE = "`oms`.`headway`"
SUCCESS_STATUSES = {"success"}
RAW_SUCCESS_STATUSES = {"success", "partial_success"}
SKIPPED_STATUSES = {"route_unavailable"}


def persist_headway(
    config: DbConfig,
    *,
    environment: str,
    samples: Sequence[ShipmentSample],
    results: Sequence[Mapping[str, object]],
) -> dict[str, int]:
    """Upsert the latest snapshot for each consolidation number."""
    rows = [
        _build_row(environment, sample, result)
        for sample, result in zip(samples, results, strict=False)
        if sample.consolidation_no and _should_persist_result(result)
    ]
    if not rows:
        return {"attempted": 0, "persisted": 0, "skipped": len(samples)}

    try:
        import pymysql
    except ImportError as exc:
        raise RuntimeError("缺少依赖 PyMySQL。请先在 py312 环境安装: pip install -r requirements.txt") from exc

    connection = pymysql.connect(
        host=config.host,
        port=config.port,
        user=config.user,
        password=config.password,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        read_timeout=15,
        write_timeout=15,
        connect_timeout=10,
        autocommit=False,
    )
    try:
        with connection.cursor() as cursor:
            for row in rows:
                cursor.execute(_UPSERT_SQL, _row_params(row))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return {"attempted": len(rows), "persisted": len(rows), "skipped": len(samples) - len(rows)}


_UPSERT_SQL = f"""
INSERT INTO {HEADWAY_TABLE} (
    environment, consolidation_no, erp_order_count, erp_shipping_company, carrier_code, container_no,
    erp_update_time, erp_create_time, departure_time, origin_port, destination_port, destination_eta,
    current_event_time, current_status, current_location, current_mode, vessel_name, voyage, imo,
    is_arrived_destination, destination_arrived_at, destination_arrival_evidence, query_status, query_route,
    last_queried_at, last_success_at, next_query_at, last_attempts, last_error_type, last_error_message,
    raw_response_json, normalized_schema_version, coverage_json
) VALUES (
    %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s,
    %s, %s, %s
)
ON DUPLICATE KEY UPDATE
    erp_order_count = VALUES(erp_order_count),
    erp_shipping_company = VALUES(erp_shipping_company),
    carrier_code = VALUES(carrier_code),
    container_no = VALUES(container_no),
    erp_update_time = VALUES(erp_update_time),
    erp_create_time = VALUES(erp_create_time),
    query_status = VALUES(query_status),
    query_route = VALUES(query_route),
    last_queried_at = VALUES(last_queried_at),
    last_attempts = VALUES(last_attempts),
    last_error_type = VALUES(last_error_type),
    last_error_message = VALUES(last_error_message),
    last_success_at = COALESCE(VALUES(last_success_at), last_success_at),
    next_query_at = VALUES(next_query_at),
    raw_response_json = COALESCE(VALUES(raw_response_json), raw_response_json),
    normalized_schema_version = COALESCE(VALUES(normalized_schema_version), normalized_schema_version),
    coverage_json = COALESCE(VALUES(coverage_json), coverage_json),
    departure_time = IF(VALUES(query_status) IN ('success'), VALUES(departure_time), departure_time),
    origin_port = IF(VALUES(query_status) IN ('success'), VALUES(origin_port), origin_port),
    destination_port = IF(VALUES(query_status) IN ('success'), VALUES(destination_port), destination_port),
    destination_eta = IF(VALUES(query_status) IN ('success'), VALUES(destination_eta), destination_eta),
    current_event_time = IF(VALUES(query_status) IN ('success'), VALUES(current_event_time), current_event_time),
    current_status = IF(VALUES(query_status) IN ('success'), VALUES(current_status), current_status),
    current_location = IF(VALUES(query_status) IN ('success'), VALUES(current_location), current_location),
    current_mode = IF(VALUES(query_status) IN ('success'), VALUES(current_mode), current_mode),
    vessel_name = IF(VALUES(query_status) IN ('success'), VALUES(vessel_name), vessel_name),
    voyage = IF(VALUES(query_status) IN ('success'), VALUES(voyage), voyage),
    imo = IF(VALUES(query_status) IN ('success'), VALUES(imo), imo),
    is_arrived_destination = IF(VALUES(query_status) IN ('success'), VALUES(is_arrived_destination), is_arrived_destination),
    destination_arrived_at = IF(VALUES(query_status) IN ('success'), VALUES(destination_arrived_at), destination_arrived_at),
    destination_arrival_evidence = IF(VALUES(query_status) IN ('success'), VALUES(destination_arrival_evidence), destination_arrival_evidence),
    updated_at = CURRENT_TIMESTAMP
"""


def _build_row(environment: str, sample: ShipmentSample, result: Mapping[str, object]) -> dict[str, object]:
    normalized = result.get("normalized")
    summary = normalized if isinstance(normalized, Mapping) else {}
    current = summary.get("current")
    current = current if isinstance(current, Mapping) else {}
    vessel = summary.get("vessel")
    vessel = vessel if isinstance(vessel, Mapping) else {}
    execution = result.get("execution")
    execution = execution if isinstance(execution, Mapping) else {}
    status = str(result.get("status") or "internal_error")
    error = result.get("error")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    raw = result.get("raw") if status in RAW_SUCCESS_STATUSES else None
    last_success_at = now if status in RAW_SUCCESS_STATUSES else None
    next_query_at = now + timedelta(hours=24 if status in RAW_SUCCESS_STATUSES else 1)
    return {
        "environment": environment,
        "consolidation_no": sample.consolidation_no,
        "erp_order_count": sample.erp_order_count,
        "erp_shipping_company": sample.shipping_company,
        "carrier_code": str(result.get("carrier") or "UNKNOWN"),
        "container_no": sample.container_no,
        "erp_update_time": _db_datetime(sample.update_time),
        "erp_create_time": _db_datetime(sample.create_time),
        "departure_time": _db_datetime(summary.get("departure_time")),
        "origin_port": _text(summary.get("origin_port") or summary.get("origin")),
        "destination_port": _text(summary.get("destination_port") or summary.get("destination")),
        "destination_eta": _db_datetime(summary.get("destination_eta")),
        "current_event_time": _db_datetime(current.get("time")),
        "current_status": _text(current.get("status")),
        "current_location": _text(current.get("location")),
        "current_mode": _text(current.get("mode")),
        "vessel_name": _text(vessel.get("name")),
        "voyage": _text(vessel.get("voyage")),
        "imo": _text(vessel.get("imo")),
        "is_arrived_destination": bool(summary.get("is_arrived_destination")) if status in SUCCESS_STATUSES else False,
        "destination_arrived_at": _db_datetime(summary.get("destination_arrived_at")),
        "destination_arrival_evidence": _text(summary.get("destination_arrival_evidence")),
        "query_status": status,
        "query_route": _text(result.get("route")),
        "last_queried_at": now,
        "last_success_at": last_success_at,
        "next_query_at": next_query_at,
        "last_attempts": int(execution.get("attempts") or 0),
        "last_error_type": _error_type(error),
        "last_error_message": _error_message(error),
        "raw_response_json": json.dumps(raw, ensure_ascii=False, separators=(",", ":"), default=str) if raw is not None else None,
        "normalized_schema_version": _text(summary.get("schema_version")),
        "coverage_json": json.dumps(summary.get("coverage"), ensure_ascii=False, separators=(",", ":"))
        if isinstance(summary.get("coverage"), Mapping)
        else None,
    }


def _should_persist_result(result: Mapping[str, object]) -> bool:
    return str(result.get("status") or "internal_error") not in SKIPPED_STATUSES


_PARAMETER_ORDER = (
    "environment", "consolidation_no", "erp_order_count", "erp_shipping_company", "carrier_code", "container_no",
    "erp_update_time", "erp_create_time", "departure_time", "origin_port", "destination_port", "destination_eta",
    "current_event_time", "current_status", "current_location", "current_mode", "vessel_name", "voyage", "imo",
    "is_arrived_destination", "destination_arrived_at", "destination_arrival_evidence", "query_status", "query_route",
    "last_queried_at", "last_success_at", "next_query_at", "last_attempts", "last_error_type", "last_error_message",
    "raw_response_json", "normalized_schema_version", "coverage_json",
)


def _row_params(row: Mapping[str, object]) -> tuple[object, ...]:
    return tuple(row[key] for key in _PARAMETER_ORDER)


def _db_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    text = str(value).strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        return parsed.replace(tzinfo=None)
    except ValueError:
        pass
    for pattern in ("%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y/%m/%d %H:%M", "%Y/%m/%d", "%Y%m%d %H:%M", "%b-%d-%Y"):
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            continue
    return None


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _error_type(value: object) -> str | None:
    if isinstance(value, Mapping):
        return _text(value.get("type"))
    return type(value).__name__ if value else None


def _error_message(value: object) -> str | None:
    if isinstance(value, Mapping):
        return _text(value.get("message"))
    return _text(value)
