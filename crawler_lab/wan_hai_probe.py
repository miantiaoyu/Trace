from __future__ import annotations

import argparse
import json
import sys
from html.parser import HTMLParser
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


TRACKING_ENTRY_URL = "https://www.wanhai.com/views/cargoTrack/CargoTrack.xhtml?file_num=65580"
TRACKING_FORM_URL = "https://www.wanhai.com/views/cargo_track_v2/tracking_query.xhtml"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/138.0.0.0 Safari/537.36"
REQUIRED_HEADERS = (
    "Ctnr No.",
    "Ctnr Date",
    "Status Name",
    "Ctnr Depot Name",
    "Voyage",
    "Vessel Name",
    "More detail",
)
BOOKING_SUMMARY_HEADERS = (
    "BL no.",
    "Oboard Date",
    "Voyage",
    "Vessel Name",
    "More detail",
)


class WanHaiTrackingError(RuntimeError):
    pass


class TableRowsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._row_stack: list[list[str]] = []
        self._cell_stack: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
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
        elif tag == "tr" and self._row_stack:
            row = self._row_stack.pop()
            if row:
                self.rows.append(row)


def fetch_tracking(
    container: str,
    *,
    headless: bool = False,
    browser_channel: str = "chromium",
) -> dict[str, object]:
    normalized_container = container.strip().upper()
    if not normalized_container:
        raise WanHaiTrackingError("柜号不能为空")

    cookie_header, viewstate = _bootstrap_session(
        headless=headless,
        browser_channel=browser_channel,
    )
    html, result_url = _submit_tracking_query(
        cookie_header=cookie_header,
        viewstate=viewstate,
        cargo_type="1",
        query_value=normalized_container,
    )

    parser = TableRowsParser()
    parser.feed(html)
    result = _extract_tracking_rows(parser.rows, normalized_container)
    result["query_url"] = TRACKING_FORM_URL
    result["result_url"] = result_url

    references = _extract_reference_numbers(result["rows"])
    if references:
        reference = references[0]
        summary_html, summary_url = _submit_tracking_query(
            cookie_header=cookie_header,
            viewstate=viewstate,
            cargo_type="2",
            query_value=reference,
        )
        summary_parser = TableRowsParser()
        summary_parser.feed(summary_html)
        result["booking_summary"] = _extract_booking_summary_rows(summary_parser.rows, reference)
        result["booking_summary_url"] = summary_url

    return result


def _submit_tracking_query(
    *,
    cookie_header: str,
    viewstate: str,
    cargo_type: str,
    query_value: str,
) -> tuple[str, str]:
    payload = urlencode(
        {
            "cargoTrackV2Bean": "cargoTrackV2Bean",
            "cargoType": cargo_type,
            "q_ref_no1": query_value,
            "q_ref_no2": "",
            "q_ref_no3": "",
            "q_ref_no4": "",
            "q_ref_no5": "",
            "q_ref_no6": "",
            "q_ref_no7": "",
            "q_ref_no8": "",
            "q_ref_no9": "",
            "q_ref_no10": "",
            "Query": "Query",
            "skipValidate": "true",
            "javax.faces.ViewState": viewstate,
        }
    ).encode("utf-8")
    request = Request(
        TRACKING_FORM_URL,
        data=payload,
        method="POST",
        headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Content-Type": "application/x-www-form-urlencoded",
            "Cookie": cookie_header,
            "Origin": "https://www.wanhai.com",
            "Referer": TRACKING_FORM_URL,
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            html = response.read().decode("utf-8", errors="replace")
            result_url = response.geturl()
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise WanHaiTrackingError(f"万海查询返回 HTTP {exc.code}: {body[:300]}") from exc
    except URLError as exc:
        raise WanHaiTrackingError(f"无法连接万海查询页面: {exc.reason}") from exc

    return html, result_url


def _bootstrap_session(*, headless: bool, browser_channel: str) -> tuple[str, str]:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise WanHaiTrackingError("缺少 Playwright。请在 py312 环境安装依赖并执行 playwright install chromium") from exc

    launch_kwargs: dict[str, object] = {"headless": headless}
    if browser_channel != "chromium":
        launch_kwargs["channel"] = browser_channel

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(**launch_kwargs)
            context = browser.new_context()
            page = context.new_page()
            try:
                for wait_ms in (8_000, 3_000):
                    page.goto(TRACKING_ENTRY_URL, wait_until="domcontentloaded", timeout=60_000)
                    page.wait_for_timeout(wait_ms)
                if "tracking_query.xhtml" not in page.url:
                    raise WanHaiTrackingError(f"万海预热后未进入查询页，当前地址为 {page.url}")
                viewstate = page.locator(
                    'form#cargoTrackV2Bean input[name="javax.faces.ViewState"]'
                ).input_value()
                cookies = context.cookies(urls=["https://www.wanhai.com"])
            finally:
                browser.close()
    except PlaywrightTimeoutError as exc:
        raise WanHaiTrackingError("万海官网在 60 秒内未完成会话预热") from exc

    cookie_header = "; ".join(
        f"{item['name']}={item['value']}"
        for item in cookies
        if str(item.get("domain", "")).endswith("wanhai.com")
    )
    if not cookie_header:
        raise WanHaiTrackingError("万海预热成功，但未拿到可用会话 Cookie")
    if not viewstate:
        raise WanHaiTrackingError("万海查询页缺少 javax.faces.ViewState")
    return cookie_header, viewstate


def _extract_tracking_rows(rows: list[list[str]], container: str) -> dict[str, object]:
    header_index = next(
        (
            index
            for index, row in enumerate(rows)
            if all(header in " ".join(row) for header in REQUIRED_HEADERS)
        ),
        None,
    )
    if header_index is None:
        raise WanHaiTrackingError("万海结果页未出现集装箱列表表头，页面结构或访问策略可能已变化")

    header = rows[header_index]
    data_rows = [row for row in rows[header_index + 1 :] if container in " ".join(row).upper()]
    if not data_rows:
        raise WanHaiTrackingError(f"万海查询结果未回显柜号 {container}")

    return {
        "carrier": "WAN_HAI",
        "container": container,
        "headers": header,
        "rows": data_rows,
    }


def _extract_reference_numbers(rows: object) -> list[str]:
    references: list[str] = []
    if not isinstance(rows, list):
        return references
    for row in rows:
        if not isinstance(row, list) or not row:
            continue
        candidates = re.findall(r"\b[A-Z0-9]{8,18}\b", str(row[-1]).upper())
        for candidate in candidates:
            if candidate not in references and "DATA" not in candidate:
                references.append(candidate)
    return references


def _extract_booking_summary_rows(rows: list[list[str]], reference: str) -> dict[str, object]:
    header_index = next(
        (
            index
            for index, row in enumerate(rows)
            if all(header in " ".join(row) for header in BOOKING_SUMMARY_HEADERS)
        ),
        None,
    )
    if header_index is None:
        raise WanHaiTrackingError("万海 Booking 摘要页未出现结果表头，页面结构可能已变化")

    header = rows[header_index]
    data_rows = [row for row in rows[header_index + 1 :] if reference in " ".join(row).upper()]
    if not data_rows:
        raise WanHaiTrackingError(f"万海 Booking 摘要结果未回显编号 {reference}")

    return {
        "reference": reference,
        "headers": header,
        "rows": data_rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="通过万海官网预热会话后提交表单查询柜号")
    parser.add_argument("--container", required=True, help="集装箱柜号，例如 WHSU6376250")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="使用无界面浏览器运行。默认使用可见浏览器以贴近人工查询流程。",
    )
    parser.add_argument(
        "--browser-channel",
        default="chromium",
        choices=("chromium", "msedge"),
        help="Playwright 浏览器通道，默认 chromium；如需系统 Edge 可传 msedge。",
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
    except WanHaiTrackingError as exc:
        print(f"查询失败: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
