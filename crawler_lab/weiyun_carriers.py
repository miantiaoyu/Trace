from __future__ import annotations

import argparse
import json

from crawler_lab.weiyun_api_probe import request_json


DEFAULT_KEYWORDS = (
    "MAERSK",
    "MSK",
    "马士基",
    "CMA",
    "达飞",
    "MSC",
    "地中海",
    "COSCO",
    "中远",
    "EVERGREEN",
    "长荣",
    "HMM",
    "韩新",
    "HAPAG",
    "赫伯",
    "KMTC",
    "高丽",
    "ONE",
    "海洋网联",
    "OOCL",
    "东方海外",
    "SEALEAD",
    "海领",
    "SM LINE",
    "森罗",
    "WAN HAI",
    "万海",
    "YANG MING",
    "阳明",
    "ZIM",
    "以星",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="读取维运网船司来源表")
    parser.add_argument("--all", action="store_true", help="打印全部船司")
    parser.add_argument("--keyword", action="append", help="按关键词过滤，可重复传入")
    args = parser.parse_args()

    response = request_json("GET", "/cargoTracking/getCarrierSource")
    if not isinstance(response, dict) or not response.get("success"):
        print(json.dumps(response, ensure_ascii=False, indent=2))
        return 1

    carriers = response.get("result") or []
    keywords = args.keyword or list(DEFAULT_KEYWORDS)
    filtered = carriers if args.all else [carrier for carrier in carriers if matches(carrier, keywords)]

    print(json.dumps(filtered, ensure_ascii=False, indent=2))
    print(f"count={len(filtered)}")
    return 0


def matches(carrier: object, keywords: list[str]) -> bool:
    text = json.dumps(carrier, ensure_ascii=False).lower()
    return any(keyword.lower() in text for keyword in keywords)


if __name__ == "__main__":
    raise SystemExit(main())
