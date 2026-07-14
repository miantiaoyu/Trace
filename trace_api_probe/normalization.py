from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Callable, Mapping

from trace_api_probe.carriers import Carrier
from trace_api_probe.models import new_tracking_summary, validate_tracking_summary


def normalize_tracking(carrier: Carrier, container: str, raw: object) -> dict[str, object]:
    """返回固定摘要字段，同时允许 raw 保留船司特有数据。"""
    result = empty_tracking_summary(carrier, container)
    normalizer = _NORMALIZERS.get(carrier)
    if normalizer is None or not isinstance(raw, Mapping):
        return result
    return validate_tracking_summary(normalizer(result, raw))


def empty_tracking_summary(carrier: Carrier, container: str) -> dict[str, object]:
    return new_tracking_summary(carrier.value, container)


def _normalize_yang_ming(result: dict[str, object], raw: Mapping[str, Any]) -> dict[str, object]:
    containers = raw.get("containerList")
    if not isinstance(containers, list) or not containers or not isinstance(containers[0], Mapping):
        return result
    item = containers[0]
    source_events = item.get("dcsaStatusInfo")
    events = _yang_ming_events(source_events)
    if not events:
        events = _yang_ming_events(item.get("ctStatusInfo"))
    _apply_events(result, events)
    eta = _first_value(item.get("ctStatusInfo"), "dportETA")
    if eta:
        result["destination_eta"] = eta
        _coverage(result)["eta"] = True
    return result


def _yang_ming_events(source: object) -> list[dict[str, object]]:
    if not isinstance(source, list):
        return []
    events = []
    for item in source:
        if not isinstance(item, Mapping):
            continue
        mode, vessel, voyage = _parse_transport(item.get("tsMode") or item.get("vesselVoyage"))
        event_class = (_text(item.get("eventClassifie")) or "").upper()
        events.append(
            {
                "time": _text(item.get("moveDate")),
                "status": _text(item.get("eventDesc")),
                "location": _text(item.get("atFacility")),
                "mode": mode,
                "vessel": vessel,
                "voyage": voyage,
                "imo": None,
                "time_type": {"ACTUAL": "ACTUAL", "ESTIMATED": "EXPECTED"}.get(event_class),
            }
        )
    return events


def _parse_transport(value: object) -> tuple[str | None, str | None, str | None]:
    text = _text(value)
    if not text:
        return None, None, None
    parts = [part.strip() for part in re.split(r"<br\s*/?>", text, flags=re.IGNORECASE) if part.strip()]
    if not parts:
        return None, None, None
    first = parts[0].upper()
    if first in {"TRUCK", "RAIL", "BARGE"}:
        return first.title(), None, None
    if first == "VESSEL":
        vessel = parts[1] if len(parts) > 1 else None
        voyage = parts[2].strip("()") if len(parts) > 2 else None
        return "Vessel", vessel, voyage
    vessel = parts[0]
    voyage = parts[1].strip("()") if len(parts) > 1 else None
    return "Vessel", vessel, voyage


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
                    "imo": None,
                    "time_type": "ACTUAL",
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
                "imo": None,
                "time_type": None,
            }
        )
    _apply_events(result, events)
    return result


def _normalize_one(result: dict[str, object], raw: Mapping[str, Any]) -> dict[str, object]:
    rows = raw.get("rows")
    if not isinstance(rows, list):
        return result
    metadata = raw.get("row_metadata")
    row_metadata = metadata if isinstance(metadata, list) else []
    events = []
    current_location: str | None = None
    current_vessel: str | None = None
    current_voyage: str | None = None
    for row_index, row in enumerate(rows):
        values = _row_values(row)
        date_index = next((index for index, value in enumerate(values) if _is_date(value)), None)
        if date_index is None or not values[:date_index]:
            continue
        prefix = values[:date_index]
        if len(prefix) >= 3:
            current_location = _join_location(prefix[0], prefix[1])
            status = prefix[-1]
            explicit_vessel = None
        elif len(prefix) == 2:
            explicit_vessel, explicit_voyage = _split_vessel_voyage(prefix[1])
            if explicit_vessel or explicit_voyage:
                status = prefix[0]
            else:
                current_location = prefix[0]
                status = prefix[1]
        else:
            status = prefix[0]
            explicit_vessel = None
        if len(prefix) != 2:
            explicit_voyage = None
        if explicit_vessel or explicit_voyage:
            current_vessel, current_voyage = explicit_vessel, explicit_voyage
        is_vessel_event = "vessel" in status.lower() or bool(explicit_vessel or explicit_voyage)
        item_metadata = row_metadata[row_index] if row_index < len(row_metadata) else None
        time_type = _time_type(item_metadata.get("time_type")) if isinstance(item_metadata, Mapping) else None
        events.append(
            {
                "time": _join_values(values[date_index], _at(values, date_index + 1)),
                "status": status,
                "location": current_location,
                "mode": "Vessel" if is_vessel_event and current_vessel else None,
                "vessel": current_vessel if is_vessel_event else None,
                "voyage": current_voyage if is_vessel_event else None,
                "imo": None,
                "time_type": time_type,
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
                        "imo": None,
                        "time_type": _time_type(item.get("event_time_type")),
                    }
                )
    _apply_events(result, events)
    return result


def _normalize_sm_line(result: dict[str, object], raw: Mapping[str, Any]) -> dict[str, object]:
    sailing_rows = _response_rows(raw.get("sailing"))
    if sailing_rows:
        sailing = sailing_rows[0]
        result["origin"] = _text(sailing.get("polNm"))
        result["destination"] = _text(sailing.get("podNm"))
        eta = _text(sailing.get("eta"))
        if eta:
            result["destination_eta"] = eta
            _coverage(result)["eta"] = True

    events = []
    for item in _response_rows(raw.get("detail")):
        vessel = _text(item.get("vslEngNm"))
        voyage = _join_compact(item.get("skdVoyNo"), item.get("skdDirCd"))
        location = _join_location(_text(item.get("placeNm")), _text(item.get("yardNm")))
        act_type = _text(item.get("actTpCd"))
        events.append(
            {
                "time": _text(item.get("eventDt")),
                "status": _clean_text(item.get("statusNm")),
                "location": location,
                "mode": "Vessel" if vessel else None,
                "vessel": vessel,
                "voyage": voyage,
                "imo": None,
                "time_type": {"A": "ACTUAL", "E": "EXPECTED"}.get((act_type or "").upper()),
            }
        )
    _apply_events(result, events)
    return result


def _normalize_evergreen(result: dict[str, object], raw: Mapping[str, Any]) -> dict[str, object]:
    events = []
    for item in _table_records(raw.get("headers"), raw.get("rows")):
        vessel, voyage = _split_vessel_voyage(item.get("船名 航次"))
        events.append(
            {
                "time": _text(item.get("日期")),
                "status": _text(item.get("货柜动态")),
                "location": _text(item.get("地点")),
                "mode": _text(item.get("Method")) or ("Vessel" if vessel else None),
                "vessel": vessel,
                "voyage": voyage,
                "imo": None,
                "time_type": None,
            }
        )
    _apply_events(result, events)
    return result


def _normalize_msc(result: dict[str, object], raw: Mapping[str, Any]) -> dict[str, object]:
    data = raw.get("Data")
    if not isinstance(data, Mapping):
        return result
    bills = data.get("BillOfLadings")
    if not isinstance(bills, list):
        return result

    container_info: Mapping[str, Any] | None = None
    for bill in bills:
        if not isinstance(bill, Mapping):
            continue
        general = bill.get("GeneralTrackingInfo")
        containers = bill.get("ContainersInfo")
        if not isinstance(containers, list):
            continue
        for item in containers:
            if not isinstance(item, Mapping):
                continue
            if _text(item.get("ContainerNumber")) != result["container"]:
                continue
            container_info = item
            if isinstance(general, Mapping):
                result["origin"] = _text(general.get("ShippedFrom")) or _text(general.get("PortOfLoad"))
                result["destination"] = _text(general.get("ShippedTo")) or _text(general.get("PortOfDischarge"))
                eta = _text(item.get("PodEtaDate")) or _text(general.get("FinalPodEtaDate"))
                if eta:
                    result["destination_eta"] = eta
                    _coverage(result)["eta"] = True
            break
        if container_info is not None:
            break

    if container_info is None:
        return result
    events = []
    source_events = container_info.get("Events")
    if isinstance(source_events, list):
        for item in source_events:
            if not isinstance(item, Mapping):
                continue
            description = _text(item.get("Description"))
            detail = item.get("Detail")
            detail_values = detail if isinstance(detail, list) else []
            vessel_data = item.get("Vessel")
            imo = _text(vessel_data.get("IMO")) if isinstance(vessel_data, Mapping) else None
            vessel = _text(detail_values[0]) if len(detail_values) >= 2 else None
            voyage = _text(detail_values[1]) if vessel and len(detail_values) >= 2 else None
            events.append(
                {
                    "time": _text(item.get("Date")),
                    "status": description,
                    "location": _text(item.get("Location")),
                    "mode": "Vessel" if vessel else None,
                    "vessel": vessel,
                    "voyage": voyage,
                    "imo": imo,
                    "time_type": "EXPECTED" if description and "estimated" in description.lower() else "ACTUAL",
                }
            )
    _apply_events(result, events)
    return result


def _normalize_wan_hai(result: dict[str, object], raw: Mapping[str, Any]) -> dict[str, object]:
    events = []
    for item in _table_records(raw.get("headers"), raw.get("rows")):
        vessel = _text(item.get("Vessel Name"))
        voyage = _text(item.get("Voyage"))
        events.append(
            {
                "time": _text(item.get("Ctnr Date")),
                "status": _text(item.get("Status Name")),
                "location": _text(item.get("Ctnr Depot Name")),
                "mode": "Vessel" if vessel else None,
                "vessel": vessel,
                "voyage": voyage,
                "imo": None,
                "time_type": "ACTUAL",
            }
        )
    _apply_events(result, events)

    if not _coverage(result)["vessel"]:
        summary = raw.get("booking_summary")
        if isinstance(summary, Mapping):
            records = _table_records(summary.get("headers"), summary.get("rows"))
            if records:
                vessel = _text(records[0].get("Vessel Name"))
                voyage = _text(records[0].get("Voyage"))
                if vessel or voyage:
                    result["vessel"] = {"name": vessel, "voyage": voyage, "imo": None}
                    _coverage(result)["vessel"] = True
    return result


def _response_rows(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, Mapping):
        return []
    rows = value.get("list")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, Mapping)]


def _table_records(headers: object, rows: object) -> list[dict[str, object]]:
    if not isinstance(headers, list) or not isinstance(rows, list):
        return []
    labels = [str(value).strip() for value in headers]
    records = []
    for row in rows:
        if not isinstance(row, list):
            continue
        records.append({label: row[index] if index < len(row) else None for index, label in enumerate(labels)})
    return records


def _join_location(location: str | None, terminal: str | None) -> str | None:
    if location and terminal:
        return f"{location} - {terminal}"
    return location or terminal


def _join_compact(*values: object) -> str | None:
    merged = "".join(value for item in values if (value := _text(item)))
    return merged or None


def _apply_events(result: dict[str, object], events: list[dict[str, object]]) -> None:
    result["events"] = events
    coverage = _coverage(result)
    coverage["events"] = bool(events)
    if not events:
        return

    typed_events = [event for event in events if event.get("time_type") in {"ACTUAL", "EXPECTED"}]
    actual_events = [event for event in typed_events if event.get("time_type") == "ACTUAL"]
    expected_events = [event for event in typed_events if event.get("time_type") == "EXPECTED"]
    current = _latest_event(actual_events) if typed_events else events[0]
    if current is not None:
        result["current"] = _event_snapshot(current)
        coverage["current"] = bool(current.get("status") or current.get("location"))

    next_expected = _next_expected_event(expected_events, current)
    if next_expected is not None:
        result["next_expected"] = _event_snapshot(next_expected)
        coverage["next_expected"] = True

    vessel_event = next(
        (
            event
            for event in (current, next_expected, *events)
            if event is not None and (event.get("vessel") or event.get("voyage") or event.get("imo"))
        ),
        None,
    )
    if vessel_event is not None:
        result["vessel"] = {
            "name": vessel_event.get("vessel"),
            "voyage": vessel_event.get("voyage"),
            "imo": vessel_event.get("imo"),
        }
        coverage["vessel"] = True


def _event_snapshot(event: Mapping[str, object]) -> dict[str, object]:
    return {
        "time": event.get("time"),
        "status": event.get("status"),
        "location": event.get("location"),
        "mode": event.get("mode"),
    }


def _latest_event(events: list[dict[str, object]]) -> dict[str, object] | None:
    return max(events, key=_event_time_key) if events else None


def _next_expected_event(
    events: list[dict[str, object]],
    current: Mapping[str, object] | None,
) -> dict[str, object] | None:
    if not events:
        return None
    current_key = _event_time_key(current) if current is not None else None
    future = [event for event in events if current_key is None or _event_time_key(event) >= current_key]
    if current_key is not None and not future:
        return None
    return min(future or events, key=_event_time_key)


def _event_time_key(event: Mapping[str, object]) -> tuple[int, str]:
    value = _text(event.get("time"))
    parsed = _parse_datetime(value)
    return (int(parsed.timestamp()), value or "") if parsed is not None else (-1, value or "")


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        return parsed.replace(tzinfo=None) if parsed.tzinfo is not None else parsed
    except ValueError:
        pass
    for pattern in (
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%Y/%m/%d %H:%M",
        "%Y/%m/%d",
        "%Y%m%d %H:%M",
        "%b-%d-%Y",
    ):
        try:
            return datetime.strptime(value, pattern)
        except ValueError:
            continue
    return None


def _time_type(value: object) -> str | None:
    normalized = _text(value)
    if normalized is None:
        return None
    upper = normalized.upper()
    return upper if upper in {"ACTUAL", "EXPECTED"} else None


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


def _clean_text(value: object) -> str | None:
    text = _text(value)
    if text is None:
        return None
    cleaned = re.sub(r"<br\s*/?>", " / ", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    return " ".join(cleaned.split()) or None


def _label(value: object) -> str:
    return " ".join(str(value).strip().lower().split())


_NORMALIZERS: Mapping[Carrier, Callable[[dict[str, object], Mapping[str, Any]], dict[str, object]]] = {
    Carrier.YANG_MING: _normalize_yang_ming,
    Carrier.SM_LINE: _normalize_sm_line,
    Carrier.EVERGREEN: _normalize_evergreen,
    Carrier.HMM: _normalize_hmm,
    Carrier.COSCO: _normalize_cosco,
    Carrier.ONE: _normalize_one,
    Carrier.MAERSK: _normalize_maersk,
    Carrier.MSC: _normalize_msc,
    Carrier.WAN_HAI: _normalize_wan_hai,
}
