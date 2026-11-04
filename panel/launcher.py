"""python3 -m panel.launcher: what the double-click files run.

With expreso.ini next to the README the panel talks to the real Expreso Andino API. Without it, the
kit's mock API starts in this same process and the page says "Modo prueba". Either way the browser
opens on its own, and closing the window stops everything.
"""
from __future__ import annotations

import argparse
import configparser
import errno
import importlib.util
import sys
import threading
import webbrowser
from dataclasses import dataclass
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Callable, List, Optional, TextIO, Tuple
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
CONFIG_NAME = "expreso.ini"
SECTION = "expreso_andino"
TEST_API_KEY = "andino-test-7f3a91"  # the kit's published test key, not a secret
DEFAULT_PORT = 8080
_THIS_COMPUTER = {"localhost", "127.0.0.1", "::1"}

_INCOMPLETE = "En expreso.ini falta %s. Completalo y volvé a abrir el panel. (Sin expreso.ini, el panel abre en modo prueba.)"


class LaunchError(Exception):
    """A reason the panel cannot open, already worded for the person who double-clicked."""


def read_config(path: Path) -> Optional[Tuple[str, str]]:
    """(url, api_key) of the real API, or None when there is no file (test mode)."""
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8-sig")  # Notepad's "UTF-8 with BOM" is still UTF-8
    except UnicodeDecodeError:
        raise LaunchError("No se pudo leer expreso.ini: guardalo con codificación UTF-8 y volvé a abrir el panel.")
    except OSError as error:
        raise LaunchError("No se pudo leer expreso.ini: %s." % (error.strerror or error))
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read_string(text, source=CONFIG_NAME)
    except configparser.DuplicateOptionError as error:
        raise LaunchError("No se pudo leer expreso.ini: %s aparece dos veces. Dejá una sola línea con %s."
                          % (error.option, error.option))
    except configparser.Error:
        parser = None
    if parser is None or not parser.has_section(SECTION):
        raise LaunchError("No se pudo leer expreso.ini: tiene que empezar con la línea [expreso_andino]. "
                          "Mirá el ejemplo en expreso.ini.ejemplo.")
    url = parser.get(SECTION, "url", fallback="").strip()
    api_key = parser.get(SECTION, "api_key", fallback="").strip()
    for name, value in (("url", url), ("api_key", api_key)):
        if not value:
            raise LaunchError(_INCOMPLETE % name)
    if not url.startswith(("https://", "http://")):
        raise LaunchError("En expreso.ini, url tiene que empezar con https:// o http://, por ejemplo https://api.example.com.")
    if url.startswith("http://") and urlsplit(url).hostname not in _THIS_COMPUTER:
        raise LaunchError("En expreso.ini, url tiene que empezar con https://. http:// solo sirve para una API en esta "
                          "misma computadora (localhost o 127.0.0.1): con otra dirección, la clave viajaría sin cifrar.")
    return url, api_key


def check_bridge(root: Path) -> None:
    if not (root / "vendor" / "caso-expreso" / "expreso_bridge").is_dir():
        raise LaunchError("Falta el puente en vendor/caso-expreso. La descarga en ZIP de GitHub no lo incluye: "
                          "cloná el repositorio con git clone --recurse-submodules, o corré git submodule update --init.")


def start_test_api(root: Path) -> Tuple[ThreadingHTTPServer, str]:
    """The kit's mock API, unchanged, on a free port in a background thread."""
    source = root / "vendor" / "caso-expreso" / "kit" / "expreso_api.py"
    spec = importlib.util.spec_from_file_location("expreso_kit_api", source)
    kit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(kit)

    class QuietHandler(kit.H):
        def log_message(self, format: str, *args) -> None:  # the window is for the operator
            pass

    api = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
    api.daemon_threads = True
    threading.Thread(target=api.serve_forever, daemon=True).start()
    return api, "http://127.0.0.1:%d" % api.server_address[1]


def bind_panel(port: int, **kwargs):
    """The panel on the asked port, or on a free one when that is taken (a second double-click)."""
    from panel import server

    try:
        return server.create_server("127.0.0.1", port, **kwargs)
    except OSError as error:
        if error.errno != errno.EADDRINUSE:
            raise
        return server.create_server("127.0.0.1", 0, **kwargs)


def _stop_test_api(api: Optional[ThreadingHTTPServer]) -> None:
    if api is not None:
        api.shutdown()
        api.server_close()


@dataclass
class Launched:
    panel: object
    test_api: Optional[ThreadingHTTPServer]
    url: str
    panel_in_background: bool = False

    def serve_in_background(self) -> None:
        self.panel_in_background = True
        threading.Thread(target=self.panel.serve_forever, daemon=True).start()

    def stop(self) -> None:
        if self.panel_in_background:
            self.panel.shutdown()
        self.panel.server_close()
        _stop_test_api(self.test_api)


def launch(
    root: Path,
    *,
    port: int = DEFAULT_PORT,
    open_browser: Callable[[str], bool] = webbrowser.open,
    out: TextIO = sys.stdout,
) -> Launched:
    check_bridge(root)
    config = read_config(root / CONFIG_NAME)
    test_api = None
    if config is None:
        test_api, base_url = start_test_api(root)
        api_key = TEST_API_KEY
    else:
        base_url, api_key = config
    try:
        panel = bind_panel(port, base_url=base_url, api_key=api_key, runs_dir=root / "runs",
                           test_mode=test_api is not None)
    except BaseException:
        _stop_test_api(test_api)
        raise
    launched = Launched(panel, test_api, "http://127.0.0.1:%d" % panel.server_address[1])

    if test_api is not None:
        print("Modo prueba: los envíos van a una API de prueba en esta computadora, no a Expreso Andino.", file=out)
    print("Panel abierto en %s" % launched.url, file=out)
    if not open_browser(launched.url):
        print("No se pudo abrir el navegador: copiá esa dirección en la barra del navegador.", file=out)
    print("Para apagarlo, cerrá esta ventana.", file=out)
    out.flush()
    return launched


def _fail(message: str, code: int, pause: bool) -> int:
    print(message, file=sys.stderr)
    if pause:
        input("Apretá Enter para cerrar esta ventana.")
    return code


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m panel.launcher", description="Abre el panel en el navegador")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--pause-on-error", action="store_true",
                        help="esperar Enter antes de salir por un error, para que la ventana no se cierre sola")
    args = parser.parse_args(argv)

    try:
        launched = launch(ROOT, port=args.port)
    except LaunchError as error:
        return _fail(str(error), 2, args.pause_on_error)
    except Exception as error:  # a traceback means nothing to whoever double-clicked; the window must stay open
        return _fail("No se pudo abrir el panel: %s: %s" % (type(error).__name__, error), 1, args.pause_on_error)
    try:
        launched.panel.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        launched.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
