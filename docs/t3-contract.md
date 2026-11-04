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
  __main__.py             python3 -m panel  (127.0.0.1:8080 by default; --port; a busy port prints one Spanish sentence and exits 2)
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
                           # (the server adds "export_too_big", "unexpected", "unexpected_midrun")
    technical: str         # the bridge's original text, for "Ver detalle técnico"

def preview_export(path: Path) -> Preview
    # load_remitos + is_andino. Also turns the bridge's known gaps into CannotRun("export_unreadable"):
    # JSON that is not a list of objects, a remito without nro_remito, JSON nested too deep
    # (RecursionError), and wrong types: nro_remito and transportista must be text; for Andino remitos
    # also cliente, servicio, observaciones and destinatario.{razon_social, direccion, localidad,
    # provincia, codigo_postal, telefono} must be text or null, and destinatario an object or null.
    # The technical message names the remito's position and the field, and only the file name
    # (never the server's path). Numbers in peso_kg, bultos and valor_declarado stay valid.

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
    # If building it or on_result raises, the error is logged ("panel.bridge") and the run goes on.
    # A null razon_social comes back as "" in the results (the bridge's report cannot print None).
```

```python
def find_overdue_shipments(path: Path, *, base_url: str, api_key: str | None, today: date,
                           client_factory: Callable[[str, str], ExpresoClient] | None = None) -> list[dict]
    # The bridge's public overdue.find_overdue over the export's Andino remitos (is_andino, like the
    # CLI's _overdue). Each dict is the API's shipment (tracking_id, external_ref, status,
    # estimated_delivery) plus recipient, client and city from the export ("" if the export does not
    # carry that remito). CannotRun like run_upload: export_unreadable, missing_key, auth_rejected,
    # api_unavailable. The kit API only knows shipments created in its own process.
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
    action: str | None   # show_fixes | reload | retry | pick_other; None when there is no button

def run_answer(results: list[UploadResult]) -> Answer    # every row of the T2 "frase de arriba" table
# problems() takes optional values={"bultos", "peso_kg", "servicio", "provincia"} read from the
# export remito, because the bridge detail does not carry them ("Los bultos figuran en 0").
def cannot_run(kind: str, export_name: str = "", context: str = "upload",
               limit_bytes: int = 20 * 1024 * 1024) -> Answer  # context "overdue": no "No se cargó ningún envío."
# Kinds: export_unreadable | export_too_big ("El archivo es demasiado grande.", names limit_bytes,
# "pick_other") | missing_key | auth_rejected | api_unavailable | auth_rejected_midrun |
# unexpected ("No se pudo completar la carga.", nothing was loaded) | unexpected_midrun ("La carga se
# cortó a mitad de camino.", loaded ones will not be duplicated, tell sistemas)
def plural(n: int, one: str, other: str) -> str         # Spanish one/other, never "+ s"
```

Overdue (docs/bitacora.md §5 "Atrasados"): `status_text(status)` (`CREATED` "Todavía no salió", `IN_TRANSIT` "En viaje", `EXCEPTION` "Con un problema en el viaje"; an unknown status is returned as is), `late_line(days_late, estimated_delivery)` ("Atrasado 1 día: tenía que llegar el 2 de octubre."), `overdue_title(n, today)` ("2 envíos atrasados al 3 de octubre": the date goes in words because the native date input shows 10/03/2026, which reads two ways), `overdue_empty(today)` ("Ningún envío atrasado al 3 de octubre."), `spanish_date(day)` (month names in a tuple, no locale).

Counting: shipments are results minus `DUPLICATE`. A run with 0 created and at least one already-existing is a second run ("desde una carga anterior"). Created > 0 and already-existing > 0 with nothing to fix uses the 04 sub-line ("3 se cargaron ahora y los otros 20 ya estaban").

## HTTP API (T3.3)

All JSON is UTF-8. Errors use `{"answer": Answer}` with the `cannot_run` phrases, never a stack trace.

Same-site rule, on every route (static and SSE included): the `Host` header must be `127.0.0.1:<port>`, `localhost:<port>` or `[::1]:<port>` (plus the bound host when given and not a wildcard), else `403 {"error": "forbidden_host"}` (this closes DNS rebinding). An `Origin` header, when present, must be `http://` + one of those hosts, else `403 {"error": "forbidden_origin"}`. `POST /api/runs` needs `Content-Type: application/json`, else `415 {"error": "unsupported_media_type"}`. Any other method (HEAD, OPTIONS, PUT, DELETE, PATCH) is `405 {"error": "method_not_allowed"}` with `Allow: GET, POST`. A client that stops sending its body for 30 s is dropped (`408 {"error": "request_timeout"}`).

| Method and path | Body | Response |
| --- | --- | --- |
| `GET /` | | `static/index.html` |
| `GET /static/<file>` | | the file, correct content type, no directory listing, no `..` |
| `POST /api/exports` | raw file bytes; header `X-Export-Name` | `201 {"export_id", "preview": Preview}`; `422 {"answer"}` for unreadable (including wrong types; the upload's folder is removed); `413 {"answer"}` with `export_too_big` when over the cap (20 MB) |
| `POST /api/runs` | `{"export_id"}` | `202 {"run_id"}`; `409 {"answer"}` if a run is active; `404` unknown export |
| `GET /api/runs/<id>/events` | | `text/event-stream`: `event: result` per remito with a `ResultView`, then `event: done` with a `RunView`, or `event: failed` with `{"answer", "technical"}`. Late subscribers get the events so far, then the rest |
| `GET /api/runs/<id>` | | `200 RunView` when done; `200 {"answer", "technical", "run_id"}` when it failed; `202 {"run_id", "running": true}` while it runs; `404 {"error": "unknown_run"}` |
| `GET /api/exports/<export_id>/overdue?today=YYYY-MM-DD` | | `200 OverdueView`; `today` defaults to the server's date. `400 {"error": "bad_date"}` unless `today` is exactly `YYYY-MM-DD` and a real date (`20261020` and `2026-W43-1` are refused, the same on every Python); `404 {"error": "unknown_export"}`; `{"answer", "technical"}` with the `cannot_run` phrases when it cannot run (`422` unreadable, `503` missing key, `502` key rejected or API down) |

```text
ResultView = { index, remito, recipient, client, address, state (TileState|null), label,
               duplicate (bool), tracking, problems: [Problem], picked: str,
               technical: str }        # technical = the bridge detail, untouched
RunView    = { run_id, export_name, export_total, shipments_total, generated_at,
               answer: Answer, counts: {ok, prev, fix, none}, results: [ResultView],
               report_file }
```

```text
OverdueView = { title, empty, items: [{ remito, recipient, client, city, tracking,
                status, status_text, late_line, days_late, estimated_delivery }] }
```

An item whose `estimated_delivery` is not an ISO date is still listed, with `late_line` `""` and `days_late` `null`.

`title` is "N envío(s) atrasado(s) al D de mes" (also for 0), `empty` is the sentence for a day with none. The cannot-run phrases end in "No se cargó ningún envío.", which is wrong for this view; the overdue endpoint uses `cannot_run(kind, name, context="overdue")`, which drops that sentence (and says "No se pudo consultar el estado de los envíos." for `api_unavailable`).

`ResultView.address` is "street, city", or "city, province" when the street is blank (`phrases.address_line`). `Answer.action` tells the page what a button does; the page never decides by the button's text.

If the run stops on an exception nobody foresaw, the `failed` event carries `cannot_run("unexpected")` (nothing loaded) or `("unexpected_midrun")` (some results were already published); `technical` is `Type: message`. It is never mapped to "Expreso Andino no responde".

Not implemented, on purpose: pruning of `runs/exports` and `runs/reports`. They grow with every upload; deleting old ones is left to the operator until it is worth building (the bridge's idempotence means an old export is safe to drop).

Configuration from the environment, read at start: `EXPRESO_API_URL` (default `http://localhost:8000`), `EXPRESO_API_KEY`. The key never reaches the browser.

## Frontend (T3.4)

`static/index.html` + `app.css` + `app.js`, no framework. Three moments on one page, with the 03 visual system and motion rules: pick the export (preview with empty tiles and "Cargar N envíos"), live progress (tiles fill from SSE `result` events), result (answer, legend, map, fix sheet, "Sin respuesta" group, technical details). Cannot-run states per 04, with "Carga de hoy, HH:MM · file" (the time of the attempt) in the header.

T4.1 decisions:
- **DOM order is answer, legend, fix sheet, map** (`#overview` is one grid; areas `answer | map` over `fixes` on wide screens, one column in that order below 64rem). On wide screens the tab order is therefore answer → sheet → map, while the picture is answer | map, sheet. This is deliberate: what needs a person comes first for keyboard and screen readers on every width; the map keeps its own heading ("Los N envíos de esta carga") and label.
- **Back and reload.** Opening the overdue view does `history.pushState({panel: "overdue"})`; Back (`popstate`) returns to the view it came from, and "Volver" calls `history.back()`. The tab's `sessionStorage` key `expreso-panel` keeps `{runId, exportId, name, at, preview}` from the moment a run starts (just `{name}` on the pick screen, for the "La última vez cargaste…" hint). On load the page asks `GET /api/runs/<id>`: `200` RunView restores the result, `200` failed restores the cannot-run screen, `202` re-subscribes to the events, anything else (a `404` after the server restarted) falls back to the pick screen without a message.
- A shipment with a non-empty `technical` that is `ok` or `prev` shows "Ver detalle técnico de R-…" under its picked line.
- The legend uses the tiles' singular labels (`LABELS`).
- T2 table deviations: the overdue title carries the date in words, and the picked line of a `prev` remito that came twice is "Ya estaba cargado de antes. No se duplicó. Venía dos veces en el archivo." (the T2 text "Se cargó una sola vez" is only true on a run that loaded it). Public Sans served from `static/` (not a data URI). Reduced motion, keyboard and forced-colors rules from 03 carry over.

## Tests

- Test-first for `phrases.py`: one test per T2 row, asserting the exact string.
- `test_bridge.py` and `test_server.py` start the kit API on a free port like the bridge's `tests/test_end_to_end.py` and check the first and second run: 19/1/1/3 then 0/20/1/3, live events in order, report written, cannot-run kinds.
- `python3 -m unittest` from the repo root runs everything.
