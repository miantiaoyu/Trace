from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class DbConfig:
    host: str
    port: int
    user: str
    password: str


def read_db_config(path: Path) -> DbConfig:
    data = _read_simple_yaml(path)
    user = data.get("user") or data.get("username")
    password = data.get("password")
    host = data.get("host")
    port = data.get("port")
    if not host and data.get("url"):
        host, parsed_port = _parse_mysql_jdbc_url(data["url"])
        port = port or str(parsed_port)

    missing = [
        key
        for key, value in (("host", host), ("port", port), ("user/username", user), ("password", password))
        if not value
    ]
    if missing:
        raise ValueError(f"数据库配置缺少字段: {', '.join(missing)}")

    return DbConfig(
        host=str(host),
        port=int(str(port)),
        user=str(user),
        password=str(password),
    )


def _parse_mysql_jdbc_url(value: str) -> tuple[str, int]:
    if not value.startswith("jdbc:"):
        raise ValueError("数据库 url 必须是 jdbc:mysql:// 格式")
    parsed = urlsplit(value.removeprefix("jdbc:"))
    if parsed.scheme != "mysql" or not parsed.hostname:
        raise ValueError("数据库 url 必须是 jdbc:mysql:// 格式")
    try:
        port = parsed.port or 3306
    except ValueError as exc:
        raise ValueError("数据库 url 的端口无效") from exc
    return parsed.hostname, port


def _read_simple_yaml(path: Path) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"未找到数据库配置文件: {path}")

    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"{path} 第 {line_number} 行不是 key: value 格式")
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values
