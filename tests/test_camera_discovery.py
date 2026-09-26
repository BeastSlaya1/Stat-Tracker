import asyncio
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import AsyncMock, Mock, patch
import flet as ft
import camera_network
from test_app_integration import app

class DiscoveryTests(TestCase):
    def instance(self,web):
        instance=app();instance.is_web=web;instance._database_token='staff-session'
        instance._rtc_state={'room_code':'OWN'};instance.discovered_cameras=[]
        instance.wireless_discovering=True
        instance._scan_lan_camera_devices=Mock(return_value=[{'name':'Legacy Android','url':'http://local/video','kind':'Local camera'}])
        return instance

    def test_native_scan_combines_online_and_lan_but_hides_own_sender(self):
        instance=self.instance(False)
        response={'devices':[{'code':'OWN','name':'Me','kind':'Windows'},{'code':'PHONE','name':'Phone','kind':'Browser'}]}
        with patch.object(camera_network,'api_request',AsyncMock(return_value=response)):
            asyncio.run(instance._scan_camera_devices_async())
        self.assertEqual([x['url'] for x in instance.discovered_cameras],['rtc://PHONE','http://local/video'])
        self.assertFalse(instance.wireless_discovering)

    def test_browser_scan_never_attempts_udp(self):
        instance=self.instance(True)
        with patch.object(camera_network,'api_request',AsyncMock(return_value={'devices':[{'code':'PC','name':'Computer','kind':'Windows'}]})):
            asyncio.run(instance._scan_camera_devices_async())
        instance._scan_lan_camera_devices.assert_not_called()
        self.assertEqual(instance.discovered_cameras[0]['url'],'rtc://PC')

    def test_signed_out_scan_does_not_request_online_devices(self):
        instance=self.instance(True);instance._database_token=''
        with patch.object(camera_network,'api_request',AsyncMock()) as request:
            asyncio.run(instance._scan_camera_devices_async())
        request.assert_not_called();self.assertIn('Sign in',instance._camera_scan_message)

    def test_selected_online_camera_stays_in_the_app(self):
        instance=self.instance(True);instance.app_mode='inputter';instance.camera_on=False
        instance._start_rtc_video=Mock()
        instance._connect_discovered_camera('rtc://PHONE')
        instance._start_rtc_video.assert_called_once_with('receive','PHONE')
        self.assertEqual(instance.camera_source,'rtc://PHONE')

    def test_embedded_control_reuses_existing_staff_session(self):
        instance=self.instance(True);instance.camera_on=False;instance.camera_source='native:back'
        instance.logger_name='Staff';instance.is_mobile=False
        created=[]
        def control(**values):created.append(values);return ft.Container()
        with patch.object(camera_network,'camera_package',SimpleNamespace(StcRtcVideo=control)):
            instance._start_rtc_video('send')
        self.assertEqual(created[0]['token'],'staff-session')
        self.assertTrue(instance.camera_mode_streaming)
        self.assertTrue(instance.camera_on)
        self.assertIs(instance._video_display_widget().content,instance._rtc_ctrl)
