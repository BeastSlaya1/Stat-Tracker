import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
import flet as ft
from test_app_integration import app

class VideoZoomTests(unittest.IsolatedAsyncioTestCase):
    def prepared(self):
        a=app();a.camera_on=False;a.camera_image=ft.Image(src='test.jpg')
        a._start_camera=Mock();a._stop_camera=Mock()
        return a

    async def test_zoom_uses_properties_without_method_listener(self):
        a=self.prepared();view=a._zoom_video_display_widget()
        with patch.object(ft.BaseControl,'_invoke_method',AsyncMock(side_effect=RuntimeError('listener missing'))) as invoke:
            await a._zoom_video_in();self.assertEqual(a._video_zoom_scene.scale,1.25)
            await a._zoom_video_out();self.assertEqual(a._video_zoom_scene.scale,1)
            await a._reset_video_zoom();invoke.assert_not_called()
        self.assertIs(a._zoom_video_display_widget(),view)
        self.assertIs(a._video_rotation_view.content,a.camera_image)
        a._start_camera.assert_not_called();a._stop_camera.assert_not_called()

    async def test_zoom_before_mount_and_after_navigation_is_safe_and_bounded(self):
        a=self.prepared()
        for _ in range(20):await a._zoom_video_in()
        self.assertEqual(a._video_zoom,4)
        view=a._zoom_video_display_widget()
        a.page.controls=[ft.Text('Sign in')]
        await a._zoom_video_out()
        self.assertEqual(a.page.controls[0].value,'Sign in')
        for _ in range(20):await a._zoom_video_out()
        self.assertEqual(a._video_zoom,1)
        self.assertIs(a._zoom_video_display_widget(),view)

    async def test_pinch_pan_and_reset_stay_inside_video(self):
        a=self.prepared();a._zoom_video_display_widget()
        a._video_zoom_size(SimpleNamespace(width=400,height=200))
        a._video_zoom_start(None)
        a._video_zoom_gesture(SimpleNamespace(scale=2,focal_point_delta=ft.Offset(10000,-10000)))
        self.assertEqual(a._video_zoom,2)
        self.assertEqual(a._video_pan,(.25,-.25))
        await a._reset_video_zoom()
        self.assertEqual(a._video_pan,(0,0));self.assertEqual(a._video_zoom_scene.scale,1)
