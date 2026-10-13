import unittest,json
from unittest.mock import Mock,patch
import flet as ft
from test_app_integration import app,controls
from test_basketball import match
from engine import make_event,recalculate_stats,generate_sequences
from hockey import statistics,sequences,report,ensure_baseline,GROUPS
from shared_match import SharedMatch,SharedError,local_address
from shared_permissions import assignment
from models import Match,SPORTS

class HockeyTests(unittest.TestCase):
    def setup_app(self):
        a=app();m=match();m.sport='HOCKEY';a.matches=[m];a.action_category='Attack';a._save=Mock();return a
    def test_shots_modifiers_scoring_and_undo(self):
        a=self.setup_app();a._hockey_action('SHOT');a._hockey_action('CONVERSION');a._hockey_action('CONVERSION')
        self.assertEqual(a.match.home_score,1);self.assertEqual(statistics(a.match)['ASSIST'][1],0)
        self.assertEqual(sequences(a.match.events)['attack'],'S^G')
        a._hockey_action('SHOT');a._hockey_action('SHOT_INCOMPLETE')
        self.assertEqual(statistics(a.match)['SHOT_RATE'][1],50)
        a._hockey_action('SHOT_AGAINST');a._hockey_action('CONVERSION')
        self.assertEqual(a.match.away_score,1)
        a._undo_last_event();self.assertEqual(a.match.away_score,0)
        a._hockey_action('SHOT_AGAINST_INCOMPLETE');self.assertEqual(sequences(a.match.events)['opposition'],'As!')
    def test_defense_incomplete_stays_in_defense(self):
        a=self.setup_app();a._hockey_action('TACKLE');a._hockey_action('TACKLE_INCOMPLETE')
        self.assertEqual(statistics(a.match)['TACKLE'][1],0)
        self.assertEqual(statistics(a.match)['TACKLE_INCOMPLETE'][1],1)
        self.assertEqual(generate_sequences(a.match.events,'home','HOCKEY')['defence'],'T!')
        self.assertEqual(sequences(a.match.events)['attack'],'')
    def test_awards_cards_export_and_choices(self):
        a=self.setup_app()
        for c in ('PENALTY_CORNER','PENALTY_STROKE','FREE_HIT','GREEN_CARD'):a._hockey_action(c)
        self.assertEqual(a.match.home_score,0)
        text=report(a.match);self.assertIn('STAT TRACKER — HOCKEY',text);self.assertNotIn('Offside',text)
        restored=Match.from_dict(json.loads(text.split('=== STAT_TRACKER_MATCH_DATA_START ===')[1].split('=== STAT_TRACKER_MATCH_DATA_END ===')[0]))
        self.assertEqual(restored.to_dict(),a.match.to_dict())
        self.assertEqual(SPORTS,['SOCCER','HOCKEY','BASKETBALL'])
    def test_historical_scores_and_manual_corrections_survive(self):
        a=self.setup_app();a.match.home_score=2;a.match.away_score=3
        a._hockey_action('GOAL');a._hockey_action('GOALS_GIVEN')
        self.assertEqual((a.match.home_score,a.match.away_score),(3,4))
        a._update_score('away',-1);a._hockey_action('PASS')
        self.assertEqual(a.match.away_score,3)
    def test_section_grids_and_incompletes(self):
        a=self.setup_app();a._hockey_action('PASS')
        for category in ('Attack','Defence','Cards','Opposition'):
            a.action_category=category
            tree=a._build_category_grid(a.match)
            labels={c.data['stat_label'] for c in controls(tree) if isinstance(getattr(c,'data',None),dict) and 'stat_label' in c.data}
            expected={r[1] for r in GROUPS[category.replace('Defence','Defense')]}
            self.assertEqual(labels-{'Conversion'},expected)
            inc=a._build_incompletes_row()
            labels={c.value for c in controls(inc) if isinstance(c,ft.Text) and c.value.endswith(' !')}
            self.assertEqual(labels,{r[1]+' !' for r in GROUPS[category.replace('Defence','Defense')] if r[3]})
    def test_shared_opposition_conversion_and_permissions(self):
        a=self.setup_app();hub=SharedMatch(a.match)
        row=hub.join(hub.join_code,'Phone',False);hub.approve(row['device'],permissions=assignment('HOCKEY','Opposition',['SHOT_AGAINST']))
        shot=make_event(a.match,'home','SHOT_AGAINST','SCC','Shot against');conv=make_event(a.match,'home','CONVERSION','SCC','Conversion');conv.target_id=shot.id
        hub.apply(row['token'],[shot.to_dict(),conv.to_dict()],[])
        self.assertEqual(hub.match.away_score,1);self.assertEqual(hub.match.home_score,0)
        with self.assertRaises(SharedError):hub.apply(row['token'],[make_event(a.match,'home','SHOT','SCC','Shot').to_dict()],[])
        hub.apply(row['token'],[],[conv.id]);self.assertEqual(hub.match.away_score,0)

class WiredTests(unittest.TestCase):
    def test_local_and_link_local_only(self):
        for ip in ('192.168.42.129','172.20.10.2','169.254.12.2'):
            self.assertEqual(local_address(ip+':8767'),'http://'+ip+':8767')
        for address in ('8.8.8.8:8767','example.com:8767','http://192.168.1.2:8767/evil','0.0.0.0:8767'):
            with self.assertRaises(SharedError):local_address(address)
    def test_all_wired_addresses_are_offered(self):
        from shared_match import addresses
        with patch('local_network.local_ipv4_addresses',return_value=['192.168.1.10','172.20.10.2','169.254.2.3']):
            self.assertEqual(addresses(8767),['192.168.1.10:8767','172.20.10.2:8767','169.254.2.3:8767'])
    def test_dictionary_has_only_current_concise_help(self):
        from basketball_dictionary import ENTRIES
        text=' '.join(body for title,body in ENTRIES)
        self.assertLess(len(text.split()),650)
        for retired in ('Bench points','In the paint','Shot tags','On court','Double-double'):self.assertNotIn(retired,text)
        for word in ('Conversion','Layup','Penalty','Timeout','percentage'):self.assertIn(word,text)

class ExportNames(unittest.TestCase):
    def test_all_exports_use_match_name(self):
        from export_utils import match_filename
        a=app();m=match();m.title='St Charles College vs Hilton';a.matches=[m];a.page.run_task=Mock()
        for sport in SPORTS:
            m.sport=sport;a._export_txt()
            self.assertEqual(a.page.run_task.call_args.args[1],'St Charles College vs Hilton.txt')
        m.title='U15A: SCC / Hilton?';self.assertEqual(match_filename(m),'U15A- SCC - Hilton-.txt')
        m.title='CON';self.assertEqual(match_filename(m),'Match CON.txt')

class BeaconTests(unittest.TestCase):
    def test_discovery_returns_no_secrets_and_hidden_host_is_silent(self):
        import socket
        from match_discovery import MAGIC,PORT
        m=match();hub=SharedMatch(m);port=hub.start()
        try:
            with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
                sock.settimeout(.35);sock.sendto(MAGIC,('127.0.0.1',PORT))
                reply=json.loads(sock.recvfrom(512)[0])
                self.assertEqual(reply,{'protocol':'stat-tracker-match-v1','port':port})
                hub.hidden=True;sock.sendto(MAGIC,('127.0.0.1',PORT))
                with self.assertRaises(socket.timeout):sock.recvfrom(512)
        finally:hub.stop()
