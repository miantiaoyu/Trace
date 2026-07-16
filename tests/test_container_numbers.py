import unittest

from trace_api_probe.container_numbers import normalize_container_number


class ContainerNumberTests(unittest.TestCase):
    def test_normalizes_valid_iso_6346_container_number(self) -> None:
        self.assertEqual(normalize_container_number(" eghu 9204414 "), "EGHU9204414")

    def test_rejects_invalid_format_and_check_digit(self) -> None:
        for value in ("9023894-1", "YMMU7349034"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_container_number(value)


if __name__ == "__main__":
    unittest.main()
