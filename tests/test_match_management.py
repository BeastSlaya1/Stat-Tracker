import asyncio
from unittest import TestCase
from unittest.mock import Mock, AsyncMock, patch
from types import SimpleNamespace
import flet as ft
import account_ui, database_ui, storage
from cloud_sync import SyncState
from test_game_browser import prepared
from test_app_integration import controls

class MatchManagementTests(TestCase):
    def test_close_keeps_match_without_queueing_delete_and_can_reopen(self):
        a=prepared();m=a.match;m.created_by_name='Creator';m.edited_by_name='Editor'
        a._database=SyncState({'known':{m.id:m.to_dict()},'versions':{m.id:1}})
        a._save=lambda:a._database_changed();a._timer_running=True
        a._stop_camera=Mock();a.camera_on=True;a.fullscreen_video=False
        with patch.object(storage,'save_sync_state'):
            a._close_match()
        self.assertIsNone(a.match);self.assertFalse(a._timer_running)
        self.assertEqual(a.matches,[m]);self.assertEqual(a._database.outgoing(),[])
        self.assertEqual(m.edited_by_name,'Editor');a._stop_camera.assert_called_once()
        a.match_dd=ft.Dropdown();a._refresh_match_dd();self.assertEqual(a.match_dd.value,"none")
        a._on_match_select(SimpleNamespace(control=SimpleNamespace(value='0')))
        self.assertIsNone(a.match)
        a._open_saved_game_workspace(m.id)
        self.assertIs(a.match,m)

    def test_delete_stale_confirmation_cannot_delete_another_account_match(self):
        a=prepared();m=a.match
        a._do_delete_match(m.id,'old-session');self.assertEqual(a.matches,[m])
        a._do_delete_match('other-match',a._database_token);self.assertEqual(a.matches,[m])
        a._database=SyncState({'known':{m.id:m.to_dict()},'versions':{m.id:1}})
        a._save=lambda:a._database_changed()
        with patch.object(storage,'save_sync_state'):
            a._do_delete_match(m.id,a._database_token)
        self.assertEqual(a.matches,[]);self.assertIsNone(a.match)
        self.assertTrue(a._database.outgoing()[0][1]['deleted'])

    def test_sync_does_not_open_first_game_when_nothing_selected(self):
        async def run():
            a=prepared();m=a.match;a.matches=[];a.active_match_idx=-1;a._database=SyncState()
            a._persist_database=AsyncMock();a._database_last_catalog=10**20
            async def receive(state,*args):state.receive({'id':m.id,'body':m.to_dict(),'version':1,'deleted':False})
            with patch.object(database_ui,'api_request',AsyncMock(return_value={'user':a._database_user})),patch.object(database_ui,'synchronize',receive),patch.object(storage,'save_matches'):
                await a._sync_database_once()
            self.assertEqual(len(a.matches),1);self.assertIsNone(a.match)
        asyncio.run(run())

    def test_only_real_edits_change_editor_credit(self):
        a=prepared();m=a.match;m.created_by_name='Original';m.created_by_id='original'
        a._database=SyncState({'known':{m.id:m.to_dict()},'versions':{m.id:1}})
        a._database_user['display_name']='Editor';m.home_score+=1
        with patch.object(storage,'save_sync_state'):a._database_changed()
        self.assertEqual(m.created_by_name,'Original');self.assertEqual(m.edited_by_name,'Editor')
        body=m.to_dict();body.pop('created_by_name');body.pop('edited_by_name')
        state=SyncState({'known':{m.id:body},'versions':{m.id:1}})
        state.observe([m.to_dict()]);self.assertEqual(state.outgoing(),[])

    def test_account_delete_confirmation_and_account_switch_guard(self):
        async def run():
            a=prepared();target={'id':'other','display_name':'Other','email':'other@example.com','role':'user'}
            a._persist_database=AsyncMock();a._sync_database_once=AsyncMock();a._open_accounts=AsyncMock()
            a._delete_account_dialog(target)
            items=list(controls(a.page.dialog));button=next(c for c in items if isinstance(c,ft.Button) and c.content=='Delete account')
            field=next(c for c in items if isinstance(c,ft.TextField))
            with patch.object(account_ui,'api_request',AsyncMock()) as request:
                await button.on_click(None);request.assert_not_called()
                field.value=target['email'];a._database_token='changed'
                await button.on_click(None);request.assert_not_called()
            a._database_token='test-session';a._delete_account_dialog(target)
            items=list(controls(a.page.dialog));next(c for c in items if isinstance(c,ft.TextField)).value=target['email']
            with patch.object(account_ui,'api_request',AsyncMock()) as request:
                await next(c for c in items if isinstance(c,ft.Button) and c.content=='Delete account').on_click(None)
                self.assertEqual(request.call_args.args[3],'DELETE')
        asyncio.run(run())
