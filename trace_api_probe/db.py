from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from trace_api_probe.carriers import Carrier, sql_aliases
from trace_api_probe.config import DbConfig


@dataclass(frozen=True)
class ShipmentSample:
    id: int
    shipping_company: str
    container_no: str
    update_time: str | None
    create_time: str | None


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
    """读取最近订单中的最新柜号，保持数据库排序并去除重复柜号。"""
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
        aliases = sql_aliases(carrier)
        placeholders = ", ".join(["%s"] * len(aliases))
        carrier_clause = f"AND shipping_company IN ({placeholders})"
        params.extend(aliases)

    limit_clause = f"LIMIT {limit}" if limit else ""
    query = f"""
        SELECT id, shipping_company, cabinet_no, update_time, create_time
        FROM trobs.po_cabinet_combination
        WHERE cabinet_no IS NOT NULL
          AND TRIM(cabinet_no) <> ''
          AND update_time >= DATE_SUB(NOW(), INTERVAL {days} DAY)
          {carrier_clause}
        ORDER BY update_time DESC, id DESC
        {limit_clause}
    """

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
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
    finally:
        connection.close()

    return _dedupe_samples(_sample_from_row(row) for row in rows)


def _sample_from_row(row: dict[str, object]) -> ShipmentSample:
    return ShipmentSample(
        id=int(row["id"]),
        shipping_company=str(row["shipping_company"]),
        container_no=str(row["cabinet_no"]).strip().upper(),
        update_time=_stringify(row.get("update_time")),
        create_time=_stringify(row.get("create_time")),
    )


def _dedupe_samples(samples: Iterable[ShipmentSample]) -> list[ShipmentSample]:
    result: list[ShipmentSample] = []
    seen: set[str] = set()
    for sample in samples:
        if sample.container_no in seen:
            continue
        seen.add(sample.container_no)
        result.append(sample)
    return result


def _stringify(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
