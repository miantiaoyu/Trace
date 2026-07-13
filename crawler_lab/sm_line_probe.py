from __future__ import annotations

import argparse
import json
import sys
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener


BASE_URL = "https://esvc.smlines.com/smline/"
PAGE_PATH = "CUP_HOM_3301.do"
API_PATH = "CUP_HOM_3301GS.do"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/138.0.0.0 Safari/537.36"


def fetch_tracking(container: str, locale: str = "zh") -> dict[str, object]:
    normalized_container = container.strip().upper()
    page_url = f"{BASE_URL}{PAGE_PATH}?sessLocale={locale}"
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    _request_page(opener, page_url, locale)

    lookup = _post_json(
        opener,
        page_url,
        locale,
        {"f_cmd": 122, "cntr_no": normalized_container, "cust_cd": ""},
    )
    item = _first_result(lookup, normalized_container)
    booking_no = str(item["bkgNo"])
    cop_no = str(item["copNo"])
    common = {"cntr_no": normalized_container, "bkg_no": booking_no, "cop_no": cop_no}

    return {
        "lookup": lookup,
        "status": _post_json(opener, page_url, locale, {"f_cmd": 123, **common}),
        "sailing": _post_json(opener, page_url, locale, {"f_cmd": 124, "bkg_no": booking_no}),
        "detail": _post_json(opener, page_url, locale, {"f_cmd": 125, **common}),
    }


def _request_page(opener: object, page_url: str, locale: str) -> None:
    request = Request(
        page_url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": _accept_language(locale),
        },
    )
    try:
        with opener.open(request, timeout=30) as response:  # type: ignore[attr-defined]
            response.read()
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"无法建立 SM Line 查询会话: {exc}") from exc


def _post_json(opener: object, page_url: str, locale: str, data: dict[str, object]) -> dict[str, object]:
    request = Request(
        f"{BASE_URL}{API_PATH}",
        data=urlencode(data).encode("utf-8"),
        method="POST",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": _accept_language(locale),
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": "https://esvc.smlines.com",
            "Referer": page_url,
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    try:
        with opener.open(request, timeout=30) as response:  # type: ignore[attr-defined]
            body = response.read().decode(response.headers.get_content_charset() or "utf-8", errors="replace")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"SM Line 查询接口返回 HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"连接 SM Line 查询接口失败: {exc.reason}") from exc

    try:
        result = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("SM Line 查询接口未返回 JSON") from exc
    if not isinstance(result, dict):
        raise RuntimeError("SM Line 查询接口返回了非对象 JSON")
    return result


def _first_result(result: dict[str, object], container: str) -> dict[str, object]:
    rows = result.get("list")
    if result.get("TRANS_RESULT_KEY") != "S" or not isinstance(rows, list) or not rows:
        raise LookupError(f"SM Line 未找到柜号 {container} 的可用追踪记录")
    first = rows[0]
    if not isinstance(first, dict) or not first.get("bkgNo") or not first.get("copNo"):
        raise RuntimeError("SM Line 查询结果缺少后续状态查询所需的 bkgNo 或 copNo")
    return first


def _accept_language(locale: str) -> str:
    return "zh-CN,zh;q=0.9,en;q=0.8" if locale == "zh" else "en-US,en;q=0.9"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="调用 SM Line 公开柜号查询接口并打印原始 JSON")
    parser.add_argument("--container", required=True, help="集装箱柜号，例如 SMCU1311081")
    parser.add_argument("--locale", choices=("zh", "en"), default="zh", help="官网页面语言，默认 zh")
    args = parser.parse_args(argv)

    try:
        result = fetch_tracking(args.container, args.locale)
    except (LookupError, RuntimeError) as exc:
        print(f"查询失败: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
