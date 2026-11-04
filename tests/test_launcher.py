from __future__ import annotations

import http.client
import io
import json
import socket
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

from panel import launcher
from panel.server import create_server

from expreso_bridge.client import ExpresoClient

from tests.kit_api import API_KEY, REPO_ROOT


def get_json(port: int, path: str) -> tuple:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", path)
        response = conn.getresponse()
        return response.status, json.loads(response.read())
    finally:
        conn.close()


class ReadConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "expreso.ini"

    def write(self, text: str) -> None:
        self.path.write_text(text, encoding="utf-8")

    def test_no_file_means_test_mode(self):
        self.assertIsNone(launcher.read_config(self.path))

    def test_complete_file_points_at_the_real_api(self):
        self.write("[expreso_andino]\nurl = https://api.example.com/v1 \napi_key =  secret-key\n")
        self.assertEqual(launcher.read_config(self.path), ("https://api.example.com/v1", "secret-key"))

    def test_missing_key_is_explained(self):
        self.write("[expreso_andino]\nurl = https://api.example.com\napi_key =\n")
        with self.assertRaises(launcher.LaunchError) as caught:
            launcher.read_config(self.path)
        self.assertEqual(
            str(caught.exception),
            "En expreso.ini falta api_key. Completalo y volvé a abrir el panel. "
            "(Sin expreso.ini, el panel abre en modo prueba.)",
        )

    def test_missing_url_is_explained(self):
        self.write("[expreso_andino]\napi_key = secret-key\n")
        with self.assertRaises(launcher.LaunchError) as caught:
            launcher.read_config(self.path)
        self.assertEqual(
            str(caught.exception),
            "En expreso.ini falta url. Completalo y volvé a abrir el panel. "
            "(Sin expreso.ini, el panel abre en modo prueba.)",
        )

    def test_url_must_be_http(self):
        self.write("[expreso_andino]\nurl = api.example.com\napi_key = secret-key\n")
        with self.assertRaises(launcher.LaunchError) as caught:
            launcher.read_config(self.path)
        self.assertEqual(
            str(caught.exception),
            "En expreso.ini, url tiene que empezar con https:// o http://, por ejemplo https://api.example.com.",
        )

    def test_unreadable_file_is_explained(self):
        self.write("url = https://api.example.com\n")  # no [expreso_andino] section
        with self.assertRaises(launcher.LaunchError) as caught:
            launcher.read_config(self.path)
        self.assertEqual(
            str(caught.exception),
            "No se pudo leer expreso.ini: tiene que empezar con la línea [expreso_andino]. "
            "Mirá el ejemplo en expreso.ini.ejemplo.",
        )


class CheckBridgeTest(unittest.TestCase):
    def test_missing_bridge_says_how_to_get_it(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(launcher.LaunchError) as caught:
                launcher.check_bridge(Path(root))
        self.assertEqual(
            str(caught.exception),
            "Falta el puente en vendor/caso-expreso. La descarga en ZIP de GitHub no lo incluye: "
            "cloná el repositorio con git clone --recurse-submodules, o corré git submodule update --init.",
        )

    def test_present_bridge_passes(self):
        launcher.check_bridge(REPO_ROOT)


class BindPanelTest(unittest.TestCase):
    def bind(self, port: int):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        panel = launcher.bind_panel(port, base_url="http://127.0.0.1:1", api_key=None,
                                    runs_dir=Path(tmp.name), test_mode=False)
        self.addCleanup(panel.server_close)
        return panel

    def test_busy_port_falls_back_to_a_free_one(self):
        with socket.socket() as taken:
            taken.bind(("127.0.0.1", 0))
            taken.listen()
            busy = taken.getsockname()[1]
            panel = self.bind(busy)
            self.assertNotEqual(panel.server_address[1], busy)
            self.assertNotEqual(panel.server_address[1], 0)

    def test_free_port_is_used_as_asked(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            free = probe.getsockname()[1]
        self.assertEqual(self.bind(free).server_address[1], free)


class ConfigEndpointTest(unittest.TestCase):
    def serve(self, **kwargs):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        server = create_server("127.0.0.1", 0, base_url="http://127.0.0.1:1", api_key=None,
                               runs_dir=Path(tmp.name), **kwargs)
        import threading
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server.server_address[1]

    def test_test_mode_is_reported_to_the_page(self):
        self.assertEqual(get_json(self.serve(test_mode=True), "/api/config"), (200, {"testMode": True}))

    def test_real_mode_is_the_default(self):
        self.assertEqual(get_json(self.serve(), "/api/config"), (200, {"testMode": False}))


class LaunchTest(unittest.TestCase):
    def launch(self, root: Path):
        opened = []
        out = io.StringIO()
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        launched = launcher.launch(root, port=port, open_browser=lambda url: opened.append(url) or True, out=out)
        self.addCleanup(launched.stop)
        launched.serve_in_background()
        return launched, opened, out.getvalue(), port

    def repo_copy(self) -> Path:
        """A root with the real bridge and an empty place for expreso.ini and runs/."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "vendor").mkdir()
        (root / "vendor" / "caso-expreso").symlink_to(REPO_ROOT / "vendor" / "caso-expreso")
        return root

    def test_without_config_it_starts_the_test_api_and_says_so(self):
        root = self.repo_copy()
        launched, opened, out, port = self.launch(root)
        url = "http://127.0.0.1:%d" % port
        self.assertEqual(opened, [url])
        self.assertEqual(out, (
            "Modo prueba: los envíos van a una API de prueba en esta computadora, no a Expreso Andino.\n"
            "Panel abierto en %s\n"
            "Para apagarlo, cerrá esta ventana.\n" % url
        ))
        self.assertEqual(get_json(port, "/api/config"), (200, {"testMode": True}))
        self.assertEqual(launched.panel.api_key, API_KEY)
        client = ExpresoClient(launched.panel.base_url, launched.panel.api_key, sleep=lambda _: None)
        self.assertIn("Córdoba", client.list_provinces())
        self.assertEqual(launched.panel.exports_dir, root / "runs" / "exports")

    def test_with_config_it_uses_the_real_api_and_starts_nothing_else(self):
        root = self.repo_copy()
        (root / "expreso.ini").write_text("[expreso_andino]\nurl = https://api.example.com\napi_key = k\n",
                                          encoding="utf-8")
        launched, opened, out, port = self.launch(root)
        url = "http://127.0.0.1:%d" % port
        self.assertEqual(out, "Panel abierto en %s\nPara apagarlo, cerrá esta ventana.\n" % url)
        self.assertIsNone(launched.test_api)
        self.assertEqual((launched.panel.base_url, launched.panel.api_key), ("https://api.example.com", "k"))
        self.assertEqual(get_json(port, "/api/config"), (200, {"testMode": False}))

    def test_a_browser_that_does_not_open_leaves_the_address_to_copy(self):
        root = self.repo_copy()
        out = io.StringIO()
        launched = launcher.launch(root, port=0, open_browser=lambda url: False, out=out)
        self.addCleanup(launched.stop)
        self.assertTrue(out.getvalue().endswith(
            "No se pudo abrir el navegador: copiá esa dirección en la barra del navegador.\n"
            "Para apagarlo, cerrá esta ventana.\n"))


class MainTest(unittest.TestCase):
    def test_a_launch_error_is_printed_and_exits_with_2(self):
        err = io.StringIO()
        with mock.patch.object(launcher, "launch", side_effect=launcher.LaunchError("Algo falta.")), \
                redirect_stderr(err):
            self.assertEqual(launcher.main([]), 2)
        self.assertEqual(err.getvalue(), "Algo falta.\n")

    def test_pause_on_error_waits_for_enter(self):
        with mock.patch.object(launcher, "launch", side_effect=launcher.LaunchError("Algo falta.")), \
                redirect_stderr(io.StringIO()), mock.patch("builtins.input", return_value="") as asked:
            self.assertEqual(launcher.main(["--pause-on-error"]), 2)
        asked.assert_called_once_with("Apretá Enter para cerrar esta ventana.")


if __name__ == "__main__":
    unittest.main()
