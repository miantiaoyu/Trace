from __future__ import annotations

import re
import ssl
import sys
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from crawler_lab.http_probe import TARGET_URL, USER_AGENT, extract_scripts, fetch_text


KEYWORDS = (
    "api",
    "track",
    "tracking",
    "container",
    "bill",
    "booking",
    "shipment",
    "vessel",
    "cargo",
)


@dataclass(frozen=True)
class MatchResult:
    url: str
    keyword: str
    snippet: str


def main() -> int:
    try:
        page = fetch_text(TARGET_URL)
    except Exception as exc:
        print(f"页面请求失败: {exc}", file=sys.stderr)
        return 1

    scripts = [url for url in extract_scripts(page.body, TARGET_URL) if is_same_origin_next_chunk(url)]
    print(f"同域名 Next.js chunk 数量: {len(scripts)}")

    results: list[MatchResult] = []
    for url in scripts:
        try:
            text = fetch_js(url)
        except Exception as exc:
            print(f"跳过 {url}: {exc}", file=sys.stderr)
            continue
        results.extend(find_matches(url, text))

    if not results:
        print("没有在 JS chunk 中找到明显接口关键词。")
        return 0

    for result in results[:120]:
        print("=" * 100)
        print(f"URL: {result.url}")
        print(f"关键词: {result.keyword}")
        print(result.snippet)
    if len(results) > 120:
        print(f"... 还有 {len(results) - 120} 条匹配未打印")
    return 0


def is_same_origin_next_chunk(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc == "www.weiyun001.com" and "/_next/static/chunks/" in parsed.path and parsed.path.endswith(".js")


def fetch_js(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/javascript,*/*"})
    context = ssl.create_default_context()
    with urlopen(request, timeout=30, context=context) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def find_matches(url: str, text: str) -> list[MatchResult]:
    results: list[MatchResult] = []
    lowered = text.lower()
    for keyword in KEYWORDS:
        start = 0
        while True:
            index = lowered.find(keyword, start)
            if index == -1:
                break
            left = max(0, index - 220)
            right = min(len(text), index + 420)
            snippet = sanitize_snippet(text[left:right])
            results.append(MatchResult(url=url, keyword=keyword, snippet=snippet))
            start = index + len(keyword)
            if len(results) >= 300:
                return results
    return results


def sanitize_snippet(value: str) -> str:
    value = re.sub(r"\s+", " ", value)
    return value.strip()


if __name__ == "__main__":
    raise SystemExit(main())
