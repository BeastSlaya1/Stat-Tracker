import unittest
from unittest.mock import Mock, patch
import flet as ft
import main
from test_app_integration import app


class RotationTests(unittest.TestCase):
    def test_rotation_preserves_capture_and_pairing_and_cycles_four_views(self):
        instance = app()
        instance.camera_on = True
        instance.camera_source = 'http://camera/video'
        instance.camera_image = ft.Image(src='test.jpg')
        instance.pair_status = 'approved'
        instance._latest_jpeg_frame = b'unchanged-stream'
        instance._stop_camera = Mock()
        instance._start_camera = Mock()
        view = instance._video_display_widget()
        for expected in (1, 2, 3, 0):
            instance._rotate_view_button().on_click(None)
            self.assertIs(instance._video_display_widget(), view)
            self.assertEqual(view.quarter_turns, expected)
            self.assertIs(view.content, instance.camera_image)
        for mirrored in (True, False):
            instance._mirror_view_button().on_click(None)
            self.assertIs(instance._video_display_widget(), view)
            self.assertEqual(view.flip.flip_x, mirrored)
        self.assertTrue(instance.camera_on)
        self.assertEqual(instance.pair_status, 'approved')
        self.assertEqual(instance._latest_jpeg_frame, b'unchanged-stream')
        instance._stop_camera.assert_not_called()
        instance._start_camera.assert_not_called()

    def test_native_preview_keeps_the_same_control_while_rotating(self):
        instance = app()
        instance.camera_on = True
        instance.camera_source = 'native:back'
        instance._stc_preview_ctrl = ft.Container()
        with patch.object(main, 'HAS_STC_CAMERA_PREVIEW', True):
            view = instance._video_display_widget()
            instance._rotate_video_view()
            self.assertIs(view.content, instance._stc_preview_ctrl)
            self.assertIs(instance._video_display_widget(), view)
            self.assertEqual(view.quarter_turns, 1)
