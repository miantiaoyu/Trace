from __future__ import annotations

import argparse
import json
import ssl
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_BASE = "https://wywapi.weiyun001.com/api"
REFERER = "https://www.weiyun001.com/track?regionredirected=true"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="探测维运网公开货物追踪接口")
    parser.add_argument("--number", default="GVTU5148354", help="柜号/提单号/订舱号")
    parser.add_argument("--carrier-code", help="维运网船司 code，例如 MSK/CMA/MSC/COSU；不传则先尝试自动识别")
    args = parser.parse_args(argv)

    probes: list[tuple[str, str, dict[str, str] | None, object | None]] = [
        ("GET", "/cargoTracking/recognitionIsContainerNo", {"number": args.number}, None),
        ("GET", "/cargoTracking/recognitionCarrierNumber", {"number": args.number.upper()}, None),
        ("GET", "/cargoTracking/recognitionCarrierByBLNo", {"number": args.number.upper()}, None),
    ]

    carrier_code = args.carrier_code or detect_carrier_code(args.number)
    if carrier_code:
        probes.append(
            (
                "POST",
                "/cargoTracking/getCarrierSearchLink",
                None,
                {"number": args.number.upper(), "code": carrier_code},
            )
        )
    else:
        print("未能自动识别船司；如需生成跳转链接，请传入 --carrier-code。", file=sys.stderr)

    for method, path, query, body in probes:
        print("=" * 100)
        print(f"{method} {path}")
        try:
            response = request_json(method, path, query=query, body=body)
        except Exception as exc:
            print(f"请求失败: {exc}", file=sys.stderr)
            continue
        print(json.dumps(response, ensure_ascii=False, indent=2))
    return 0


def detect_carrier_code(number: str) -> str | None:
    for path in ("/cargoTracking/recognitionCarrierNumber", "/cargoTracking/recognitionCarrierByBLNo"):
        response = request_json("GET", path, query={"number": number.upper()})
        if not isinstance(response, dict) or not response.get("success"):
            continue

        result = response.get("result")
        if isinstance(result, dict):
            code = result.get("code")
            return str(code) if code else None
        if isinstance(result, list) and result:
            first = result[0]
            if isinstance(first, dict):
                code = first.get("code")
                return str(code) if code else None
    return None


def request_json(method: str, path: str, query: dict[str, str] | None = None, body: object | None = None) -> object:
    url = API_BASE + path
    if query:
        url += "?" + urlencode(query)

    payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=payload,
        method=method,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Referer": REFERER,
            "Origin": "https://www.weiyun001.com",
        },
    )

    context = ssl.create_default_context()
    try:
        with urlopen(request, timeout=30, context=context) as response:
            text = response.read().decode(response.headers.get_content_charset() or "utf-8", errors="replace")
    except HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {text}") from exc
    except URLError as exc:
        raise RuntimeError(str(exc.reason)) from exc

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw_text": text}


if __name__ == "__main__":
    raise SystemExit(main())
