# T3 contract · The panel over the bridge

Technical contract for T3 (`odd/tasks/panel-operaciones.md`). Every T3 worker reads this file. The reasoning in Spanish lives in `docs/bitacora.md` ("Cómo se conecta el panel con el puente").

## Rules that do not move

- **The bridge logic does not change.** `vendor/caso-expreso` is a git submodule pinned to `514738140353c4c818ed725cb21a375a333f626f`. Nothing under `vendor/` is ever edited.
- **The panel calls the bridge's public functions in-process**: `remitos.load_remitos`, `remitos.is_andino`, `client.ExpresoClient`, `upload.upload_remitos`, `report.render_run_report`, `overdue.find_overdue`. It never calls private functions (`_upload_one`, `_upload`, `main`) and never re-implements a business rule (dedup, classification, retries, validation).
- **Live progress comes from the bridge's own log line.** `upload_remitos` logs one INFO record per remito on the logger `expreso_bridge.upload` with `record.args == (remito_number, outcome.value, tracking_id, detail)`. The panel attaches a `logging.Handler` to that logger for the duration of a run. Only one run at a time (a lock), so handlers never mix.
- **Standard library only**, Python 3.9+ (the bridge's floor). No frameworks, no build step.
- **Copy comes from `docs/bitacora.md` §5 "Frases finales (T2)"** and the adaptations in `design/resultado-corrida/04-estados.html` (the "3 nuevos + 20 de antes" sub-line, the "Sin respuesta" sheet group). Visuals come from `design/resultado-corrida/03-el-mapa.html` and `04-estados.html`, decisions from `design/resultado-corrida/polish-t1-1.md`.

## Layout

```
vendor/caso-expreso/      submodule, read-only
panel/
  __init__.py
  __main__.py             python3 -m panel  (127.0.0.1:8080 by default; --port)
  bridge.py               adapter over expreso_bridge (T3.1)
  phrases.py              T2 phrases as code (T3.2)
  server.py               HTTP + SSE server (T3.3)
  static/                 index.html, app.css, app.js, public-sans.woff2 (T3.4)
tests/
  test_bridge.py          against the kit API, like the bridge's end-to-end test
  test_phrases.py
  test_server.py
runs/                     gitignored: uploaded exports and run reports
```

`panel/bridge.py` puts `vendor/caso-expreso` on `sys.path` once, at import, and imports `expreso_bridge.*` from there.

## `panel/bridge.py` (T3.1)

```python
@dataclass(frozen=True)
class Shipment:            # one per distinct Expreso Andino remito, in export order
    remito: str
    recipient: str         # destinatario.razon_social
    client: str            # cliente (the LogiSur customer; not carried by UploadResult)
    street: str
    city: str
    province: str          # as written in the export

@dataclass(frozen=True)
class Preview:
    export_name: str
    export_total: int      # every remito in the file
    shipments: list[Shipment]
    duplicates: list[str]  # remito numbers that appear more than once
    andino_remitos: int    # Expreso Andino remitos in the file, repeats included (for "Los otros N")

class CannotRun(Exception):
    kind: str              # "export_unreadable" | "missing_key" | "auth_rejected"
                           # | "api_unavailable" | "auth_rejected_midrun"
    technical: str         # the bridge's original text, for "Ver detalle técnico"

def preview_export(path: Path) -> Preview
    # load_remitos + is_andino. Also turns the bridge's known gaps into CannotRun("export_unreadable"):
    # JSON that is not a list of objects, a remito without nro_remito.

@dataclass(frozen=True)
class RunResult:
    results: list[UploadResult]   # exactly what upload_remitos returned
    report_path: Path             # render_run_report written to runs/, like the CLI does
    generated_at: datetime
    export_total: int

def run_upload(path: Path, *, base_url: str, api_key: str | None, reports_dir: Path,
               on_result: Callable[[int, UploadResult], None] | None = None,
               client_factory: Callable[[str, str], ExpresoClient] | None = None) -> RunResult
    # Missing key -> CannotRun("missing_key"). AuthenticationError before any result ->
    # "auth_rejected"; after at least one result -> "auth_rejected_midrun". ApiError from the
    # first call (list_provinces) -> "api_unavailable". on_result(index, result) is called from
    # the logging handler, index counting from 0 over the Andino remitos (duplicates included).
    # The UploadResult passed to on_result is rebuilt from record.args (outcome via Outcome(value)).
```

## `panel/phrases.py` (T3.2)

Pure functions, no I/O. Every string comes from the T2 table.

```python
TileState = Literal["ok", "prev", "fix", "none"]
LABELS = {"ok": "Cargado", "prev": "Ya estaba", "fix": "Para corregir", "none": "Sin respuesta"}

def tile_state(outcome: Outcome) -> TileState | None   # DUPLICATE -> None (no tile of its own)

@dataclass(frozen=True)
class Problem:
    title: str
    hint: str

def problems(detail: str, observations: str = "") -> list[Problem]
    # Splits the bridge detail on "; " and maps each part (export field + API message, or a local
    # InvalidRemito text) to its T2 row. Placeholders ({valor}, {n}) are filled from the detail.
    # Unknown parts -> the "rechazó este envío sin explicar por qué" row. Observations add
    # "El remito dice «…»." (and the codigo_postal special case).
def failure(detail: str) -> Problem          # 5xx / sin conexión vs respuesta inesperada
def picked_line(result: UploadResult, duplicated: bool) -> str   # line shown when a tile is chosen

@dataclass(frozen=True)
class Answer:
    headline: str
    sub: str
    button: str | None

def run_answer(results: list[UploadResult]) -> Answer    # every row of the T2 "frase de arriba" table
# problems() takes optional values={"bultos", "peso_kg", "servicio", "provincia"} read from the
# export remito, because the bridge detail does not carry them ("Los bultos figuran en 0").
def cannot_run(kind: str, export_name: str = "") -> Answer
def plural(n: int, one: str, other: str) -> str         # Spanish one/other, never "+ s"
```

Counting: shipments are results minus `DUPLICATE`. A run with 0 created and at least one already-existing is a second run ("desde una carga anterior"). Created > 0 and already-existing > 0 with nothing to fix uses the 04 sub-line ("3 se cargaron ahora y los otros 20 ya estaban").

## HTTP API (T3.3)

All JSON is UTF-8. Errors use `{"answer": Answer}` with the `cannot_run` phrases, never a stack trace.

| Method and path | Body | Response |
| --- | --- | --- |
| `GET /` | | `static/index.html` |
| `GET /static/<file>` | | the file, correct content type, no directory listing, no `..` |
| `POST /api/exports` | raw file bytes; header `X-Export-Name` | `201 {"export_id", "preview": Preview}` or `422 {"answer"}` for unreadable |
| `POST /api/runs` | `{"export_id"}` | `202 {"run_id"}`; `409 {"answer"}` if a run is active; `404` unknown export |
| `GET /api/runs/<id>/events` | | `text/event-stream`: `event: result` per remito with a `ResultView`, then `event: done` with a `RunView`, or `event: failed` with `{"answer", "technical"}`. Late subscribers get the events so far, then the rest |
| `GET /api/runs/<id>` | | `RunView` |

```text
ResultView = { index, remito, recipient, client, address, state (TileState|null), label,
               duplicate (bool), tracking, problems: [Problem], picked: str,
               technical: str }        # technical = the bridge detail, untouched
RunView    = { run_id, export_name, export_total, shipments_total, generated_at,
               answer: Answer, counts: {ok, prev, fix, none}, results: [ResultView],
               report_file }
```

Configuration from the environment, read at start: `EXPRESO_API_URL` (default `http://localhost:8000`), `EXPRESO_API_KEY`. The key never reaches the browser.

## Frontend (T3.4)

`static/index.html` + `app.css` + `app.js`, no framework. Three moments on one page, with the 03 visual system and motion rules: pick the export (preview with empty tiles and "Cargar N envíos"), live progress (tiles fill from SSE `result` events), result (answer, legend, map, fix sheet, "Sin respuesta" group, technical details). Cannot-run states per 04. Public Sans served from `static/` (not a data URI). Reduced motion, keyboard and forced-colors rules from 03 carry over.

## Tests

- Test-first for `phrases.py`: one test per T2 row, asserting the exact string.
- `test_bridge.py` and `test_server.py` start the kit API on a free port like the bridge's `tests/test_end_to_end.py` and check the first and second run: 19/1/1/3 then 0/20/1/3, live events in order, report written, cannot-run kinds.
- `python3 -m unittest` from the repo root runs everything.
