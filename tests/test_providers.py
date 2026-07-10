import unittest
from unittest.mock import patch

from trace_api_probe.carriers import Carrier
from trace_api_probe.providers import MaerskProvider, MissingCredentialError


class ProviderTests(unittest.TestCase):
    def test_maersk_provider_requires_api_key_or_client_id(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "MAERSK_API_KEY": "",
                "MAERSK_CLIENT_ID": "",
                "MAERSK_BEARER_TOKEN": "",
            },
            clear=True,
        ):
            with self.assertRaises(MissingCredentialError) as context:
                MaerskProvider().fetch_raw("MSKU1234567")

        self.assertEqual(context.exception.carrier, Carrier.MAERSK)
        self.assertIn("MAERSK_API_KEY", str(context.exception))

    def test_maersk_provider_uses_configured_base_url(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "MAERSK_API_KEY": "test-key",
                "MAERSK_TRACK_TRACE_URL": "https://example.test/events",
            },
            clear=True,
        ):
            config = MaerskProvider()._config_from_env()

        self.assertEqual(config.base_url, "https://example.test/events")
        self.assertEqual(config.headers["Consumer-Key"], "test-key")


if __name__ == "__main__":
    unittest.main()
