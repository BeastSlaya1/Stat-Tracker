import unittest
import flet as ft
from ui_widgets import update_layout
from test_app_integration import app, controls
from test_basketball import match

class LayoutUpdates(unittest.TestCase):
    def test_scroll_panels_keep_identity_and_receive_updated_content(self):
        first=ft.Container(content=ft.Column([ft.Row([ft.Text('Old')],scroll=ft.ScrollMode.AUTO)],scroll=ft.ScrollMode.AUTO))
        vertical=first.content; horizontal=vertical.controls[0]
        new_text=ft.Text('Updated score')
        result=update_layout(first,ft.Container(content=ft.Column([ft.Row([new_text],scroll=ft.ScrollMode.AUTO)],scroll=ft.ScrollMode.AUTO)))
        self.assertIs(result,first)
        self.assertIs(result.content,vertical)
        self.assertIs(result.content.controls[0],horizontal)
        self.assertIs(horizontal.controls[0],new_text)

    def test_callbacks_and_new_controls_are_not_stale(self):
        old=ft.Column([ft.Button('Shot',disabled=True)])
        handler=lambda _:None
        button=ft.Button('Conversion',on_click=handler,disabled=False)
        update_layout(old,ft.Column([button,ft.Text('S')]))
        self.assertIs(old.controls[0],button)
        self.assertIs(old.controls[0].on_click,handler)
        self.assertFalse(old.controls[0].disabled)
        self.assertEqual(len(old.controls),2)

    def test_fullscreen_refresh_preserves_panels_and_clock_reference(self):
        a=app();a.matches=[match()];a._timer_running=False;a.camera_on=False
        a.page.width=1920;a._fs_skeleton=None
        for name in ('left','top','video','bottom','right'):setattr(a,'fs_'+name+'_slot',ft.Container())
        camera=ft.Text('Live video');a._video_display_widget=lambda:camera
        a._rotate_view_button=lambda:ft.Button('Rotate');a._mirror_view_button=lambda:ft.Button('Mirror')
        a._build_fullscreen_logger(a.match)
        right=a.fs_right_slot.content;scroll=right.content;video=a.fs_video_slot.content
        a.match.minute=3
        a._build_fullscreen_logger(a.match)
        self.assertIs(a.fs_right_slot.content,right)
        self.assertIs(right.content,scroll)
        self.assertIs(a.fs_video_slot.content,video)
        self.assertIn(a._bb_clock_text,list(controls(a.fs_top_slot)))
        self.assertIn('3',a._bb_clock_text.value)
