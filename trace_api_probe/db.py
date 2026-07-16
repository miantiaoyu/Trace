from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Iterable, Mapping

from trace_api_probe.carriers import Carrier, normalize_carrier, sql_aliases, sql_prefixes
from trace_api_probe.config import DbConfig


@dataclass(frozen=True)
class ShipmentSample:
    id: int
    shipping_company: str
    container_no: str
    update_time: str | None
    create_time: str | None
    consolidation_no: str | None = None
    erp_order_count: int = 1
    source_error: str | None = None


def fetch_latest_container(config: DbConfig, carrier: Carrier) -> ShipmentSample:
    samples = fetch_recent_shipments(config, days=3650, carrier=carrier, limit=1)
    if not samples:
        raise LookupError(f"只读库中没有找到 {carrier.value} 的可用柜号")
    return samples[0]


def fetch_recent_shipments(
    config: DbConfig,
    *,
    days: int = 7,
    carrier: Carrier | None = None,
    limit: int = 20,
) -> list[ShipmentSample]:
    """读取最近 ERP 记录并按拼柜号聚合，每个拼柜号只返回一个查询样本。"""
    if days <= 0:
        raise ValueError("查询天数必须大于 0")
    if limit < 0:
        raise ValueError("limit 不能小于 0；传 0 表示不限制")

    try:
        import pymysql
    except ImportError as exc:
        raise RuntimeError("缺少依赖 PyMySQL。请先在 py312 环境安装: pip install -r requirements.txt") from exc

    params: list[object] = []
    carrier_clause = ""
    if carrier is not None:
        conditions: list[str] = []
        aliases = sql_aliases(carrier)
        if aliases:
            placeholders = ", ".join(["%s"] * len(aliases))
            conditions.append(f"shipping_company IN ({placeholders})")
            params.extend(aliases)

        for prefix in sql_prefixes(carrier):
            conditions.append("UPPER(TRIM(shipping_company)) LIKE %s")
            params.append(f"{prefix.upper()}%")

        carrier_clause = f"AND ({' OR '.join(conditions)})"

    query = f"""
        SELECT id, shipping_company, cabinet_no, cabinet_combination_number, update_time, create_time
        FROM trobs.po_cabinet_combination
        WHERE cabinet_no IS NOT NULL
          AND TRIM(cabinet_no) <> ''
          AND cabinet_combination_number IS NOT NULL
          AND TRIM(cabinet_combination_number) <> ''
          AND update_time >= DATE_SUB(NOW(), INTERVAL {days} DAY)
          {carrier_clause}
        ORDER BY update_time DESC, id DESC
    """

    connection = _connect(config, pymysql)
    try:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
    finally:
        connection.close()

    grouped = _group_samples(rows)
    return grouped if limit == 0 else grouped[:limit]


def fetch_pending_shipments(
    source_config: DbConfig,
    target_config: DbConfig,
    *,
    environment: str,
    days: int = 7,
    carrier: Carrier | None = None,
    limit: int = 20,
) -> list[ShipmentSample]:
    """返回新拼柜号及尚未在最终卸船港完成的到期记录。"""
    recent_candidates = fetch_recent_shipments(source_config, days=days, carrier=carrier, limit=0)
    pending_keys = _fetch_due_headway_keys(target_config, environment)
    pending_key_set = set(pending_keys)
    historical_candidates = _fetch_shipments_by_consolidation_numbers(source_config, pending_keys, carrier=carrier)
    # Due records must not starve behind a continuous stream of new ERP rows when limit is finite.
    candidates = _merge_samples(historical_candidates, recent_candidates)
    states = _fetch_headway_states(
        target_config,
        environment,
        [sample.consolidation_no for sample in candidates],
    )
    pending = []
    for sample in candidates:
        key = sample.consolidation_no
        state = states.get(key) if key else None
        if state is None:
            pending.append(sample)
            continue
        if key not in pending_key_set:
            continue
        if bool(state.get("is_arrived_destination")):
            continue
        next_query_at = state.get("next_query_at")
        if next_query_at is None or _as_datetime(next_query_at) <= datetime.now():
            pending.append(sample)
    return pending if limit == 0 else pending[:limit]


def _sample_from_row(row: dict[str, object]) -> ShipmentSample:
    container_no = "".join(str(row["cabinet_no"]).upper().split())
    consolidation_no = _clean_identifier(row.get("cabinet_combination_number")) or container_no
    return ShipmentSample(
        id=int(row["id"]),
        shipping_company=str(row["shipping_company"]),
        container_no=container_no,
        update_time=_stringify(row.get("update_time")),
        create_time=_stringify(row.get("create_time")),
        consolidation_no=consolidation_no,
    )


def _group_samples(rows: Iterable[dict[str, object]]) -> list[ShipmentSample]:
    groups: dict[str, list[ShipmentSample]] = defaultdict(list)
    for row in rows:
        sample = _sample_from_row(row)
        if sample.consolidation_no:
            groups[sample.consolidation_no].append(sample)

    result: list[ShipmentSample] = []
    for consolidation_no, samples in groups.items():
        containers = {sample.container_no for sample in samples}
        carriers = {normalize_carrier(sample.shipping_company) or sample.shipping_company for sample in samples}
        source_error = None
        if len(containers) > 1:
            source_error = f"拼柜号 {consolidation_no} 对应多个柜号: {', '.join(sorted(containers))}"
        elif len(carriers) > 1:
            source_error = f"拼柜号 {consolidation_no} 对应多个船司"
        result.append(
            replace(
                samples[0],
                consolidation_no=consolidation_no,
                erp_order_count=len(samples),
                source_error=source_error,
            )
        )
    return result


def _fetch_headway_states(config: DbConfig, environment: str, consolidation_numbers: list[str | None]) -> dict[str, Mapping[str, object]]:
    keys = [key for key in consolidation_numbers if key]
    if not keys:
        return {}
    try:
        import pymysql
    except ImportError as exc:
        raise RuntimeError("缺少依赖 PyMySQL。请先在 py312 环境安装: pip install -r requirements.txt") from exc
    placeholders = ", ".join(["%s"] * len(keys))
    query = f"""
        SELECT consolidation_no, is_arrived_destination, next_query_at
        FROM oms.headway
        WHERE environment = %s AND consolidation_no IN ({placeholders})
    """
    connection = _connect(config, pymysql)
    try:
        with connection.cursor() as cursor:
            cursor.execute(query, [environment, *keys])
            rows = cursor.fetchall()
    finally:
        connection.close()
    return {str(row["consolidation_no"]): row for row in rows}


def _fetch_due_headway_keys(config: DbConfig, environment: str) -> list[str]:
    try:
        import pymysql
    except ImportError as exc:
        raise RuntimeError("缺少依赖 PyMySQL。请先在 py312 环境安装: pip install -r requirements.txt") from exc
    query = f"""
        SELECT consolidation_no
        FROM oms.headway
        WHERE environment = %s
          AND is_arrived_destination = 0
          AND (next_query_at IS NULL OR next_query_at <= NOW())
        ORDER BY next_query_at IS NOT NULL, next_query_at, id
    """
    connection = _connect(config, pymysql)
    try:
        with connection.cursor() as cursor:
            cursor.execute(query, [environment])
            rows = cursor.fetchall()
    finally:
        connection.close()
    return [str(row["consolidation_no"]) for row in rows if row.get("consolidation_no")]


def _fetch_shipments_by_consolidation_numbers(
    config: DbConfig,
    consolidation_numbers: list[str],
    *,
    carrier: Carrier | None,
) -> list[ShipmentSample]:
    if not consolidation_numbers:
        return []
    try:
        import pymysql
    except ImportError as exc:
        raise RuntimeError("缺少依赖 PyMySQL。请先在 py312 环境安装: pip install -r requirements.txt") from exc
    placeholders = ", ".join(["%s"] * len(consolidation_numbers))
    query = f"""
        SELECT id, shipping_company, cabinet_no, cabinet_combination_number, update_time, create_time
        FROM trobs.po_cabinet_combination
        WHERE cabinet_combination_number IN ({placeholders})
          AND cabinet_no IS NOT NULL
          AND TRIM(cabinet_no) <> ''
        ORDER BY update_time DESC, id DESC
    """
    connection = _connect(config, pymysql)
    try:
        with connection.cursor() as cursor:
            cursor.execute(query, consolidation_numbers)
            rows = cursor.fetchall()
    finally:
        connection.close()
    samples = _group_samples(rows)
    if carrier is None:
        return samples
    return [sample for sample in samples if normalize_carrier(sample.shipping_company) == carrier]


def _merge_samples(*groups: list[ShipmentSample]) -> list[ShipmentSample]:
    result: list[ShipmentSample] = []
    seen: set[str] = set()
    for group in groups:
        for sample in group:
            key = sample.consolidation_no or sample.container_no
            if key in seen:
                continue
            seen.add(key)
            result.append(sample)
    return result


def _connect(config: DbConfig, pymysql: object) -> object:
    return pymysql.connect(
        host=config.host,
        port=config.port,
        user=config.user,
        password=config.password,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        read_timeout=15,
        write_timeout=15,
        connect_timeout=10,
    )


def _clean_identifier(value: object) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split()).strip()
    return text or None


def _as_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00").replace(" ", "T")).replace(tzinfo=None)


def _stringify(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
