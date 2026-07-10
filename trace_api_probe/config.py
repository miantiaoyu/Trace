from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DbConfig:
    host: str
    port: int
    user: str
    password: str


def read_db_config(path: Path) -> DbConfig:
    data = _read_simple_yaml(path)
    missing = [key for key in ("host", "port", "user", "password") if not data.get(key)]
    if missing:
        raise ValueError(f"数据库配置缺少字段: {', '.join(missing)}")

    return DbConfig(
        host=data["host"],
        port=int(data["port"]),
        user=data["user"],
        password=data["password"],
    )


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
