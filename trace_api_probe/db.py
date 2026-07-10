from __future__ import annotations

from dataclasses import dataclass

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
    try:
        import pymysql
    except ImportError as exc:
        raise RuntimeError("缺少依赖 PyMySQL。请先在 py312 环境安装: pip install -r requirements.txt") from exc

    aliases = sql_aliases(carrier)
    placeholders = ", ".join(["%s"] * len(aliases))
    query = f"""
        SELECT id, shipping_company, cabinet_no, update_time, create_time
        FROM trobs.po_cabinet_combination
        WHERE cabinet_no IS NOT NULL
          AND cabinet_no <> ''
          AND shipping_company IN ({placeholders})
        ORDER BY update_time DESC, id DESC
        LIMIT 1
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
            cursor.execute(query, aliases)
            row = cursor.fetchone()
    finally:
        connection.close()

    if row is None:
        raise LookupError(f"只读库中没有找到 {carrier.value} 的可用柜号")

    return ShipmentSample(
        id=int(row["id"]),
        shipping_company=str(row["shipping_company"]),
        container_no=str(row["cabinet_no"]),
        update_time=_stringify(row.get("update_time")),
        create_time=_stringify(row.get("create_time")),
    )


def _stringify(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
