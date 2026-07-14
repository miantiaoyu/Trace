from __future__ import annotations

from enum import Enum


class Carrier(str, Enum):
    MAERSK = "MAERSK"
    CMA_CGM = "CMA_CGM"
    MSC = "MSC"
    YANG_MING = "YANG_MING"
    SM_LINE = "SM_LINE"
    EVERGREEN = "EVERGREEN"
    COSCO = "COSCO"
    ONE = "ONE"
    WAN_HAI = "WAN_HAI"
    APL = "APL"
    HMM = "HMM"
    OOCL = "OOCL"
    ZIM = "ZIM"
    TS_LINES = "TS_LINES"
    HAPAG_LLOYD = "HAPAG_LLOYD"
    KMTC = "KMTC"
    SEA_LEAD = "SEA_LEAD"


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
    Carrier.YANG_MING: ("YML", "YML阳明", "YML 阳明", "阳明", "YANGMING", "YANG MING"),
    Carrier.SM_LINE: ("SML", "SML森罗商船", "SML 森罗商船", "SM LINE", "SMLine", "森罗商船"),
    Carrier.EVERGREEN: ("EMC", "EMC长荣", "EMC 长荣", "EVERGREEN", "长荣"),
    Carrier.COSCO: ("COSCO", "COSCO中远", "COSCO 中远", "中远", "中远海运"),
    Carrier.ONE: ("ONE", "ONE海洋网联", "ONE 海洋网联", "海洋网联"),
    Carrier.WAN_HAI: ("WANHAI", "WAN HAI", "WANHAI万海", "WAN HAI 万海", "万海"),
    Carrier.APL: ("APL", "APL美总", "APL 美总", "美总"),
    Carrier.HMM: ("HMM", "HMM韩新", "HMM 韩新", "韩新", "HMM BCO", "HMM NVO"),
    Carrier.OOCL: (
        "OOCL",
        "OOCL东方海外",
        "OOCL 东方海外",
        "OOCL 东方海外 BCO",
        "OOCL 东方海外 NVO",
        "东方海外",
    ),
    Carrier.ZIM: ("ZIM", "ZIM以星", "ZIM 以星", "ZIM 以星 BCO", "ZIM 以星 NVO", "以星"),
    Carrier.TS_LINES: ("TS", "TS LINES", "TS Lines", "TS Lines正达", "正达"),
    Carrier.HAPAG_LLOYD: ("HPL", "HPL赫伯罗特", "HPL 赫伯罗特", "HAPAG-LLOYD", "HAPAG LLOYD", "赫伯罗特"),
    Carrier.KMTC: ("KMTC", "KMTC高丽", "KMTC 高丽", "高丽"),
    Carrier.SEA_LEAD: ("SLS", "SLS海领", "SLS 海领", "SEALEAD", "SEA LEAD", "海领"),
}


SQL_PREFIXES: dict[Carrier, tuple[str, ...]] = {
    # 只读库中 HMM 的中文说明存在历史字符集乱码，例如 "HMM ş«ĐÂ BCO"。
    # HMM 前缀本身稳定，使用前缀作为数据库筛选的兼容条件。
    Carrier.HMM: ("HMM",),
}


def normalize_carrier(value: str | None) -> Carrier | None:
    if value is None:
        return None

    compact = _compact(value)
    if compact.startswith("HMM"):
        return Carrier.HMM

    for carrier, aliases in ALIASES.items():
        if compact == _compact(carrier.value):
            return carrier
        for alias in aliases:
            if compact == _compact(alias):
                return carrier
    return None


def sql_aliases(carrier: Carrier) -> tuple[str, ...]:
    return ALIASES[carrier]


def sql_prefixes(carrier: Carrier) -> tuple[str, ...]:
    return SQL_PREFIXES.get(carrier, ())


def parse_carrier(value: str) -> Carrier:
    normalized = normalize_carrier(value)
    if normalized is None:
        allowed = ", ".join(carrier.value for carrier in Carrier)
        raise ValueError(f"不支持的船司: {value!r}。支持: {allowed}")
    return normalized


def _compact(value: str) -> str:
    return "".join(value.upper().split())
