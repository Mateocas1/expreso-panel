"""HTTP + SSE server for the panel. Standard library only; see docs/t3-contract.md "HTTP API (T3.3)".

The server never holds business rules: it stores the uploaded export, runs `bridge.run_upload` in a
background thread and turns what the bridge reports into the views the page draws, with the sentences
from `panel.phrases`. The API key stays in this process.
"""
from __future__ import annotations

import dataclasses
import json
import re
import threading
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlsplit

from panel import bridge, phrases  # first: puts vendor/caso-expreso on sys.path

from expreso_bridge.remitos import is_andino, load_remitos
from expreso_bridge.upload import Outcome, UploadResult

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_MAX_UPLOAD_BYTES = 20 * 1024 * 1024
KEEPALIVE_SECONDS = 15.0

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".woff2": "font/woff2",
    ".txt": "text/plain; charset=utf-8",
}

_RUN_ID = r"[0-9a-f]{32}"


def _answer(answer: phrases.Answer) -> dict:
    return {"answer": dataclasses.asdict(answer)}


def display_name(raw: Optional[str]) -> str:
    """The X-Export-Name header, cleaned for display. It is never used as a path."""
    name = unquote(raw or "").replace("\\", "/").split("/")[-1]
    name = "".join(char for char in name if char.isprintable()).strip()
    return name[:120] or "export.json"


def file_name(display: str) -> str:
    """A filesystem-safe version of the export name, used only inside the upload's own folder."""
    safe = "".join(char if char.isalnum() or char in "._-" else "_" for char in display).strip("._")
    return safe[:120] or "export.json"


class Export:
    def __init__(self, export_id: str, path: Path, preview: bridge.Preview):
        self.export_id = export_id
        self.path = path
        self.preview = preview
        self.shipments = {s.remito: s for s in preview.shipments}
        self.duplicates = set(preview.duplicates)
        # Same order and length as the bridge's results: on_result's index counts over these.
        self.andino = [r for r in load_remitos(path) if is_andino(r)]


class Run:
    """The events of one run, kept so a late subscriber replays them and then follows."""

    def __init__(self, run_id: str, export: Export):
        self.run_id = run_id
        self.export = export
        self.events: List[Tuple[str, dict]] = []
        self.finished = False
        self.view: Optional[dict] = None      # the RunView, once done
        self.failure: Optional[dict] = None   # {"answer", "technical"}, if it failed
        self.changed = threading.Condition()

    def publish(self, name: str, data: dict, finished: bool = False) -> None:
        with self.changed:
            self.events.append((name, data))
            self.finished = finished
            self.changed.notify_all()


def _remito_values(remito: dict) -> dict:
    destinatario = remito.get("destinatario") or {}
    return {
        "bultos": remito.get("bultos"),
        "peso_kg": remito.get("peso_kg"),
        "servicio": remito.get("servicio"),
        "provincia": destinatario.get("provincia"),
    }


def result_view(index: int, result: UploadResult, export: Export) -> dict:
    remito = export.andino[index] if index < len(export.andino) else {}
    shipment = export.shipments.get(result.remito_number)
    state = phrases.tile_state(result.outcome)
    duplicate = result.outcome is Outcome.DUPLICATE
    duplicated = result.remito_number in export.duplicates and not duplicate
    observations = remito.get("observaciones") or result.observations

    if result.outcome is Outcome.REJECTED:
        found = phrases.problems(result.detail, observations, _remito_values(remito))
    elif result.outcome is Outcome.FAILED:
        found = [phrases.failure(result.detail)]
    else:
        found = []
    # The picked line is built from the same problems the page lists, so the values stay in it.
    if result.outcome is Outcome.REJECTED:
        picked = " ".join("%s. %s" % (p.title, p.hint) for p in found)
    else:
        picked = phrases.picked_line(result, duplicated)

    return {
        "index": index,
        "remito": result.remito_number,
        "recipient": (shipment.recipient if shipment else "") or result.recipient,
        "client": shipment.client if shipment else "",
        "address": ", ".join(part for part in (shipment.street, shipment.city) if part) if shipment else "",
        "state": state,
        "label": phrases.LABELS[state] if state else "",
        "duplicate": duplicate,
        "tracking": result.tracking_id,
        "problems": [dataclasses.asdict(p) for p in found],
        "picked": picked,
        "technical": result.detail,
    }


def run_view(run: Run, outcome: bridge.RunResult, views: List[dict]) -> dict:
    counts = {"ok": 0, "prev": 0, "fix": 0, "none": 0}
    for view in views:
        if view["state"]:
            counts[view["state"]] += 1
    return {
        "run_id": run.run_id,
        "export_name": run.export.preview.export_name,
        "export_total": outcome.export_total,
        "shipments_total": sum(counts.values()),
        "generated_at": outcome.generated_at.isoformat(timespec="seconds"),
        "answer": dataclasses.asdict(phrases.run_answer(outcome.results)),
        "counts": counts,
        "results": views,
        "report_file": outcome.report_path.name,
    }


class PanelServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        address: Tuple[str, int],
        *,
        base_url: str,
        api_key: Optional[str],
        runs_dir: Path,
        client_factory: Optional[Callable] = None,
        max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
    ):
        super().__init__(address, Handler)
        self.base_url = base_url
        self.api_key = api_key or None
        self.exports_dir = runs_dir / "exports"
        self.reports_dir = runs_dir / "reports"
        self.client_factory = client_factory
        self.max_upload_bytes = max_upload_bytes
        self.exports: Dict[str, Export] = {}
        self.runs: Dict[str, Run] = {}
        self.active: Optional[Run] = None
        self.state_lock = threading.Lock()

    # --- uploads -----------------------------------------------------------------------------

    def store_export(self, content: bytes, name: str) -> Tuple[Optional[Export], Optional[bridge.CannotRun]]:
        export_id = uuid.uuid4().hex
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        # One folder per upload, keeping a filesystem-safe copy of the original name: the bridge
        # writes path.name into its run report, so the report names the real export.
        folder = self.exports_dir / export_id
        folder.mkdir()
        path = folder / file_name(name)
        path.write_bytes(content)
        try:
            preview = bridge.preview_export(path)
            preview = dataclasses.replace(preview, export_name=name)
            export = Export(export_id, path, preview)
        except bridge.CannotRun as error:
            path.unlink()
            folder.rmdir()
            return None, error
        self.exports[export_id] = export
        return export, None

    # --- runs --------------------------------------------------------------------------------

    def start_run(self, export: Export) -> Optional[Run]:
        """None when another run is active."""
        with self.state_lock:
            if self.active is not None:
                return None
            run = Run(uuid.uuid4().hex, export)
            self.runs[run.run_id] = run
            self.active = run
        threading.Thread(target=self._execute, args=(run,), daemon=True).start()
        return run

    def _execute(self, run: Run) -> None:
        views: Dict[int, dict] = {}

        def on_result(index: int, result: UploadResult) -> None:
            view = result_view(index, result, run.export)
            views[index] = view
            run.publish("result", view)

        try:
            outcome = bridge.run_upload(
                run.export.path,
                base_url=self.base_url,
                api_key=self.api_key,
                reports_dir=self.reports_dir,
                on_result=on_result,
                client_factory=self.client_factory,
            )
            final = [result_view(i, r, run.export) for i, r in enumerate(outcome.results)]
            run.view = run_view(run, outcome, final)
            self._release(run)
            run.publish("done", run.view, finished=True)
        except bridge.CannotRun as error:
            self._fail(run, error.kind, error.technical)
        except Exception as error:  # never a stack trace to the page: the phrase plus the message
            self._fail(run, "api_unavailable", "%s: %s" % (type(error).__name__, error))

    def _fail(self, run: Run, kind: str, technical: str) -> None:
        name = run.export.preview.export_name
        run.failure = {"answer": dataclasses.asdict(phrases.cannot_run(kind, name)), "technical": technical}
        self._release(run)
        run.publish("failed", run.failure, finished=True)

    def _release(self, run: Run) -> None:
        with self.state_lock:
            if self.active is run:
                self.active = None


def create_server(
    host: str,
    port: int,
    *,
    base_url: str,
    api_key: Optional[str],
    runs_dir: Path,
    client_factory: Optional[Callable] = None,
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
) -> PanelServer:
    return PanelServer(
        (host, port),
        base_url=base_url,
        api_key=api_key,
        runs_dir=runs_dir,
        client_factory=client_factory,
        max_upload_bytes=max_upload_bytes,
    )


class Handler(BaseHTTPRequestHandler):
    server: PanelServer

    def log_message(self, format: str, *args) -> None:  # keep the terminal for the operator
        pass

    # --- plumbing ----------------------------------------------------------------------------

    def _send(self, status: int, body: bytes, content_type: str, extra: Optional[dict] = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8", {"Cache-Control": "no-store"})

    def _error(self, status: int, code: str) -> None:
        self._json(status, {"error": code})

    def _read_body(self) -> Optional[bytes]:
        """None when the declared size is over the cap (a 413 was already sent)."""
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length > self.server.max_upload_bytes:
            self.close_connection = True
            self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, _answer(phrases.cannot_run(
                "export_unreadable", display_name(self.headers.get("X-Export-Name")))))
            return None
        return self.rfile.read(length) if length > 0 else b""

    # --- routing -----------------------------------------------------------------------------

    def do_GET(self) -> None:
        try:
            path = urlsplit(self.path).path
            events = re.fullmatch(r"/api/runs/(%s)/events" % _RUN_ID, path)
            run = re.fullmatch(r"/api/runs/(%s)" % _RUN_ID, path)
            if path == "/":
                self._static(STATIC_DIR / "index.html")
            elif path.startswith("/static/"):
                self._static_file(path[len("/static/"):])
            elif events:
                self._events(events.group(1))
            elif run:
                self._run(run.group(1))
            else:
                self._error(HTTPStatus.NOT_FOUND, "not_found")
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except Exception:
            self._safe_500()

    def do_POST(self) -> None:
        try:
            path = urlsplit(self.path).path
            if path == "/api/exports":
                self._post_export()
            elif path == "/api/runs":
                self._post_run()
            else:
                self._error(HTTPStatus.NOT_FOUND, "not_found")
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except Exception:
            self._safe_500()

    def _safe_500(self) -> None:
        try:
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "internal")
        except Exception:
            self.close_connection = True

    # --- static ------------------------------------------------------------------------------

    def _static_file(self, relative: str) -> None:
        relative = unquote(relative)
        if not relative or ".." in relative.split("/") or relative.startswith("/") or "\\" in relative:
            return self._error(HTTPStatus.NOT_FOUND, "not_found")
        self._static(STATIC_DIR / relative)

    def _static(self, target: Path) -> None:
        try:
            resolved = target.resolve()
            inside = resolved.is_relative_to(STATIC_DIR.resolve())
        except (OSError, ValueError):
            inside = False
        content_type = CONTENT_TYPES.get(target.suffix.lower())
        if not inside or content_type is None or not resolved.is_file():
            return self._error(HTTPStatus.NOT_FOUND, "not_found")
        self._send(HTTPStatus.OK, resolved.read_bytes(), content_type, {"Cache-Control": "no-cache"})

    # --- API ---------------------------------------------------------------------------------

    def _post_export(self) -> None:
        content = self._read_body()
        if content is None:
            return
        name = display_name(self.headers.get("X-Export-Name"))
        export, error = self.server.store_export(content, name)
        if export is None:
            return self._json(HTTPStatus.UNPROCESSABLE_ENTITY, _answer(phrases.cannot_run(error.kind, name)))
        preview = dataclasses.asdict(export.preview)
        count = len(export.preview.shipments)
        # The sentences the page shows above the empty tiles, so the page does not rebuild them.
        preview["title"] = phrases.preview_title(count)
        preview["sub"] = phrases.preview_sub(export.preview.export_total, export.preview.andino_remitos)
        preview["button"] = phrases.load_button(count)
        self._json(HTTPStatus.CREATED, {"export_id": export.export_id, "preview": preview})

    def _post_run(self) -> None:
        content = self._read_body()
        if content is None:
            return
        try:
            export_id = json.loads(content.decode("utf-8")).get("export_id")
        except (ValueError, AttributeError):
            return self._error(HTTPStatus.BAD_REQUEST, "bad_request")
        export = self.server.exports.get(export_id) if isinstance(export_id, str) else None
        if export is None:
            return self._error(HTTPStatus.NOT_FOUND, "unknown_export")
        run = self.server.start_run(export)
        if run is None:
            return self._json(HTTPStatus.CONFLICT, _answer(phrases.run_in_progress()))
        self._json(HTTPStatus.ACCEPTED, {"run_id": run.run_id})

    def _run(self, run_id: str) -> None:
        run = self.server.runs.get(run_id)
        if run is None:
            return self._error(HTTPStatus.NOT_FOUND, "unknown_run")
        if run.view is not None:
            self._json(HTTPStatus.OK, run.view)
        elif run.failure is not None:
            self._json(HTTPStatus.OK, dict(run.failure, run_id=run_id))
        else:
            self._json(HTTPStatus.ACCEPTED, {"run_id": run_id, "running": True})

    def _events(self, run_id: str) -> None:
        run = self.server.runs.get(run_id)
        if run is None:
            return self._error(HTTPStatus.NOT_FOUND, "unknown_run")
        self.close_connection = True  # the stream has no length: the end of the stream is the close
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Connection", "close")
        self.end_headers()
        sent = 0
        while True:
            with run.changed:
                if sent == len(run.events) and not run.finished:
                    run.changed.wait(KEEPALIVE_SECONDS)
                pending = run.events[sent:]
                finished = run.finished
            if pending:
                chunk = "".join(
                    "event: %s\ndata: %s\n\n" % (name, json.dumps(data, ensure_ascii=False))
                    for name, data in pending
                )
                sent += len(pending)
            elif finished:
                return
            else:
                chunk = ": keepalive\n\n"
            self.wfile.write(chunk.encode("utf-8"))
            self.wfile.flush()
            if finished and sent == len(run.events):
                return
