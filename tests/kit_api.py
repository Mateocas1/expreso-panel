"""Starts the kit's mock Expreso Andino API on a free port, for tests."""
from __future__ import annotations

import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent
KIT_DIR = REPO_ROOT / "vendor" / "caso-expreso" / "kit"
KIT_EXPORT = KIT_DIR / "remitos_2026-09-30.json"
API_KEY = "andino-test-7f3a91"


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _wait_until_listening(port: int, timeout_seconds: float = 5.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            return
        except OSError:
            time.sleep(0.05)
    raise RuntimeError(f"mock API did not start on port {port}")


@contextmanager
def running_kit_api() -> Iterator[str]:
    """Yields the base URL of a fresh mock API (empty state) and stops it on exit."""
    port = free_port()
    server = subprocess.Popen(
        [sys.executable, str(KIT_DIR / "expreso_api.py"), str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_until_listening(port)
        yield f"http://127.0.0.1:{port}"
    finally:
        server.terminate()
        server.wait()
