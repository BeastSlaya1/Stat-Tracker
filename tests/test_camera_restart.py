import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock
import flet as ft
from test_app_integration import app

class CameraRestartTests(TestCase):
    def prepared(self):
        a=app();a._rtc_ctrl=ft.Container();a.camera_on=True;a.camera_mode_streaming=True
        a.camera_error_text=ft.Text('');a._build_camera_source_picker=lambda:ft.Text('Sources')
        a._full_refresh=Mock();a._rtc_state={'status':'Starting camera…'}
        return a
    def test_startup_and_pairing_events_do_not_rebuild_camera(self):
        a=self.prepared();root=a._build_network_camera_mode();video=a._rtc_mode_video;camera=a._rtc_ctrl
        for state in [{'status':'Starting camera…'},{'status':'Ready','receiver_name':'Receiver','approved':False},{'status':'Live','approved':True}]:
            a._on_rtc_state(SimpleNamespace(control=camera,data=json.dumps(state)))
            a._full_refresh.assert_not_called()
            self.assertIs(root,a._build_network_camera_mode());self.assertIs(video,a._rtc_mode_video)
            self.assertIs(a._rtc_mode_video.content.content,camera)
        self.assertEqual(a._rtc_status_text.value,'Live');self.assertFalse(a._rtc_pair_panel.visible)
    def test_failure_rebuilds_once_and_ignores_old_events(self):
        a=self.prepared();camera=a._rtc_ctrl
        a._on_rtc_state(SimpleNamespace(control=camera,data=json.dumps({'status':'Failed','error':'Permission denied'})))
        a._full_refresh.assert_called_once();self.assertFalse(a.camera_on)
        a._on_rtc_state(SimpleNamespace(control=camera,data=json.dumps({'status':'Starting camera…'})))
        a._full_refresh.assert_called_once();self.assertEqual(a.camera_error,'Permission denied')
