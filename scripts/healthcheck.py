"""Docker healthcheck for the three roles that share this image.

The same image runs the ASGI server (daphne), the Celery worker and Celery beat,
so a plain HTTP check in the Dockerfile would mark the worker and the beat as
unhealthy. This script finds out which role the container has and checks that one:

- daphne:        GET /health/ (answers 503 when PostgreSQL or Redis are down)
- celery worker: ``celery inspect ping`` against this very worker, which proves it
                 is connected to the broker and answering, not just alive
- celery beat:   the broker (Redis) is reachable, since beat only publishes there

Exit status 0 is healthy, 1 unhealthy. A container whose role cannot be told (for
example an interactive shell) is reported healthy so it is never flagged by mistake.
"""

import os
import socket
import subprocess
import sys
import urllib.request


def process_args():
    """Command line of every process in the container, as a list of argv lists."""
    result = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/cmdline", "rb") as handle:
                argv = [a.decode() for a in handle.read().split(b"\0") if a]
        except OSError:
            continue
        if argv:
            result.append(argv)
    return result


def detect_role(processes):
    """Return ("web", port), ("worker", None), ("beat", None) or (None, None)."""
    for argv in processes:
        names = [os.path.basename(a) for a in argv]
        if "daphne" in names:
            port = argv[argv.index("-p") + 1] if "-p" in argv else "8000"
            return "web", port
    for argv in processes:
        names = [os.path.basename(a) for a in argv]
        if "celery" in names and "worker" in argv:
            return "worker", None
    for argv in processes:
        names = [os.path.basename(a) for a in argv]
        if "celery" in names and "beat" in argv:
            return "beat", None
    return None, None


def check_web(port):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/health/", timeout=5):
        return True  # urlopen raises on any non-2xx status


def check_worker():
    node = f"celery@{socket.gethostname()}"
    completed = subprocess.run(
        ["celery", "-A", "project", "inspect", "ping", "-d", node, "-t", "10"],
        capture_output=True,
        text=True,
        timeout=25,
    )
    return completed.returncode == 0 and "pong" in completed.stdout


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check_beat():
    # Running ``python scripts/healthcheck.py`` puts scripts/ on sys.path, not the
    # project root, so ``project`` could not be imported.
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
    from project.celery import app

    with app.connection_for_read() as connection:
        connection.ensure_connection(max_retries=1, timeout=5)
    return True


def main():
    role, port = detect_role(process_args())
    try:
        if role == "web":
            healthy = check_web(port)
        elif role == "worker":
            healthy = check_worker()
        elif role == "beat":
            healthy = check_beat()
        else:
            print("healthcheck: unknown role, assuming healthy")
            return 0
    except Exception as exc:  # any failure means unhealthy
        print(f"healthcheck: {role} unhealthy: {exc}")
        return 1

    if not healthy:
        print(f"healthcheck: {role} unhealthy")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
