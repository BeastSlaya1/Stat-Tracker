"""Profile details and optional authenticator-app two-factor authentication."""
import flet as ft
import base64
import qrcode
from qrcode.image.svg import SvgPathFillImage
from cloud_sync import api_request, ApiError


class SecurityMixin:
    async def _open_security_dialog(self, _=None):
        token = self._database_token
        dialog = ft.AlertDialog(title=ft.Text('Profile and security'), scrollable=True)
        self._security_dialog = dialog

        def dismissed(_=None):
            if getattr(self, '_security_dialog', None) is dialog:
                self._security_dialog = None
            dialog.content = None

        def close(_):
            dismissed()
            self.page.pop_dialog()

        async def load(_=None):
            dialog.content = ft.Column([ft.ProgressRing(), ft.Text('Loading profile and security…')], tight=True)
            self.page.update()
            try:
                profile = await api_request(self._database_url, '/profile', token)
            except Exception as error:
                if getattr(self, '_security_dialog', None) is not dialog or token != self._database_token:
                    return
                if isinstance(error, ApiError) and error.status in (404, 405):
                    message = 'The account server needs an update before profile and security can be used. Contact your administrator, then retry.'
                elif isinstance(error, ApiError) and error.status == 401:
                    message = 'Your sign-in has expired. Close this window and sign in again.'
                else:
                    message = str(error) if isinstance(error, ApiError) else 'Could not load profile and security. Check your connection and retry.'
                dialog.content = ft.Column([ft.Text(message), ft.Button('Retry', on_click=load)], tight=True)
                self.page.update()
                return
            if token == self._database_token and getattr(self, '_security_dialog', None) is dialog:
                self._populate_security_dialog(dialog, profile, token)
                self.page.update()

        dialog.actions = [ft.TextButton('Close', on_click=close)]
        dialog.on_dismiss = dismissed
        dialog.content = ft.Text('Loading profile and security…')
        self.page.show_dialog(dialog)
        await load()

    def _populate_security_dialog(self, dialog, profile, token):
        email = ft.TextField(label='Email (used to sign in)', value=profile['email'])
        phone = ft.TextField(label='Phone number', value=profile['phone'], hint_text='+27821234567')
        password = ft.TextField(label='Current password', password=True, can_reveal_password=True)
        code = ft.TextField(label='Authenticator or recovery code', visible=profile['two_factor_enabled'])
        status = ft.Text('2FA enabled' if profile['two_factor_enabled'] else '2FA is not enabled')
        message = ft.Text('Save profile details here. Manage sign-in methods below to enable additional ways to sign in.', size=12)
        secret = ft.TextField(label='Authenticator setup key', read_only=True, visible=False)
        instructions = ft.Text('Open Microsoft Authenticator, Google Authenticator, or another TOTP app. Add an account (Other account in Microsoft Authenticator) and scan this QR code. On the same phone, enter the setup key manually as a time-based account. Then enter its six-digit code below.', visible=False)
        qr = ft.Image(src='', width=240, height=240, visible=False)
        recovery = ft.TextField(label='Save these recovery codes somewhere safe. Each works once.', multiline=True, read_only=True, visible=False)
        for field in (email, phone, password, code, secret, recovery):
            field.on_focus = self._mark_input_focused
            field.on_blur = self._mark_input_blurred
        busy = False

        async def perform(path, extra=None):
            nonlocal busy
            if busy or token != self._database_token or getattr(self, '_security_dialog', None) is not dialog:
                return None
            busy = True
            for button in buttons:
                button.disabled = True
            self.page.update()
            try:
                result = await api_request(self._database_url, path, token, 'POST',
                    {'password': password.value or '', 'code': (code.value or '').strip(), **(extra or {})})
                if token != self._database_token or getattr(self, '_security_dialog', None) is not dialog:
                    return None
                code.value = ''
                return result
            except Exception as error:
                message.value = str(error) if isinstance(error, ApiError) else 'Could not connect. Try again.'
                return None
            finally:
                busy = False
                for button in buttons:
                    button.disabled = False
                self.page.update()

        async def save(_):
            result = await perform('/profile', {'email': email.value or '', 'phone': phone.value or ''})
            if result:
                self._database_user['email'] = result['email']
                email.value, phone.value = result['email'], result['phone']
                password.value = ''
                message.value = 'Profile saved. Other devices will need to sign in again.'
                await self._persist_database()
                self.page.update()

        async def setup(_):
            result = await perform('/security/setup')
            if result:
                secret.value = result['secret']
                if result.get('uri'):
                    image = qrcode.make(result['uri'], image_factory=SvgPathFillImage, border=4)
                    qr.src = 'data:image/svg+xml;base64,' + base64.b64encode(image.to_string()).decode('ascii')
                    qr.visible = True
                secret.visible = instructions.visible = code.visible = confirm.visible = True
                enable.visible = False
                message.value = 'Setup expires in ten minutes. 2FA stays off until you confirm a code.'
                self.page.update()

        async def confirm_setup(_):
            result = await perform('/security/confirm')
            if result:
                secret.value = password.value = ''
                qr.src = ''
                qr.visible = False
                secret.visible = instructions.visible = confirm.visible = False
                disable.visible = code.visible = recovery.visible = True
                recovery.value = '\n'.join(result['recovery_codes'])
                status.value = '2FA enabled'
                message.value = 'Save your recovery codes now; they will not be shown again. Use a fresh authenticator code when signing in.'
                self.page.update()

        async def disable_2fa(_):
            result = await perform('/security/disable')
            if result:
                password.value = recovery.value = secret.value = ''
                recovery.visible = disable.visible = code.visible = False
                enable.visible = True
                status.value = '2FA is not enabled'
                message.value = '2FA disabled. Other devices will need to sign in again.'
                self.page.update()

        enable = ft.Button('Set up authenticator', on_click=setup, visible=not profile['two_factor_enabled'])
        confirm = ft.Button('Confirm and enable 2FA', on_click=confirm_setup, visible=False)
        disable = ft.Button('Disable 2FA', on_click=disable_2fa, visible=profile['two_factor_enabled'])
        save_button = ft.Button('Save profile', on_click=save)
        buttons = [enable, confirm, disable, save_button]
        dialog.content = ft.Container(width=440, content=ft.Column([
            email, phone, password, status,
            ft.Text('Works with Microsoft Authenticator, Google Authenticator and other TOTP apps.', size=12),
            instructions, qr, secret, code,
            ft.Row(buttons, wrap=True), ft.Button("Manage sign-in methods", on_click=self._open_signin_options), ft.Button("Connect Auth0", on_click=self._open_auth0_link), recovery, message], tight=True, scroll=ft.ScrollMode.AUTO))

    async def _open_signin_options(self, _=None):
        token = self._database_token
        dialog = ft.AlertDialog(title=ft.Text("Sign-in methods"), scrollable=True)
        password = ft.TextField(label="Current password", password=True, can_reveal_password=True)
        factor = ft.TextField(label="Fresh authenticator or recovery code (if enabled)")
        delivered = ft.TextField(label="Code received by email or SMS", visible=False)
        message = ft.Text("Loading sign-in methods…")
        choices = ft.Column(tight=True)
        pending = None
        busy = False
        for field in (password, factor, delivered):
            field.on_focus = self._mark_input_focused
            field.on_blur = self._mark_input_blurred
        def close(_):
            dialog.content = None
            self.page.pop_dialog()
        async def request(path, extra):
            nonlocal busy
            if busy or token != self._database_token or dialog.content is None:
                return None
            busy = True
            try:
                result = await api_request(self._database_url, path, token, 'POST',
                    {'password': password.value or '', 'code': (factor.value or '').strip(), **extra})
                factor.value = ''
                return result if token == self._database_token and dialog.content is not None else None
            except Exception as error:
                message.value = str(error) if isinstance(error, ApiError) else 'Could not connect. Try again.'
            finally:
                busy = False
                self.page.update()
        async def refresh():
            try:
                settings = await api_request(self._database_url, '/signin/options', token)
                if token != self._database_token or dialog.content is None:
                    return
                async def auth(_):
                    if await request('/signin/preference', {'method':'authenticator','enabled':not settings['authenticator_login']}):
                        message.value = 'Preference saved. If enabled, wait for the next new authenticator code before signing in.'
                        await refresh()
                async def enroll(channel):
                    nonlocal pending
                    result = await request('/signin/enroll', {'channel':channel})
                    if result:
                        pending = result['challenge']
                        delivered.visible = confirm.visible = True
                        message.value = result['message']
                        self.page.update()
                async def remove(channel):
                    if await request('/signin/preference', {'method':channel,'enabled':False}):
                        message.value = 'Code sign-in disabled.'
                        await refresh()
                async def enroll_email(_): await enroll('email')
                async def enroll_sms(_): await enroll('sms')
                async def remove_email(_): await remove('email')
                async def remove_sms(_): await remove('sms')
                choices.controls = [
                    ft.Text('Password sign-in remains available. Authenticator sign-in uses only your account email and a fresh app code; it is a single-factor alternative.', size=12),
                    ft.Button('Disable authenticator sign-in' if settings['authenticator_login'] else 'Enable authenticator sign-in', on_click=auth),
                    ft.Text('Email: ' + ('verified' if settings['email_verified'] else 'not verified') + ('' if settings['email'] else ' — awaiting administrator setup')),
                    ft.Button('Verify saved email', on_click=enroll_email, disabled=not settings['email']),
                    ft.Button('Disable email sign-in', on_click=remove_email, visible=settings['email_verified']),
                    ft.Text('SMS: ' + ('verified' if settings['sms_verified'] else 'not verified') + ('' if settings['sms'] else ' — awaiting administrator setup')),
                    ft.Button('Verify saved phone number', on_click=enroll_sms, disabled=not settings['sms']),
                    ft.Button('Disable SMS sign-in', on_click=remove_sms, visible=settings['sms_verified']),
                    ft.Text('Save your contact details in Profile and security first. Email/SMS sign-in still asks for your authenticator code when 2FA is enabled.', size=12),
                ]
                self.page.update()
            except Exception as error:
                message.value = 'The account server needs the sign-in update.' if isinstance(error, ApiError) and error.status in (401,404) else str(error)
                self.page.update()
        async def confirm_code(_):
            nonlocal pending
            if pending and await request('/signin/confirm', {'challenge':pending,'verification_code':(delivered.value or '').strip()}):
                pending = None
                delivered.value = password.value = ''
                delivered.visible = confirm.visible = False
                message.value = 'Contact verified. Code sign-in is enabled.'
                await refresh()
        confirm = ft.Button('Confirm contact', on_click=confirm_code, visible=False)
        dialog.content = ft.Container(width=440, content=ft.Column([
            password, factor, choices, delivered, confirm, message], tight=True, scroll=ft.ScrollMode.AUTO))
        dialog.actions = [ft.TextButton('Close', on_click=close)]
        dialog.on_dismiss = lambda _: setattr(dialog, 'content', None)
        self.page.show_dialog(dialog)
        await refresh()
        if message.value == 'Loading sign-in methods…':
            message.value = 'Enter your current password to change a sign-in method.'
            self.page.update()
