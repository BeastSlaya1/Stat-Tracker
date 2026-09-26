import asyncio
from dataclasses import replace
from unittest import TestCase
from unittest.mock import Mock,AsyncMock
import flet as ft
from test_app_integration import app,controls

def prepared():
    a=app();a._save=Mock();a._open_new_match_dialog()
    items=list(controls(a.page.dialog))
    next(c for c in items if isinstance(c,ft.TextField) and c.label=='Opponent team name (required)').value='Hilton'
    next(c for c in items if isinstance(c,ft.Button) and c.content=='Create Match').on_click(None)
    a._save.reset_mock();return a

class GameBrowserTests(TestCase):
    def test_shared_browser_only_for_staff_and_admin(self):
        for role in ['admin','staff','user']:
            a=prepared();a._database_user['role']=role;a._open_database_dialog()
            buttons=[c.content for c in controls(a.page.dialog) if isinstance(c,ft.Button)]
            self.assertEqual('Browse saved games' in buttons,role!='user')
        a.page.dialog=None;a._show_saved_games();self.assertIsNone(a.page.dialog)

    def test_viewing_does_not_change_active_game_or_save(self):
        a=prepared();a.matches.append(replace(a.matches[0],id='second'))
        before=[m.to_dict() for m in a.matches]
        a._view_saved_game('second')
        self.assertEqual(a.active_match_idx,0);self.assertEqual(before,[m.to_dict() for m in a.matches]);a._save.assert_not_called()
        self.assertEqual(a.page.dialog.title.value,'View game')

    def test_search_and_pagination(self):
        a=prepared();first=a.matches[0];a.matches=[replace(first,id=str(i),title=f'Game {i}') for i in range(24)]
        a._show_saved_games()
        def views():return [c for c in controls(a.page.dialog) if isinstance(c,ft.Button) and c.content=='View game']
        self.assertEqual(len(views()),20)
        next(c for c in controls(a.page.dialog) if isinstance(c,ft.TextButton) and c.content=='Next').on_click(None)
        self.assertEqual(len(views()),4)
        search=next(c for c in controls(a.page.dialog) if isinstance(c,ft.TextField))
        search.value='Game 23';search.on_change(None);self.assertEqual(len(views()),1)

    def test_edit_opens_selected_game_using_current_id(self):
        a=prepared();first=a.matches[0];a.matches=[replace(first,id='new'),first]
        a._stop_camera=Mock();a._open_edit_match_dialog=Mock()
        a._open_saved_game_workspace(first.id,edit_details=True)
        self.assertEqual(a.active_match_idx,1);a._open_edit_match_dialog.assert_called_once();a._save.assert_not_called()

    def test_refresh_uses_normal_sync_and_hides_results_after_account_change(self):
        a=prepared();a._sync_database_once=AsyncMock();a._show_saved_games=Mock()
        asyncio.run(a._open_saved_games());a._sync_database_once.assert_awaited_once();a._show_saved_games.assert_called_once()
        async def switch():a._database_token='different'
        a._sync_database_once=AsyncMock(side_effect=switch);a._show_saved_games.reset_mock()
        asyncio.run(a._open_saved_games());a._show_saved_games.assert_not_called()
