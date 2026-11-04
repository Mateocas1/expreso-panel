"""`Abrir panel.sh`, run the way a file manager runs it: no terminal attached, fake tools on PATH."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.kit_api import REPO_ROOT

SCRIPT = REPO_ROOT / "Abrir panel.sh"
RECORDER = '#!/bin/sh\nprintf "%%s\\n" "$PWD" "$EXPRESO_PANEL_IN_TERMINAL" "$@" > "%s"\n'


class LinuxLauncherTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.bin = Path(tmp.name) / "bin"
        self.bin.mkdir()
        self.record = Path(tmp.name) / "record"
        for tool in ("dirname", "basename"):  # the only external commands the script may need
            (self.bin / tool).symlink_to(shutil.which(tool))

    def fake(self, name: str) -> None:
        path = self.bin / name
        path.write_text(RECORDER % self.record)
        path.chmod(0o755)

    def run_script(self, **env) -> subprocess.CompletedProcess:
        environ = {"PATH": str(self.bin), "HOME": str(self.bin.parent), **env}
        return subprocess.run([str(SCRIPT)], env=environ, stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, timeout=10)

    def recorded(self) -> list:
        return self.record.read_text().splitlines()

    def test_is_executable(self):
        self.assertTrue(os.access(SCRIPT, os.X_OK))

    def test_from_a_file_manager_it_reopens_itself_in_a_terminal(self):
        self.fake("xdg-terminal-exec")
        self.fake("x-terminal-emulator")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.recorded(), [str(REPO_ROOT), "1", str(SCRIPT)])

    def test_terminals_that_need_a_flag_get_it(self):
        self.fake("x-terminal-emulator")
        self.run_script()
        self.assertEqual(self.recorded(), [str(REPO_ROOT), "1", "-e", str(SCRIPT)])

    def test_gnome_terminal_gets_its_separator(self):
        self.fake("gnome-terminal")
        self.run_script()
        self.assertEqual(self.recorded(), [str(REPO_ROOT), "1", "--", str(SCRIPT)])

    def test_inside_the_terminal_it_runs_the_launcher_from_the_repo(self):
        self.fake("python3")
        self.fake("xdg-terminal-exec")  # must not be used again
        result = self.run_script(EXPRESO_PANEL_IN_TERMINAL="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.recorded(), [str(REPO_ROOT), "1", "-m", "panel.launcher", "--pause-on-error"])

    def test_without_any_terminal_it_still_opens_the_panel(self):
        self.fake("python3")
        self.run_script()
        self.assertEqual(self.recorded(), [str(REPO_ROOT), "", "-m", "panel.launcher", "--pause-on-error"])

    def test_missing_python_is_explained(self):
        result = self.run_script(EXPRESO_PANEL_IN_TERMINAL="1")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, (
            "Hace falta Python 3.9 o superior para abrir el panel.\n"
            "Instalalo con el gestor de paquetes del sistema (el paquete suele llamarse python3).\n"
            "Apretá Enter para cerrar esta ventana."
        ))


if __name__ == "__main__":
    unittest.main()
