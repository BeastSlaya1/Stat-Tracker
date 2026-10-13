import asyncio
import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import AsyncMock, Mock, patch
import flet as ft
import security_ui
from test_app_integration import app, controls

class CameraIdentityTests(TestCase):
    def test_detection_keeps_ids_and_labels_when_order_changes(self):
        a=app();a.camera_scanning=False;a.camera_source='device:usb';a.detected_cameras=[]
        a._detect_rtc_cameras();first=a._camera_detector
        a._on_detected_rtc_cameras(SimpleNamespace(control=first,data=json.dumps({'devices':[
            {'id':'main','label':'Built-in'},{'id':'usb','label':'USB Camera'},{'id':'capture','label':'Capture card'}]})))
        self.assertEqual(a.detected_cameras,['device:main','device:usb','device:capture'])
        self.assertEqual(a._camera_labels['device:usb'],'USB Camera')
        a._detect_rtc_cameras();second=a._camera_detector
        a._on_detected_rtc_cameras(SimpleNamespace(control=first,data='{"devices":[]}'))
        self.assertTrue(a.camera_scanning)
        a._on_detected_rtc_cameras(SimpleNamespace(control=second,data=json.dumps({'devices':[{'id':'usb','label':'USB Camera'},{'id':'main','label':'Built-in'}]})))
        self.assertEqual(a.camera_source,'device:usb')
        self.assertFalse(a.camera_scanning)

    def test_selected_device_id_reaches_capture(self):
        for source in ['device:main','device:usb','device:capture']:
            a=app();a.camera_source=source;a.camera_on=False;a.is_mobile=False
            a.page.platform='windows'
            a._start_rtc_video('preview')
            self.assertEqual(a._rtc_ctrl.device_id,source[7:])

class SecurityScreenTests(TestCase):
    def test_profile_and_enrollment_ui_does_not_persist_secrets(self):
        a=app();a._persist_database=AsyncMock()
        responses=[{'email':'a@example.com','phone':'','two_factor_enabled':False},
                   {'secret':'TEST-SETUP-KEY'}, {'ok':True,'recovery_codes':['one-use-code']}]
        async def run():
            with patch.object(security_ui,'api_request',AsyncMock(side_effect=responses)) as api:
                await a._open_security_dialog()
                items=list(controls(a.page.dialog))
                fields={c.label:c for c in items if isinstance(c,ft.TextField)}
                buttons={c.content:c for c in items if isinstance(c,ft.Button)}
                fields['Current password'].value='test-password'
                await buttons['Set up authenticator'].on_click(None)
                self.assertTrue(fields['Authenticator setup key'].visible)
                fields['Authenticator or recovery code'].value='123456'
                await buttons['Confirm and enable 2FA'].on_click(None)
                self.assertEqual(fields['Authenticator setup key'].value,'')
                self.assertEqual(fields['Current password'].value,'')
                self.assertFalse(fields['Authenticator setup key'].visible)
                self.assertTrue(buttons['Disable 2FA'].visible)
                self.assertEqual(api.call_args.args[1],'/security/confirm')
                a._persist_database.assert_not_called()
                for field in fields.values():
                    field.on_focus(None);self.assertTrue(a._text_input_focused)
                    field.on_blur(None);self.assertFalse(a._text_input_focused)
        asyncio.run(run())

class SecurityLoadingTests(TestCase):
    def test_dialog_is_visible_before_profile_request_finishes(self):
        a=app()
        async def run():
            started=asyncio.Event();finish=asyncio.Event()
            async def pending(*args):
                started.set();await finish.wait()
                return {'email':'a@example.com','phone':'','two_factor_enabled':False}
            with patch.object(security_ui,'api_request',pending):
                task=asyncio.create_task(a._open_security_dialog())
                await started.wait()
                dialog=a.page.dialog
                self.assertTrue(any(isinstance(c,ft.ProgressRing) for c in controls(dialog)))
                dialog.actions[0].on_click(None)
                finish.set();await task
                self.assertIsNone(a.page.dialog)
                self.assertIsNone(dialog.content)
        asyncio.run(run())

    def test_missing_server_route_has_visible_retry(self):
        a=app()
        async def run():
            with patch.object(security_ui,'api_request',AsyncMock(side_effect=[
                security_ui.ApiError(404,{'error':'Not found'}),
                {'email':'a@example.com','phone':'','two_factor_enabled':False}])):
                await a._open_security_dialog()
                items=list(controls(a.page.dialog))
                self.assertTrue(any(isinstance(c,ft.Text) and 'server needs an update' in c.value for c in items))
                await next(c for c in items if isinstance(c,ft.Button) and c.content=='Retry').on_click(None)
                self.assertTrue(any(isinstance(c,ft.TextField) and c.label=='Email (used to sign in)' for c in controls(a.page.dialog)))
        asyncio.run(run())

    def test_authenticator_qr_is_generated_locally_and_cleared_on_confirm(self):
        a=app();a._persist_database=AsyncMock()
        uri='otpauth://totp/Stat%20Tracker:a%40example.com?secret=JBSWY3DPEHPK3PXP&issuer=Stat%20Tracker&algorithm=SHA1&digits=6&period=30'
        async def run():
            with patch.object(security_ui,'api_request',AsyncMock(side_effect=[
                {'email':'a@example.com','phone':'','two_factor_enabled':False},
                {'secret':'JBSWY3DPEHPK3PXP','uri':uri},
                {'ok':True,'recovery_codes':['backup']}])):
                with patch.object(security_ui.qrcode,'make',wraps=security_ui.qrcode.make) as make:
                    await a._open_security_dialog()
                    items=list(controls(a.page.dialog));buttons={c.content:c for c in items if isinstance(c,ft.Button)}
                    await buttons['Set up authenticator'].on_click(None)
                    make.assert_called_once()
                    self.assertEqual(make.call_args.args[0],uri)
                    qr=next(c for c in items if isinstance(c,ft.Image))
                    self.assertTrue(qr.visible)
                    self.assertTrue(qr.src.startswith('data:image/svg+xml;base64,'))
                    await buttons['Confirm and enable 2FA'].on_click(None)
                    self.assertFalse(qr.visible);self.assertEqual(qr.src,'')
                    a._persist_database.assert_not_called()
        asyncio.run(run())

class ConnectedTabletTests(TestCase):
    def test_virtual_tablet_opens_connection_picker_not_default_camera(self):
        a=app();a._camera_labels={'device:tablet':"Beast's Tab S5e (Windows Virtual Camera)"}
        a.page.run_task=Mock();a._select_local_camera=Mock()
        a._select_camera_source('device:tablet')
        a._select_local_camera.assert_not_called()
        self.assertEqual(a.page.run_task.call_args.args[1],'device:tablet')

    def test_camera_selection_starts_capture_even_when_camera_was_off(self):
        a=app();a.camera_on=False;a.camera_mode_streaming=False;a._start_rtc_video=Mock()
        a._select_local_camera('device:usb')
        self.assertEqual(a.camera_source,'device:usb')
        a._start_rtc_video.assert_called_once_with('preview')

    def test_remote_tablet_selection_uses_selected_stream(self):
        import camera_network
        a=app();a._connect_discovered_camera=Mock()
        async def run():
            with patch.object(camera_network,'api_request',AsyncMock(return_value={'devices':[
                {'name':"Beast's Tab S5e",'kind':'Android','code':'TABLET1'}]})):
                await a._open_remote_camera_dialog('device:tablet',"Beast's Tab S5e")
                items=list(controls(a.page.dialog))
                button=next(c for c in items if isinstance(c,ft.Button) and c.content=="Beast's Tab S5e (Android)")
                button.on_click(None)
                a._connect_discovered_camera.assert_called_once_with('rtc://TABLET1')
                self.assertIsNone(a.page.dialog)
        asyncio.run(run())
