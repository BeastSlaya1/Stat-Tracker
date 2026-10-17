"""Browser-based Auth0 sign-in; PKCE material stays in this dialog's memory."""
import base64
import hashlib
import secrets
import flet as ft
from cloud_sync import api_request, ApiError

class Auth0Mixin:
    async def _open_auth0_login(self, _=None):
        await self._open_auth0_flow(False)

    async def _open_auth0_link(self, _=None):
        await self._open_auth0_flow(True)

    async def _open_auth0_flow(self, linking=False):
        self.page.pop_dialog()
        platform = str(getattr(self.page, 'platform', 'windows')).lower()
        platform = 'web' if self.is_web else 'android' if 'android' in platform else 'windows' if 'windows' in platform else None
        dialog = ft.AlertDialog(title=ft.Text('Connect Auth0' if linking else 'Sign in with Auth0'), scrollable=True)
        active = True
        ticket = verifier = None
        token = self._database_token if linking else ''
        busy = False
        config_checked = False
        message = ft.Text('Use the same verified email as your Stat Tracker account.' if linking else 'First time? Sign in with your existing Stat Tracker password and use Profile and security > Connect Auth0 before choosing this option.')
        password = ft.TextField(label='Current Stat Tracker password', password=True, can_reveal_password=True, visible=linking)
        factor = ft.TextField(label='Fresh Stat Tracker authenticator or recovery code (if enabled)')
        for field in (password,factor):
            field.on_focus=self._mark_input_focused
            field.on_blur=self._mark_input_blurred
        def dismissed(_=None):
            nonlocal active,ticket,verifier
            active=False;ticket=verifier=None
            password.value=factor.value=''
            dialog.content=None
        async def close(_):
            old=ticket
            dismissed();self.page.pop_dialog()
            if old:
                try:await api_request(self._database_url,'/auth0/cancel',method='POST',body={'ticket':old})
                except Exception:pass
        def error_text(error):
            if isinstance(error,ApiError) and error.status in (401,404,405) and not config_checked:
                return 'The account server needs the Auth0 update. Run GitHub Actions > Deploy account and sync server, then try again.'
            return str(error) if isinstance(error,ApiError) else 'Could not connect. Check your connection and try again.'
        async def begin(_):
            nonlocal busy,ticket,verifier,config_checked
            if busy or not active:return
            if platform is None:
                message.value='Auth0 is currently configured for Website, Windows and Android.';self.page.update();return
            busy=True;start.disabled=True;self.page.update()
            try:
                config_checked=False
                await api_request(self._database_url,'/auth0/config')
                config_checked=True
                if ticket:
                    await api_request(self._database_url,'/auth0/cancel',method='POST',body={'ticket':ticket})
                ticket=verifier=None
                browser.visible=finish.visible=False
                verifier=secrets.token_urlsafe(48)
                challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
                result=await api_request(self._database_url,'/auth0/start',token,'POST',{
                    'platform':platform,'purpose':'link' if linking else 'login','challenge':challenge,
                    'password':password.value or '', 'code':(factor.value or '').strip()})
                if not active or linking and token!=self._database_token:return
                ticket=result['ticket'];password.value=factor.value=''
                browser.url=result['authorize_url'];browser.visible=finish.visible=True
                start.content='Start again'
                message.value='Complete Auth0 sign-in in your browser, return here, enter a fresh Stat Tracker code if 2FA is enabled, then choose Finish sign-in.'
                self.page.update()
                try:await self.page.launch_url(result['authorize_url'])
                except Exception:
                    message.value='Choose Open Auth0 in browser, complete sign-in, then return here.'
            except Exception as error:
                message.value=error_text(error)
            finally:
                busy=False;start.disabled=False
                if active:self.page.update()
        async def complete(_):
            nonlocal busy,ticket,verifier
            if busy or not active or not ticket:return
            busy=True;finish.disabled=True;self.page.update()
            try:
                state=await api_request(self._database_url,'/auth0/status',method='POST',body={'ticket':ticket})
                if not active:return
                if state['status']=='pending':
                    message.value='Finish signing in in the browser first.';return
                if state['status']!='ready':
                    message.value='Browser sign-in was cancelled or expired. Choose Start again.';return
                result=await api_request(self._database_url,'/auth0/finish',token,'POST',{
                    'ticket':ticket,'verifier':verifier,'code':(factor.value or '').strip()})
                if not active or linking and token!=self._database_token:return
                ticket=verifier=None;factor.value=''
                if linking:
                    finish.visible=browser.visible=False
                    message.value='Auth0 connected. Your existing matches and permissions are preserved. You can now choose Sign in with Auth0.'
                else:
                    if self._database_transition:return
                    self._database_transition=True
                    try:
                        await self._accept_database_login(self._database_url,result)
                        dismissed();self.page.pop_dialog()
                    finally:self._database_transition=False
                    await self._sync_database_once()
            except Exception as error:
                message.value=error_text(error)
                if isinstance(error,ApiError) and error.status in (401,403,409):
                    ticket=verifier=None
                    browser.visible=finish.visible=False
                    message.value+=' Choose Start again.'
            finally:
                busy=False;finish.disabled=False
                if active:self.page.update()
        start=ft.Button('Open Auth0 sign-in',on_click=begin)
        browser=ft.Button('Open Auth0 in browser',visible=False)
        finish=ft.Button('Finish sign-in',on_click=complete,visible=False)
        dialog.content=ft.Container(width=460,content=ft.Column([message,password,factor,start,browser,finish],tight=True,scroll=ft.ScrollMode.AUTO))
        dialog.actions=[ft.TextButton('Close',on_click=close)]
        dialog.on_dismiss=dismissed
        self.page.show_dialog(dialog)
