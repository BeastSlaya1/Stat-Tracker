import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
import flet as ft
from test_app_integration import app, controls
from test_basketball import match
from engine import make_event
from shared_match import SharedMatch, SharedError, local_request
from shared_permissions import assignment, catalog

class Assignments(unittest.TestCase):
    def setUp(self):self.hub=SharedMatch(match())
    def guest(self,section='All',stats=None):
        row=self.hub.request_join(self.hub.discovery_id,'Phone',False,'test-'+str(len(self.hub.members)))
        self.hub.approve(row['device'],True,assignment('BASKETBALL',section,stats));return row
    def event(self,code,**details):
        event=make_event(self.hub.match,'home','BB_'+code,'SCC',code);event.basketball=details;return event
    def test_requests_require_approval_and_cannot_cross_hidden_boundary(self):
        row=self.hub.request_join(self.hub.discovery_id,'Phone',False,'a')
        for operation in (lambda:self.hub.snapshot(row['token']),lambda:self.hub.signal(row['token'])):
            with self.assertRaises(SharedError) as e:operation()
            self.assertEqual(e.exception.status,425)
        with self.assertRaises(SharedError):self.hub.request_join('stale','Phone',False,'b')
        self.hub.hidden=True
        with self.assertRaises(SharedError):self.hub.request_join(self.hub.discovery_id,'Phone',True,'b')
        self.hub.hidden=False;self.hub.cancel_join(row['token'])
        with self.assertRaises(SharedError):self.hub.snapshot(row['token'])
    def test_per_stat_permissions_cover_conversion_incomplete_and_undo(self):
        row=self.guest('Attack',['SHOT']);token=row['token'];shot=self.event('SHOT')
        self.hub.apply(token,[shot.to_dict()],[])
        conversion=self.event('CONVERSION',target_id=shot.id,points=3,assist=True)
        self.hub.apply(token,[conversion.to_dict()],[])
        self.assertEqual(self.hub.match.home_score,3)
        for code in ('LAYUP','DREB','TF','SHOT_AGAINST','TIMEOUT'):
            with self.assertRaises(SharedError):self.hub.apply(token,[self.event(code).to_dict()],[])
        self.hub.approve(row['device'],True,assignment('BASKETBALL','Defense',['DREB']))
        with self.assertRaises(SharedError):self.hub.apply(token,[],[shot.id])
        self.hub.apply(token,[self.event('DREB').to_dict()],[])
        self.assertEqual(self.hub.snapshot(token)['permissions']['stats'],['DREB'])
    def test_all_devices_receive_all_events_but_only_their_video_signals(self):
        a=self.guest('Attack',['LAYUP']);b=self.guest('Defense',['STL'])
        self.hub.apply(a['token'],[self.event('LAYUP').to_dict()],[])
        self.hub.apply(b['token'],[self.event('STL').to_dict()],[])
        snapshots=[self.hub.snapshot(t) for t in (self.hub.host_token,a['token'],b['token'])]
        self.assertTrue(all(len(s['match']['events'])==2 and s['match']['home_score']==2 for s in snapshots))
        for row in (a,b):self.hub.signal(self.hub.host_token,{'device':row['device'],'offer':{'type':'offer','sdp':'v=0 '+row['device']}})
        self.assertEqual(self.hub.signal(a['token'])['offer']['sdp'],'v=0 '+a['device'])
        self.assertEqual(len(self.hub.signal(self.hub.host_token)['devices']),2)
    def test_penalties_are_scoped_and_spoofed_conversion_is_rejected(self):
        a=self.guest('Attack',['PENALTY_ATTACK'])
        self.hub.apply(a['token'],[self.event('PENALTY',direction='attack',penalty_type='PF').to_dict()],[])
        with self.assertRaises(SharedError):self.hub.apply(a['token'],[self.event('PENALTY',direction='opposition',penalty_type='PF').to_dict()],[])
        b=self.guest('Attack',['SHOT']);shot=self.event('SHOT');self.hub.apply(b['token'],[shot.to_dict()],[])
        with self.assertRaises(SharedError):self.hub.apply(b['token'],[self.event('CONVERSION',target_id=shot.id,points=100).to_dict()],[])
    def test_expired_requests_release_slots(self):
        row=self.hub.request_join(self.hub.discovery_id,'Phone',False,'a')
        self.hub.members[row['token']]['created']-=121
        with self.assertRaises(SharedError):self.hub.snapshot(row['token'])
        self.assertNotIn(row['token'],self.hub.members)
    def test_guest_controls_follow_assignment(self):
        a=app();a.matches=[match()];a._live_session={'host':False,'device':'phone','permissions':assignment('BASKETBALL','Attack',['SHOT'])};a._bb_category='Attack'
        tiles=a._bb_action_tiles(lambda _:None)
        names=[c.value for tile in tiles for c in controls(tile) if isinstance(c,ft.Text)]
        self.assertEqual(names,['Shot','Conversion'])
        tabs=[c.value for c in controls(a._bb_tabs()) if isinstance(c,ft.Text)]
        self.assertEqual(tabs,['Attack'])
        a._bb_log('LAYUP');self.assertEqual(a.match.events,[])
        a._save=Mock();a._bb_log('SHOT');self.assertEqual(len(a.match.events),1)

class JoinFlow(unittest.IsolatedAsyncioTestCase):
    async def test_scan_connect_approve_opens_match_and_video_without_second_connect(self):
        host=app();host.matches=[match()];host._timer_running=False;host.camera_on=False;host._start_live_host()
        hub=host._live_session['hub'];address=host._live_session['address']
        guest=app();guest._timer_running=False;guest.camera_on=False;guest.fullscreen_video=False
        guest.scoreboard_ref=ft.Container();guest._build_scoreboard=lambda _:ft.Text('Score');guest._start_rtc_video=Mock()
        guest._open_shared_match();dialog=guest.page.dialog
        scan=next(c for c in controls(dialog) if isinstance(c,ft.Button) and c.content=='Scan for shared matches')
        try:
            with patch('shared_match.discover_matches',return_value=[{'address':address,'name':'SCC match','sport':'BASKETBALL','session':hub.discovery_id}]):await scan.on_click(None)
            connect=next(c for c in controls(dialog) if isinstance(c,ft.Button) and c.content=='Connect to this match')
            task=asyncio.create_task(connect.on_click(None))
            for _ in range(100):
                if hub.members:break
                await asyncio.sleep(.01)
            host._show_live_approval(host._live_session,hub.snapshot(hub.host_token)['members'])
            prompt=host.page.dialog
            selector=next(c for c in controls(prompt) if isinstance(c,ft.Dropdown))
            selector.value='Defense';selector.on_select(None)
            boxes=[c for c in controls(prompt) if isinstance(c,ft.Checkbox)]
            for box in boxes:
                box.value=box.label=='Steal';box.on_change(SimpleNamespace(control=box))
            approve=next(c for c in controls(prompt) if isinstance(c,ft.Button) and c.content=='Approve connection')
            approve.on_click(None);await asyncio.wait_for(task,3)
            self.assertTrue(guest._live_guest());self.assertIsNone(guest.page.dialog)
            self.assertEqual(guest._live_session['permissions'],assignment('BASKETBALL','Defense',['STL']))
            self.assertEqual(guest._bb_category,'Defence');guest._start_rtc_video.assert_called_with('live-guest')
        finally:hub.stop()
