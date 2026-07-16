from __future__ import annotations

import argparse
import json
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from crawler_lab.html_tables import extract_table_rows


TRACKING_URL = "https://www.evergreen-shipping.cn/servlet/TDB1_CargoTracking.do"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/138.0.0.0 Safari/537.36"
TRACKING_HEADERS = ("箱号", "柜型", "日期", "货柜动态", "地点", "船名 航次", "Method", "VGM")
REQUIRED_HEADERS = ("箱号", "货柜动态", "地点")


class TrackingPageError(RuntimeError):
    pass


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

    return _extract_tracking_rows(extract_table_rows(html), normalized_container)


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

    data_rows = [row for row in rows[header_index + 1 :] if container in " ".join(row).upper()]
    if not data_rows:
        raise TrackingPageError(f"长荣查询结果未回显柜号 {container}")

    result = {
        "carrier": "EVERGREEN",
        "container": container,
        "url": TRACKING_URL,
        "headers": list(TRACKING_HEADERS),
        "rows": data_rows,
    }
    eta_match = re.search(
        r"预计抵达时间\s*[:：]\s*([A-Z]{3}-\d{2}-\d{4})",
        " ".join(" ".join(row) for row in rows),
        flags=re.IGNORECASE,
    )
    if eta_match:
        result["destination_eta"] = eta_match.group(1).upper()
    return result


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
