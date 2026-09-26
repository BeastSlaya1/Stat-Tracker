import asyncio
from unittest import TestCase
from unittest.mock import AsyncMock,Mock,patch
import flet as ft
import database_ui,account_ui
from cloud_sync import SyncState
from test_app_integration import app,controls

class AccountTests(TestCase):
    def test_create_match_dialog_scrolls_and_requires_sign_in(self):
        a=app();a._open_new_match_dialog();self.assertTrue(a.page.dialog.scrollable)
        a._database_token='';a._open_new_match_dialog()
        self.assertEqual(a.page.dialog.title.value,'Account and database')

    def test_account_type_choices_follow_role(self):
        for role,expected in [('admin',['admin','staff','user']),('staff',['user'])]:
            a=app();a._database_user['role']=role;a._create_account_dialog()
            dropdown=next(c for c in controls(a.page.dialog) if isinstance(c,ft.Dropdown))
            self.assertEqual([o.key for o in dropdown.options],expected)
        a=app();a._database_user['role']='user';a._open_database_dialog()
        self.assertFalse(any(isinstance(c,ft.Button) and c.content in ('Manage accounts','Manage shared database') for c in controls(a.page.dialog)))

    def test_switching_accounts_keeps_pending_work_separate(self):
        async def run():
            a=app();a._database=SyncState();a._persist_database=AsyncMock();a._sync_database_once=AsyncMock();a._save=Mock()
            a._open_new_match_dialog()
            fields=list(controls(a.page.dialog))
            next(c for c in fields if isinstance(c,ft.TextField) and c.label=='Opponent team name (required)').value='Private match'
            next(c for c in fields if isinstance(c,ft.Button) and c.content=='Create Match').on_click(None)
            original=a.matches[0].id
            async def login(user):
                a._open_database_dialog()
                button=next(c for c in controls(a.page.dialog) if isinstance(c,ft.Button) and c.content=='Sign in')
                with patch.object(database_ui,'api_request',AsyncMock(side_effect=[{'token':'new-session','user':user},{}])):
                    await button.on_click(None)
            await login({'id':'ordinary-user','role':'user','email':'u@example.com'})
            self.assertEqual(a.matches,[])
            self.assertIn(original,a._database_accounts['test-admin:admin']['state']['pending'])
            self.assertEqual(a._database.outgoing(),[])
            await login({'id':'test-admin','role':'admin','email':'a@example.com'})
            self.assertEqual([m.id for m in a.matches],[original])
            self.assertFalse(a._database_transition)
        asyncio.run(run())

    def test_management_forms_open_without_exposing_connection_address(self):
        async def run():
            a=app()
            with patch.object(account_ui,'api_request',AsyncMock(return_value={'accounts':[{'id':'u','email':'u@example.com','display_name':'User','role':'user','enabled':1}]})):
                await a._open_accounts()
            a._edit_account({'id':'u','email':'u@example.com','display_name':'User','role':'user','enabled':1})
            self.assertTrue(a.page.dialog.scrollable)
            a._edit_catalog_table({'name':'Schools','version':1,'fields':{'ID':'number','School_ID':'text'},'rows':[{'ID':1,'School_ID':'School'}]})
            self.assertTrue(a.page.dialog.scrollable)
            next(c for c in controls(a.page.dialog) if isinstance(c,ft.Button) and c.content=='Add row').on_click(None)
            self.assertTrue(any(isinstance(c,ft.TextField) and c.label=='School_ID' for c in controls(a.page.dialog)))
        asyncio.run(run())
