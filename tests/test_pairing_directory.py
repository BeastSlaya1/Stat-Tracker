import asyncio
import time
import unittest
from unittest.mock import Mock,AsyncMock,patch
from pairing_directory import PairingDirectory
from shared_match import SharedError
from test_app_integration import app,controls
from test_basketball import match
import flet as ft

class DirectoryTests(unittest.TestCase):
 def test_offer_reply_is_scoped_to_host_and_guest_secrets(self):
  d=PairingDirectory();host=d.dispatch('/register',body={'name':'SCC vs Team','sport':'BASKETBALL'})
  other=d.dispatch('/register',body={'name':'Other'})
  join=d.dispatch('/connect',body={'host':host['id']});body={'host':host['id'],'request':join['request']}
  for token in ('',other['token'],join['token']):
   with self.assertRaises(SharedError):d.dispatch('/host/offer',token,{**body,'code':'STC1.offer'})
  d.dispatch('/host/offer',host['token'],{**body,'code':'STC1.offer'})
  with self.assertRaises(SharedError):d.dispatch('/reply',host['token'],{'request':join['request']})
  self.assertEqual(d.dispatch('/reply',join['token'],{'request':join['request']})['offer'],'STC1.offer')
  d.dispatch('/answer',join['token'],{'request':join['request'],'code':'STC1.answer'})
  poll=d.dispatch('/host/poll',host['token'],{'host':host['id']})
  self.assertEqual(poll['requests'][0]['answer'],'STC1.answer')
  self.assertNotIn('token',poll['requests'][0]);self.assertNotIn('token',d.dispatch('/list')['matches'][0])
  d.dispatch('/host/leave',host['token'],{'host':host['id']})
  with self.assertRaises(SharedError):d.dispatch('/reply',join['token'],{'request':join['request']})
 def test_hidden_expiry_and_request_limits(self):
  d=PairingDirectory()
  with self.assertRaises(SharedError):d.dispatch('/register',body={'hidden':True})
  host=d.dispatch('/register',body={'name':'Test'})
  for _ in range(8):d.dispatch('/connect',body={'host':host['id']})
  with self.assertRaises(SharedError):d.dispatch('/connect',body={'host':host['id']})
  d.hosts[host['id']]['seen']=time.monotonic()-46
  self.assertEqual(d.dispatch('/list'),{'matches':[]});self.assertEqual(d.requests,{})

class DirectoryHttpTests(unittest.TestCase):
 def test_browser_preflight_discovery_and_registration(self):
  import urllib.request,json
  d=PairingDirectory();port=d.start('127.0.0.1',(0,));base=f'http://127.0.0.1:{port}'
  try:
   req=urllib.request.Request(base+'/register',method='OPTIONS',headers={'Origin':'https://example.test','Access-Control-Request-Private-Network':'true'})
   with urllib.request.urlopen(req) as r:self.assertEqual(r.headers['Access-Control-Allow-Private-Network'],'true')
   req=urllib.request.Request(base+'/register',data=json.dumps({'name':'Browser match'}).encode(),headers={'Origin':'https://example.test','Content-Type':'application/json'})
   with urllib.request.urlopen(req) as r:
    self.assertEqual(r.headers['Access-Control-Allow-Origin'],'*');host=json.load(r)
   with urllib.request.urlopen(base+'/list') as r:self.assertEqual(json.load(r)['matches'][0]['id'],host['id'])
  finally:d.stop()

class SharingPanelTests(unittest.IsolatedAsyncioTestCase):
 async def test_copy_retains_exact_code_and_active_panel_uses_same_title(self):
  a=app();a.is_web=True;a.matches=[match()];a._ensure_peer_link=Mock();a._local_sharing_controls=Mock(return_value=[])
  a._pairing_codes={'output':'STC1.long=code','incoming':''}
  a._open_shared_match();dialog=a.page.dialog
  copy=next(c for c in controls(dialog) if isinstance(c,ft.Button) and c.content=='Copy')
  with patch.object(ft.Clipboard,'set',new_callable=AsyncMock) as clipboard:
   await copy.on_click(None);clipboard.assert_awaited_once_with('STC1.long=code')
  from shared_match import SharedMatch
  hub=SharedMatch(a.match);a._live_session={'host':True,'hub':hub,'address':'peer','token':hub.host_token}
  a._open_shared_match()
  self.assertEqual(a.page.dialog.title.value,'Shared match')
  self.assertEqual(next(c for c in controls(a.page.dialog) if isinstance(c,ft.TextField) and c.label=='Your connection code').value,'STC1.long=code')
  self.assertIn('Devices and controls',[c.value for c in controls(a.page.dialog) if isinstance(c,ft.Text)])
 async def test_removed_jersey_disappears_but_save_preserves_history(self):
  a=app();a.matches=[match()];a._persist_database=AsyncMock();a._apply_roster=Mock()
  tasks=[];a.page.run_task=lambda f,*args:tasks.append((f,args))
  roster={'version':1,'players':[{'id':'a'*32,'number':1234,'active':True}]}
  with patch('player_ui.api_request',new_callable=AsyncMock,return_value=roster) as api:
   a._open_team_jerseys();await tasks[0][0]()
   remove=next(c for c in controls(a.page.dialog) if isinstance(c,ft.TextButton) and c.content=='Remove')
   remove.on_click(None)
   self.assertNotIn('#1234',[c.value for c in controls(a.page.dialog) if isinstance(c,ft.Text)])
   save=next(c for c in controls(a.page.dialog) if isinstance(c,ft.Button) and c.content=='Save');await save.on_click(None)
   self.assertFalse(api.call_args.kwargs['body']['players'][0]['active'])

class PlayerAttributionTests(unittest.TestCase):
 def test_each_player_gets_only_their_actions_and_remote_projection_agrees(self):
  from basketball import summary
  from shared_match import SharedMatch
  from models import Match
  a=app();a.matches=[match()];a._save=lambda:None
  a.match.home_team.players[0].number=1234
  a._bb_log('LAYUP');a._bb_log('OREB');a._bb_log('STL')
  a._selected_jerseys['bb']='1';a._bb_log('BLK');a._bb_log('DREB')
  hub=SharedMatch(a.match);guest=hub.join(hub.join_code,'Tablet',False);hub.approve(guest['device'])
  replica=Match.from_dict(hub.snapshot(guest['token'])['match'])
  for m in (a.match,replica):
   players=summary(m)['home']['players']
   self.assertEqual(players['0']['name'],'#1234')
   self.assertEqual((players['0']['stats']['PTS'],players['0']['stats']['OREB'],players['0']['stats']['STL']),(2,1,1))
   self.assertEqual((players['1']['stats']['PTS'],players['1']['stats']['BLK'],players['1']['stats']['DREB']),(0,1,1))
