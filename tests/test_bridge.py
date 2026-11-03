from __future__ import annotations

import json
import logging
import tempfile
import threading
import unittest
from collections import Counter
from pathlib import Path

from panel import bridge  # first: puts vendor/caso-expreso on sys.path
from panel.bridge import CannotRun, preview_export, run_upload

from expreso_bridge.client import AuthenticationError, ExpresoClient
from expreso_bridge.upload import Outcome

from tests.kit_api import API_KEY, KIT_EXPORT, free_port, running_kit_api

UPLOAD_LOGGER = "expreso_bridge.upload"


def fast_client(base_url: str, api_key: str) -> ExpresoClient:
    return ExpresoClient(base_url, api_key, sleep=lambda _: None, timeout_seconds=0.5)


class AuthFailsAfter(ExpresoClient):
    """Test-only client whose create_shipment starts failing with a 401 after N calls."""

    def __init__(self, *args, calls_before_failure: int, **kwargs):
        super().__init__(*args, **kwargs)
        self._calls_left = calls_before_failure

    def create_shipment(self, shipment: dict):
        if self._calls_left == 0:
            raise AuthenticationError("la API rechazó la API key (401)")
        self._calls_left -= 1
        return super().create_shipment(shipment)


class TempDirTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def write_export(self, content: str, name: str = "export.json") -> Path:
        path = self.tmp / name
        path.write_text(content, encoding="utf-8")
        return path


class PreviewExportTest(TempDirTestCase):
    def test_kit_export_counts(self):
        preview = preview_export(KIT_EXPORT)

        self.assertEqual(preview.export_name, "remitos_2026-09-30.json")
        self.assertEqual(preview.export_total, 51)
        self.assertEqual(len({s.remito for s in preview.shipments}), 23)
        self.assertEqual(len(preview.shipments), 23)
        self.assertEqual(preview.duplicates, ["R-10000507"])
        self.assertEqual(preview.andino_remitos, 24)

    def test_shipment_carries_client_recipient_and_city(self):
        preview = preview_export(KIT_EXPORT)

        shipment = next(s for s in preview.shipments if s.remito == "R-10000477")
        self.assertEqual(shipment.client, "Textil Del Plata SRL")
        self.assertEqual(shipment.recipient, "Panadería La Espiga")
        self.assertEqual(shipment.city, "Pilar")

    def assert_unreadable(self, path: Path) -> CannotRun:
        with self.assertRaises(CannotRun) as caught:
            preview_export(path)
        self.assertEqual(caught.exception.kind, "export_unreadable")
        self.assertTrue(caught.exception.technical)
        return caught.exception

    def test_missing_file(self):
        error = self.assert_unreadable(self.tmp / "nope.json")
        self.assertIn("nope.json", error.technical)

    def test_invalid_json(self):
        self.assert_unreadable(self.write_export("{not json"))

    def test_json_object_instead_of_list(self):
        self.assert_unreadable(self.write_export('{"remitos": []}'))

    def test_list_with_non_dict(self):
        self.assert_unreadable(self.write_export('[{"nro_remito": "R-1"}, 7]'))

    def test_remito_without_number(self):
        self.assert_unreadable(self.write_export(json.dumps([{"transportista": "Expreso Andino"}])))


class RunUploadTest(TempDirTestCase):
    def run_once(self, base_url: str, **kwargs):
        kwargs.setdefault("api_key", API_KEY)
        kwargs.setdefault("client_factory", fast_client)
        return run_upload(KIT_EXPORT, base_url=base_url, reports_dir=self.tmp / "runs", **kwargs)

    def test_first_and_second_run_against_the_kit_api(self):
        with running_kit_api() as base_url:
            events: list = []
            first = self.run_once(base_url, on_result=lambda i, r: events.append((i, r)))
            second = self.run_once(base_url)

        self.assertEqual(
            Counter(r.outcome for r in first.results),
            Counter({Outcome.CREATED: 19, Outcome.ALREADY_EXISTS: 1,
                     Outcome.DUPLICATE: 1, Outcome.REJECTED: 3}),
        )
        self.assertEqual(first.export_total, 51)
        self.assertEqual(len(events), 24)
        self.assertEqual([i for i, _ in events], list(range(24)))
        for (_, streamed), final in zip(events, first.results):
            self.assertEqual(streamed, final)

        report = first.report_path.read_text(encoding="utf-8")
        self.assertTrue(report.startswith("# Resumen de corrida"))
        self.assertIn("remitos_2026-09-30.json", report)
        self.assertEqual(first.report_path.parent, self.tmp / "runs")
        self.assertNotEqual(first.report_path, second.report_path)

        self.assertEqual(
            Counter(r.outcome for r in second.results),
            Counter({Outcome.CREATED: 0, Outcome.ALREADY_EXISTS: 20,
                     Outcome.DUPLICATE: 1, Outcome.REJECTED: 3}) + Counter(),
        )

    def assert_cannot_run(self, kind: str, **kwargs):
        with self.assertRaises(CannotRun) as caught:
            self.run_once(**kwargs)
        self.assertEqual(caught.exception.kind, kind)
        self.assertTrue(caught.exception.technical)
        return caught.exception

    def test_missing_key(self):
        for key in (None, ""):
            with self.subTest(key=key):
                self.assert_cannot_run("missing_key", base_url="http://127.0.0.1:1", api_key=key)

    def test_wrong_key(self):
        with running_kit_api() as base_url:
            self.assert_cannot_run("auth_rejected", base_url=base_url, api_key="wrong")
        self.assertFalse((self.tmp / "runs").exists())

    def test_api_not_running(self):
        self.assert_cannot_run("api_unavailable", base_url=f"http://127.0.0.1:{free_port()}")

    def test_unreadable_export_is_reported_before_anything_else(self):
        with self.assertRaises(CannotRun) as caught:
            run_upload(self.tmp / "nope.json", base_url="http://127.0.0.1:1", api_key=None,
                       reports_dir=self.tmp / "runs")
        self.assertEqual(caught.exception.kind, "export_unreadable")

    def test_auth_rejected_midrun(self):
        def factory(base_url: str, api_key: str) -> ExpresoClient:
            return AuthFailsAfter(base_url, api_key, sleep=lambda _: None,
                                  timeout_seconds=0.5, calls_before_failure=3)

        seen: list = []
        with running_kit_api() as base_url:
            self.assert_cannot_run("auth_rejected_midrun", base_url=base_url,
                                   client_factory=factory,
                                   on_result=lambda i, r: seen.append(i))
        self.assertTrue(seen)
        self.assertFalse((self.tmp / "runs").exists())

    def test_handler_is_removed_after_success_and_after_errors(self):
        upload_logger = logging.getLogger(UPLOAD_LOGGER)
        handlers_before = list(upload_logger.handlers)
        level_before = upload_logger.level

        with running_kit_api() as base_url:
            self.run_once(base_url)
            self.assert_cannot_run("auth_rejected", base_url=base_url, api_key="wrong")

            def boom(i, r):
                raise RuntimeError("callback failed")

            with self.assertRaises(Exception):
                self.run_once(base_url, on_result=boom)

        self.assertEqual(upload_logger.handlers, handlers_before)
        self.assertEqual(upload_logger.level, level_before)

    def test_runs_are_serialized(self):
        started = threading.Event()

        def factory(base_url: str, api_key: str) -> ExpresoClient:
            started.set()
            return fast_client(base_url, api_key)

        with running_kit_api() as base_url:
            worker = threading.Thread(
                target=lambda: self.run_once(base_url, client_factory=factory))
            with bridge.RUN_LOCK:
                worker.start()
                self.assertFalse(started.wait(0.3), "a run started while another held the lock")
            worker.join(30)
        self.assertTrue(started.is_set())
        self.assertFalse(bridge.RUN_LOCK.locked())


if __name__ == "__main__":
    unittest.main()
