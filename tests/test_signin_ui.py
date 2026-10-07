import asyncio
import unittest
from unittest.mock import AsyncMock, patch
import flet as ft
import database_ui
import security_ui
from test_app_integration import app, controls

class SignInUITests(unittest.IsolatedAsyncioTestCase):
    async def test_authenticator_selection_sends_no_password(self):
        a=app();a._check_signin_method=AsyncMock();a._open_database_dialog()
        items=list(controls(a.page.dialog))
        method=next(c for c in items if isinstance(c,ft.Dropdown) and c.label=='Sign-in method')
        fields={c.label:c for c in items if isinstance(c,ft.TextField)}
        method.value='authenticator';method.on_select(None)
        fields['Email'].value='staff@example.com'
        fields['Authenticator or recovery code (if enabled)'].value='123456'
        self.assertFalse(fields['Password'].visible)
        with patch.object(database_ui,'api_request',AsyncMock(side_effect=RuntimeError('offline'))) as api:
            await a.page.dialog.actions[-1].on_click(None)
            self.assertEqual(api.call_args.args[1],'/signin/authenticator')
            self.assertNotIn('password',api.call_args.kwargs['body'])
            self.assertEqual(api.call_args.kwargs['body']['code'],'123456')

    async def test_email_selection_requires_send_and_clears_old_challenge(self):
        a=app();a._check_signin_method=AsyncMock();a._open_database_dialog();items=list(controls(a.page.dialog))
        method=next(c for c in items if isinstance(c,ft.Dropdown))
        method.value='email';method.on_select(None)
        fields={c.label:c for c in items if isinstance(c,ft.TextField)}
        send=next(c for c in items if isinstance(c,ft.Button) and c.content=='Send code')
        signin=a.page.dialog.actions[-1]
        with patch.object(database_ui,'api_request',AsyncMock(return_value={'challenge':'one','message':'Sent'})) as api:
            await signin.on_click(None);api.assert_not_awaited()
            await send.on_click(None)
            fields['Email'].value='changed@example.com';fields['Email'].on_change(None)
            api.reset_mock();await signin.on_click(None);api.assert_not_awaited()

    async def test_unconfigured_contact_methods_are_disabled(self):
        a=app()
        settings={'email':False,'sms':False,'email_verified':False,'sms_verified':False,'authenticator_login':False}
        with patch.object(security_ui,'api_request',AsyncMock(return_value=settings)):
            await a._open_signin_options()
        buttons={c.content:c for c in controls(a.page.dialog) if isinstance(c,ft.Button)}
        self.assertTrue(buttons['Verify saved email'].disabled)
        self.assertTrue(buttons['Verify saved phone number'].disabled)
        self.assertFalse(buttons['Enable authenticator sign-in'].disabled)

    async def test_old_server_gives_deployment_instructions(self):
        from cloud_sync import ApiError
        a=app()
        with patch.object(database_ui,'api_request',AsyncMock(side_effect=ApiError(401,{'error':'Sign in to sync the shared database.'}))):
            with self.assertRaises(ApiError) as error:
                await a._check_signin_method('authenticator')
        self.assertIn('Deploy account and sync server',str(error.exception))

    async def test_unconfigured_method_does_not_attempt_login(self):
        from cloud_sync import ApiError
        a=app()
        with patch.object(database_ui,'api_request',AsyncMock(return_value={'password':True,'authenticator':True,'email':False})) as api:
            with self.assertRaises(ApiError):await a._check_signin_method('email')
            self.assertEqual(api.await_count,1)
            await a._check_signin_method('authenticator')
