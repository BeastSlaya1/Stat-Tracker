import unittest
from unittest.mock import AsyncMock, patch
import flet as ft
import auth0_ui
from cloud_sync import ApiError
from test_app_integration import app, controls

class Auth0UITests(unittest.IsolatedAsyncioTestCase):
    async def flow(self, linking=False):
        a=app();a.page.launch_url=AsyncMock()
        await a._open_auth0_flow(linking)
        items=list(controls(a.page.dialog))
        buttons={c.content:c for c in items if isinstance(c,ft.Button)}
        fields={c.label:c for c in items if isinstance(c,ft.TextField)}
        message=next(c for c in items if isinstance(c,ft.Text) and c.value not in ('Connect Auth0','Sign in with Auth0'))
        return a,buttons,fields,message

    async def test_old_server_and_wrong_password_have_distinct_errors(self):
        a,b,f,m=await self.flow(True)
        with patch.object(auth0_ui,'api_request',AsyncMock(side_effect=ApiError(401,{'error':'Old server'}))):
            await b['Open Auth0 sign-in'].on_click(None)
        self.assertIn('Deploy account and sync server',m.value)
        with patch.object(auth0_ui,'api_request',AsyncMock(side_effect=[{'available':True},ApiError(401,{'error':'Enter your current password'})])):
            await b['Open Auth0 sign-in'].on_click(None)
        self.assertIn('current password',m.value)
        self.assertNotIn('Deploy account',m.value)

    async def test_pkce_and_pending_login_do_not_create_session(self):
        a,b,f,m=await self.flow()
        a._accept_database_login=AsyncMock();a._sync_database_once=AsyncMock()
        with patch.object(auth0_ui,'api_request',AsyncMock(side_effect=[{'available':True},{'ticket':'ticket','authorize_url':'https://example.com/auth'},{'status':'pending'}])) as api:
            await b['Open Auth0 sign-in'].on_click(None)
            request=api.call_args.args[4]
            self.assertEqual(len(request['challenge']),43)
            self.assertNotIn('verifier',request)
            await b['Finish sign-in'].on_click(None)
        a._accept_database_login.assert_not_awaited()
        self.assertIn('browser first',m.value)
        with patch.object(auth0_ui,'api_request',AsyncMock(side_effect=[{'status':'ready'},{'token':'accepted','user':{'id':'same-user'}}])) as api:
            await b['Finish sign-in'].on_click(None)
            self.assertEqual(len(api.call_args.args[4]['verifier']),64)
        a._accept_database_login.assert_awaited_once()
        a._sync_database_once.assert_awaited_once()
        self.assertIsNone(a.page.dialog)

    async def test_close_clears_password_and_cancels_ticket(self):
        a,b,f,m=await self.flow(True)
        password=f['Current Stat Tracker password'];password.value='private'
        with patch.object(auth0_ui,'api_request',AsyncMock(side_effect=[{'available':True},{'ticket':'ticket','authorize_url':'https://example.com/auth'}, {'ok':True}])) as api:
            await b['Open Auth0 sign-in'].on_click(None)
            self.assertEqual(password.value,'')
            await a.page.dialog.actions[0].on_click(None)
            self.assertEqual(api.call_args.args[1],'/auth0/cancel')
        self.assertIsNone(a.page.dialog)
