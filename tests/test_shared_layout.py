import unittest
import flet as ft
from test_app_integration import app, controls
from test_basketball import match
from engine import make_event, generate_sequences
from shared_match import SharedMatch

class SharedLayoutTests(unittest.TestCase):
    def test_portrait_keeps_video_outside_scrolling_stats(self):
        a=app();a.matches=[match()];a.page.height=844;a._layout_width=lambda:390
        a.fullscreen_video=True;a._timer_running=False;a.camera_on=False;a._bb_clock_text=ft.Text('Q1');a.camera_image=ft.Image(src='test.jpg')
        tree=a._build_portrait_logging(a.match)
        sections=tree.content.controls
        self.assertEqual(len(sections),3)
        self.assertIsNone(tree.content.scroll)
        self.assertIsInstance(sections[1].content,ft.Stack)
        self.assertEqual(sections[2].scroll,ft.ScrollMode.AUTO)
        self.assertTrue(sections[2].expand)
        text=[c.value for c in controls(sections[2]) if isinstance(c,ft.Text)]
        self.assertTrue(any(t.startswith('Opposition:') for t in text))
        self.assertIn('Incompletes',text)
        self.assertFalse(any(isinstance(c,ft.GridView) for c in controls(sections[2])))
        for control in controls(tree):
            if isinstance(control,(ft.Row,ft.Column)) and control.wrap:
                self.assertFalse(any(getattr(child,'expand',False) for child in control.controls))
    def test_generic_incomplete_stays_with_own_interleaved_action(self):
        m=match();m.sport='SOCCER'
        first=make_event(m,'home','PASS','SCC','Pass')
        second=make_event(m,'home','LONG_PASS','SCC','Long pass')
        incomplete=make_event(m,'home','PASS_INCOMPLETE','SCC','Incomplete')
        incomplete.target_id=first.id
        result=generate_sequences([first,second,incomplete],'home')
        self.assertIn('!',result['attack'])
        self.assertTrue(result['attack'].split()[0].endswith('!'))
    def test_guest_own_action_survives_remote_input_for_conversion(self):
        a=app();a.matches=[match()];a._save=lambda:None
        a._live_session={'host':False,'device':'phone'}
        a._bb_log('SHOT');a.match.events[-1].source_device='phone'
        other=make_event(a.match,'home','BB_LAYUP','SCC','Layup');other.source_device='tablet';a.match.events.append(other)
        self.assertEqual(a._bb_conversion_event().event_type,'BB_SHOT')
    def test_host_disconnect_freezes_projected_clock(self):
        from unittest.mock import patch
        hub=SharedMatch(match())
        with patch('shared_match.time.monotonic',return_value=100):hub.control(hub.match,True)
        with patch('shared_match.time.monotonic',return_value=120):one=hub.snapshot(hub.host_token)
        with patch('shared_match.time.monotonic',return_value=130):two=hub.snapshot(hub.host_token)
        self.assertEqual(one['match']['second'],two['match']['second'])
        self.assertFalse(one['running'])

class SharedUiIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_host_and_guest_exchange_inputs_and_undo_without_losing_other_device(self):
        from unittest.mock import Mock
        from shared_match import local_request
        host=app();host.matches=[match()];host._timer_running=False;host.camera_on=False
        host._start_live_host()
        try:
            guest=app();guest._timer_running=False;guest.camera_on=False;guest.fullscreen_video=False
            guest.scoreboard_ref=ft.Container();guest._build_scoreboard=lambda m:ft.Text(str(m.home_score))
            guest._start_rtc_video=Mock();guest._save=guest._live_capture
            await guest._join_live(host._live_session['address'],host._live_session['hub'].join_code,'Phone')
            host._live_session['hub'].approve(guest._live_join['device'])
            await guest._finish_live_join()
            self.assertTrue(guest._fixture_visible(guest.match))
            guest._bb_log('SHOT')
            host._save=host._live_capture;host._bb_log('LAYUP')
            session=guest._live_session
            data=local_request(session['address'],'/events',session['token'],{'added':list(guest._live_pending.values()),'removed':[]})
            guest._live_pending.clear();guest._live_adopt(data)
            self.assertEqual(guest.match.home_score,2)
            self.assertEqual(guest._bb_conversion_event().event_type,'BB_SHOT')
            guest._bb_mark_incomplete('SHOT')
            data=local_request(session['address'],'/events',session['token'],{'added':list(guest._live_pending.values()),'removed':[]})
            guest._live_pending.clear();guest._live_adopt(data)
            self.assertEqual(guest.match.home_score,2)
            self.assertEqual(len(guest.match.events),3)
            self.assertTrue(guest.match.local_shared_guest)
        finally:host._live_session['hub'].stop()
