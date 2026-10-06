import unittest
import flet as ft
from basketball import summary, sequences
from models import Match
from test_basketball import match
from test_app_integration import app, controls

class SCCBasketballTests(unittest.TestCase):
    def setup_app(self):
        a=app();a.matches=[match()];a._save=lambda:None
        return a

    def convert(self,a,points,assist):
        a._bb_open_conversion()
        items=list(controls(a.page.dialog))
        group=next(c for c in items if isinstance(c,ft.RadioGroup))
        check=next(c for c in items if isinstance(c,ft.Checkbox))
        group.value=str(points);check.value=assist;group.on_change(None)
        a.page.dialog.actions[-1].on_click(None)

    def test_conversion_points_assist_sequences_and_undo(self):
        for points in (1,2,3):
            for assist in (False,True):
                a=self.setup_app();a._bb_log('SHOT')
                self.assertEqual(a.match.home_score,0)
                self.convert(a,points,assist)
                stats=summary(a.match)['home']['team']
                self.assertEqual((stats['PTS'],stats['AST'],stats['SHOTS']),(points,int(assist),1))
                self.assertEqual(stats['FTA']+stats['FGA'],1)
                self.assertEqual(sequences(a.match.events)['attack'],'S^'+('A' if assist else '')+str(points))
                self.assertIsNone(a._bb_conversion_event())
                restored=Match.from_dict(a.match.to_dict())
                self.assertEqual(summary(restored),summary(a.match))
                a._undo_last_event()
                self.assertEqual(a.match.home_score,0)
                self.assertEqual(summary(a.match)['home']['team']['AST'],0)
                self.assertIsNone(a._bb_conversion_event())

    def test_conversion_invalidated_by_action_cancel_and_stale_dialog(self):
        a=self.setup_app();a._bb_log('SHOT');a._bb_log('OREB')
        self.assertIsNone(a._bb_conversion_event())
        a._bb_log('SHOT');a._bb_open_conversion()
        dialog=a.page.dialog
        group=next(c for c in controls(dialog) if isinstance(c,ft.RadioGroup));group.value='3'
        a._bb_log('STL');dialog.actions[-1].on_click(None)
        self.assertEqual(a.match.home_score,0)
        a._bb_log('SHOT');a._bb_open_conversion();a.page.dialog.actions[0].on_click(None)
        self.assertIsNone(a._bb_conversion_event())

    def test_layup_incomplete_and_delete_conversion_do_not_double_count(self):
        a=self.setup_app();a._bb_log('LAYUP')
        self.assertEqual(a.match.home_score,2)
        a._bb_mark_incomplete('LAYUP')
        stats=summary(a.match)['home']['team']
        self.assertEqual((stats['2A'],stats['2M'],stats['LAYUPS'],stats['LAYUP_MISSES']),(1,0,1,1))
        self.assertEqual(a.match.home_score,0)
        a._undo_last_event();self.assertEqual(a.match.home_score,2)
        a._bb_log('SHOT');target=a.match.events[-1].id;self.convert(a,3,True)
        a._delete_event(target)
        self.assertEqual(a.match.home_score,2)
        self.assertFalse(any(e.event_type=='BB_CONVERSION' for e in a.match.events))

    def test_shot_incomplete_is_unclassified_and_not_convertible(self):
        a=self.setup_app();a._bb_log('SHOT');a._bb_mark_incomplete('SHOT')
        self.assertIsNone(a._bb_conversion_event())
        stats=summary(a.match)['home']['team']
        self.assertEqual((stats['SHOTS'],stats['SHOT_MISSES'],stats['PTS']),(1,1,0))
        self.assertEqual(sequences(a.match.events)['attack'],'S!')

    def test_penalties_belong_to_scc_with_direction_and_preserve_scores(self):
        a=self.setup_app();a.match.home_score=5;a.match.away_score=4
        for direction in ('attack','defence'):
            popup=a._bb_penalty_button(direction)
            next(i for i in popup.items if i.content=='Personal foul').on_click(None)
        stats=summary(a.match)['home']['team']
        self.assertEqual((stats['PENALTIES_WON'],stats['PENALTIES_GIVEN'],stats['FD'],stats['PF']),(1,1,1,1))
        self.assertEqual((a.match.home_score,a.match.away_score),(5,4))
        self.assertTrue(all(e.team_id=='home' for e in a.match.events))
        self.assertEqual(sequences(a.match.events),{'attack':'P[PF]','defence':'P[PF]','cards':''})
        a._update_score('away',2)
        self.assertEqual(a.match.away_score,6)
        self.assertEqual(a.match.events[-1].team_id,'home')
        self.assertEqual(summary(a.match)['away']['team']['FGA'],0)
        a._undo_last_event();self.assertEqual(a.match.away_score,4)

    def test_stale_team_selection_cannot_record_opponent_stats(self):
        a=self.setup_app();a._bb_side='away';a._bb_log('STL','away')
        self.assertEqual(a.match.events[-1].team_id,'home')
        a._timer_running=False;a._build_live_video_panel=lambda:ft.Text('Video')
        logger=a._build_basketball_logger(a.match)
        self.assertFalse(any(isinstance(c,ft.Dropdown) and c.label=='Logging for' for c in controls(logger)))
        for sport in ('SOCCER','RUGBY','HOCKEY','NETBALL'):
            a.match.sport=sport;a._quick_action('PASS','Pass')
            self.assertEqual(a.match.events[-1].team_id,'home')
