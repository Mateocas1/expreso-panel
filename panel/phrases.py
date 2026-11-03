"""T2 phrases as code: bridge results in, Spanish sentences out. Pure functions, no I/O.

Copy comes from docs/bitacora.md section 5 ("Frases finales (T2)") plus the adaptations in
design/resultado-corrida/04-estados.html. The matchers below rely on the exact strings the bridge
produces (see the comments on each one).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional

from expreso_bridge.upload import Outcome, UploadResult

LABELS = {"ok": "Cargado", "prev": "Ya estaba", "fix": "Para corregir", "none": "Sin respuesta"}

# Titles and hints of the "fix sheet" groups (04-estados.html). "Sin respuesta" has no hint in 04.
SHEET_TITLES = {"fix": "Para corregir en LogiSur", "none": "Sin respuesta de Expreso Andino"}
SHEET_HINTS = {"fix": "Cuando los corrijas, volvé a cargar el export. No se duplica nada."}

PROGRESS_HINT = "Cada casillero se completa cuando Expreso Andino confirma el envío."

_TILE_BY_OUTCOME = {
    Outcome.CREATED: "ok",
    Outcome.ALREADY_EXISTS: "prev",
    Outcome.REJECTED: "fix",
    Outcome.FAILED: "none",
}

DUPLICATED_LINE = "Venía dos veces en el archivo. Se cargó una sola vez."


def tile_state(outcome: Outcome) -> Optional[str]:
    """ok | prev | fix | none. A duplicate is the same shipment as the first one: no tile."""
    return _TILE_BY_OUTCOME.get(outcome)


def plural(n: int, one: str, other: str) -> str:
    """The word to use for n: `one` for exactly 1, `other` for everything else (0 included)."""
    return one if n == 1 else other


@dataclass(frozen=True)
class Problem:
    title: str
    hint: str


@dataclass(frozen=True)
class Answer:
    headline: str
    sub: str
    button: Optional[str]


# --- Problems of a shipment to fix ------------------------------------------------------------

_REQUIRED = r"destinatario\.(?P<field>razon_social|direccion|localidad|provincia|codigo_postal)"

# Each part of a rejection detail. Parts come from upload.py `_describe_validation_errors`
# ("<export field>: <API message>", kit/expreso_api.py `_validate`) or from remitos.py
# `to_shipment` (InvalidRemito: "provincia desconocida: '…'", "peso inválido: '…'",
# "servicio desconocido: '…'").
_REQUIRED_FIELD = re.compile(_REQUIRED + r": required non-empty string")
_PROVINCE_LOCAL = re.compile(r"provincia desconocida: '(?P<value>.*)'", re.DOTALL)
_PROVINCE_API = re.compile(r"destinatario\.provincia: unknown province, see GET /v1/provinces")
_PACKAGES = re.compile(r"bultos: integer >= 1")
_WEIGHT_LOCAL = re.compile(r"peso inválido: '(?P<value>.*)'", re.DOTALL)
_WEIGHT_API = re.compile(r"peso_kg: number > 0")
_SERVICE_LOCAL = re.compile(r"servicio desconocido: '(?P<value>.*)'", re.DOTALL)
_SERVICE_API = re.compile(r"servicio: one of: standard, express")
_DECLARED = re.compile(r"valor_declarado: number >= 0")
_NUMBER = re.compile(r"nro_remito: required string")

_REQUIRED_TEXT = {
    "razon_social": Problem("Falta el nombre del destinatario", "Completalo en el remito."),
    "direccion": Problem("Falta la dirección", "En el remito quedó en blanco."),
    "localidad": Problem("Falta la localidad", "Completala en el remito."),
    "provincia": Problem("Falta la provincia", "Completala en el remito."),
    "codigo_postal": Problem("Falta el código postal", "Completalo en el remito."),
}
_PROVINCE_HINT = "Escribila completa, por ejemplo «Buenos Aires» o «Córdoba»."
_UNEXPLAINED = Problem(
    "Expreso Andino rechazó este envío sin explicar por qué",
    "Avisale a sistemas con el número de remito.",
)
_NO_CP_OBSERVATION = "no informo cp"


def _fold(text: str) -> str:
    """Lower-case and accent-insensitive key, enough to recognise the known observation."""
    table = str.maketrans("áéíóúü", "aeiouu")
    return " ".join(text.lower().translate(table).split())


def _number(value: object) -> str:
    """A number as the people reading it write it: decimal comma, no trailing .0."""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).replace(".", ",")


def _quoted(value: str, template: str, bare: str, hint: str) -> Problem:
    return Problem(template.format(value) if value else bare, hint)


def _map_part(part: str, values: Mapping[str, object]) -> Problem:
    match = _REQUIRED_FIELD.fullmatch(part)
    if match:
        return _REQUIRED_TEXT[match.group("field")]
    match = _PROVINCE_LOCAL.fullmatch(part)
    if match and not match.group("value").strip():
        return _REQUIRED_TEXT["provincia"]
    if match:
        return Problem("La provincia «%s» no se reconoce" % match.group("value"), _PROVINCE_HINT)
    if _PROVINCE_API.fullmatch(part):
        value = values.get("provincia")
        title = "La provincia «%s» no se reconoce" % value if value else "La provincia no se reconoce"
        return Problem(title, _PROVINCE_HINT)
    if _PACKAGES.fullmatch(part):
        value = values.get("bultos")
        title = "Los bultos figuran en %s" % _number(value) if value is not None else "Los bultos no son válidos"
        return Problem(title, "Tiene que haber al menos 1 bulto.")
    match = _WEIGHT_LOCAL.fullmatch(part)
    if match:
        return Problem(
            "El peso «%s» no se puede leer" % match.group("value"),
            "Escribilo como número, por ejemplo 29,5. Sin separador de miles.",
        )
    if _WEIGHT_API.fullmatch(part):
        value = values.get("peso_kg")
        title = "El peso figura en %s" % _number(value) if value is not None else "El peso no es válido"
        return Problem(title, "Tiene que ser mayor que 0.")
    match = _SERVICE_LOCAL.fullmatch(part)
    if match:
        return Problem("El servicio «%s» no existe" % match.group("value"), "Tiene que ser Normal o Urgente.")
    if _SERVICE_API.fullmatch(part):
        value = values.get("servicio")
        title = "El servicio «%s» no existe" % value if value else "El servicio no existe"
        return Problem(title, "Tiene que ser Normal o Urgente.")
    if _DECLARED.fullmatch(part):
        return Problem("El valor declarado es negativo", "Tiene que ser 0 o más.")
    if _NUMBER.fullmatch(part):
        return Problem("El remito no tiene número", "Revisalo en LogiSur antes de volver a cargar.")
    return _UNEXPLAINED


def problems(
    detail: str,
    observations: str = "",
    values: Optional[Mapping[str, object]] = None,
) -> List[Problem]:
    """One Problem per part of a rejection detail (parts are joined with "; " by the bridge).

    `values` is optional: the bridge detail does not carry the numeric/enum values the API
    complained about (bultos, peso_kg, servicio, provincia), so the caller may pass them keyed by
    export field to fill the {n}/{valor} placeholders. Without them the title drops the value.
    """
    values = values or {}
    note = observations.strip()
    found = []
    for part in detail.split("; "):
        problem = _map_part(part, values)
        if note:
            is_zip = _REQUIRED_FIELD.fullmatch(part) and part.startswith("destinatario.codigo_postal")
            if is_zip and _NO_CP_OBSERVATION in _fold(note):
                hint = "El remito dice «%s»: hay que pedírselo al cliente." % note
            else:
                hint = "%s El remito dice «%s»." % (problem.hint, note)
            problem = Problem(problem.title, hint)
        found.append(problem)
    return found


# --- Failures after retrying ------------------------------------------------------------------

_NO_RESPONSE = Problem(
    "Expreso Andino no respondió",
    "No se perdió nada: volvé a cargar el export en unos minutos.",
)
_UNEXPECTED = Problem(
    "Expreso Andino respondió algo inesperado",
    "Volvé a cargar el export más tarde; si sigue igual, avisale a sistemas con el número de remito.",
)
# upload.py `_classify` (TRANSIENT_STATUSES = 500, 502, 503, 504) and client.py `_request`.
_TRANSIENT = re.compile(r"la API respondió 50[0234] en los \d+ intentos")
_OFFLINE = re.compile(r"sin conexión con la API tras \d+ intentos: .*", re.DOTALL)


def failure(detail: str) -> Problem:
    if _TRANSIENT.fullmatch(detail) or _OFFLINE.fullmatch(detail):
        return _NO_RESPONSE
    return _UNEXPECTED


# --- The line shown when a tile is picked ------------------------------------------------------

def picked_line(result: UploadResult, duplicated: bool) -> str:
    """`duplicated`: the same remito came again in the export (shown on the first one's tile)."""
    outcome = result.outcome
    if outcome is Outcome.CREATED:
        line = "Cargado. Seguimiento %s." % result.tracking_id
    elif outcome is Outcome.ALREADY_EXISTS:
        line = "Ya estaba cargado de antes. No se duplicó."
    elif outcome is Outcome.DUPLICATE:
        return DUPLICATED_LINE
    elif outcome is Outcome.REJECTED:
        return " ".join(
            "%s. %s" % (p.title, p.hint) for p in problems(result.detail, result.observations)
        )
    else:
        problem = failure(result.detail)
        return "%s. %s" % (problem.title, problem.hint)
    return "%s %s" % (line, DUPLICATED_LINE) if duplicated else line


# --- The answer at the top ---------------------------------------------------------------------

def run_answer(results: List[UploadResult]) -> Answer:
    shipments = [r for r in results if r.outcome is not Outcome.DUPLICATE]
    total = len(shipments)

    def count(outcome: Outcome) -> int:
        return sum(1 for r in shipments if r.outcome is outcome)

    ok, prev = count(Outcome.CREATED), count(Outcome.ALREADY_EXISTS)
    fix, none = count(Outcome.REJECTED), count(Outcome.FAILED)
    envios = plural(total, "envío", "envíos")

    if fix and none:
        loaded = ok + prev
        sub = "%d esperan un dato de LogiSur y %d no tuvieron respuesta de Expreso Andino." % (fix, none)
        if fix == 1:
            sub = sub.replace("1 esperan", "1 espera")
        if none == 1:
            sub = sub.replace("1 no tuvieron", "1 no tuvo")
        if loaded:
            sub += " %s." % (
                "Los otros %d ya están cargados" % loaded if loaded > 1 else "El otro ya está cargado"
            )
        return Answer("%d de %d %s no se cargaron." % (fix + none, total, envios), sub, "Ver qué pasó")

    if fix:
        others = total - fix
        verb = plural(fix, "espera", "esperan")
        headline = "%d de %d %s %s un dato de LogiSur." % (fix, total, envios, verb)
        if not others:
            sub = ""
        elif ok == 0 and prev > 0:
            sub = (
                "Los otros %d ya estaban en Expreso Andino desde una carga anterior. "
                "No se cargó nada dos veces." % others
                if others > 1
                else "El otro ya estaba en Expreso Andino desde una carga anterior. "
                "No se cargó nada dos veces."
            )
        elif others > 1:
            sub = "Los otros %d ya están en Expreso Andino. No hace falta hacer nada con ellos." % others
        else:
            sub = "El otro ya está en Expreso Andino. No hace falta hacer nada con él."
        return Answer(headline, sub, "Ver qué falta")

    if none:
        verb = plural(none, "se cargó", "se cargaron")
        return Answer(
            "%d de %d %s no %s." % (none, total, envios, verb),
            "Expreso Andino no respondió. No se perdió nada: volvé a cargar el export en unos minutos.",
            "Volver a cargar el export",
        )

    headline = "No tenés que hacer nada."
    if total == 0:
        return Answer(headline, "Este export no tiene envíos para Expreso Andino.", None)
    if ok and prev:
        return Answer(
            headline,
            "Los %d envíos ya están en Expreso Andino: %d %s ahora y los otros %d ya estaban. "
            "No se cargó nada dos veces."
            % (total, ok, plural(ok, "se cargó", "se cargaron"), prev),
            None,
        )
    if prev:
        subject = "Los %d envíos ya estaban" % total if total > 1 else "El envío ya estaba"
        return Answer(headline, subject + " en Expreso Andino. No se cargó nada dos veces.", None)
    subject = "Los %d envíos ya están" % total if total > 1 else "El envío ya está"
    return Answer(headline, subject + " en Expreso Andino.", None)


# --- No se pudo correr -------------------------------------------------------------------------

_NOTHING_LOADED = "No se cargó ningún envío."


def cannot_run(kind: str, export_name: str = "") -> Answer:
    """kind: export_unreadable | missing_key | auth_rejected | api_unavailable | auth_rejected_midrun."""
    if kind == "export_unreadable":
        return Answer(
            "No se pudo leer el archivo.",
            "«%s» no parece un export de LogiSur o está dañado. "
            "Descargalo de nuevo desde LogiSur y volvé a elegirlo. %s" % (export_name, _NOTHING_LOADED),
            "Elegir otro archivo",
        )
    if kind == "missing_key":
        return Answer(
            "El panel no está conectado con Expreso Andino.",
            "Falta configurar la clave de acceso. Avisale a sistemas. " + _NOTHING_LOADED,
            None,
        )
    if kind == "auth_rejected":
        return Answer(
            "Expreso Andino no aceptó la conexión.",
            "La clave de acceso del panel no es válida. Avisale a sistemas. " + _NOTHING_LOADED,
            None,
        )
    if kind == "api_unavailable":
        return Answer(
            "Expreso Andino no responde.",
            _NOTHING_LOADED + " Probá de nuevo en unos minutos; si sigue igual, avisale a sistemas.",
            "Volver a intentar",
        )
    if kind == "auth_rejected_midrun":
        return Answer(
            "La carga se cortó a mitad de camino.",
            "Expreso Andino dejó de aceptar la conexión. Avisale a sistemas. "
            "Lo que se llegó a cargar no se va a duplicar cuando vuelvas a cargar el export.",
            None,
        )
    raise KeyError(kind)


# --- Before and during the load ----------------------------------------------------------------

def preview_title(shipments: int) -> str:
    return "%d %s para Expreso Andino" % (shipments, plural(shipments, "envío", "envíos"))


def preview_sub(export_total: int, andino_remitos: int) -> str:
    # Remitos, not shipments: a remito repeated in the export still belongs to Expreso Andino.
    others = export_total - andino_remitos
    return "El archivo tiene %d remitos. %s van con %s y no se tocan." % (
        export_total,
        "Los otros %d" % others if others != 1 else "El otro",
        "otros transportistas",
    )


def load_button(shipments: int) -> str:
    return "Cargar %d %s" % (shipments, plural(shipments, "envío", "envíos"))


def progress(done: int, total: int) -> str:
    return "Cargando %d de %d…" % (done, total)
