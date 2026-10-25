import asyncio
from unittest import TestCase
from unittest.mock import AsyncMock,patch
import flet as ft
import account_ui
from test_app_integration import app,controls

class PasswordTests(TestCase):
    def test_option_available_to_every_signed_in_role(self):
        for role in ('admin','staff','user'):
            a=app();a._database_user['role']=role;a._open_database_dialog()
            self.assertTrue(any(isinstance(c,ft.Button) and c.content=='Change password' for c in controls(a.page.dialog)))
        a._database_token='';a._open_database_dialog()
        self.assertFalse(any(isinstance(c,ft.Button) and c.content=='Change password' for c in controls(a.page.dialog)))

    def test_mismatch_is_blocked_and_success_clears_fields_without_signing_out(self):
        async def run():
            a=app();a._change_password_dialog();self.assertTrue(a.page.dialog.scrollable)
            fields={c.label:c for c in controls(a.page.dialog) if isinstance(c,ft.TextField)}
            self.assertTrue(all(c.password for c in fields.values()))
            fields['Current password'].value='Old password 123'
            fields['New password'].value='New password 456'
            fields['Confirm new password'].value='Does not match'
            save=next(c for c in controls(a.page.dialog) if isinstance(c,ft.Button))
            with patch.object(account_ui,'api_request',AsyncMock(return_value={'ok':True})) as request:
                await save.on_click(None);request.assert_not_called()
                fields['Confirm new password'].value=fields['New password'].value
                await save.on_click(None)
                self.assertEqual(request.call_args.args[1],'/password')
                self.assertTrue(all(c.value=='' for c in fields.values()))
                self.assertEqual(a._database_token,'test-session')
                self.assertIsNone(a.page.dialog)
        asyncio.run(run())
