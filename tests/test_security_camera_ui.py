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
