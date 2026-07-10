from __future__ import annotations

from enum import Enum


class Carrier(str, Enum):
    MAERSK = "MAERSK"
    CMA_CGM = "CMA_CGM"
    MSC = "MSC"


ALIASES: dict[Carrier, tuple[str, ...]] = {
    Carrier.MAERSK: (
        "MSK",
        "MSK马士基",
        "MSK 马士基",
        "MSK 马士基 BCO",
        "MSK 马士基 NVO",
        "MAERSK",
        "马士基",
    ),
    Carrier.CMA_CGM: (
        "CMA",
        "CMA达飞",
        "CMA 达飞",
        "CMA CGM",
        "CMACGM",
        "达飞",
    ),
    Carrier.MSC: (
        "MSC",
        "MSC地中海",
        "MSC 地中海",
        "地中海",
    ),
}


def normalize_carrier(value: str | None) -> Carrier | None:
    if value is None:
        return None

    compact = _compact(value)
    for carrier, aliases in ALIASES.items():
        if compact == _compact(carrier.value):
            return carrier
        for alias in aliases:
            if compact == _compact(alias):
                return carrier
    return None


def sql_aliases(carrier: Carrier) -> tuple[str, ...]:
    return ALIASES[carrier]


def parse_carrier(value: str) -> Carrier:
    normalized = normalize_carrier(value)
    if normalized is None:
        allowed = ", ".join(carrier.value for carrier in Carrier)
        raise ValueError(f"不支持的船司: {value!r}。支持: {allowed}")
    return normalized


def _compact(value: str) -> str:
    return "".join(value.upper().split())
