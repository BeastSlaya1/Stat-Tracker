import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, AsyncMock
import flet as ft
from test_app_integration import app, controls
from test_basketball import match
from shared_match import SharedMatch, SharedError
from shared_permissions import assignment
from engine import make_event
from scripts.prepare_offline_web import prepare

class PeerAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.app=app();self.app.matches=[match()]
        self.hub=SharedMatch(self.app.match);self.app._live_session={'host':True,'hub':self.hub}
        self.app._peer_members={}
    def test_pairing_requires_approval_and_binds_authority_to_connection(self):
        a=self.app._peer_dispatch('peer-a','/join',{'name':'Browser A','hidden':False})
        b=self.app._peer_dispatch('peer-b','/join',{'name':'Browser B','hidden':False})
        with self.assertRaises(SharedError):self.app._peer_dispatch('peer-a','/state',{})
        self.hub.approve(a['device'],permissions=assignment('BASKETBALL','Attack',['SHOT']))
        self.hub.approve(b['device'],permissions=assignment('BASKETBALL',stream_only=True))
        event=make_event(self.hub.match,'home','BB_SHOT','#0','Shot');event.basketball={'player_id':'0','jersey':0}
        self.app._peer_dispatch('peer-a','/events',{'added':[event.to_dict()]})
        with self.assertRaises(SharedError):self.app._peer_dispatch('peer-b','/events',{'token':a['token'],'added':[event.to_dict()]})
        with self.assertRaises(SharedError):self.app._peer_dispatch('unknown','/state',{'token':self.hub.host_token})
        self.assertEqual(len(self.app._peer_dispatch('peer-b','/state',{})['match']['events']),1)
    def test_hidden_boundary_and_unknown_actions_remain_blocked(self):
        with self.assertRaises(SharedError):self.app._peer_dispatch('peer','/join',{'name':'Browser','hidden':True})
        self.app._peer_dispatch('peer','/join',{'name':'Browser','hidden':False})
        with self.assertRaises(SharedError):self.app._peer_dispatch('peer','/assign',{'video':'peer'})

class PeerRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_approved_devices_receive_video_and_selected_sender_routes(self):
        a=app();a.matches=[match()];hub=SharedMatch(a.match)
        one=hub.join(hub.join_code,'Camera',False);two=hub.join(hub.join_code,'Waiting',False)
        hub.approve(one['device'],permissions=assignment('BASKETBALL',stream_only=True))
        a._peer_members={'one':one,'two':two};a._peer_source=None;a._peer_command=AsyncMock()
        a._live_session={'host':True,'hub':hub,'address':'peer'}
        await a._peer_sync_source()
        a._peer_command.assert_awaited_with('source',source='one',viewers=['one'])
        hub.approve(two['device']);await a._peer_sync_source()
        a._peer_command.assert_awaited_with('source',source='one',viewers=['one','two'])
        hub.approve(one['device'],False);await a._peer_sync_source()
        a._peer_command.assert_awaited_with('source',source='self',viewers=['two'])
    async def test_browser_host_does_not_start_socket_server(self):
        a=app();a.matches=[match()];a._timer_running=False;a.camera_on=False
        a._ensure_peer_link=Mock();a._peer_command=AsyncMock();a._peer_members={};a._peer_source=None
        from unittest.mock import patch
        with patch.object(SharedMatch,'start') as start:
            await a._peer_start_host();start.assert_not_called()
        self.assertEqual(a._live_session['address'],'peer')

class OfflinePackageTests(unittest.TestCase):
    def test_runtime_is_local_and_api_responses_are_not_cached(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in ('index.html','python-worker.js','pyodide/pyodide.mjs','assets/app/app.zip'):
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('noCdn: false, pyodideUrl: "https://cdn.example/pyodide.mjs"')
            result=prepare(root)
            self.assertIn('pyodide/pyodide.mjs',result['files'])
            self.assertNotIn('https://cdn.example',(root/'index.html').read_text())
            self.assertIn('./pyodide/pyodide.mjs',(root/'index.html').read_text())
            script=(root/'flutter_service_worker.js').read_text()
            self.assertIn("if(!urls.includes(key))return",script)
            self.assertIn("event.request.method!=='GET'",script)
            self.assertIn('caches.delete(CACHE)',script)
