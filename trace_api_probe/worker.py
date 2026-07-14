from __future__ import annotations

import argparse
import json
import sys

from trace_api_probe.carriers import parse_carrier
from trace_api_probe.tracking import TrackingOptions, fetch_raw_for_carrier


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Trace Provider 子进程")
    parser.add_argument("--carrier", required=True)
    parser.add_argument("--container", required=True)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--browser-channel", choices=("chromium", "msedge"), default="chromium")
    args = parser.parse_args(argv)
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


if __name__ == "__main__":
    raise SystemExit(main())
