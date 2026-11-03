"""One test per row of the T2 tables (docs/bitacora.md section 5), asserting the exact strings.

Detail strings are the ones the bridge really produces:
upload.py `_describe_validation_errors` (export field + API message), remitos.py `to_shipment`
(InvalidRemito), kit/expreso_api.py `_validate` (API messages), upload.py `_classify` and client.py.
"""
import unittest

from panel import phrases
from panel.phrases import Answer, Problem
from expreso_bridge.upload import Outcome, UploadResult


def result(outcome, remito="R-10000477", detail="", tracking="", observations=""):
    return UploadResult(remito, "Panadería La Espiga", outcome, tracking, detail, observations)


def shipments(ok=0, prev=0, fix=0, none=0, duplicates=0):
    items = []
    items += [result(Outcome.CREATED, tracking="ANDC4BD591C") for _ in range(ok)]
    items += [result(Outcome.ALREADY_EXISTS, tracking="ANDC4BD591C") for _ in range(prev)]
    items += [result(Outcome.REJECTED, detail="destinatario.codigo_postal: required non-empty string")
              for _ in range(fix)]
    items += [result(Outcome.FAILED, detail="la API respondió 503 en los 4 intentos") for _ in range(none)]
    items += [result(Outcome.DUPLICATE, detail="se procesó solo la primera aparición") for _ in range(duplicates)]
    return items


class TileStateTests(unittest.TestCase):
    def test_each_outcome_has_its_tile(self):
        self.assertEqual(phrases.tile_state(Outcome.CREATED), "ok")
        self.assertEqual(phrases.tile_state(Outcome.ALREADY_EXISTS), "prev")
        self.assertEqual(phrases.tile_state(Outcome.REJECTED), "fix")
        self.assertEqual(phrases.tile_state(Outcome.FAILED), "none")

    def test_duplicate_has_no_tile_of_its_own(self):
        self.assertIsNone(phrases.tile_state(Outcome.DUPLICATE))

    def test_labels(self):
        self.assertEqual(
            phrases.LABELS,
            {"ok": "Cargado", "prev": "Ya estaba", "fix": "Para corregir", "none": "Sin respuesta"},
        )

    def test_sheet_titles_and_hint(self):
        self.assertEqual(phrases.SHEET_TITLES["fix"], "Para corregir en LogiSur")
        self.assertEqual(phrases.SHEET_TITLES["none"], "Sin respuesta de Expreso Andino")
        self.assertEqual(
            phrases.SHEET_HINTS["fix"],
            "Cuando los corrijas, volvé a cargar el export. No se duplica nada.",
        )


class PickedLineTests(unittest.TestCase):
    """Estados de un envío: frase al elegir el casillero."""

    def test_created(self):
        r = result(Outcome.CREATED, tracking="ANDC4BD591C")
        self.assertEqual(phrases.picked_line(r, False), "Cargado. Seguimiento ANDC4BD591C.")

    def test_created_after_retry_is_the_same_line(self):
        plain = result(Outcome.CREATED, tracking="ANDC4BD591C")
        retried = result(
            Outcome.CREATED,
            tracking="ANDC4BD591C",
            detail="confirmado en el intento 2 tras un error de la API",
        )
        self.assertEqual(phrases.picked_line(retried, False), phrases.picked_line(plain, False))

    def test_already_exists(self):
        r = result(Outcome.ALREADY_EXISTS, tracking="ANDC4BD591C")
        self.assertEqual(phrases.picked_line(r, False), "Ya estaba cargado de antes. No se duplicó.")

    def test_duplicated_in_the_export_adds_the_sentence_to_the_first_tile(self):
        r = result(Outcome.CREATED, tracking="ANDC4BD591C")
        self.assertEqual(
            phrases.picked_line(r, True),
            "Cargado. Seguimiento ANDC4BD591C. Venía dos veces en el archivo. Se cargó una sola vez.",
        )
        prev = result(Outcome.ALREADY_EXISTS)
        self.assertEqual(
            phrases.picked_line(prev, True),
            "Ya estaba cargado de antes. No se duplicó. Venía dos veces en el archivo. Se cargó una sola vez.",
        )

    def test_the_duplicate_result_itself_says_the_same(self):
        r = result(Outcome.DUPLICATE, detail="se procesó solo la primera aparición")
        self.assertEqual(
            phrases.picked_line(r, True),
            "Venía dos veces en el archivo. Se cargó una sola vez.",
        )

    def test_rejected_is_one_phrase_per_problem(self):
        r = result(Outcome.REJECTED, detail="destinatario.localidad: required non-empty string")
        self.assertEqual(
            phrases.picked_line(r, False),
            "Falta la localidad. Completala en el remito.",
        )

    def test_failed_is_the_failure_phrase(self):
        r = result(Outcome.FAILED, detail="la API respondió 503 en los 4 intentos")
        self.assertEqual(
            phrases.picked_line(r, False),
            "Expreso Andino no respondió. No se perdió nada: volvé a cargar el export en unos minutos.",
        )


class FailureTests(unittest.TestCase):
    NO_RESPONSE = Problem(
        "Expreso Andino no respondió",
        "No se perdió nada: volvé a cargar el export en unos minutos.",
    )
    UNEXPECTED = Problem(
        "Expreso Andino respondió algo inesperado",
        "Volvé a cargar el export más tarde; si sigue igual, avisale a sistemas con el número de remito.",
    )

    def test_every_transient_status_is_no_response(self):
        for status in (500, 502, 503, 504):
            with self.subTest(status=status):
                detail = f"la API respondió {status} en los 4 intentos"
                self.assertEqual(phrases.failure(detail), self.NO_RESPONSE)

    def test_no_connection_is_no_response(self):
        detail = "sin conexión con la API tras 4 intentos: [Errno 111] Connection refused"
        self.assertEqual(phrases.failure(detail), self.NO_RESPONSE)

    def test_any_other_answer_is_unexpected(self):
        for detail in (
            "respuesta inesperada de la API (404): {'error': 'not_found'}",
            "respuesta inesperada de la API (400): {'error': 'invalid_json'}",
        ):
            with self.subTest(detail=detail):
                self.assertEqual(phrases.failure(detail), self.UNEXPECTED)

    def test_unknown_failure_text_is_unexpected(self):
        self.assertEqual(phrases.failure("algo que el puente no dice"), self.UNEXPECTED)


class ProblemTests(unittest.TestCase):
    """Frases por problema: one test per row."""

    def single(self, detail, observations=""):
        found = phrases.problems(detail, observations)
        self.assertEqual(len(found), 1)
        return found[0]

    def test_razon_social(self):
        self.assertEqual(
            self.single("destinatario.razon_social: required non-empty string"),
            Problem("Falta el nombre del destinatario", "Completalo en el remito."),
        )

    def test_direccion(self):
        self.assertEqual(
            self.single("destinatario.direccion: required non-empty string"),
            Problem("Falta la dirección", "En el remito quedó en blanco."),
        )

    def test_localidad(self):
        self.assertEqual(
            self.single("destinatario.localidad: required non-empty string"),
            Problem("Falta la localidad", "Completala en el remito."),
        )

    def test_provincia_missing(self):
        self.assertEqual(
            self.single("destinatario.provincia: required non-empty string"),
            Problem("Falta la provincia", "Completala en el remito."),
        )

    def test_codigo_postal(self):
        self.assertEqual(
            self.single("destinatario.codigo_postal: required non-empty string"),
            Problem("Falta el código postal", "Completalo en el remito."),
        )

    def test_codigo_postal_with_the_known_observation(self):
        self.assertEqual(
            self.single("destinatario.codigo_postal: required non-empty string", "Cliente no informó CP"),
            Problem(
                "Falta el código postal",
                "El remito dice «Cliente no informó CP»: hay que pedírselo al cliente.",
            ),
        )

    def test_provincia_desconocida_local(self):
        self.assertEqual(
            self.single("provincia desconocida: 'Atlantida'"),
            Problem(
                "La provincia «Atlantida» no se reconoce",
                "Escribila completa, por ejemplo «Buenos Aires» o «Córdoba».",
            ),
        )

    def test_provincia_desconocida_from_the_api_has_no_value_in_the_detail(self):
        self.assertEqual(
            self.single("destinatario.provincia: unknown province, see GET /v1/provinces"),
            Problem(
                "La provincia no se reconoce",
                "Escribila completa, por ejemplo «Buenos Aires» o «Córdoba».",
            ),
        )

    def test_provincia_desconocida_from_the_api_with_the_value_supplied(self):
        found = phrases.problems(
            "destinatario.provincia: unknown province, see GET /v1/provinces",
            values={"provincia": "Atlantida"},
        )
        self.assertEqual(found[0].title, "La provincia «Atlantida» no se reconoce")

    def test_bultos(self):
        found = phrases.problems("bultos: integer >= 1", values={"bultos": 0})
        self.assertEqual(found, [Problem("Los bultos figuran en 0", "Tiene que haber al menos 1 bulto.")])

    def test_bultos_without_the_value(self):
        self.assertEqual(
            self.single("bultos: integer >= 1"),
            Problem("Los bultos no son válidos", "Tiene que haber al menos 1 bulto."),
        )

    def test_peso_invalido(self):
        self.assertEqual(
            self.single("peso inválido: 'mucho'"),
            Problem(
                "El peso «mucho» no se puede leer",
                "Escribilo como número, por ejemplo 29,5. Sin separador de miles.",
            ),
        )

    def test_peso_no_positivo(self):
        found = phrases.problems("peso_kg: number > 0", values={"peso_kg": 0.0})
        self.assertEqual(found, [Problem("El peso figura en 0", "Tiene que ser mayor que 0.")])

    def test_peso_no_positivo_decimal_uses_comma(self):
        found = phrases.problems("peso_kg: number > 0", values={"peso_kg": -2.5})
        self.assertEqual(found[0].title, "El peso figura en -2,5")

    def test_peso_no_positivo_without_the_value(self):
        self.assertEqual(
            self.single("peso_kg: number > 0"),
            Problem("El peso no es válido", "Tiene que ser mayor que 0."),
        )

    def test_servicio_desconocido_local(self):
        self.assertEqual(
            self.single("servicio desconocido: 'rapido'"),
            Problem("El servicio «rapido» no existe", "Tiene que ser Normal o Urgente."),
        )

    def test_servicio_from_the_api(self):
        self.assertEqual(
            self.single("servicio: one of: standard, express"),
            Problem("El servicio no existe", "Tiene que ser Normal o Urgente."),
        )

    def test_valor_declarado(self):
        self.assertEqual(
            self.single("valor_declarado: number >= 0"),
            Problem("El valor declarado es negativo", "Tiene que ser 0 o más."),
        )

    def test_nro_remito(self):
        self.assertEqual(
            self.single("nro_remito: required string"),
            Problem("El remito no tiene número", "Revisalo en LogiSur antes de volver a cargar."),
        )

    def test_rejection_without_detail_is_the_fallback(self):
        self.assertEqual(
            self.single("la API rechazó los datos sin detalle"),
            Problem(
                "Expreso Andino rechazó este envío sin explicar por qué",
                "Avisale a sistemas con el número de remito.",
            ),
        )

    def test_unknown_message_is_the_fallback(self):
        self.assertEqual(
            self.single("recipient: required object"),
            Problem(
                "Expreso Andino rechazó este envío sin explicar por qué",
                "Avisale a sistemas con el número de remito.",
            ),
        )

    def test_several_problems_in_one_detail_are_listed_in_order(self):
        detail = (
            "destinatario.direccion: required non-empty string; "
            "destinatario.codigo_postal: required non-empty string; "
            "bultos: integer >= 1"
        )
        found = phrases.problems(detail)
        self.assertEqual(
            [p.title for p in found],
            ["Falta la dirección", "Falta el código postal", "Los bultos no son válidos"],
        )

    def test_local_invalid_remito_text_with_three_problems(self):
        detail = "provincia desconocida: 'Atlantida'; peso inválido: 'mucho'; servicio desconocido: 'rapido'"
        self.assertEqual(
            [p.title for p in phrases.problems(detail)],
            [
                "La provincia «Atlantida» no se reconoce",
                "El peso «mucho» no se puede leer",
                "El servicio «rapido» no existe",
            ],
        )

    def test_known_and_unknown_parts_mix(self):
        found = phrases.problems("destinatario.localidad: required non-empty string; algo raro")
        self.assertEqual(found[0].title, "Falta la localidad")
        self.assertEqual(found[1].title, "Expreso Andino rechazó este envío sin explicar por qué")

    def test_observation_is_added_to_every_problem(self):
        found = phrases.problems(
            "destinatario.localidad: required non-empty string; valor_declarado: number >= 0",
            "Dejar con el encargado",
        )
        self.assertEqual(found[0].hint, "Completala en el remito. El remito dice «Dejar con el encargado».")
        self.assertEqual(found[1].hint, "Tiene que ser 0 o más. El remito dice «Dejar con el encargado».")

    def test_codigo_postal_with_another_observation_keeps_the_hint_and_adds_it(self):
        found = phrases.problems(
            "destinatario.codigo_postal: required non-empty string", "Tocar timbre dos veces"
        )
        self.assertEqual(
            found[0].hint, "Completalo en el remito. El remito dice «Tocar timbre dos veces»."
        )

    def test_blank_observation_adds_nothing(self):
        found = phrases.problems("destinatario.localidad: required non-empty string", "   ")
        self.assertEqual(found[0].hint, "Completala en el remito.")

    def test_picked_line_of_a_rejection_includes_the_observation(self):
        r = result(
            Outcome.REJECTED,
            detail="destinatario.codigo_postal: required non-empty string",
            observations="Cliente no informó CP",
        )
        self.assertEqual(
            phrases.picked_line(r, False),
            "Falta el código postal. El remito dice «Cliente no informó CP»: hay que pedírselo al cliente.",
        )

    def test_picked_line_lists_every_problem(self):
        r = result(
            Outcome.REJECTED,
            detail="destinatario.direccion: required non-empty string; valor_declarado: number >= 0",
        )
        self.assertEqual(
            phrases.picked_line(r, False),
            "Falta la dirección. En el remito quedó en blanco. "
            "El valor declarado es negativo. Tiene que ser 0 o más.",
        )


class PluralTests(unittest.TestCase):
    def test_one(self):
        self.assertEqual(phrases.plural(1, "envío", "envíos"), "envío")

    def test_many(self):
        self.assertEqual(phrases.plural(23, "envío", "envíos"), "envíos")

    def test_zero_is_other(self):
        self.assertEqual(phrases.plural(0, "envío", "envíos"), "envíos")

    def test_irregular_forms_are_given_not_derived(self):
        self.assertEqual(phrases.plural(1, "se cargó", "se cargaron"), "se cargó")
        self.assertEqual(phrases.plural(2, "se cargó", "se cargaron"), "se cargaron")


class RunAnswerTests(unittest.TestCase):
    """La frase de arriba: one test per row."""

    def test_to_fix(self):
        self.assertEqual(
            phrases.run_answer(shipments(ok=19, prev=1, fix=3)),
            Answer(
                "3 de 23 envíos esperan un dato de LogiSur.",
                "Los otros 20 ya están en Expreso Andino. No hace falta hacer nada con ellos.",
                "Ver qué falta",
            ),
        )

    def test_to_fix_and_no_response(self):
        self.assertEqual(
            phrases.run_answer(shipments(ok=18, fix=3, none=2)),
            Answer(
                "5 de 23 envíos no se cargaron.",
                "3 esperan un dato de LogiSur y 2 no tuvieron respuesta de Expreso Andino. "
                "Los otros 18 ya están cargados.",
                "Ver qué pasó",
            ),
        )

    def test_only_no_response(self):
        self.assertEqual(
            phrases.run_answer(shipments(ok=21, none=2)),
            Answer(
                "2 de 23 envíos no se cargaron.",
                "Expreso Andino no respondió. No se perdió nada: volvé a cargar el export en unos minutos.",
                "Volver a cargar el export",
            ),
        )

    def test_all_good_first_load(self):
        self.assertEqual(
            phrases.run_answer(shipments(ok=23)),
            Answer("No tenés que hacer nada.", "Los 23 envíos ya están en Expreso Andino.", None),
        )

    def test_second_load_with_things_left_to_fix(self):
        self.assertEqual(
            phrases.run_answer(shipments(prev=20, fix=3)),
            Answer(
                "3 de 23 envíos esperan un dato de LogiSur.",
                "Los otros 20 ya estaban en Expreso Andino desde una carga anterior. "
                "No se cargó nada dos veces.",
                "Ver qué falta",
            ),
        )

    def test_second_load_all_good(self):
        self.assertEqual(
            phrases.run_answer(shipments(prev=23)),
            Answer(
                "No tenés que hacer nada.",
                "Los 23 envíos ya estaban en Expreso Andino. No se cargó nada dos veces.",
                None,
            ),
        )

    def test_wednesday_some_new_some_before(self):
        self.assertEqual(
            phrases.run_answer(shipments(ok=3, prev=20)),
            Answer(
                "No tenés que hacer nada.",
                "Los 23 envíos ya están en Expreso Andino: 3 se cargaron ahora y los otros 20 ya estaban. "
                "No se cargó nada dos veces.",
                None,
            ),
        )

    def test_duplicates_are_not_shipments(self):
        self.assertEqual(
            phrases.run_answer(shipments(ok=23, duplicates=1)),
            phrases.run_answer(shipments(ok=23)),
        )

    def test_singular_forms(self):
        answer = phrases.run_answer(shipments(ok=1, fix=1))
        self.assertEqual(answer.headline, "1 de 2 envíos espera un dato de LogiSur.")
        self.assertEqual(
            answer.sub, "El otro ya está en Expreso Andino. No hace falta hacer nada con él."
        )
        self.assertEqual(
            phrases.run_answer(shipments(ok=1)).sub, "El envío ya está en Expreso Andino."
        )
        self.assertEqual(
            phrases.run_answer(shipments(ok=2, none=1)).headline, "1 de 3 envíos no se cargó."
        )

    def test_all_to_fix_has_no_others_sentence(self):
        answer = phrases.run_answer(shipments(fix=3))
        self.assertEqual(answer.headline, "3 de 3 envíos esperan un dato de LogiSur.")
        self.assertEqual(answer.sub, "")
        self.assertEqual(answer.button, "Ver qué falta")

    def test_empty_run(self):
        answer = phrases.run_answer([])
        self.assertEqual(answer.headline, "No tenés que hacer nada.")
        self.assertEqual(answer.button, None)


class RunInProgressTests(unittest.TestCase):
    def test_run_in_progress(self):
        self.assertEqual(
            phrases.run_in_progress(),
            Answer("Ya hay una carga en curso.", "Esperá a que termine para cargar otro export.", None),
        )


class CannotRunTests(unittest.TestCase):
    def test_export_unreadable(self):
        self.assertEqual(
            phrases.cannot_run("export_unreadable", "planilla_octubre.xlsx"),
            Answer(
                "No se pudo leer el archivo.",
                "«planilla_octubre.xlsx» no parece un export de LogiSur o está dañado. "
                "Descargalo de nuevo desde LogiSur y volvé a elegirlo. No se cargó ningún envío.",
                "Elegir otro archivo",
            ),
        )

    def test_missing_key(self):
        self.assertEqual(
            phrases.cannot_run("missing_key"),
            Answer(
                "El panel no está conectado con Expreso Andino.",
                "Falta configurar la clave de acceso. Avisale a sistemas. No se cargó ningún envío.",
                None,
            ),
        )

    def test_auth_rejected(self):
        self.assertEqual(
            phrases.cannot_run("auth_rejected"),
            Answer(
                "Expreso Andino no aceptó la conexión.",
                "La clave de acceso del panel no es válida. Avisale a sistemas. No se cargó ningún envío.",
                None,
            ),
        )

    def test_api_unavailable(self):
        self.assertEqual(
            phrases.cannot_run("api_unavailable"),
            Answer(
                "Expreso Andino no responde.",
                "No se cargó ningún envío. Probá de nuevo en unos minutos; si sigue igual, avisale a sistemas.",
                "Volver a intentar",
            ),
        )

    def test_auth_rejected_midrun(self):
        self.assertEqual(
            phrases.cannot_run("auth_rejected_midrun"),
            Answer(
                "La carga se cortó a mitad de camino.",
                "Expreso Andino dejó de aceptar la conexión. Avisale a sistemas. "
                "Lo que se llegó a cargar no se va a duplicar cuando vuelvas a cargar el export.",
                None,
            ),
        )

    def test_unknown_kind_is_an_error(self):
        with self.assertRaises(KeyError):
            phrases.cannot_run("nope")


class BeforeAndDuringTests(unittest.TestCase):
    def test_preview_and_progress(self):
        self.assertEqual(phrases.preview_title(23), "23 envíos para Expreso Andino")
        self.assertEqual(phrases.preview_title(1), "1 envío para Expreso Andino")
        self.assertEqual(
            phrases.preview_sub(51, 24),
            "El archivo tiene 51 remitos. Los otros 27 van con otros transportistas y no se tocan.",
        )
        self.assertEqual(phrases.load_button(23), "Cargar 23 envíos")
        self.assertEqual(phrases.load_button(1), "Cargar 1 envío")
        self.assertEqual(phrases.progress(14, 23), "Cargando 14 de 23…")
        self.assertEqual(
            phrases.PROGRESS_HINT, "Cada casillero se completa cuando Expreso Andino confirma el envío."
        )


if __name__ == "__main__":
    unittest.main()


class EmptyProvinceTests(unittest.TestCase):
    def test_empty_local_province_reads_as_missing(self):
        self.assertEqual(
            phrases.problems("provincia desconocida: ''"),
            [phrases.Problem("Falta la provincia", "Completala en el remito.")],
        )
