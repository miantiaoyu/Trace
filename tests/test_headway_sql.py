import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CREATE_SQL_PATH = ROOT / "sql" / "headway.sql"
COMMENTS_SQL_PATH = ROOT / "sql" / "headway_add_comments.sql"


class HeadwaySqlTests(unittest.TestCase):
    def test_every_column_has_comment_in_create_and_existing_table_scripts(self) -> None:
        create_sql = CREATE_SQL_PATH.read_text(encoding="utf-8")
        comments_sql = COMMENTS_SQL_PATH.read_text(encoding="utf-8")

        create_columns = _column_comments(create_sql)
        migration_columns = _modified_column_comments(comments_sql)

        self.assertTrue(create_columns)
        self.assertEqual(set(create_columns), set(_column_names(create_sql)))
        self.assertEqual(set(migration_columns), set(create_columns))
        self.assertTrue(all(create_columns.values()))
        self.assertTrue(all(migration_columns.values()))
        self.assertRegex(create_sql, r"(?i)COMMENT\s*=\s*'[^']+'")
        self.assertRegex(comments_sql, r"(?i)COMMENT\s*=\s*'[^']+'")


def _column_names(sql: str) -> list[str]:
    return re.findall(r"(?m)^\s{4}`([^`]+)`", sql)


def _column_comments(sql: str) -> dict[str, str]:
    return {
        match.group("name"): match.group("comment")
        for match in re.finditer(
            r"(?m)^\s{4}`(?P<name>[^`]+)`[^\n]*\bCOMMENT\s+'(?P<comment>[^']+)'",
            sql,
            re.IGNORECASE,
        )
    }


def _modified_column_comments(sql: str) -> dict[str, str]:
    return {
        match.group("name"): match.group("comment")
        for match in re.finditer(
            r"(?m)^\s{4}MODIFY\s+COLUMN\s+`(?P<name>[^`]+)`[^\n]*\bCOMMENT\s+'(?P<comment>[^']+)'",
            sql,
            re.IGNORECASE,
        )
    }


if __name__ == "__main__":
    unittest.main()
