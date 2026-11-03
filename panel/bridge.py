"""Adapter over the Expreso bridge: preview an export and run an upload with live progress.

Calls only the bridge's public functions, in-process. Business rules stay in the bridge.
"""
from __future__ import annotations

import logging
import sys
import threading
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Optional

VENDOR_DIR = Path(__file__).resolve().parent.parent / "vendor" / "caso-expreso"
if str(VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(VENDOR_DIR))

from expreso_bridge.client import ApiError, AuthenticationError, ExpresoClient  # noqa: E402
from expreso_bridge.overdue import find_overdue  # noqa: E402
from expreso_bridge.remitos import is_andino, load_remitos  # noqa: E402
from expreso_bridge.report import render_run_report  # noqa: E402
from expreso_bridge.upload import Outcome, UploadResult, upload_remitos  # noqa: E402

UPLOAD_LOGGER = "expreso_bridge.upload"

# One run at a time: the progress handler is attached to a process-wide logger.
RUN_LOCK = threading.Lock()


@dataclass(frozen=True)
class Shipment:
    remito: str
    recipient: str
    client: str
    street: str
    city: str
    province: str


@dataclass(frozen=True)
class Preview:
    export_name: str
    export_total: int
    shipments: list[Shipment]
    duplicates: list[str]
    andino_remitos: int    # Expreso Andino remitos in the file, repeats included


class CannotRun(Exception):
    def __init__(self, kind: str, technical: str):
        super().__init__(technical)
        self.kind = kind
        self.technical = technical


@dataclass(frozen=True)
class RunResult:
    results: list[UploadResult]
    report_path: Path
    generated_at: datetime
    export_total: int


def _read_export(path: Path) -> list[dict]:
    try:
        remitos = load_remitos(path)
    except (OSError, ValueError) as error:
        raise CannotRun("export_unreadable", f"No se pudo leer el export {path}: {error}") from error
    if not isinstance(remitos, list):
        raise CannotRun(
            "export_unreadable",
            f"El export {path.name} no es una lista de remitos (es {type(remitos).__name__})",
        )
    for position, remito in enumerate(remitos, start=1):
        if not isinstance(remito, dict):
            raise CannotRun(
                "export_unreadable",
                f"El remito {position} del export {path.name} no es un objeto",
            )
        if "nro_remito" not in remito:
            raise CannotRun(
                "export_unreadable",
                f"El remito {position} del export {path.name} no tiene nro_remito",
            )
    return remitos


def preview_export(path: Path) -> Preview:
    remitos = _read_export(path)
    shipments: list[Shipment] = []
    seen: set[str] = set()
    duplicates: list[str] = []
    andino_remitos = 0
    for remito in remitos:
        if not is_andino(remito):
            continue
        andino_remitos += 1
        number = remito["nro_remito"]
        if number in seen:
            if number not in duplicates:
                duplicates.append(number)
            continue
        seen.add(number)
        recipient = remito.get("destinatario") or {}
        shipments.append(Shipment(
            remito=number,
            recipient=recipient.get("razon_social") or "",
            client=remito.get("cliente") or "",
            street=recipient.get("direccion") or "",
            city=recipient.get("localidad") or "",
            province=recipient.get("provincia") or "",
        ))
    return Preview(
        export_name=path.name,
        export_total=len(remitos),
        shipments=shipments,
        duplicates=duplicates,
        andino_remitos=andino_remitos,
    )


class _ProgressHandler(logging.Handler):
    """Turns the bridge's per-remito log line into on_result(index, UploadResult) calls."""

    def __init__(self, on_result: Callable[[int, UploadResult], None], remitos: list[dict]):
        super().__init__(level=logging.INFO)
        self._on_result = on_result
        self._remitos = remitos
        self.count = 0

    def emit(self, record: logging.LogRecord) -> None:
        number, outcome_value, tracking_id, detail = record.args
        remito = self._remitos[self.count]
        recipient = remito.get("destinatario") or {}
        result = UploadResult(
            remito_number=number,
            recipient=recipient.get("razon_social", ""),
            outcome=Outcome(outcome_value),
            tracking_id=tracking_id,
            detail=detail,
            observations=remito.get("observaciones") or "",
        )
        index = self.count
        self.count += 1
        self._on_result(index, result)


def run_upload(
    path: Path,
    *,
    base_url: str,
    api_key: Optional[str],
    reports_dir: Path,
    on_result: Optional[Callable[[int, UploadResult], None]] = None,
    client_factory: Optional[Callable[[str, str], ExpresoClient]] = None,
) -> RunResult:
    remitos = _read_export(path)
    if not api_key:
        raise CannotRun("missing_key", "Falta la variable de entorno EXPRESO_API_KEY.")
    andino_remitos = [remito for remito in remitos if is_andino(remito)]

    with RUN_LOCK:
        client = (client_factory or ExpresoClient)(base_url, api_key)
        progress = _ProgressHandler(on_result or (lambda index, result: None), andino_remitos)
        upload_logger = logging.getLogger(UPLOAD_LOGGER)
        previous_level = upload_logger.level
        upload_logger.addHandler(progress)
        upload_logger.setLevel(logging.INFO)
        try:
            results = upload_remitos(andino_remitos, client)
        except AuthenticationError as error:
            kind = "auth_rejected_midrun" if progress.count else "auth_rejected"
            raise CannotRun(kind, str(error)) from error
        except ApiError as error:
            raise CannotRun("api_unavailable", str(error)) from error
        finally:
            upload_logger.removeHandler(progress)
            upload_logger.setLevel(previous_level)

    generated_at = datetime.now()
    report = render_run_report(
        results,
        export_name=path.name,
        export_total=len(remitos),
        generated_at=generated_at,
    )
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"corrida_{generated_at:%Y-%m-%dT%H%M%S_%f}.md"
    report_path.write_text(report, encoding="utf-8")
    return RunResult(results, report_path, generated_at, len(remitos))


def find_overdue_shipments(
    path: Path,
    *,
    base_url: str,
    api_key: Optional[str],
    today: date,
    client_factory: Optional[Callable[[str, str], ExpresoClient]] = None,
) -> list[dict]:
    """The bridge's overdue shipments for the export's Andino remitos, with recipient, client and city.

    The shipment dicts are the API's (tracking_id, external_ref, status, estimated_delivery) plus
    `recipient`, `client` and `city` taken from the export ("" when the API knows a remito the export
    does not carry).
    """
    remitos = _read_export(path)
    if not api_key:
        raise CannotRun("missing_key", "Falta la variable de entorno EXPRESO_API_KEY.")
    external_refs = [remito["nro_remito"] for remito in remitos if is_andino(remito)]
    context = {s.remito: s for s in preview_export(path).shipments}

    client = (client_factory or ExpresoClient)(base_url, api_key)
    try:
        found = find_overdue(external_refs, client, today)
    except AuthenticationError as error:
        raise CannotRun("auth_rejected", str(error)) from error
    except ApiError as error:
        raise CannotRun("api_unavailable", str(error)) from error

    enriched = []
    for shipment in found:
        known = context.get(shipment.get("external_ref"))
        enriched.append(dict(
            shipment,
            recipient=known.recipient if known else "",
            client=known.client if known else "",
            city=known.city if known else "",
        ))
    return enriched
