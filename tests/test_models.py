import unittest

from pydantic import ValidationError

from trace_api_probe.models import new_tracking_summary, validate_tracking_summary


class TrackingModelsTests(unittest.TestCase):
    def test_creates_fixed_empty_summary(self) -> None:
        result = new_tracking_summary("MAERSK", "MSKU0000001")

        self.assertEqual(result["schema_version"], "1.1")
        self.assertEqual(result["current"]["status"], None)
        self.assertEqual(result["events"], [])
        self.assertFalse(result["coverage"]["current"])

    def test_rejects_unknown_normalized_fields(self) -> None:
        result = new_tracking_summary("HMM", "HMMU0000001")
        result["unexpected"] = "value"

        with self.assertRaises(ValidationError):
            validate_tracking_summary(result)

    def test_rejects_invalid_event_time_type(self) -> None:
        result = new_tracking_summary("MSC", "MSCU0000001")
        result["events"] = [
            {
                "time": "2026-07-14",
                "status": "Loaded",
                "location": "SHANGHAI",
                "mode": "Vessel",
                "vessel": "TEST VESSEL",
                "voyage": "001E",
                "imo": None,
                "time_type": "PLANNED",
            }
        ]

        with self.assertRaises(ValidationError):
            validate_tracking_summary(result)


if __name__ == "__main__":
    unittest.main()
