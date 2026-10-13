import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from shared_match import SharedMatch, SharedError, local_request, local_address
from test_basketball import match
from engine import make_event

class SharedTests(unittest.TestCase):
    def setUp(self):self.hub=SharedMatch(match())
    def guest(self,name='Logger'):
        result=self.hub.join(self.hub.join_code,name,False)
        self.hub.approve(result['device']);return result['token']
    def event(self,code='BB_LAYUP'):
        return make_event(self.hub.match,'home',code,'SCC',code).to_dict()
    def test_join_requires_code_approval_and_matching_visibility(self):
        with self.assertRaises(SharedError):self.hub.join('bad','Logger',False)
        with self.assertRaises(SharedError):self.hub.join(self.hub.join_code,'Logger',True)
        pending=self.hub.join(self.hub.join_code,'Logger',False)
        with self.assertRaises(SharedError):self.hub.snapshot(pending['token'])
        self.hub.approve(pending['device']);self.assertEqual(self.hub.snapshot(pending['token'])['device'],pending['device'])
        self.hub.approve(pending['device'],False)
        with self.assertRaises(SharedError):self.hub.snapshot(pending['token'])
    def test_concurrent_events_and_retries_merge_exactly_once(self):
        tokens=[self.guest('A'),self.guest('B')];events=[self.event() for _ in range(40)]
        def add(i):return self.hub.apply(tokens[i%2],[events[i]],[])
        with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(add,range(40)))
        with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(add,range(40)))
        snapshot=self.hub.snapshot(self.hub.host_token)['match']
        self.assertEqual(len(snapshot['events']),40);self.assertEqual(snapshot['home_score'],80)
    def test_modifiers_reference_own_action_and_undo_is_scoped(self):
        a,b=self.guest('A'),self.guest('B');shot=self.event('BB_SHOT');layup=self.event()
        conversion=self.event('BB_CONVERSION');conversion['basketball']={'target_id':shot['id'],'points':3,'assist':True}
        self.hub.apply(a,[shot,conversion],[]);self.hub.apply(b,[layup],[])
        self.assertEqual(self.hub.match.home_score,5)
        with self.assertRaises(SharedError):self.hub.apply(b,[],[shot['id']])
        self.hub.apply(a,[],[shot['id']]);self.assertEqual(self.hub.match.home_score,2)
        self.hub.apply(a,[shot],[]);self.assertEqual(self.hub.match.home_score,2)
    def test_guests_cannot_send_host_time_events(self):
        with self.assertRaises(SharedError):self.hub.apply(self.guest(),[self.event('BB_TIMEOUT')],[])
    def test_snapshot_tracks_host_clock_and_pause(self):
        m=match();m.minute=1;m.second=58;m.possession_team='home'
        with patch('shared_match.time.monotonic',return_value=100):self.hub.control(m,True)
        with patch('shared_match.time.monotonic',return_value=103):snapshot=self.hub.snapshot(self.hub.host_token)
        self.assertEqual((snapshot['match']['minute'],snapshot['match']['second']),(2,1))
        self.assertEqual(snapshot['match']['stats']['home_possession_seconds'],3)
        with patch('shared_match.time.monotonic',return_value=110):self.assertFalse(self.hub.snapshot(self.hub.host_token)['running'])
        self.hub.control(m,False);self.assertFalse(self.hub.snapshot(self.hub.host_token)['running'])
    def test_video_has_independent_approved_receivers(self):
        a,b=self.guest('A'),self.guest('B');host=self.hub.host_token
        identities=[self.hub.actor(t) for t in (a,b)]
        for identity in identities:self.hub.signal(host,{'device':identity,'offer':{'type':'offer','sdp':'v=0 '+identity}})
        self.assertNotEqual(self.hub.signal(a)['offer'],self.hub.signal(b)['offer'])
        self.hub.signal(a,{'generation':0,'answer':{'type':'answer','sdp':'v=0 answer-a'}})
        self.assertNotIn('answer',self.hub.signal(b))
        with self.assertRaises(SharedError):self.hub.signal(b,{'device':identities[0],'offer':{'type':'offer','sdp':'v=0 fake'}})
        self.hub.signal(host,{'reset':True});self.assertNotIn('offer',self.hub.signal(a))
    def test_real_local_http_join_approval_and_logging(self):
        port=self.hub.start();address=f'http://127.0.0.1:{port}'
        try:
            join=local_request(address,'/join',body={'code':self.hub.join_code,'name':'Phone','hidden':False})
            with self.assertRaises(SharedError):local_request(address,'/state',join['token'])
            self.hub.approve(join['device'])
            result=local_request(address,'/events',join['token'],{'added':[self.event()],'removed':[]})
            self.assertEqual(result['match']['home_score'],2)
        finally:self.hub.stop()
    def test_only_literal_private_addresses_are_accepted(self):
        self.assertEqual(local_address('192.168.1.2:12345'),'http://192.168.1.2:12345')
        for address in ['https://192.168.1.2:12345','8.8.8.8:12345','example.com:12345','http://user:pass@192.168.1.2:12345','203.0.113.1:1234','http://192.168.1.2:12345/?secret=x']:
            with self.subTest(address=address),self.assertRaises(SharedError):local_address(address)

    def test_retry_of_undone_conversion_batch_is_idempotent(self):
        token=self.guest();shot=self.event('BB_SHOT');conversion=self.event('BB_CONVERSION')
        conversion['basketball']={'target_id':shot['id'],'points':3}
        self.hub.apply(token,[shot,conversion],[shot['id']])
        self.hub.apply(token,[shot,conversion],[shot['id']])
        self.assertEqual(self.hub.match.events,[])
        self.assertEqual(self.hub.match.home_score,0)
