from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ConfigSelectionTests(unittest.TestCase):
    def test_compose_uses_safe_default_source_and_target_config_names(self) -> None:
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

        self.assertIn("${TRACE_SOURCE_CONFIG:-./prod-db.yml}", compose)
        self.assertIn("${TRACE_TARGET_CONFIG:-./test-db.yml}", compose)

    def test_runner_accepts_one_line_config_overrides(self) -> None:
        runner = (ROOT / "deploy" / "run-trace.sh").read_text(encoding="utf-8")

        self.assertIn("--source-config|--target-config", runner)
        self.assertIn('export TRACE_SOURCE_CONFIG=', runner)
        self.assertIn('export TRACE_TARGET_CONFIG=', runner)
        self.assertIn('"$@"', runner)

    def test_installer_validates_selected_source_and_target_files(self) -> None:
        installer = (ROOT / "deploy" / "install-systemd.sh").read_text(encoding="utf-8")

        self.assertIn('TRACE_TARGET_CONFIG="${TRACE_TARGET_CONFIG:-./test-db.yml}"', installer)
        self.assertIn('for config_file in "${TRACE_SOURCE_CONFIG}" "${TRACE_TARGET_CONFIG}"', installer)
        self.assertNotIn("docker-compose.yml prod-db.yml test-db.yml deploy/run-trace.sh", installer)

    def test_config_bundle_contains_templates_without_real_credentials(self) -> None:
        prod = (ROOT / "config" / "prod-db.yml.example").read_text(encoding="utf-8")
        test = (ROOT / "config" / "test-db.yml.example").read_text(encoding="utf-8")
        prod_oms = (ROOT / "config" / "prod-oms.yml.example").read_text(encoding="utf-8")

        self.assertIn("CHANGE_ME", prod)
        self.assertIn("CHANGE_ME", test)
        self.assertIn("CHANGE_ME", prod_oms)
        self.assertNotIn("123456", test)

    def test_bundle_builder_writes_linux_compatible_zip_paths(self) -> None:
        builder = (ROOT / "tools" / "build_server_bundle.ps1").read_text(encoding="utf-8")

        self.assertIn("ZipFileExtensions", builder)
        self.assertIn(".Replace('", builder)


if __name__ == "__main__":
    unittest.main()
