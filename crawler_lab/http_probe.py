from __future__ import annotations

import html
import re
import ssl
import sys
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urljoin
from urllib.request import Request, urlopen


TARGET_URL = "https://www.weiyun001.com/track?regionredirected=true"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


@dataclass(frozen=True)
class PageProbe:
    status: int
    content_type: str
    body: str


def main() -> int:
    try:
        page = fetch_text(TARGET_URL)
    except Exception as exc:
        print(f"请求失败: {exc}", file=sys.stderr)
        return 1

    scripts = extract_scripts(page.body, TARGET_URL)
    tokens = extract_interesting_tokens(page.body)

    print(f"URL: {TARGET_URL}")
    print(f"HTTP 状态: {page.status}")
    print(f"Content-Type: {page.content_type}")
    print(f"标题: {extract_title(page.body) or '(未找到)'}")
    print(f"HTML 长度: {len(page.body)}")
    print()

    print(f"Script 数量: {len(scripts)}")
    for script in scripts[:80]:
        print(f"- {script}")
    if len(scripts) > 80:
        print(f"... 还有 {len(scripts) - 80} 个 script")
    print()

    print("疑似关键词:")
    for token in tokens[:120]:
        print(f"- {token}")
    return 0


def fetch_text(url: str) -> PageProbe:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"})
    context = ssl.create_default_context()
    with urlopen(request, timeout=30, context=context) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        body = response.read().decode(charset, errors="replace")
        return PageProbe(
            status=response.status,
            content_type=response.headers.get("Content-Type", ""),
            body=body,
        )


def extract_scripts(body: str, base_url: str) -> list[str]:
    scripts: list[str] = []
    for match in re.finditer(r"<script[^>]+src=[\"']([^\"']+)[\"']", body, flags=re.I):
        src = match.group(1)
        if src.startswith("//"):
            scripts.append("https:" + src)
        else:
            scripts.append(urljoin(base_url, src))
    return scripts


def extract_title(body: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", body, flags=re.I | re.S)
    if not match:
        return ""
    return html.unescape(re.sub(r"\s+", " ", match.group(1)).strip())


def extract_interesting_tokens(body: str) -> list[str]:
    seen: set[str] = set()
    tokens: list[str] = []
    pattern = re.compile(r"(?:api|track|query|container|bill|bl|booking|shipment)[^\"'<>\s]{0,120}", re.I)
    for match in pattern.finditer(body):
        token = html.unescape(match.group(0))
        if token not in seen:
            seen.add(token)
            tokens.append(token)
    return tokens


if __name__ == "__main__":
    raise SystemExit(main())
