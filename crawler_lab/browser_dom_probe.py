from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from urllib.parse import quote


@dataclass(frozen=True)
class DomProviderSpec:
    url_template: str
    required_terms: tuple[str, ...]


SPECS = {
    "COSCO": DomProviderSpec(
        "https://elines.coscoshipping.com/scct/public/ct/base?lang=zh&trackingType=containerNumber&number={container}",
        ("动态节点", "时间", "位置", "运输方式"),
    ),
    "ONE": DomProviderSpec(
        "https://ecomm.one-line.com/one-ecom/manage-shipment/cargo-tracking?trakNoParam={container}",
        ("Gate In to Outbound Terminal",),
    ),
}


class DomTrackingError(RuntimeError):
    pass


def fetch_tracking(carrier: str, container: str) -> dict[str, object]:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise DomTrackingError("缺少 Playwright。请在 py312 环境安装 playwright 并执行 playwright install chromium") from exc

    normalized_carrier = carrier.upper()
    if normalized_carrier not in SPECS:
        raise DomTrackingError(f"不支持的 DOM Provider: {carrier}")
    normalized_container = container.strip().upper()
    spec = SPECS[normalized_carrier]
    url = spec.url_template.format(container=quote(normalized_container))

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            rows_locator = page.locator("tr")
            page.wait_for_function("() => document.querySelectorAll('tr').length >= 2", timeout=20_000)
            body = page.locator("body").inner_text()
            rows = [split_row(text) for text in rows_locator.all_inner_texts()]
            browser.close()
    except PlaywrightTimeoutError as exc:
        raise DomTrackingError(f"{normalized_carrier} 查询页在 20 秒内未出现结果表") from exc

    if normalized_container not in body.upper():
        raise DomTrackingError(f"{normalized_carrier} 页面结果未回显请求柜号 {normalized_container}")
    validate_contract(rows, spec.required_terms, normalized_carrier)
    if len(rows) < 2:
        raise DomTrackingError(f"{normalized_carrier} 页面未返回数据行")

    return {"carrier": normalized_carrier, "container": normalized_container, "url": url, "rows": rows}


def split_row(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def validate_contract(rows: list[list[str]], expected: tuple[str, ...], carrier: str) -> None:
    content = " ".join(value for row in rows for value in row)
    missing = [label for label in expected if label not in content]
    if missing:
        raise DomTrackingError(f"{carrier} 页面结果结构变化，缺少: {', '.join(missing)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="读取 COSCO/ONE 官方追踪页的结构化 DOM 表格")
    parser.add_argument("--carrier", required=True, choices=sorted(SPECS))
    parser.add_argument("--container", required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(fetch_tracking(args.carrier, args.container), ensure_ascii=False, indent=2))
    except DomTrackingError as exc:
        print(f"查询失败: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
