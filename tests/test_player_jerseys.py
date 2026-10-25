import unittest
from test_app_integration import app, controls
from test_basketball import match
import test_scc_basketball
from basketball import summary
from shared_match import SharedMatch, SharedError
from shared_permissions import assignment
from engine import make_event

class JerseyTests(unittest.TestCase):
    def setup_app(self):
        a=app();a.matches=[match()];a._save=lambda:None
        return a
    def test_selection_required_but_opposition_is_team_level(self):
        a=self.setup_app();a._selected_jerseys={}
        a._bb_log('SHOT');self.assertEqual(a.match.events,[])
        a._bb_log('LAYUP_AGAINST');self.assertEqual(a.match.away_score,2)
        self.assertEqual(a.match.events[-1].basketball['player_id'],'')
    def test_original_jersey_keeps_incomplete_after_selection_changes(self):
        a=self.setup_app();a._bb_log('SHOT');a._selected_jerseys['bb']='1';a._bb_mark_incomplete('SHOT')
        stats=summary(a.match)['home']['players']
        self.assertEqual(stats['0']['stats']['SHOT_MISSES'],1)
        self.assertNotIn('1',stats)
    def test_assist_goes_to_second_jersey(self):
        a=self.setup_app();a._bb_log('SHOT');a._selected_jerseys['bb']='1'
        test_scc_basketball.SCCBasketballTests().convert(a,3,True)
        stats=summary(a.match)['home']['players']
        self.assertEqual((stats['0']['stats']['PTS'],stats['0']['stats']['AST']),(3,0))
        self.assertEqual((stats['1']['stats']['PTS'],stats['1']['stats']['AST']),(0,1))
        a._undo_last_event();self.assertNotIn('1',summary(a.match)['home']['players'])
    def test_shared_assignment_rejects_wrong_and_inactive_jerseys(self):
        hub=SharedMatch(match());row=hub.join(hub.join_code,'Phone',False)
        hub.approve(row['device'],permissions=assignment('BASKETBALL','Attack',['SHOT'],players=['0']))
        def action(pid):
            e=make_event(hub.match,'home','BB_SHOT','Spoofed name','Shot');e.basketball={'player_id':pid,'jersey':99};return e
        for pid in ('1','unknown',''):
            with self.assertRaises(SharedError):hub.apply(row['token'],[action(pid).to_dict()],[])
        hub.apply(row['token'],[action('0').to_dict()],[])
        self.assertEqual(hub.match.events[0].player_name,'#0');self.assertEqual(hub.match.events[0].basketball['jersey'],0)
        hub.match.home_team.players[0].active=False
        with self.assertRaises(SharedError):hub.apply(row['token'],[action('0').to_dict()],[])
    def test_remove_jersey_keeps_old_points(self):
        a=self.setup_app();a._bb_log('2_MADE');a.match.home_team.team_code='U15A'
        a._apply_roster('U15A',[{'id':'0','number':0,'active':False},{'id':'1','number':1,'active':True}])
        self.assertIsNone(a._selected_player());self.assertEqual(summary(a.match)['home']['players']['0']['stats']['PTS'],2)
