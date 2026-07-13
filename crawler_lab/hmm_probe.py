from __future__ import annotations

import argparse
import json
import os
import sys
from html.parser import HTMLParser


TRACKING_PAGE_URL = "https://www.hmm21.com/e-service/general/trackNTrace/TrackNTrace.do"
TRACKING_RESPONSE_PATH = "/e-service/general/trackNTrace/selectTrackNTrace.do"
CONTAINER_INPUT_SELECTOR = 'input[name="srchCntrNo1"]'
SEARCH_BUTTON_SELECTOR = 'button[onclick="search()"]'


class HmmTrackingError(RuntimeError):
    pass


class ResultTablesParser(HTMLParser):
    """Extract tables from HMM's official HTML fragment without visual scraping."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._table_stack: list[list[list[str]]] = []
        self._row_stack: list[list[str]] = []
        self._cell_stack: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._table_stack.append([])
        elif tag == "tr" and self._table_stack:
            self._row_stack.append([])
        elif tag in {"td", "th"} and self._row_stack:
            self._cell_stack.append([])

    def handle_data(self, data: str) -> None:
        if self._cell_stack:
            self._cell_stack[-1].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._cell_stack and self._row_stack:
            value = " ".join("".join(self._cell_stack.pop()).split())
            self._row_stack[-1].append(value)
        elif tag == "tr" and self._row_stack and self._table_stack:
            row = self._row_stack.pop()
            if row:
                self._table_stack[-1].append(row)
        elif tag == "table" and self._table_stack:
            table = self._table_stack.pop()
            if table:
                self.tables.append(table)


def fetch_tracking(
    container: str,
    *,
    headless: bool = False,
    browser_channel: str = "chromium",
) -> dict[str, object]:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
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

    launch_kwargs: dict[str, object] = {"headless": False}
    if browser_channel != "chromium":
        launch_kwargs["channel"] = browser_channel

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(**launch_kwargs)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            try:
                page.goto(TRACKING_PAGE_URL, wait_until="domcontentloaded", timeout=60_000)
                page.locator(CONTAINER_INPUT_SELECTOR).wait_for(state="visible", timeout=20_000)
                page.locator(CONTAINER_INPUT_SELECTOR).fill(normalized_container)
                with page.expect_response(
                    lambda response: TRACKING_RESPONSE_PATH in response.url
                    and response.request.method == "POST"
                    and response.status == 200,
                    timeout=60_000,
                ) as response_info:
                    page.locator(SEARCH_BUTTON_SELECTOR).click()
                raw_html = response_info.value.text()
            finally:
                browser.close()
    except PlaywrightTimeoutError as exc:
        raise HmmTrackingError("HMM 官网在 60 秒内未返回追踪结果") from exc
    except PlaywrightError as exc:
        raise HmmTrackingError(f"HMM 浏览器启动或页面访问失败: {exc}") from exc

    return _build_result(raw_html, normalized_container)


def _build_result(raw_html: str, container: str) -> dict[str, object]:
    normalized_html = raw_html.upper()
    if "TRACKING RESULT" not in normalized_html:
        raise HmmTrackingError("HMM 追踪响应缺少 Tracking Result，页面结构或访问策略可能已变化")
    if container not in normalized_html:
        raise HmmTrackingError(f"HMM 追踪响应未回显柜号 {container}")
    if "SHIPMENT PROGRESS" not in normalized_html:
        raise HmmTrackingError("HMM 追踪响应缺少 Shipment Progress，无法确认轨迹数据")

    parser = ResultTablesParser()
    parser.feed(raw_html)
    return {
        "carrier": "HMM",
        "container": container,
        "query_url": TRACKING_PAGE_URL,
        "result_endpoint": TRACKING_RESPONSE_PATH,
        "tables": parser.tables,
        "raw_html": raw_html,
    }


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
