import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import flet as ft
import main
import storage
from cloud_sync import SyncState


class Page:
    def __init__(self):
        self.services = []
        self.dialog = None
    def show_dialog(self, dialog):
        self.dialog = dialog
    def pop_dialog(self):
        self.dialog = None
    def update(self):
        pass
    def run_task(self, function, *args):
        pass


def controls(control):
    yield control
    content = getattr(control, "content", None)
    if isinstance(content, ft.Control):
        yield from controls(content)
    for child in getattr(control, "controls", []) or []:
        yield from controls(child)
    for child in getattr(control, "actions", []) or []:
        yield from controls(child)


def app():
    instance = main.StatTrackerApp.__new__(main.StatTrackerApp)
    instance.page = Page()
    instance.is_web = False
    instance._web_prefs = None
    instance.matches = []
    instance.active_match_idx = 0
    instance._full_refresh = lambda: None
    instance._snack = lambda *args: None
    instance._init_database_sync()
    return instance


class AppTests(unittest.TestCase):
    def test_creation_offers_and_saves_only_home_or_away(self):
        for venue in ("Home", "Away"):
            instance = app()
            instance._open_new_match_dialog()
            items = list(controls(instance.page.dialog))
            field = next(c for c in items if isinstance(c, ft.Dropdown) and c.label == "Venue")
            self.assertEqual([option.key for option in field.options], ["Home", "Away"])
            field.value = venue
            opponent = next(c for c in items if isinstance(c, ft.TextField) and c.label == "Opponent team name (required)")
            opponent.value = "Hilton"
            create = next(c for c in items if isinstance(c, ft.Button) and c.content == "Create Match")
            with patch.object(main, "save_matches"):
                create.on_click(None)
            self.assertEqual(instance.matches[0].location, venue)

    def test_login_fields_disable_match_keyboard_shortcuts(self):
        instance = app()
        instance._open_database_dialog()
        fields = [c for c in controls(instance.page.dialog) if isinstance(c, ft.TextField)]
        self.assertEqual(len(fields), 2)
        for field in fields:
            field.on_focus(None)
            self.assertTrue(instance._text_input_focused)
            field.on_blur(None)
            self.assertFalse(instance._text_input_focused)

    def test_native_queue_is_written_before_change_handler_returns(self):
        instance = app()
        instance._database = SyncState()
        instance._open_new_match_dialog()
        items = list(controls(instance.page.dialog))
        next(c for c in items if isinstance(c, ft.TextField) and c.label == "Opponent team name (required)").value = "Hilton"
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "sync.json")
            with patch.object(storage, "SYNC_FILE", path), patch.object(main, "save_matches"):
                next(c for c in items if isinstance(c, ft.Button) and c.content == "Create Match").on_click(None)
                payload = json.loads(Path(path).read_text())
                self.assertEqual(len(payload["state"]["pending"]), 1)
                self.assertNotIn("password", payload)

    def test_access_schools_are_available_offline(self):
        instance = app()
        self.assertIn("Hilton", instance._database_school_names())
        self.assertNotIn("St Charles College", instance._database_school_names())


if __name__ == "__main__":
    unittest.main()
