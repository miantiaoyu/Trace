from __future__ import annotations

import argparse
import json
import sys

from trace_api_probe.carriers import parse_carrier
from trace_api_probe.provider_sessions import open_reusable_provider
from trace_api_probe.tracking import TrackingOptions, fetch_raw_for_carrier


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Trace Provider 子进程")
    parser.add_argument("--carrier", required=True)
    parser.add_argument("--container")
    parser.add_argument("--serve", action="store_true", help="使用 JSONL 协议持续处理同一船司查询")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--browser-channel", choices=("chromium", "msedge"), default="chromium")
    args = parser.parse_args(argv)
    if args.serve:
        return _serve(args.carrier, args.headless, args.browser_channel)
    if not args.container:
        parser.error("非 --serve 模式必须传 --container")
    try:
        carrier = parse_carrier(args.carrier)
        raw = fetch_raw_for_carrier(
            carrier,
            args.container,
            TrackingOptions(headless=args.headless, browser_channel=args.browser_channel),
        )
        payload = json.dumps(raw, ensure_ascii=False, default=str)
        sys.stdout.buffer.write(payload.encode("utf-8") + b"\n")
        return 0
    except Exception as exc:
        sys.stderr.buffer.write(f"{type(exc).__name__}: {exc}\n".encode("utf-8", errors="replace"))
        return 1


def _serve(carrier_name: str, headless: bool, browser_channel: str) -> int:
    carrier = parse_carrier(carrier_name)
    options = TrackingOptions(headless=headless, browser_channel=browser_channel)
    with open_reusable_provider(
        carrier,
        headless=headless,
        browser_channel=browser_channel,
    ) as reusable_fetch:
        for line in sys.stdin:
            try:
                request = json.loads(line)
                container = str(request["container"])
                result = (
                    reusable_fetch(container)
                    if reusable_fetch is not None
                    else fetch_raw_for_carrier(carrier, container, options)
                )
                response = {"ok": True, "result": result}
            except Exception as exc:
                response = {
                    "ok": False,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            sys.stdout.buffer.write(
                json.dumps(response, ensure_ascii=False, default=str).encode("utf-8") + b"\n"
            )
            sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
