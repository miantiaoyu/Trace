from __future__ import annotations

import argparse
import json
import sys
from urllib.parse import quote


TRACKING_PAGE_URL = "https://www.maersk.com.cn/tracking/{container}"


class MaerskTrackingError(RuntimeError):
    pass


def fetch_tracking(container: str) -> dict[str, object]:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise MaerskTrackingError("缺少 Playwright。请在 py312 环境安装依赖并执行 playwright install chromium") from exc

    normalized_container = container.strip().upper()
    if not normalized_container:
        raise MaerskTrackingError("柜号不能为空")
    page_url = TRACKING_PAGE_URL.format(container=quote(normalized_container))

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            with page.expect_response(
                lambda response: "/synergy/tracking/" in response.url and response.status == 200,
                timeout=60_000,
            ) as response_info:
                page.goto(page_url, wait_until="domcontentloaded", timeout=30_000)
            payload = response_info.value.json()
            browser.close()
    except PlaywrightTimeoutError as exc:
        raise MaerskTrackingError("马士基追踪页在 60 秒内未返回轨迹数据") from exc

    return _validate_payload(payload, normalized_container)


def _validate_payload(payload: object, container: str) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise MaerskTrackingError("马士基追踪响应不是 JSON 对象")

    containers = payload.get("containers")
    if not isinstance(containers, list):
        raise MaerskTrackingError("马士基追踪响应缺少 containers")
    if not any(isinstance(item, dict) and str(item.get("container_num", "")).upper() == container for item in containers):
        raise MaerskTrackingError(f"马士基追踪响应未回显柜号 {container}")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="通过马士基官网追踪页读取原始 JSON 响应")
    parser.add_argument("--container", required=True, help="集装箱柜号，例如 GVTU5148354")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(fetch_tracking(args.container), ensure_ascii=False, indent=2))
    except MaerskTrackingError as exc:
        print(f"查询失败: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
