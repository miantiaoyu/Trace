from __future__ import annotations

import argparse
import json
import sys

from trace_api_probe.providers.browser_session import BrowserPageSession


TRACKING_PAGE_URL = "https://www.msc.com/en/track-a-shipment?agencyPath=hkg"
COOKIE_ACCEPT_SELECTOR = "#onetrust-accept-btn-handler"
TRACKING_INPUT_SELECTOR = "#trackingNumber"
SEARCH_BUTTON_SELECTOR = "form.js-form button.msc-search-autocomplete__search"
TRACKING_RESPONSE_PATH = "/api/feature/tools/TrackingInfo"


class MscTrackingError(RuntimeError):
    pass


def fetch_tracking(
    container: str,
    *,
    headless: bool = False,
    browser_channel: str = "chromium",
    page: object | None = None,
) -> dict[str, object]:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    except ImportError as exc:
        raise MscTrackingError("缺少 Playwright。请在 py312 环境安装依赖并执行 playwright install chromium") from exc

    normalized_container = container.strip().upper()
    if not normalized_container:
        raise MscTrackingError("柜号不能为空")

    try:
        if page is None:
            with BrowserPageSession(headless=headless, browser_channel=browser_channel) as session:
                payload = _fetch_payload(session.page, normalized_container)
        else:
            payload = _fetch_payload(page, normalized_container)
    except PlaywrightTimeoutError as exc:
        raise MscTrackingError("MSC 官网在 60 秒内未返回追踪结果") from exc

    return _validate_payload(payload, normalized_container)


def _fetch_payload(page: object, container: str) -> object:
    page.goto(TRACKING_PAGE_URL, wait_until="domcontentloaded", timeout=60_000)
    _accept_cookies(page)
    page.locator(TRACKING_INPUT_SELECTOR).wait_for(state="visible", timeout=20_000)
    page.locator(TRACKING_INPUT_SELECTOR).fill(container)
    page.locator(SEARCH_BUTTON_SELECTOR).wait_for(state="visible", timeout=10_000)
    with page.expect_response(
        lambda response: TRACKING_RESPONSE_PATH in response.url
        and response.request.method == "POST"
        and response.status == 200,
        timeout=60_000,
    ) as response_info:
        page.locator(SEARCH_BUTTON_SELECTOR).click()
    return response_info.value.json()


def _accept_cookies(page: object) -> None:
    try:
        page.locator(COOKIE_ACCEPT_SELECTOR).click(timeout=5_000)
    except Exception:
        return


def _validate_payload(payload: object, container: str) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise MscTrackingError("MSC 追踪响应不是 JSON 对象")
    if payload.get("IsSuccess") is not True:
        raise MscTrackingError(f"MSC 追踪响应 IsSuccess 不是 true: {payload!r}")

    data = payload.get("Data")
    if not isinstance(data, dict):
        raise MscTrackingError("MSC 追踪响应缺少 Data")

    tracking_number = str(data.get("TrackingNumber", "")).strip().upper()
    if tracking_number != container:
        raise MscTrackingError(f"MSC 追踪响应未回显柜号 {container}")

    bill_of_ladings = data.get("BillOfLadings")
    if not isinstance(bill_of_ladings, list):
        raise MscTrackingError("MSC 追踪响应缺少 BillOfLadings")

    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="通过 MSC 官网查询页读取页面返回的原始 JSON")
    parser.add_argument("--container", required=True, help="集装箱柜号，例如 TLLU8937468")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="使用无界面浏览器运行。默认使用可见浏览器以贴近人工查询流程。",
    )
    parser.add_argument(
        "--browser-channel",
        default="chromium",
        choices=("chromium", "msedge"),
        help="Playwright 浏览器通道，默认 chromium；如需系统 Edge 可传 msedge。",
    )
    args = parser.parse_args(argv)
    try:
        print(
            json.dumps(
                fetch_tracking(
                    args.container,
                    headless=args.headless,
                    browser_channel=args.browser_channel,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
    except MscTrackingError as exc:
        print(f"查询失败: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
