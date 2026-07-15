from pathlib import Path
import tempfile
import unittest

from trace_api_probe.config import read_db_config


class ConfigTests(unittest.TestCase):
    def test_read_db_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "prod-db.yml"
            config_path.write_text(
                "host: example.mysql\nport: 3306\nuser: reader\npassword: secret\n",
                encoding="utf-8",
            )

            config = read_db_config(config_path)

        self.assertEqual(config.host, "example.mysql")
        self.assertEqual(config.port, 3306)
        self.assertEqual(config.user, "reader")
        self.assertEqual(config.password, "secret")

    def test_read_spring_datasource_jdbc_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "test-db.yml"
            config_path.write_text(
                "url: jdbc:mysql://172.16.48.10:3306/oms?useSSL=false\n"
                "username: root\n"
                "password: test-secret\n",
                encoding="utf-8",
            )

            config = read_db_config(config_path)

        self.assertEqual(config.host, "172.16.48.10")
        self.assertEqual(config.port, 3306)
        self.assertEqual(config.user, "root")
        self.assertEqual(config.password, "test-secret")


if __name__ == "__main__":
    unittest.main()
