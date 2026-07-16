import unittest

from trace_api_probe.providers.browser_dom_probe import split_row


class BrowserDomProbeTests(unittest.TestCase):
    def test_splits_newlines_and_tabs_into_cells(self) -> None:
        self.assertEqual(
            split_row("离开始发港\n2026-07-05 17:15:11\nXiamen Terminal\tVessel"),
            ["离开始发港", "2026-07-05 17:15:11", "Xiamen Terminal", "Vessel"],
        )


if __name__ == "__main__":
    unittest.main()
