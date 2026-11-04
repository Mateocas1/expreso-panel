"""python3 -m panel [--host 127.0.0.1] [--port 8080]"""
import argparse
import errno
import os
import sys

from panel import server


def main() -> int:
    parser = argparse.ArgumentParser(prog="python3 -m panel", description="Panel de operaciones LogiSur → Expreso Andino")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    base_url = os.environ.get("EXPRESO_API_URL") or "http://localhost:8000"
    api_key = os.environ.get("EXPRESO_API_KEY") or None
    if api_key is None:
        print("EXPRESO_API_KEY no está definida: el panel abre, pero no puede cargar envíos.", file=sys.stderr)

    try:
        httpd = server.create_server(
            args.host, args.port, base_url=base_url, api_key=api_key, runs_dir=server.ROOT / "runs"
        )
    except OSError as error:
        if error.errno != errno.EADDRINUSE:
            raise
        print(
            "El puerto %d ya está en uso. Probá con otro: python3 -m panel --port %d" % (args.port, args.port + 10),
            file=sys.stderr,
        )
        return 2
    print("Panel en http://%s:%d (API: %s)" % (args.host, httpd.server_address[1], base_url))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
