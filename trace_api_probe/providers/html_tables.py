from __future__ import annotations

from selectolax.parser import HTMLParser, Node


def extract_table_rows(html: str) -> list[list[str]]:
    tree = HTMLParser(html)
    rows = [_extract_row(row) for row in tree.css("tr")]
    return [row for row in rows if row]


def extract_tables(html: str) -> list[list[list[str]]]:
    tree = HTMLParser(html)
    tables = []
    for table in tree.css("table"):
        rows = [_extract_row(row) for row in table.css("tr")]
        rows = [row for row in rows if row]
        if rows:
            tables.append(rows)
    return tables


def _extract_row(row: Node) -> list[str]:
    cells = []
    node = row.child
    while node is not None:
        if node.tag in {"td", "th"}:
            value = " ".join(node.text(separator=" ", strip=True).split())
            cells.append(value)
        node = node.next
    return cells
