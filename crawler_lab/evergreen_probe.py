from __future__ import annotations

import argparse
import json
import sys
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


TRACKING_URL = "https://www.evergreen-shipping.cn/servlet/TDB1_CargoTracking.do"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/138.0.0.0 Safari/537.36"
REQUIRED_HEADERS = ("箱号", "货柜动态", "地点")


class TrackingPageError(RuntimeError):
    pass


class TableRowsParser(HTMLParser):
    """Collect table rows without relying on the page's visual layout."""

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


def fetch_tracking(container: str) -> dict[str, object]:
    normalized_container = container.strip().upper()
    if not normalized_container:
        raise TrackingPageError("柜号不能为空")

    payload = urlencode(
        {
            "TYPE": "CNTR",
            "SEL": "s_cntr",
            "CNTR": normalized_container,
            "NO": normalized_container,
        }
    ).encode("utf-8")
    request = Request(
        TRACKING_URL,
        data=payload,
        method="POST",
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": TRACKING_URL,
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            html = response.read().decode(response.headers.get_content_charset() or "utf-8", errors="replace")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise TrackingPageError(f"长荣查询返回 HTTP {exc.code}: {body[:300]}") from exc
    except URLError as exc:
        raise TrackingPageError(f"无法连接长荣查询页面: {exc.reason}") from exc

    parser = TableRowsParser()
    parser.feed(html)
    return _extract_tracking_rows(parser.rows, normalized_container)


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
        raise TrackingPageError("长荣查询页面未出现轨迹结果表，页面结构或访问策略可能已变化")

    header = rows[header_index]
    data_rows = [row for row in rows[header_index + 1 :] if container in " ".join(row).upper()]
    if not data_rows:
        raise TrackingPageError(f"长荣查询结果未回显柜号 {container}")

    return {
        "carrier": "EVERGREEN",
        "container": container,
        "url": TRACKING_URL,
        "headers": header,
        "rows": data_rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="查询长荣官网公开柜号追踪页面")
    parser.add_argument("--container", required=True, help="集装箱柜号，例如 EGHU9204414")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(fetch_tracking(args.container), ensure_ascii=False, indent=2))
    except TrackingPageError as exc:
        print(f"查询失败: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
