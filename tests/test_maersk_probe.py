import unittest

from crawler_lab.maersk_probe import MaerskTrackingError, _validate_payload


class MaerskProbeTests(unittest.TestCase):
    def test_accepts_matching_container(self) -> None:
        payload = {"containers": [{"container_num": "GVTU5148354", "locations": []}]}

        self.assertIs(_validate_payload(payload, "GVTU5148354"), payload)

    def test_rejects_missing_container_echo(self) -> None:
        with self.assertRaisesRegex(MaerskTrackingError, "未回显柜号"):
            _validate_payload({"containers": [{"container_num": "MSKU1234567"}]}, "GVTU5148354")

    def test_rejects_non_list_containers(self) -> None:
        with self.assertRaisesRegex(MaerskTrackingError, "缺少 containers"):
            _validate_payload({"containers": {}}, "GVTU5148354")


if __name__ == "__main__":
    unittest.main()
