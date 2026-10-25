import json
import unittest
from unittest.mock import patch
from match_discovery import discovery_targets
from shared_match import discover_matches

class FeemDiscoveryTests(unittest.TestCase):
    def test_hotspot_targets_include_direct_and_directed_broadcast(self):
        self.assertEqual(set(discovery_targets('192.168.137.201')),{'255.255.255.255','192.168.137.255','192.168.137.1','192.168.137.254'})
        self.assertNotIn('192.168.137.1',discovery_targets('192.168.137.1'))

    def test_fifth_adapter_is_scanned_slow_hotspot_retried_and_duplicates_merged(self):
        attempts={};timeouts=[]
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,limit):return json.dumps({'protocol':'stat-tracker-match-v1','name':'SCC vs Hilton','sport':'HOCKEY','session':'same-host'}).encode()
        class Opener:
            def open(self,request,timeout):
                address=request.full_url;attempts[address]=attempts.get(address,0)+1
                if address in ('http://192.168.137.1:8767/discover','http://192.168.137.254:8767/discover'):
                    timeouts.append(timeout)
                    if attempts[address]>1:return Response()
                raise TimeoutError()
        interfaces=[f'10.{i}.0.2:8767' for i in range(4)]+['192.168.137.201:8767']
        with patch('shared_match.addresses',return_value=interfaces),patch('match_discovery.discover_addresses',return_value=[]),patch('shared_match.build_opener',return_value=Opener()):
            rows=discover_matches()
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['session'],'same-host')
        self.assertIn('http://192.168.137.100:8767/discover',attempts)
        self.assertTrue(all(t>=1 for t in timeouts))

    def test_announced_non_default_port_is_verified_and_kept(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,limit):return b'{"protocol":"stat-tracker-match-v1","name":"Match","sport":"HOCKEY","session":"abc"}'
        class Opener:
            def open(self,request,timeout):
                if request.full_url=='http://192.168.137.1:9000/discover':return Response()
                raise TimeoutError()
        with patch('shared_match.addresses',return_value=['192.168.137.201:8767']),patch('match_discovery.discover_addresses',return_value=['http://192.168.137.1:9000']),patch('shared_match.build_opener',return_value=Opener()):
            rows=discover_matches()
        self.assertEqual([r['address'] for r in rows],['http://192.168.137.1:9000'])
