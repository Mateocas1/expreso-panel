from __future__ import annotations

import http.client
import json
import socket
import tempfile
import threading
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from panel import bridge, phrases  # first: puts vendor/caso-expreso on sys.path
from panel.server import Handler, Run, create_server

from expreso_bridge.client import ExpresoClient

from tests.kit_api import API_KEY, KIT_EXPORT, running_kit_api


def fast_client(base_url: str, api_key: str) -> ExpresoClient:
    return ExpresoClient(base_url, api_key, sleep=lambda _: None, timeout_seconds=0.5)


class GatedClient(ExpresoClient):
    """Holds the run at its first API call until the test opens the gate."""

    gate = threading.Event()

    def list_provinces(self):
        self.gate.wait(10)
        return super().list_provinces()


JSON = {"Content-Type": "application/json"}


def answer_dict(answer: phrases.Answer) -> dict:
    return {"headline": answer.headline, "sub": answer.sub, "button": answer.button, "action": answer.action}


class PanelClient:
    """Minimal HTTP client over the panel; remembers every body so tests can look for the key."""

    def __init__(self, port: int):
        self.port = port
        self.bodies: list[bytes] = []

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        data = response.read()
        self.bodies.append(data)
        conn.close()
        return response, data

    def json(self, method, path, body=None, headers=None):
        response, data = self.request(method, path, body, headers)
        return response.status, json.loads(data)

    def upload(self, content: bytes, name="remitos_2026-09-30.json"):
        return self.json("POST", "/api/exports", content, {"X-Export-Name": name})

    def start_run(self, export_id):
        body = json.dumps({"export_id": export_id}).encode()
        return self.json("POST", "/api/runs", body, {"Content-Type": "application/json"})

    def events(self, run_id):
        """Reads the whole SSE stream (the server closes it after done/failed)."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        conn.request("GET", f"/api/runs/{run_id}/events")
        response = conn.getresponse()
        assert response.status == 200
        self.content_type = response.getheader("Content-Type")
        self.cache_control = response.getheader("Cache-Control")
        raw = response.read().decode("utf-8")
        self.bodies.append(raw.encode("utf-8"))
        conn.close()
        parsed = []
        for block in raw.split("\n\n"):
            lines = [line for line in block.split("\n") if line and not line.startswith(":")]
            if not lines:
                continue
            name = next(line[7:] for line in lines if line.startswith("event: "))
            data = next(line[6:] for line in lines if line.startswith("data: "))
            parsed.append((name, json.loads(data)))
        return parsed


class PanelTestCase(unittest.TestCase):
    api_key = API_KEY
    client_factory = staticmethod(fast_client)
    max_upload_bytes = 20 * 1024 * 1024

    def setUp(self):
        api = running_kit_api()
        base_url = api.__enter__()
        self.addCleanup(api.__exit__, None, None, None)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.runs_dir = Path(tmp.name)
        self.server = create_server(
            "127.0.0.1", 0,
            base_url=base_url, api_key=self.api_key, runs_dir=self.runs_dir,
            client_factory=self.client_factory, max_upload_bytes=self.max_upload_bytes,
        )
        thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.panel = PanelClient(self.server.server_address[1])

    def upload_kit(self):
        status, body = self.panel.upload(KIT_EXPORT.read_bytes())
        self.assertEqual(status, 201)
        return body["export_id"]

    def run_kit(self):
        status, body = self.panel.start_run(self.upload_kit())
        self.assertEqual(status, 202)
        return body["run_id"]

    def finish_kit_run(self):
        run_id = self.run_kit()
        return run_id, self.panel.events(run_id)

    def results_by_remito(self, events):
        done = events[-1][1]
        return {r["remito"]: r for r in done["results"]}


class UploadTest(PanelTestCase):
    def test_preview_of_the_kit_export(self):
        status, body = self.panel.upload(KIT_EXPORT.read_bytes())

        self.assertEqual(status, 201)
        preview = body["preview"]
        self.assertEqual(preview["export_name"], "remitos_2026-09-30.json")
        self.assertEqual(len(preview["shipments"]), 23)
        self.assertEqual(preview["andino_remitos"], 24)
        self.assertEqual(preview["export_total"], 51)
        self.assertEqual(preview["duplicates"], ["R-10000507"])
        self.assertEqual(phrases.preview_title(23), "23 envíos para Expreso Andino")
        self.assertEqual(
            preview["title"], "23 envíos para Expreso Andino",
        )
        self.assertEqual(preview["sub"], phrases.preview_sub(51, 24))
        self.assertEqual(preview["button"], "Cargar 23 envíos")
        self.assertTrue((self.runs_dir / "exports" / body["export_id"] / "remitos_2026-09-30.json").is_file())

    def test_unreadable_export_is_422_with_the_phrase(self):
        status, body = self.panel.upload(b"esto no es json", name="planilla.xlsx")

        self.assertEqual(status, 422)
        self.assertEqual(
            body, {"answer": answer_dict(phrases.cannot_run("export_unreadable", "planilla.xlsx"))}
        )

    def test_export_that_is_not_a_list_is_422(self):
        status, body = self.panel.upload(b'{"remitos": []}')

        self.assertEqual(status, 422)
        self.assertEqual(body["answer"]["headline"], "No se pudo leer el archivo.")

    def test_export_name_is_display_only(self):
        status, body = self.panel.upload(KIT_EXPORT.read_bytes(), name="../../etc/passwd")

        self.assertEqual(status, 201)
        self.assertEqual(body["preview"]["export_name"], "passwd")
        stored = [p.relative_to(self.runs_dir) for p in (self.runs_dir / "exports").rglob("*") if p.is_file()]
        self.assertEqual(stored, [Path("exports", body["export_id"], "passwd")])

    def test_header_may_be_percent_encoded(self):
        status, body = self.panel.upload(KIT_EXPORT.read_bytes(), name="remitos%20ma%C3%B1ana.json")

        self.assertEqual(body["preview"]["export_name"], "remitos mañana.json")


class UploadCapTest(PanelTestCase):
    max_upload_bytes = 1000

    def test_too_big_is_413_with_the_phrase(self):
        status, body = self.panel.upload(b" " * 2000, name="enorme.json")

        self.assertEqual(status, 413)
        self.assertEqual(
            body, {"answer": answer_dict(phrases.cannot_run("export_too_big", limit_bytes=1000))}
        )
        self.assertEqual(body["answer"]["headline"], "El archivo es demasiado grande.")
        self.assertEqual(body["answer"]["action"], "pick_other")


class FirstRunTest(PanelTestCase):
    def test_stream_has_24_results_in_order_then_done(self):
        run_id, events = self.finish_kit_run()

        self.assertEqual(self.panel.content_type, "text/event-stream; charset=utf-8")
        self.assertEqual(self.panel.cache_control, "no-cache")
        self.assertEqual([name for name, _ in events], ["result"] * 24 + ["done"])
        self.assertEqual([data["index"] for name, data in events[:24]], list(range(24)))
        done = events[-1][1]
        self.assertEqual(done["run_id"], run_id)
        self.assertEqual(done["counts"], {"ok": 19, "prev": 1, "fix": 3, "none": 0})
        self.assertEqual(done["shipments_total"], 23)
        self.assertEqual(done["export_total"], 51)
        self.assertEqual(done["export_name"], "remitos_2026-09-30.json")
        self.assertEqual(
            done["answer"],
            {
                "headline": "3 de 23 envíos esperan un dato de LogiSur.",
                "sub": "Los otros 20 ya están en Expreso Andino. No hace falta hacer nada con ellos.",
                "button": "Ver qué falta",
                "action": "show_fixes",
            },
        )
        self.assertEqual([r["index"] for r in done["results"]], list(range(24)))
        self.assertTrue((self.runs_dir / "reports" / done["report_file"]).is_file())
        report = (self.runs_dir / "reports" / done["report_file"]).read_text(encoding="utf-8")
        self.assertIn("- Export: `remitos_2026-09-30.json`", report)

    def test_live_results_carry_the_same_view_as_the_final_ones(self):
        _, events = self.finish_kit_run()

        live = [data for name, data in events if name == "result"]
        self.assertEqual(live, events[-1][1]["results"])

    def test_missing_postal_code_has_client_and_hint(self):
        _, events = self.finish_kit_run()

        view = self.results_by_remito(events)["R-10000477"]
        self.assertEqual(view["client"], "Textil Del Plata SRL")
        self.assertEqual(view["recipient"], "Panadería La Espiga")
        self.assertEqual(view["address"], "Belgrano 2184, Pilar")
        self.assertEqual(view["state"], "fix")
        self.assertEqual(view["label"], "Para corregir")
        self.assertFalse(view["duplicate"])
        self.assertEqual(
            view["problems"],
            [{
                "title": "Falta el código postal",
                "hint": "El remito dice «Cliente no informó CP»: hay que pedírselo al cliente.",
            }],
        )
        self.assertEqual(view["technical"], "destinatario.codigo_postal: required non-empty string")

    def test_empty_street_reads_city_and_province(self):
        _, events = self.finish_kit_run()

        view = self.results_by_remito(events)["R-10000516"]
        self.assertEqual(view["recipient"], "Sanitarios Rivera")
        self.assertEqual(view["address"], "Caballito, Capital Federal")

    def test_zero_packages_reads_the_value_from_the_export(self):
        _, events = self.finish_kit_run()

        view = self.results_by_remito(events)["R-10000541"]
        self.assertEqual(view["problems"][0]["title"], "Los bultos figuran en 0")
        self.assertEqual(view["state"], "fix")

    def test_created_view_has_tracking_and_picked_line(self):
        _, events = self.finish_kit_run()

        view = next(v for v in events[-1][1]["results"] if v["state"] == "ok")
        self.assertRegex(view["tracking"], r"^ANDC")
        self.assertEqual(view["picked"], "Cargado. Seguimiento %s." % view["tracking"])
        self.assertEqual(view["problems"], [])

    def test_duplicate_row_has_no_tile_and_marks_the_original(self):
        _, events = self.finish_kit_run()

        rows = [v for v in events[-1][1]["results"] if v["remito"] == "R-10000507"]
        self.assertEqual(len(rows), 2)
        original, duplicate = rows
        self.assertIsNone(duplicate["state"])
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(duplicate["picked"], phrases.DUPLICATED_LINE)
        self.assertFalse(original["duplicate"])
        self.assertTrue(original["picked"].endswith(phrases.DUPLICATED_LINE))

    def test_run_view_by_id_equals_the_done_payload(self):
        run_id, events = self.finish_kit_run()

        status, body = self.panel.json("GET", f"/api/runs/{run_id}")

        self.assertEqual(status, 200)
        self.assertEqual(body, events[-1][1])

    def test_late_subscriber_replays_everything(self):
        run_id, first = self.finish_kit_run()

        self.assertEqual(self.panel.events(run_id), first)

    def test_second_run_is_all_previous(self):
        export_id = self.upload_kit()
        first = self.panel.start_run(export_id)[1]["run_id"]
        self.panel.events(first)

        status, body = self.panel.start_run(export_id)
        self.assertEqual(status, 202)
        done = self.panel.events(body["run_id"])[-1][1]

        self.assertEqual(done["counts"], {"ok": 0, "prev": 20, "fix": 3, "none": 0})
        # The repeated remito did not load "once" on a run that loaded nothing
        repeated = next(v for v in done["results"] if v["remito"] == "R-10000507" and not v["duplicate"])
        self.assertEqual(repeated["picked"], "Ya estaba cargado de antes. No se duplicó. Venía dos veces en el archivo.")
        self.assertEqual(done["answer"]["headline"], "3 de 23 envíos esperan un dato de LogiSur.")
        self.assertEqual(
            done["answer"]["sub"],
            "Los otros 20 ya estaban en Expreso Andino desde una carga anterior. "
            "No se cargó nada dos veces.",
        )

    def test_key_is_in_no_response_body(self):
        self.finish_kit_run()

        for body in self.panel.bodies:
            self.assertNotIn(API_KEY.encode(), body)


class ConcurrencyTest(PanelTestCase):
    client_factory = staticmethod(lambda base_url, api_key: GatedClient(base_url, api_key))

    def setUp(self):
        GatedClient.gate = threading.Event()
        self.addCleanup(GatedClient.gate.set)
        super().setUp()

    def test_second_start_while_active_is_409(self):
        export_id = self.upload_kit()
        status, first = self.panel.start_run(export_id)
        self.assertEqual(status, 202)

        status, body = self.panel.start_run(export_id)

        self.assertEqual(status, 409)
        self.assertEqual(body, {"answer": answer_dict(phrases.run_in_progress())})
        GatedClient.gate.set()
        self.assertEqual(self.panel.events(first["run_id"])[-1][0], "done")
        self.assertEqual(self.panel.start_run(export_id)[0], 202)

    def test_subscriber_that_arrives_mid_run_gets_the_rest(self):
        run_id = self.run_kit()
        collected = []
        reader = threading.Thread(target=lambda: collected.extend(self.panel.events(run_id)))
        reader.start()
        GatedClient.gate.set()
        reader.join(20)

        self.assertEqual([n for n, _ in collected], ["result"] * 24 + ["done"])


class FailureTest(PanelTestCase):
    api_key = None

    def test_missing_key_is_a_failed_event(self):
        _, events = self.finish_kit_run()

        self.assertEqual([name for name, _ in events], ["failed"])
        payload = events[0][1]
        self.assertEqual(payload["answer"], answer_dict(phrases.cannot_run("missing_key", "remitos_2026-09-30.json")))
        self.assertTrue(payload["technical"])


class RoutesTest(PanelTestCase):
    def test_unknown_export_and_run_are_404(self):
        body = json.dumps({"export_id": "nope"}).encode()
        self.assertEqual(self.panel.request("POST", "/api/runs", body, JSON)[0].status, 404)
        self.assertEqual(self.panel.request("GET", "/api/runs/nope")[0].status, 404)
        self.assertEqual(self.panel.request("GET", "/api/runs/nope/events")[0].status, 404)
        self.assertEqual(self.panel.request("GET", "/api/other")[0].status, 404)

    def test_bad_json_body_is_400_without_a_trace(self):
        response, data = self.panel.request("POST", "/api/runs", b"{no", JSON)

        self.assertEqual(response.status, 400)
        self.assertNotIn(b"Traceback", data)

    def test_static_traversal_is_404(self):
        for path in ("/static/../server.py", "/static/%2e%2e/server.py", "/static/..%2fserver.py",
                     "/static//etc/passwd", "/static/", "/static/nope.css"):
            response, _ = self.panel.request("GET", path)
            self.assertEqual(response.status, 404, path)

    def test_static_serves_files_with_their_content_type(self):
        static = Path(__file__).resolve().parent.parent / "panel" / "static"
        font = static / "public-sans.woff2"
        if not font.is_file():
            self.skipTest("panel/static is still being built")

        response, data = self.panel.request("GET", "/static/public-sans.woff2")

        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("Content-Type"), "font/woff2")
        self.assertEqual(data, font.read_bytes())

    def test_root_is_index_html_or_404_while_it_does_not_exist(self):
        index = Path(__file__).resolve().parent.parent / "panel" / "static" / "index.html"

        response, data = self.panel.request("GET", "/")

        if index.is_file():
            self.assertEqual(response.status, 200)
            self.assertEqual(response.getheader("Content-Type"), "text/html; charset=utf-8")
            self.assertEqual(data, index.read_bytes())
        else:
            self.assertEqual(response.status, 404)


class OverdueTest(PanelTestCase):
    def overdue(self, export_id, query=""):
        return self.panel.json("GET", "/api/exports/%s/overdue%s" % (export_id, query))

    def test_after_a_first_run_two_are_late_one_day(self):
        self.finish_kit_run()
        export_id = next(iter(self.server.exports))

        status, body = self.overdue(export_id, "?today=2026-10-03")

        self.assertEqual(status, 200)
        self.assertEqual(body["title"], "2 envíos atrasados al 3 de octubre")
        self.assertEqual(body["empty"], "Ningún envío atrasado al 3 de octubre.")
        items = sorted(body["items"], key=lambda item: item["remito"])
        self.assertEqual([item["remito"] for item in items], ["R-10000513", "R-10000548"])
        for item in items:
            self.assertEqual(
                sorted(item),
                ["city", "client", "days_late", "estimated_delivery", "late_line", "recipient",
                 "remito", "status", "status_text", "tracking"],
            )
            self.assertEqual(item["status"], "IN_TRANSIT")
            self.assertEqual(item["status_text"], "En viaje")
            self.assertEqual(item["days_late"], 1)
            self.assertEqual(item["estimated_delivery"], "2026-10-02")
            self.assertEqual(item["late_line"], "Atrasado 1 día: tenía que llegar el 2 de octubre.")
            self.assertRegex(item["tracking"], r"^AND")
            self.assertTrue(item["recipient"] and item["client"] and item["city"])

    def test_nothing_late_gives_the_empty_sentence(self):
        self.finish_kit_run()
        export_id = next(iter(self.server.exports))

        status, body = self.overdue(export_id, "?today=2026-10-02")

        self.assertEqual(status, 200)
        self.assertEqual(body["items"], [])
        self.assertEqual(body["title"], "0 envíos atrasados al 2 de octubre")
        self.assertEqual(body["empty"], "Ningún envío atrasado al 2 de octubre.")

    def test_default_today_is_accepted(self):
        self.finish_kit_run()
        export_id = next(iter(self.server.exports))

        status, body = self.overdue(export_id)

        self.assertEqual(status, 200)
        self.assertEqual(body["empty"], phrases.overdue_empty(date.today()))
        self.assertEqual(body["title"], phrases.overdue_title(len(body["items"]), date.today()))

    def test_bad_date_is_400(self):
        export_id = self.upload_kit()
        for value in ("2026-13-01", "ayer", ""):
            with self.subTest(value=value):
                status, body = self.overdue(export_id, "?today=" + value)
                self.assertEqual((status, body), (400, {"error": "bad_date"}))

    def test_unknown_export_is_404(self):
        status, body = self.overdue("0" * 32, "?today=2026-10-03")

        self.assertEqual((status, body), (404, {"error": "unknown_export"}))


class OverdueWithoutKeyTest(PanelTestCase):
    api_key = None

    def test_missing_key_is_a_cannot_run_answer(self):
        export_id = self.upload_kit()

        status, body = self.panel.json("GET", "/api/exports/%s/overdue?today=2026-10-03" % export_id)

        self.assertEqual(status, 503)
        self.assertEqual(body["answer"], answer_dict(phrases.cannot_run("missing_key", context="overdue")))
        self.assertNotIn("No se cargó", body["answer"]["sub"])
        self.assertTrue(body["technical"])


class WrongTypesTest(PanelTestCase):
    def exports(self):
        folder = self.runs_dir / "exports"
        return sorted(folder.iterdir()) if folder.exists() else []

    def test_exports_with_wrong_types_are_422_and_leave_no_folder(self):
        cases = {
            "destinatario text": b'[{"nro_remito":"A1","transportista":"Expreso Andino","destinatario":"x"}]',
            "nro_remito list": b'[{"nro_remito":["a"]}]',
            "transportista number": b'[{"nro_remito":"A1","transportista":5}]',
            "nested": b"[" * 100000,
        }
        for label, content in cases.items():
            with self.subTest(label):
                status, body = self.panel.upload(content, name="malo.json")
                self.assertEqual(status, 422)
                self.assertEqual(body, {"answer": answer_dict(phrases.cannot_run("export_unreadable", "malo.json"))})
                self.assertEqual(self.exports(), [])

    def test_a_failure_while_storing_leaves_no_folder(self):
        with mock.patch("panel.server.bridge.preview_export", side_effect=RuntimeError("boom")):
            status, body = self.panel.json("POST", "/api/exports", KIT_EXPORT.read_bytes(), {"X-Export-Name": "a.json"})

        self.assertEqual((status, body), (500, {"error": "internal"}))
        self.assertEqual(self.exports(), [])

    def test_the_reviewed_crash_never_reaches_the_run(self):
        remitos = json.loads(KIT_EXPORT.read_text(encoding="utf-8"))
        andino = [r for r in remitos if r["transportista"] == "Expreso Andino"]
        for position, remito in enumerate(andino):
            remito["nro_remito"] = "Z-%d" % position
        andino[-1]["destinatario"]["razon_social"] = 12345

        status, body = self.panel.upload(json.dumps(remitos).encode())

        self.assertEqual(status, 422)
        self.assertEqual(body["answer"]["headline"], "No se pudo leer el archivo.")


class BoomClient(ExpresoClient):
    """Raises a plain RuntimeError at its Nth create_shipment (0 = before the first result)."""

    boom_at = 0
    calls = 0

    def create_shipment(self, shipment):
        if type(self).calls == self.boom_at:
            raise RuntimeError("boom")
        type(self).calls += 1
        return super().create_shipment(shipment)


def boom_after(count: int):
    client_class = type("Boom%d" % count, (BoomClient,), {"boom_at": count, "calls": 0})
    return lambda base_url, api_key: client_class(base_url, api_key, sleep=lambda _: None, timeout_seconds=0.5)


class UnexpectedFailureTest(PanelTestCase):
    client_factory = staticmethod(boom_after(3))

    def test_midrun_says_it_was_cut_in_half_and_keeps_the_exception(self):
        _, events = self.finish_kit_run()

        self.assertEqual([name for name, _ in events], ["result"] * 3 + ["failed"])
        failed = events[-1][1]
        self.assertEqual(failed["answer"], answer_dict(phrases.cannot_run("unexpected_midrun")))
        self.assertEqual(failed["technical"], "RuntimeError: boom")
        self.assertEqual(failed["answer"]["headline"], "La carga se cortó a mitad de camino.")


class UnexpectedBeforeAnyTest(PanelTestCase):
    client_factory = staticmethod(boom_after(0))

    def test_before_any_result_says_nothing_was_loaded(self):
        _, events = self.finish_kit_run()

        self.assertEqual([name for name, _ in events], ["failed"])
        self.assertEqual(events[0][1]["answer"], answer_dict(phrases.cannot_run("unexpected")))
        self.assertEqual(events[0][1]["answer"]["sub"], "No se cargó ningún envío. Avisale a sistemas.")
        self.assertEqual(events[0][1]["technical"], "RuntimeError: boom")


class RawMixin:
    def raw(self, request: bytes, timeout=5.0) -> bytes:
        with socket.create_connection(("127.0.0.1", self.panel.port), timeout=timeout) as sock:
            sock.sendall(request)
            chunks = []
            while True:
                try:
                    chunk = sock.recv(65536)
                except socket.timeout:
                    break
                if not chunk:
                    break
                chunks.append(chunk)
        return b"".join(chunks)


class SameSiteTest(PanelTestCase):
    def hosts(self):
        port = self.panel.port
        return ["127.0.0.1:%d" % port, "localhost:%d" % port, "[::1]:%d" % port]

    def test_foreign_host_is_403_on_every_route(self):
        port = self.panel.port
        export_id = self.upload_kit()
        calls = [
            ("GET", "/"), ("GET", "/static/app.js"), ("GET", "/api/runs/%s" % ("0" * 32)),
            ("GET", "/api/runs/%s/events" % ("0" * 32)), ("GET", "/api/exports/%s/overdue" % export_id),
            ("POST", "/api/exports"), ("POST", "/api/runs"),
        ]
        for host in ("attacker.example:%d" % port, "127.0.0.1", "127.0.0.1:%d" % (port + 1), ""):
            for method, path in calls:
                with self.subTest(host=host, call=(method, path)):
                    headers = {"Host": host, "Origin": "http://%s" % host, "Content-Type": "text/plain"}
                    status, body = self.panel.json(method, path, b"{}" if method == "POST" else None, headers)
                    self.assertEqual((status, body), (403, {"error": "forbidden_host"}))

    def test_rebinding_post_stores_nothing_and_starts_nothing(self):
        host = "attacker.example:%d" % self.panel.port
        headers = {"Host": host, "Origin": "http://" + host, "Content-Type": "text/plain"}

        status, _ = self.panel.json("POST", "/api/exports", KIT_EXPORT.read_bytes(), headers)

        self.assertEqual(status, 403)
        self.assertFalse((self.runs_dir / "exports").exists())
        self.assertEqual(self.server.exports, {})

    def test_loopback_names_are_accepted(self):
        for host in self.hosts():
            with self.subTest(host=host):
                response, _ = self.panel.request("GET", "/", headers={"Host": host})
                self.assertIn(response.status, (200, 404))
                self.assertNotEqual(response.status, 403)

    def test_origin_must_be_an_allowed_host(self):
        port = self.panel.port
        for origin in ("http://attacker.example:%d" % port, "https://127.0.0.1:%d" % port, "null",
                       "http://127.0.0.1", "http://127.0.0.1:%d/x" % port):
            with self.subTest(origin=origin):
                status, body = self.panel.json("GET", "/api/runs/%s" % ("0" * 32), headers={"Origin": origin})
                self.assertEqual((status, body), (403, {"error": "forbidden_origin"}))
        for host in self.hosts():
            with self.subTest(origin_ok=host):
                headers = {"Host": host, "Origin": "http://" + host}
                status, body = self.panel.json("GET", "/api/runs/%s" % ("0" * 32), headers=headers)
                self.assertEqual((status, body), (404, {"error": "unknown_run"}))

    def test_runs_require_a_json_content_type(self):
        export_id = self.upload_kit()
        body = json.dumps({"export_id": export_id}).encode()
        for content_type in ("text/plain", "application/x-www-form-urlencoded", None):
            with self.subTest(content_type=content_type):
                headers = {"Content-Type": content_type} if content_type else {}
                status, answer = self.panel.json("POST", "/api/runs", body, headers)
                self.assertEqual((status, answer), (415, {"error": "unsupported_media_type"}))
        self.assertIsNone(self.server.active)
        status, _ = self.panel.json("POST", "/api/runs", body, {"Content-Type": "application/json; charset=utf-8"})
        self.assertEqual(status, 202)


class TimeoutTest(RawMixin, PanelTestCase):
    def test_a_body_that_never_arrives_is_dropped(self):
        with mock.patch.object(Handler, "timeout", 0.3):
            reply = self.raw(
                b"POST /api/exports HTTP/1.1\r\nHost: 127.0.0.1:%d\r\nContent-Length: 500\r\n\r\nabc"
                % self.panel.port,
                timeout=5,
            )

        self.assertTrue(reply.startswith(b"HTTP/1.0 408") or reply == b"", reply[:60])
        self.assertFalse((self.runs_dir / "exports").exists() and list((self.runs_dir / "exports").iterdir()))


class MethodsTest(PanelTestCase):
    def test_other_methods_are_a_json_405(self):
        for method in ("HEAD", "OPTIONS", "PUT", "DELETE", "PATCH"):
            with self.subTest(method=method):
                response, data = self.panel.request(method, "/")
                self.assertEqual(response.status, 405)
                self.assertEqual(response.getheader("Allow"), "GET, POST")
                self.assertEqual(response.getheader("Content-Type"), "application/json; charset=utf-8")
                if method != "HEAD":
                    self.assertEqual(json.loads(data), {"error": "method_not_allowed"})


class EventsErrorTest(RawMixin, PanelTestCase):
    def test_an_error_after_the_headers_never_writes_a_second_response(self):
        run_id = "a" * 32
        run = Run(run_id, None)
        run.publish("result", {"not": object()}, finished=True)  # json.dumps fails mid-stream
        self.server.runs[run_id] = run

        with self.assertLogs("panel.server", "ERROR"):
            reply = self.raw(b"GET /api/runs/%s/events HTTP/1.1\r\nHost: 127.0.0.1:%d\r\n\r\n"
                             % (run_id.encode(), self.panel.port))

        self.assertEqual(reply.count(b"HTTP/1."), 1, reply)
        self.assertTrue(reply.startswith(b"HTTP/1.0 200"))


class StrictDateAndOverdueItemTest(PanelTestCase):
    def test_only_yyyy_mm_dd_is_a_date(self):
        export_id = self.upload_kit()
        for value in ("20261020", "2026-W43-1", "2026-10-3", "%EF%BC%92%EF%BC%90%EF%BC%92%EF%BC%96-10-20", "2026-10-20T00:00"):
            with self.subTest(value=value):
                status, body = self.panel.json("GET", "/api/exports/%s/overdue?today=%s" % (export_id, value))
                self.assertEqual((status, body), (400, {"error": "bad_date"}))

    def test_overdue_item_with_an_unreadable_date_is_shown_without_late_line(self):
        export_id = self.upload_kit()
        found = [{"external_ref": "R-1", "tracking_id": "AND1", "status": "IN_TRANSIT",
                  "estimated_delivery": "pronto", "recipient": "x", "client": "y", "city": "z"}]

        with mock.patch("panel.server.bridge.find_overdue_shipments", return_value=found):
            status, body = self.panel.json("GET", "/api/exports/%s/overdue?today=2026-10-03" % export_id)

        self.assertEqual(status, 200)
        item = body["items"][0]
        self.assertEqual((item["late_line"], item["days_late"], item["estimated_delivery"]), ("", None, "pronto"))
        self.assertEqual(item["remito"], "R-1")


class BusyPortTest(unittest.TestCase):
    def test_a_port_in_use_is_one_spanish_sentence_and_exit_code_2(self):
        from contextlib import redirect_stderr, redirect_stdout
        from io import StringIO
        from panel import __main__ as entry

        with socket.socket() as busy:
            busy.bind(("127.0.0.1", 0))
            busy.listen()
            port = busy.getsockname()[1]
            err = StringIO()
            with mock.patch("sys.argv", ["panel", "--port", str(port)]), redirect_stderr(err), redirect_stdout(StringIO()):
                code = entry.main()

        self.assertEqual(code, 2)
        self.assertEqual(
            err.getvalue().strip().splitlines()[-1],
            "El puerto %d ya está en uso. Probá con otro: python3 -m panel --port %d" % (port, port + 10),
        )


if __name__ == "__main__":
    unittest.main()
