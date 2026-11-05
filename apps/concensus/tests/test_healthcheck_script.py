"""scripts/healthcheck.py: the role-aware Docker healthcheck shared by the web
server, the Celery worker and Celery beat."""

import importlib.util
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "healthcheck.py"


@pytest.fixture(scope="module")
def hc():
    spec = importlib.util.spec_from_file_location("social_healthcheck", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


DAPHNE = [
    "/usr/local/bin/python",
    "/usr/local/bin/daphne",
    "-b",
    "0.0.0.0",
    "-p",
    "8000",
    "project.asgi:application",
]
WORKER = ["/usr/local/bin/python", "/usr/local/bin/celery", "-A", "project", "worker"]
BEAT = ["/usr/local/bin/python", "/usr/local/bin/celery", "-A", "project", "beat"]
PING = ["celery", "-A", "project", "inspect", "ping", "-d", "celery@x", "-t", "10"]


class TestDetectRole:
    def test_web_with_its_port(self, hc):
        assert hc.detect_role([["sh"], DAPHNE]) == ("web", "8000")

    def test_web_uses_the_port_it_was_started_with(self, hc):
        argv = ["daphne", "-b", "0.0.0.0", "-p", "9001", "project.asgi:application"]
        assert hc.detect_role([argv]) == ("web", "9001")

    def test_web_defaults_to_8000_without_a_port(self, hc):
        assert hc.detect_role([["daphne", "project.asgi:application"]]) == (
            "web",
            "8000",
        )

    def test_worker(self, hc):
        assert hc.detect_role([WORKER]) == ("worker", None)

    def test_beat(self, hc):
        assert hc.detect_role([BEAT]) == ("beat", None)

    def test_the_healthchecks_own_celery_call_is_not_taken_for_a_worker(self, hc):
        assert hc.detect_role([PING]) == (None, None)

    def test_unknown_role(self, hc):
        assert hc.detect_role([["sh"], ["sleep", "1"]]) == (None, None)

    def test_no_processes(self, hc):
        assert hc.detect_role([]) == (None, None)


class TestChecks:
    def test_web_is_healthy_on_a_2xx(self, hc):
        with patch.object(hc.urllib.request, "urlopen") as urlopen:
            assert hc.check_web("8000") is True

        assert urlopen.call_args.args[0] == "http://127.0.0.1:8000/health/"

    def test_web_raises_when_the_health_endpoint_fails(self, hc):
        with patch.object(hc.urllib.request, "urlopen", side_effect=OSError("503")):
            with pytest.raises(OSError):
                hc.check_web("8000")

    def test_worker_needs_a_pong_from_this_node(self, hc):
        done = subprocess.CompletedProcess([], 0, stdout="-> celery@x: OK\n  pong\n")
        with (
            patch.object(hc.subprocess, "run", return_value=done) as run,
            patch.object(hc.socket, "gethostname", return_value="abc"),
        ):
            assert hc.check_worker() is True

        assert "celery@abc" in run.call_args.args[0]

    def test_worker_without_pong_is_unhealthy(self, hc):
        done = subprocess.CompletedProcess([], 1, stdout="Error: no nodes replied")
        with patch.object(hc.subprocess, "run", return_value=done):
            assert hc.check_worker() is False

    def test_worker_with_a_zero_exit_but_no_pong_is_unhealthy(self, hc):
        done = subprocess.CompletedProcess([], 0, stdout="")
        with patch.object(hc.subprocess, "run", return_value=done):
            assert hc.check_worker() is False

    def test_beat_connects_to_the_broker(self, hc):
        connection = MagicMock()
        app = MagicMock()
        app.connection_for_read.return_value.__enter__.return_value = connection
        fake = MagicMock(app=app)

        with patch.dict(sys.modules, {"project.celery": fake}):
            assert hc.check_beat() is True

        connection.ensure_connection.assert_called_once()

    def test_beat_raises_when_the_broker_is_down(self, hc):
        connection = MagicMock()
        connection.ensure_connection.side_effect = ConnectionError("redis down")
        app = MagicMock()
        app.connection_for_read.return_value.__enter__.return_value = connection

        with patch.dict(sys.modules, {"project.celery": MagicMock(app=app)}):
            with pytest.raises(ConnectionError):
                hc.check_beat()


class TestMain:
    def _run(self, hc, role, check, result=True, error=None):
        target = {"web": "check_web", "worker": "check_worker", "beat": "check_beat"}
        with (
            patch.object(hc, "process_args", return_value=[]),
            patch.object(
                hc,
                "detect_role",
                return_value=(role, "8000" if role == "web" else None),
            ),
            patch.object(hc, target[check], return_value=result, side_effect=error),
        ):
            return hc.main()

    def test_healthy_web(self, hc):
        assert self._run(hc, "web", "web") == 0

    def test_healthy_worker(self, hc):
        assert self._run(hc, "worker", "worker") == 0

    def test_healthy_beat(self, hc):
        assert self._run(hc, "beat", "beat") == 0

    def test_a_failing_check_is_unhealthy(self, hc, capsys):
        assert self._run(hc, "worker", "worker", result=False) == 1
        assert "worker unhealthy" in capsys.readouterr().out

    def test_an_exception_is_unhealthy_and_reported(self, hc, capsys):
        assert self._run(hc, "web", "web", error=OSError("boom")) == 1
        assert "web unhealthy: boom" in capsys.readouterr().out

    def test_unknown_role_is_assumed_healthy(self, hc, capsys):
        with (
            patch.object(hc, "process_args", return_value=[]),
            patch.object(hc, "detect_role", return_value=(None, None)),
        ):
            assert hc.main() == 0
        assert "unknown role" in capsys.readouterr().out


def test_process_args_reads_proc_without_failing(hc):
    processes = hc.process_args()

    assert isinstance(processes, list)
