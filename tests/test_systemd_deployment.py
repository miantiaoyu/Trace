from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SystemdDeploymentTests(unittest.TestCase):
    def test_runner_keeps_one_shot_persistent_batch_contract(self) -> None:
        runner = (ROOT / "deploy" / "run-trace.sh").read_text(encoding="utf-8")

        self.assertIn('compose=(docker-compose)', runner)
        self.assertIn('run --rm --no-deps -T trace', runner)
        self.assertIn('--limit "${TRACE_LIMIT:-0}"', runner)
        self.assertIn("--persist", runner)

    def test_service_waits_for_docker_and_runs_the_batch_once(self) -> None:
        service = (ROOT / "deploy" / "systemd" / "trace.service").read_text(encoding="utf-8")

        self.assertIn("Requires=docker.service", service)
        self.assertIn("After=docker.service network-online.target", service)
        self.assertIn("Type=oneshot", service)
        self.assertIn("ExecStart=/opt/trace/deploy/run-trace.sh", service)
        self.assertIn("TimeoutStartSec=0", service)

    def test_timer_runs_daily_and_catches_up_after_downtime(self) -> None:
        timer = (ROOT / "deploy" / "systemd" / "trace.timer").read_text(encoding="utf-8")

        self.assertIn("OnCalendar=*-*-* 02:00:00", timer)
        self.assertIn("Persistent=true", timer)
        self.assertIn("WantedBy=timers.target", timer)

    def test_installer_does_not_start_the_timer_before_validation(self) -> None:
        installer = (ROOT / "deploy" / "install-systemd.sh").read_text(encoding="utf-8")

        self.assertIn("systemctl enable trace.timer", installer)
        self.assertNotIn("enable --now", installer)
        self.assertIn('TRACE_LIMIT="${TRACE_LIMIT:-1}"', installer)
        self.assertIn('if [[ ! -e "/etc/sysconfig/trace" ]]', installer)

    def test_server_bundle_uses_systemd_files_instead_of_xxl_job(self) -> None:
        builder = (ROOT / "tools" / "build_server_bundle.ps1").read_text(encoding="utf-8")

        self.assertIn('"deploy\\run-trace.sh"', builder)
        self.assertIn('"deploy\\install-systemd.sh"', builder)
        self.assertIn('"deploy\\systemd"', builder)
        self.assertNotIn("xxl-job", builder)

    def test_server_runbook_changes_batch_limits_persistently(self) -> None:
        runbook = (ROOT / "deploy" / "SERVER_README.md").read_text(encoding="utf-8")

        self.assertIn("TRACE_LIMIT=.*/TRACE_LIMIT=20", runbook)
        self.assertIn("TRACE_LIMIT=.*/TRACE_LIMIT=0", runbook)


if __name__ == "__main__":
    unittest.main()
