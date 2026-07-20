from __future__ import annotations

import argparse
import json
import os
import sys

from trace_api_probe.providers.html_tables import extract_tables
from trace_api_probe.providers.browser_session import BrowserPageSession


TRACKING_PAGE_URL = "https://www.hmm21.com/e-service/general/trackNTrace/TrackNTrace.do"
TRACKING_RESPONSE_PATH = "/e-service/general/trackNTrace/selectTrackNTrace.do"
CONTAINER_INPUT_SELECTOR = 'input[name="srchCntrNo1"]'
SEARCH_BUTTON_SELECTOR = 'button[onclick="search()"]'
TRACKING_RESPONSE_TIMEOUT_MS = 120_000


class HmmTrackingError(RuntimeError):
    pass


def fetch_tracking(
    container: str,
    *,
    headless: bool = False,
    browser_channel: str = "chromium",
    page: object | None = None,
) -> dict[str, object]:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    except ImportError as exc:
        raise HmmTrackingError("缺少 Playwright。请在运行环境安装依赖并执行 playwright install chromium") from exc

    normalized_container = container.strip().upper()
    if not normalized_container:
        raise HmmTrackingError("柜号不能为空")
    if headless:
        raise HmmTrackingError(
            "HMM 官网当前不支持无头浏览器查询。请不要传 --headless；Linux 服务器请使用 Xvfb 提供虚拟显示器。"
        )
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        raise HmmTrackingError("HMM 需要有界浏览器。Linux 服务器请使用 xvfb-run -a 启动命令。")

    try:
        if page is None:
            with BrowserPageSession(
                headless=False,
                browser_channel=browser_channel,
                viewport={"width": 1440, "height": 900},
            ) as session:
                raw_html = _fetch_html(session.page, normalized_container)
        else:
            raw_html = _fetch_html(page, normalized_container)
    except PlaywrightTimeoutError as exc:
        raise HmmTrackingError("HMM 官网在 120 秒内未返回追踪结果") from exc
    except PlaywrightError as exc:
        raise HmmTrackingError(f"HMM 浏览器启动或页面访问失败: {exc}") from exc

    return _build_result(raw_html, normalized_container)


def _fetch_html(page: object, container: str) -> str:
    page.goto(TRACKING_PAGE_URL, wait_until="domcontentloaded", timeout=60_000)
    page.locator(CONTAINER_INPUT_SELECTOR).wait_for(state="visible", timeout=20_000)
    page.locator(CONTAINER_INPUT_SELECTOR).fill(container)
    with page.expect_response(
        lambda response: TRACKING_RESPONSE_PATH in response.url
        and response.request.method == "POST"
        and response.status == 200,
        timeout=TRACKING_RESPONSE_TIMEOUT_MS,
    ) as response_info:
        page.locator(SEARCH_BUTTON_SELECTOR).click()
    raw_html = response_info.value.text()
    if "TRACKING RESULT" not in raw_html.upper():
        page.wait_for_timeout(1_000)
        body_text = page.locator("body").inner_text()
        if "YOUR ACCESS IS BLOCKED BY OUR FIREWALL" in body_text.upper():
            raise HmmTrackingError("HMM 防火墙已拦截当前公网出口 IP，请联系 HMM 申请解封或白名单")
    return raw_html


def _build_result(raw_html: str, container: str) -> dict[str, object]:
    normalized_html = raw_html.upper()
    if "YOUR ACCESS IS BLOCKED BY OUR FIREWALL" in normalized_html:
        raise HmmTrackingError("HMM 防火墙已拦截当前公网出口 IP，请联系 HMM 申请解封或白名单")
    if "TRACKING RESULT" not in normalized_html:
        raise HmmTrackingError("HMM 追踪响应缺少 Tracking Result，页面结构或访问策略可能已变化")
    if container not in normalized_html:
        raise HmmTrackingError(f"HMM 追踪响应未回显柜号 {container}")
    if "SHIPMENT PROGRESS" not in normalized_html:
        raise HmmTrackingError("HMM 追踪响应缺少 Shipment Progress，无法确认轨迹数据")

    tables = extract_tables(raw_html)
    table_headers = [table[0] for table in tables if table]
    sections = {
        "route": _has_headers(table_headers, {"origin", "destination"}),
        "container_summary": _has_headers(table_headers, {"container no.", "movement"}),
        "vessel_legs": _has_headers(table_headers, {"vessel / voyage", "loading port", "discharging port"}),
        "events": _has_event_headers(table_headers),
    }
    if not sections["container_summary"]:
        raise HmmTrackingError("HMM 追踪响应未识别到柜信息表，页面结构可能已变化")
    return {
        "carrier": "HMM",
        "container": container,
        "query_url": TRACKING_PAGE_URL,
        "result_endpoint": TRACKING_RESPONSE_PATH,
        "tables": tables,
        "parse_diagnostics": {
            "table_count": len(tables),
            "table_headers": table_headers,
            "sections": sections,
        },
        "raw_html": raw_html,
    }


def _has_headers(headers: list[list[str]], required: set[str]) -> bool:
    return any(required.issubset({_label(value) for value in header}) for header in headers)


def _has_event_headers(headers: list[list[str]]) -> bool:
    for header in headers:
        labels = {_label(value) for value in header}
        if {"location", "status description"}.issubset(labels) and (
            {"date", "time"}.issubset(labels) or "date / time" in labels
        ):
            return True
    return False


def _label(value: object) -> str:
    return " ".join(str(value).strip().lower().split())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="通过 HMM 官网 Track & Trace 页面查询柜号")
    parser.add_argument("--container", required=True, help="集装箱柜号，例如 HMMU4706485")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="HMM 当前不支持无头模式；传入将返回明确错误。",
    )
    parser.add_argument(
        "--browser-channel",
        default="chromium",
        choices=("chromium", "msedge"),
        help="Playwright 浏览器通道，默认 chromium。",
    )
    args = parser.parse_args(argv)
    try:
        print(
            json.dumps(
                fetch_tracking(
                    args.container,
                    headless=args.headless,
                    browser_channel=args.browser_channel,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
    except HmmTrackingError as exc:
        print(f"查询失败: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
