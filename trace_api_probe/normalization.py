from __future__ import annotations

import re
from typing import Any, Callable, Mapping

from trace_api_probe.carriers import Carrier


def normalize_tracking(carrier: Carrier, container: str, raw: object) -> dict[str, object]:
    """返回固定摘要字段，同时允许 raw 保留船司特有数据。"""
    result = _empty_summary(carrier, container)
    normalizer = _NORMALIZERS.get(carrier)
    if normalizer is None or not isinstance(raw, Mapping):
        return result
    return normalizer(result, raw)


def _empty_summary(carrier: Carrier, container: str) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "carrier": carrier.value,
        "container": container,
        "current": {"time": None, "status": None, "location": None, "mode": None},
        "vessel": {"name": None, "voyage": None, "imo": None},
        "origin": None,
        "destination": None,
        "destination_eta": None,
        "events": [],
        "coverage": {
            "current": False,
            "events": False,
            "vessel": False,
            "eta": False,
        },
    }


def _normalize_yang_ming(result: dict[str, object], raw: Mapping[str, Any]) -> dict[str, object]:
    containers = raw.get("containerList")
    if not isinstance(containers, list) or not containers or not isinstance(containers[0], Mapping):
        return result
    item = containers[0]
    events = _event_list(item.get("ctStatusInfo"), "moveDate", "eventDesc", "atFacility", "tsMode", "vesselVoyage")
    _apply_events(result, events)
    eta = _first_value(item.get("ctStatusInfo"), "dportETA")
    if eta:
        result["destination_eta"] = eta
        _coverage(result)["eta"] = True
    return result


def _normalize_hmm(result: dict[str, object], raw: Mapping[str, Any]) -> dict[str, object]:
    tables = raw.get("tables")
    if not isinstance(tables, list):
        return result

    route_table = _hmm_route_table(tables)
    if route_table is not None:
        header, rows = route_table
        origin_index = header.index("origin")
        destination_index = header.index("destination")
        result["origin"] = _hmm_location(rows, origin_index)
        result["destination"] = _hmm_location(rows, destination_index)
        eta = _at(rows.get("arrival(etb)", []), destination_index)
        if eta:
            result["destination_eta"] = eta
            _coverage(result)["eta"] = True

    events = _hmm_events(tables)
    _apply_events(result, events)

    if not _coverage(result)["vessel"]:
        vessels = _hmm_vessels(tables)
        if vessels:
            result["vessel"] = {"name": vessels[0][0], "voyage": vessels[0][1], "imo": None}
            _coverage(result)["vessel"] = True
    return result


def _hmm_route_table(tables: list[object]) -> tuple[list[str], dict[str, list[object]]] | None:
    for table in tables:
        if not isinstance(table, list) or len(table) < 2 or not isinstance(table[0], list):
            continue
        header = [_label(value) for value in table[0]]
        if not {"origin", "destination"}.issubset(header):
            continue
        rows = {
            _label(row[0]): row
            for row in table[1:]
            if isinstance(row, list) and row and _label(row[0])
        }
        if "location" in rows:
            return header, rows
    return None


def _hmm_location(rows: Mapping[str, list[object]], index: int) -> str | None:
    location = _at(rows.get("location", []), index)
    terminal = _at(rows.get("terminal", []), index)
    if location and terminal:
        return f"{location} - {terminal}"
    return location or terminal


def _hmm_events(tables: list[object]) -> list[dict[str, object]]:
    candidates: list[tuple[int, list[dict[str, object]]]] = []
    for table in tables:
        if not isinstance(table, list) or len(table) < 2 or not isinstance(table[0], list):
            continue
        header = [_label(value) for value in table[0]]
        if not {"location", "status description"}.issubset(header):
            continue
        has_separate_time = "date" in header and "time" in header
        has_combined_time = "date / time" in header
        if not has_separate_time and not has_combined_time:
            continue

        location_index = header.index("location")
        status_index = header.index("status description")
        mode_index = header.index("mode") if "mode" in header else None
        events = []
        for row in table[1:]:
            if not isinstance(row, list):
                continue
            if has_separate_time:
                time_value = _join_values(_at(row, header.index("date")), _at(row, header.index("time")))
            else:
                time_value = _at(row, header.index("date / time"))
            status = _at(row, status_index)
            location = _at(row, location_index)
            if not (time_value or status or location):
                continue
            raw_mode = _at(row, mode_index) if mode_index is not None else None
            vessel, voyage = _split_vessel_voyage(raw_mode)
            events.append(
                {
                    "time": time_value,
                    "status": status,
                    "location": location,
                    "mode": "Vessel" if vessel else raw_mode,
                    "vessel": vessel,
                    "voyage": voyage,
                }
            )
        if events:
            candidates.append((1 if has_separate_time else 0, events))

    if not candidates:
        return []
    _, events = max(candidates, key=lambda candidate: (candidate[0], len(candidate[1])))
    return sorted(events, key=lambda event: str(event.get("time") or ""), reverse=True)


def _hmm_vessels(tables: list[object]) -> list[tuple[str | None, str | None]]:
    for table in tables:
        if not isinstance(table, list) or len(table) < 2 or not isinstance(table[0], list):
            continue
        header = [_label(value) for value in table[0]]
        if "vessel / voyage" not in header:
            continue
        index = header.index("vessel / voyage")
        vessels = []
        for row in table[1:]:
            if not isinstance(row, list):
                continue
            vessel, voyage = _split_vessel_voyage(_at(row, index))
            if vessel or voyage:
                vessels.append((vessel, voyage))
        return vessels
    return []


def _normalize_cosco(result: dict[str, object], raw: Mapping[str, Any]) -> dict[str, object]:
    rows = raw.get("rows")
    if not isinstance(rows, list) or len(rows) < 2:
        return result
    headers = _row_values(rows[0])
    indexes = {name: headers.index(name) for name in ("动态节点", "时间", "位置", "运输方式") if name in headers}
    if not {"动态节点", "时间", "位置"}.issubset(indexes):
        return result
    events = []
    for row in rows[1:]:
        values = _row_values(row)
        events.append(
            {
                "time": _at(values, indexes["时间"]),
                "status": _at(values, indexes["动态节点"]),
                "location": _at(values, indexes["位置"]),
                "mode": _at(values, indexes["运输方式"]) if "运输方式" in indexes else None,
                "vessel": None,
                "voyage": None,
            }
        )
    _apply_events(result, events)
    return result


def _normalize_one(result: dict[str, object], raw: Mapping[str, Any]) -> dict[str, object]:
    rows = raw.get("rows")
    if not isinstance(rows, list):
        return result
    events = []
    for row in rows:
        values = _row_values(row)
        date_index = next((index for index, value in enumerate(values) if _is_date(value)), None)
        if date_index is None or not values[:date_index]:
            continue
        prefix = values[:date_index]
        status = prefix[-1]
        location = prefix[0] if len(prefix) >= 3 else None
        vessel, voyage = _split_vessel_voyage(prefix[1] if len(prefix) == 2 else None)
        events.append(
            {
                "time": _join_values(values[date_index], _at(values, date_index + 1)),
                "status": status,
                "location": location,
                "mode": None,
                "vessel": vessel,
                "voyage": voyage,
            }
        )
    _apply_events(result, events)
    return result


def _normalize_maersk(result: dict[str, object], raw: Mapping[str, Any]) -> dict[str, object]:
    result["origin"] = _location_label(raw.get("origin"))
    result["destination"] = _location_label(raw.get("destination"))
    containers = raw.get("containers")
    if not isinstance(containers, list) or not containers or not isinstance(containers[0], Mapping):
        return result
    container = containers[0]
    eta = _text(container.get("eta_final_delivery"))
    if eta:
        result["destination_eta"] = eta
        _coverage(result)["eta"] = True

    events = []
    locations = container.get("locations")
    if isinstance(locations, list):
        for location in locations:
            if not isinstance(location, Mapping):
                continue
            location_name = _location_label(location)
            source_events = location.get("events")
            if not isinstance(source_events, list):
                continue
            for item in source_events:
                if not isinstance(item, Mapping):
                    continue
                events.append(
                    {
                        "time": _text(item.get("event_time")),
                        "status": _text(item.get("activity")),
                        "location": location_name,
                        "mode": _text(item.get("transport_mode")),
                        "vessel": _text(item.get("vessel_name")),
                        "voyage": _text(item.get("voyage_num")),
                    }
                )
    _apply_events(result, events)
    for event in events:
        if event["vessel"] or event["voyage"]:
            result["vessel"] = {"name": event["vessel"], "voyage": event["voyage"], "imo": None}
            _coverage(result)["vessel"] = True
            break
    return result


def _event_list(
    source: object,
    time_key: str,
    status_key: str,
    location_key: str,
    mode_key: str,
    voyage_key: str,
) -> list[dict[str, object]]:
    if not isinstance(source, list):
        return []
    events = []
    for item in source:
        if not isinstance(item, Mapping):
            continue
        events.append(
            {
                "time": _text(item.get(time_key)),
                "status": _text(item.get(status_key)),
                "location": _text(item.get(location_key)),
                "mode": _text(item.get(mode_key)),
                "vessel": None,
                "voyage": _text(item.get(voyage_key)),
            }
        )
    return events


def _apply_events(result: dict[str, object], events: list[dict[str, object]]) -> None:
    result["events"] = events
    coverage = _coverage(result)
    coverage["events"] = bool(events)
    if not events:
        return
    current = events[0]
    result["current"] = {
        "time": current["time"],
        "status": current["status"],
        "location": current["location"],
        "mode": current["mode"],
    }
    coverage["current"] = bool(current["status"] or current["location"])
    for event in events:
        if event["vessel"] or event["voyage"]:
            result["vessel"] = {"name": event["vessel"], "voyage": event["voyage"], "imo": None}
            coverage["vessel"] = True
            break


def _coverage(result: dict[str, object]) -> dict[str, bool]:
    return result["coverage"]  # type: ignore[return-value]


def _first_value(source: object, key: str) -> str | None:
    if not isinstance(source, list):
        return None
    for item in source:
        if isinstance(item, Mapping):
            value = _text(item.get(key))
            if value:
                return value
    return None


def _at(values: list[object], index: int) -> str | None:
    return _text(values[index]) if index < len(values) else None


def _row_values(row: object) -> list[str]:
    if not isinstance(row, list):
        return []
    if len(row) == 1:
        return [value.strip() for value in str(row[0]).split("\t") if value.strip()]
    return [value.strip() for value in (str(item) for item in row) if value.strip()]


def _is_date(value: str) -> bool:
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value))


def _split_vessel_voyage(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    match = re.fullmatch(r"(.+?)\s+(\d{3,4}[A-Z])", value)
    if match is None:
        return None, None
    return match.group(1), match.group(2)


def _location_label(value: object) -> str | None:
    if not isinstance(value, Mapping):
        return None
    city = _text(value.get("city"))
    terminal = _text(value.get("terminal"))
    if city and terminal:
        return f"{city} - {terminal}"
    return city or terminal


def _join_values(*values: str | None) -> str | None:
    merged = " ".join(value for value in values if value)
    return merged or None


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _label(value: object) -> str:
    return " ".join(str(value).strip().lower().split())


_NORMALIZERS: Mapping[Carrier, Callable[[dict[str, object], Mapping[str, Any]], dict[str, object]]] = {
    Carrier.YANG_MING: _normalize_yang_ming,
    Carrier.HMM: _normalize_hmm,
    Carrier.COSCO: _normalize_cosco,
    Carrier.ONE: _normalize_one,
    Carrier.MAERSK: _normalize_maersk,
}
