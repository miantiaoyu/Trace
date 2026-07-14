import unittest

from crawler_lab.html_tables import extract_table_rows, extract_tables


class HtmlTablesTests(unittest.TestCase):
    def test_extracts_rows_from_malformed_html(self) -> None:
        html = "<table><tr><th>Status<th>Location<tr><td>Loaded<td>Shanghai</table>"

        self.assertEqual(
            extract_table_rows(html),
            [["Status", "Location"], ["Loaded", "Shanghai"]],
        )

    def test_preserves_separate_tables(self) -> None:
        html = "<table><tr><td>A</td></tr></table><table><tr><td>B</td></tr></table>"

        self.assertEqual(extract_tables(html), [[["A"]], [["B"]]])


if __name__ == "__main__":
    unittest.main()
