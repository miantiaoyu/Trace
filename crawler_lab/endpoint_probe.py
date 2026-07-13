from __future__ import annotations

import re
import ssl
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from crawler_lab.http_probe import TARGET_URL, USER_AGENT, extract_scripts, fetch_text


ENDPOINT_PATTERNS = (
    re.compile(r"[\"']((?:https://wywapi\.weiyun001\.com)?/api/[^\"']{1,180})[\"']"),
    re.compile(r"[\"'](/[^\"']*(?:cargoTracking|track|Track|container|Container|booking|Booking|ship|Ship|cargo|Cargo)[^\"']*)[\"']"),
)


def main() -> int:
    page = fetch_text(TARGET_URL)
    scripts = [url for url in extract_scripts(page.body, TARGET_URL) if is_same_origin_chunk(url)]
    endpoints: list[str] = []

    for script_url in scripts:
        text = fetch_text_file(script_url)
        for pattern in ENDPOINT_PATTERNS:
            for match in pattern.finditer(text):
                endpoint = match.group(1)
                if should_ignore(endpoint):
                    continue
                if endpoint not in endpoints:
                    endpoints.append(endpoint)

    print(f"疑似端点数量: {len(endpoints)}")
    for endpoint in endpoints:
        print(endpoint)
    return 0


def is_same_origin_chunk(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc == "www.weiyun001.com" and "/_next/static/chunks/" in parsed.path and parsed.path.endswith(".js")


def fetch_text_file(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/javascript,*/*"})
    context = ssl.create_default_context()
    with urlopen(request, timeout=30, context=context) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def should_ignore(value: str) -> bool:
    ignored = ("/_next/", "CustomerLogoImages", ".png", ".jpg", ".jpeg", ".css", ".svg")
    return any(item in value for item in ignored)


if __name__ == "__main__":
    raise SystemExit(main())
