import unittest

from crawler_lab.msc_probe import MscTrackingError, _validate_payload


class MscProbeTests(unittest.TestCase):
    def test_accepts_matching_container(self) -> None:
        payload = {
            "IsSuccess": True,
            "Data": {
                "TrackingNumber": "TLLU8937468",
                "BillOfLadings": [],
            },
        }

        self.assertIs(_validate_payload(payload, "TLLU8937468"), payload)

    def test_rejects_failed_response(self) -> None:
        with self.assertRaisesRegex(MscTrackingError, "IsSuccess"):
            _validate_payload({"IsSuccess": False, "Data": {}}, "TLLU8937468")

    def test_rejects_missing_container_echo(self) -> None:
        payload = {
            "IsSuccess": True,
            "Data": {
                "TrackingNumber": "MSCU1234567",
                "BillOfLadings": [],
            },
        }

        with self.assertRaisesRegex(MscTrackingError, "未回显柜号"):
            _validate_payload(payload, "TLLU8937468")

    def test_rejects_missing_bill_of_ladings(self) -> None:
        payload = {
            "IsSuccess": True,
            "Data": {
                "TrackingNumber": "TLLU8937468",
            },
        }

        with self.assertRaisesRegex(MscTrackingError, "BillOfLadings"):
            _validate_payload(payload, "TLLU8937468")


if __name__ == "__main__":
    unittest.main()
