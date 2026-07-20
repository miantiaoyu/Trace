from __future__ import annotations

from contextlib import contextmanager
from typing import Callable, Iterator

from trace_api_probe.carriers import Carrier
from trace_api_probe.providers.browser_session import BrowserPageSession


ProviderFetch = Callable[[str], object]


@contextmanager
def open_reusable_provider(
    carrier: Carrier,
    *,
    headless: bool,
    browser_channel: str,
) -> Iterator[ProviderFetch | None]:
    """为浏览器型船司打开批次级会话；纯 HTTP 路线返回 None。"""
    if carrier is Carrier.HMM:
        from trace_api_probe.providers.hmm_probe import fetch_tracking

        with BrowserPageSession(
            headless=False,
            browser_channel=browser_channel,
            viewport={"width": 1440, "height": 900},
        ) as session:
            yield lambda container: fetch_tracking(
                container,
                headless=False,
                browser_channel=browser_channel,
                page=session.page,
            )
        return

    if carrier is Carrier.MSC:
        from trace_api_probe.providers.msc_probe import fetch_tracking

        with BrowserPageSession(headless=headless, browser_channel=browser_channel) as session:
            yield lambda container: fetch_tracking(
                container,
                headless=headless,
                browser_channel=browser_channel,
                page=session.page,
            )
        return

    if carrier is Carrier.MAERSK:
        from trace_api_probe.providers.maersk_probe import fetch_tracking

        with BrowserPageSession(headless=True) as session:
            yield lambda container: fetch_tracking(container, page=session.page)
        return

    if carrier in (Carrier.COSCO, Carrier.ONE):
        from trace_api_probe.providers.browser_dom_probe import fetch_tracking

        with BrowserPageSession(headless=True) as session:
            yield lambda container: fetch_tracking(carrier.value, container, page=session.page)
        return

    if carrier is Carrier.WAN_HAI:
        from trace_api_probe.providers.wan_hai_probe import WanHaiSession

        session = WanHaiSession(headless=headless, browser_channel=browser_channel)
        yield session.fetch
        return

    yield None
