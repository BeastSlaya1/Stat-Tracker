import unittest
from unittest.mock import patch
from shared_match import SharedMatch, SharedError, local_request
from shared_permissions import assignment
from test_basketball import match
from engine import make_event


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.hub = SharedMatch(match())
        self.a = self.guest('Camera')
        self.b = self.guest('Timer')

    def guest(self, name):
        row = self.hub.join(self.hub.join_code, name, False)
        self.hub.approve(row['device'], permissions=assignment('BASKETBALL', 'Attack', ['SHOT']))
        return row

    def assign(self):
        return self.hub.assign_controllers(self.hub.host_token, self.a['device'], self.b['device'])

    def clock(self, running=True):
        return {'generation':self.hub.control_generation, 'running':running,
                'clock':{'minute':2, 'second':15, 'period':'Q2', 'basketball_elapsed':135}}

    def test_only_host_can_assign_approved_devices(self):
        with self.assertRaises(SharedError):self.hub.assign_controllers(self.a['token'], 'host', self.a['device'])
        pending = self.hub.join(self.hub.join_code, 'Pending', False)
        with self.assertRaises(SharedError):self.hub.assign_controllers(self.hub.host_token, pending['device'], 'host')
        self.assertEqual(self.assign()['controllers'], {'video':self.a['device'], 'time':self.b['device']})

    def test_assigned_camera_sends_to_host_and_other_guests_only(self):
        self.assign()
        peers = self.hub.signal(self.a['token'])['devices']
        self.assertEqual({p['id'] for p in peers}, {'host', self.b['device']})
        for identity in ('host', self.b['device']):
            self.hub.signal(self.a['token'], {'device':identity,'offer':{'type':'offer','sdp':'v=0 '+identity}})
        self.assertEqual(self.hub.signal(self.hub.host_token)['offer']['sdp'], 'v=0 host')
        generation = self.hub.video_generation
        self.hub.signal(self.hub.host_token, {'generation':generation,'answer':{'type':'answer','sdp':'v=0 host answer'}})
        with self.assertRaises(SharedError):self.hub.signal(self.b['token'], {'reset':True})
        self.hub.assign_controllers(self.hub.host_token, 'host', self.b['device'])
        self.assertNotIn('offer', self.hub.signal(self.b['token']))
        with self.assertRaises(SharedError):self.hub.signal(self.a['token'], {'reset':True})

    def test_time_authority_handover_and_host_poll_does_not_overwrite(self):
        self.assign()
        with self.assertRaises(SharedError):self.hub.delegated_control(self.a['token'], self.clock())
        self.hub.delegated_control(self.b['token'], self.clock())
        self.hub.control(match(), False)
        self.assertTrue(self.hub.running)
        self.assertEqual(self.hub.match.minute, 2)
        event = make_event(self.hub.match, 'home', 'BB_TIMEOUT', 'SCC', 'Timeout')
        self.hub.apply(self.b['token'], [event.to_dict()], [])
        stale = self.clock()
        self.hub.assign_controllers(self.hub.host_token, 'host', 'host')
        self.assertFalse(self.hub.running)
        with self.assertRaises(SharedError):self.hub.delegated_control(self.b['token'], stale)
        self.hub.assign_controllers(self.hub.host_token, 'host', self.b['device'])
        with self.assertRaises(SharedError):self.hub.delegated_control(self.b['token'], stale)

    def test_departure_restores_host_and_pauses_clock(self):
        self.assign()
        self.hub.delegated_control(self.b['token'], self.clock())
        self.hub.cancel_join(self.b['token'])
        self.assertEqual(self.hub.controllers['time'], 'host')
        self.assertFalse(self.hub.running)
        self.hub.approve(self.a['device'], False)
        self.assertEqual(self.hub.controllers['video'], 'host')

    def test_missing_timer_heartbeat_stops_extrapolation(self):
        self.assign()
        with patch('shared_match.time.monotonic', return_value=100):
            self.hub.delegated_control(self.b['token'], self.clock())
        with patch('shared_match.time.monotonic', return_value=110):
            self.hub.control(match(), False)
            data=self.hub.snapshot(self.hub.host_token)
        self.assertFalse(data['running'])
        self.assertEqual(data['match']['second'], 21)

    def test_multiple_sections_and_time_actions_are_independently_enforced(self):
        permissions=assignment('BASKETBALL',['Attack','Defense'],['SHOT','STL'])
        self.hub.approve(self.a['device'],permissions=permissions)
        self.assertEqual(self.hub.snapshot(self.a['token'])['permissions']['sections'],['Attack','Defense'])
        self.assign()
        for code in ('BB_TO','BB_SUBSTITUTION'):
            event=make_event(self.hub.match,'home',code,'SCC',code)
            with self.assertRaises(SharedError):self.hub.apply(self.a['token'],[event.to_dict()],[])
            self.hub.apply(self.b['token'],[event.to_dict()],[])
            self.hub.apply(self.b['token'],[],[event.id])
        for code in ('BB_SHOT','BB_STL'):
            self.hub.apply(self.a['token'],[make_event(self.hub.match,'home',code,'SCC',code).to_dict()],[])
        with self.assertRaises(SharedError):
            self.hub.apply(self.a['token'],[make_event(self.hub.match,'home','BB_TF','SCC','TF').to_dict()],[])

    def test_http_control_endpoint_requires_assigned_token(self):
        self.assign();port=self.hub.start()
        try:
            address=f'http://127.0.0.1:{port}'
            with self.assertRaises(SharedError):local_request(address, '/control', self.a['token'], self.clock())
            data=local_request(address, '/control', self.b['token'], self.clock(False))
            self.assertEqual(data['match']['second'],15)
            self.assertFalse(data['running'])
        finally:self.hub.stop()


class ControllerUiTests(unittest.TestCase):
    def test_host_selectors_and_handover_preserve_clock_and_require_camera_consent(self):
        import flet as ft
        from unittest.mock import Mock
        from test_app_integration import app, controls
        a=app();a.matches=[match()];a._timer_running=False;a.camera_on=False;a.fullscreen_video=False
        a.scoreboard_ref=ft.Container();a._save=Mock();a._start_rtc_video=Mock();a._stop_camera=Mock()
        a._start_live_host();hub=a._live_session['hub']
        try:
            row=hub.join(hub.join_code,'Tablet',False);hub.approve(row['device'])
            a._open_shared_match()
            fields={c.label:c for c in controls(a.page.dialog) if isinstance(c,ft.Dropdown)}
            fields['Device sharing video'].value=row['device']
            fields['Device controlling time'].value=row['device']
            next(c for c in controls(a.page.dialog) if isinstance(c,ft.Button) and c.content=='Save device assignments').on_click(None)
            self.assertEqual(hub.controllers,{'video':row['device'],'time':row['device']})
            a._start_rtc_video.assert_called_once_with('live-guest')
            self.assertFalse(a._live_time_only())
            hub.delegated_control(row['token'],{'generation':hub.control_generation,'running':False,'clock':{'minute':3,'second':20,'period':'Q2','basketball_elapsed':200}})
            data=hub.assign_controllers(hub.host_token,'host','host');a._live_adopt(data)
            self.assertEqual(a.match.minute,3);self.assertEqual(a.match.second,20)
            self.assertTrue(a._live_time_only());self.assertFalse(a._timer_running)
            self.assertEqual(a._start_rtc_video.call_count,1)
        finally:hub.stop()
