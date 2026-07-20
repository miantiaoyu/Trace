from __future__ import annotations


class BrowserPageSession:
    """在一组同船司查询中复用 Playwright、浏览器、上下文和页面。"""

    def __init__(
        self,
        *,
        headless: bool,
        browser_channel: str = "chromium",
        viewport: dict[str, int] | None = None,
    ) -> None:
        self._headless = headless
        self._browser_channel = browser_channel
        self._viewport = viewport
        self._playwright_manager = None
        self._browser = None
        self._context = None
        self.page = None

    def __enter__(self) -> "BrowserPageSession":
        from playwright.sync_api import sync_playwright

        self._playwright_manager = sync_playwright()
        playwright = self._playwright_manager.start()
        launch_kwargs: dict[str, object] = {"headless": self._headless}
        if self._browser_channel != "chromium":
            launch_kwargs["channel"] = self._browser_channel
        self._browser = playwright.chromium.launch(**launch_kwargs)
        context_kwargs = {"viewport": self._viewport} if self._viewport is not None else {}
        self._context = self._browser.new_context(**context_kwargs)
        self.page = self._context.new_page()
        return self

    def __exit__(self, *args: object) -> None:
        if self._context is not None:
            self._context.close()
        if self._browser is not None:
            self._browser.close()
        if self._playwright_manager is not None:
            self._playwright_manager.__exit__(*args)
