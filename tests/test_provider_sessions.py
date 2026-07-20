import unittest
from unittest.mock import patch

from trace_api_probe.carriers import Carrier
from trace_api_probe.provider_sessions import open_reusable_provider


class ProviderSessionTests(unittest.TestCase):
    def test_hmm_reuses_one_browser_page_for_multiple_containers(self) -> None:
        pages = []
        calls = []

        class FakeBrowserSession:
            def __init__(self, **kwargs):
                self.page = object()
                pages.append(self.page)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

        def fetch(container, **kwargs):
            calls.append((container, kwargs["page"]))
            return {"container": container}

        with patch("trace_api_probe.provider_sessions.BrowserPageSession", FakeBrowserSession), patch(
            "trace_api_probe.providers.hmm_probe.fetch_tracking", fetch
        ):
            with open_reusable_provider(
                Carrier.HMM,
                headless=False,
                browser_channel="chromium",
            ) as provider:
                provider("HMMU4706485")
                provider("HMMU4706486")

        self.assertEqual(len(pages), 1)
        self.assertEqual([container for container, _ in calls], ["HMMU4706485", "HMMU4706486"])
        self.assertIs(calls[0][1], calls[1][1])


if __name__ == "__main__":
    unittest.main()
