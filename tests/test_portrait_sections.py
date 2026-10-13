import unittest
import flet as ft
from test_app_integration import app, controls
from test_basketball import match
from engine import make_event

class PortraitSectionTests(unittest.TestCase):
    def test_basketball_incompletes_follow_section_with_other_sections_latest_action(self):
        a=app();a.matches=[match()];a.fullscreen_video=True;a.page.height=1280;a._layout_width=lambda:800
        a.match.events=[make_event(a.match,'home','BB_SHOT','SCC','Shot')]
        expected={'Attack':{'Short pass !','Long pass !','Dribble !','Layup !','Shot !','Off. rebound !'},
                  'Defence':{'Steal !','Block !','Def. rebound !','Deflection !','Loose ball !'},
                  'Opposition':{'Layup against !','Shot against !'},'Cards':set()}
        for category,labels in expected.items():
            a._bb_category=category;tree=a._bb_incompletes()
            actual={c.value for c in controls(tree) if isinstance(c,ft.Text) and c.value.endswith(' !')}
            self.assertEqual(actual,labels)
            for button in controls(tree):
                if isinstance(button,ft.Container) and button.ink and button.on_click:
                    self.assertEqual(category,'Attack')

    def test_generic_incompletes_match_category(self):
        a=app();a.last_logged_action='SHOT'
        for category,expected in [('Attack',{'PASS','LONG_PASS','CROSS','SHOT','THROW_IN'}),('Defence',{'TACKLE','INTERCEPT','BLOCK','SAVE','CLEAR','OFFSIDE'}),('Opposition',{'OFFSIDE_GIVEN'}),('Cards',set())]:
            a.action_category=category
            self.assertEqual(a._visible_incomplete_parents(),expected)
            tree=a._build_incompletes_row()
            self.assertFalse(any(isinstance(c,ft.GridView) for c in controls(tree)))

    def test_portrait_stretches_to_screen_and_clock_has_own_row(self):
        a=app();a.matches=[match()];a.page.height=1280;a._layout_width=lambda:800
        a.fullscreen_video=True;a._timer_running=False;a.camera_on=False;a._bb_clock_text=ft.Text('Q2 00:00');a.camera_image=ft.Image(src='test.jpg')
        tree=a._build_portrait_logging(a.match)
        self.assertEqual(tree.width,float('inf'))
        self.assertEqual(tree.content.horizontal_alignment,ft.CrossAxisAlignment.STRETCH)
        top=tree.content.controls[0]
        self.assertIs(top.controls[1].controls[1],a._bb_clock_text)
        grids=[c for c in controls(tree) if isinstance(c,ft.ResponsiveRow)]
        self.assertEqual(len(grids),2)
        self.assertTrue(all(c.col['xs']==6 for grid in grids for c in grid.controls))
        self.assertTrue(all(c.col['md']==3 for grid in grids for c in grid.controls))
