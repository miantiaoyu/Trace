from __future__ import annotations

import argparse
import json
import ssl
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_URL = "https://www.yangming.com/api/CargoTracking/GetTracking"
REFERER = "https://www.yangming.com/en/esolution/tracking/cargo_tracking"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def fetch_tracking(container: str) -> object:
    query = urlencode(
        {
            "paramTrackNo": container.upper(),
            "paramTrackPosition": "SEARCH",
            "paramRefNo": "",
        }
    )
    request = Request(
        f"{API_URL}?{query}",
        headers={
            "Accept": "application/json, text/plain, */*",
            "Referer": REFERER,
            "User-Agent": USER_AGENT,
        },
    )
    context = ssl.create_default_context()
    try:
        with urlopen(request, timeout=30, context=context) as response:
            body = response.read().decode(response.headers.get_content_charset() or "utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"连接阳明查询接口失败: {exc.reason}") from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("阳明接口未返回 JSON") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="调用阳明公开柜号查询接口并打印原始 JSON")
    parser.add_argument("--container", required=True, help="集装箱柜号，例如 YMMU7349033")
    args = parser.parse_args(argv)

    try:
        result = fetch_tracking(args.container)
    except RuntimeError as exc:
        print(f"查询失败: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
