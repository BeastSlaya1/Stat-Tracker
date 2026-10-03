"""Profile details and optional authenticator-app two-factor authentication."""
import flet as ft
from cloud_sync import api_request, ApiError


class SecurityMixin:
    async def _open_security_dialog(self, _=None):
        token = self._database_token
        try:
            profile = await api_request(self._database_url, '/profile', token)
        except Exception as error:
            self._snack(str(error) if isinstance(error, ApiError) else 'Could not load account security.')
            return
        if token != self._database_token:
            return
        email = ft.TextField(label='Email (used to sign in)', value=profile['email'])
        phone = ft.TextField(label='Phone number', value=profile['phone'], hint_text='+27821234567')
        password = ft.TextField(label='Current password', password=True, can_reveal_password=True)
        code = ft.TextField(label='Authenticator or recovery code', visible=profile['two_factor_enabled'])
        status = ft.Text('2FA enabled' if profile['two_factor_enabled'] else '2FA is not enabled')
        message = ft.Text('Email and phone are profile details. No email or SMS codes are sent.', size=12)
        secret = ft.TextField(label='Authenticator setup key', read_only=True, visible=False)
        instructions = ft.Text('Add an account in your authenticator app using this key. Choose time-based codes, then enter the six-digit code below.', visible=False)
        recovery = ft.TextField(label='Save these recovery codes somewhere safe. Each works once.', multiline=True, read_only=True, visible=False)
        for field in (email, phone, password, code, secret, recovery):
            field.on_focus = self._mark_input_focused
            field.on_blur = self._mark_input_blurred
        busy = False

        async def perform(path, extra=None):
            nonlocal busy
            if busy or token != self._database_token:
                return None
            busy = True
            for button in buttons:
                button.disabled = True
            self.page.update()
            try:
                result = await api_request(self._database_url, path, token, 'POST',
                    {'password': password.value or '', 'code': (code.value or '').strip(), **(extra or {})})
                if token != self._database_token:
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
                secret.visible = instructions.visible = code.visible = confirm.visible = True
                enable.visible = False
                message.value = 'Setup expires in ten minutes. 2FA stays off until you confirm a code.'
                self.page.update()

        async def confirm_setup(_):
            result = await perform('/security/confirm')
            if result:
                secret.value = password.value = ''
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
        self.page.show_dialog(ft.AlertDialog(title=ft.Text('Profile and security'), scrollable=True,
            content=ft.Container(width=440, content=ft.Column([
                email, phone, password, status, instructions, secret, code,
                ft.Row(buttons, wrap=True), recovery, message], tight=True, scroll=ft.ScrollMode.AUTO)),
            actions=[ft.TextButton('Close', on_click=lambda _: self.page.pop_dialog())]))
