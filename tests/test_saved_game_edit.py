from unittest import TestCase
from dataclasses import replace
import flet as ft
from test_app_integration import controls
from test_game_browser import prepared

class SavedGameEditTests(TestCase):
    def test_existing_game_edit_saves_details(self):
        a=prepared();a._open_edit_match_dialog()
        self.assertTrue(a.page.dialog.scrollable)
        fields=list(controls(a.page.dialog))
        next(c for c in fields if isinstance(c,ft.TextField) and c.label=='Opponent team name').value='Updated opponent'
        next(c for c in fields if isinstance(c,ft.Button) and c.content=='Save Changes').on_click(None)
        self.assertEqual(a.matches[0].away_team.name,'Updated opponent');a._save.assert_called_once()

    def test_remote_replacement_requires_reopening_instead_of_losing_edit(self):
        a=prepared();a._open_edit_match_dialog();a.matches=[replace(a.matches[0])]
        next(c for c in controls(a.page.dialog) if isinstance(c,ft.Button) and c.content=='Save Changes').on_click(None)
        a._save.assert_not_called()
        self.assertTrue(any(isinstance(c,ft.Text) and 'changed while' in str(c.value) for c in controls(a.page.dialog)))
