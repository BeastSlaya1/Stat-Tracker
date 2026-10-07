import unittest
from dataclasses import replace
from unittest.mock import Mock
import flet as ft
from test_app_integration import app,controls
from test_basketball import match
from match_statistics import match_statistics
from engine import make_event,generate_sequences
from basketball import sequences

class CoachTests(unittest.TestCase):
    def test_dashboard_scopes_matches_and_customizes_selection(self):
        a=app();a._database_user={'id':'coach','role':'coach','team_code':'U15A','sport':'BASKETBALL'}
        first=match();first.id='first';first.home_team.team_code='U15A'
        second=replace(first,id='second',away_team=replace(first.away_team,name='Hilton',short_name='HIL'))
        wrong=replace(first,id='wrong',sport='SOCCER')
        a.matches=[first,second,wrong];a._persist_database=Mock()
        view=a._build_coach_dashboard()
        boxes=[c for c in controls(view) if isinstance(c,ft.Checkbox)]
        for c in boxes[:2]:c.value=True;c.on_change(type('E',(),{'control':c})())
        self.assertEqual(a._coach_preferences['coach']['matches'],['second','first'])
        view=a._build_coach_dashboard();texts=[c.value for c in controls(view) if isinstance(c,ft.Text)]
        self.assertIn('2 matches selected',texts)
        self.assertTrue(any(isinstance(c,ft.ProgressBar) for c in controls(view)))
        a.page.dialog=None;a._open_new_match_dialog();self.assertIsNone(a.page.dialog)
        a._view_saved_game('first');buttons=[c for c in controls(a.page.dialog) if isinstance(c,(ft.Button,ft.TextButton))]
        self.assertTrue(all(c.visible is False for c in buttons if c.content in ('Edit details','Open workspace')))

    def test_stats_are_scc_only_and_markers_have_requested_symbols(self):
        m=match();m.sport='SOCCER';data=match_statistics(m)
        self.assertTrue(all(k.startswith('home_') for k in data))
        events=[make_event(m,'home',code,'SCC',code) for code in ['TURNOVER','SUBSTITUTION','TIMEOUT','END_QUARTER','FULL_TIME']]
        self.assertEqual(generate_sequences(events,'home')['attack'],'[TURN][SUB][STOP][TIME][FT]')
        for e in events:e.event_type='BB_'+('TO' if e.event_type=='TURNOVER' else e.event_type)
        self.assertEqual(sequences(events)['attack'],'[TURN][SUB][STOP][TIME][FT]')

    def test_coach_account_requires_team_and_sport_controls(self):
        a=app();a._create_account_dialog()
        items=list(controls(a.page.dialog));role=next(c for c in items if isinstance(c,ft.Dropdown) and c.label=='Account type')
        role.value='coach';role.on_select(None)
        self.assertTrue(next(c for c in items if isinstance(c,ft.Dropdown) and c.label=='Team / Age Group').visible)
        self.assertTrue(next(c for c in items if isinstance(c,ft.Dropdown) and c.label=='Coached sport').visible)

    def test_shared_team_choices_restore_normalized_assignments(self):
        from team_options import team_dropdown, TEAM_RANK_OPTIONS
        self.assertEqual(team_dropdown("U171ST").value,"U17 1st")
        self.assertEqual([o.key for o in team_dropdown().options],TEAM_RANK_OPTIONS)

    def test_match_and_coach_use_one_shared_dropdown(self):
        from team_options import TEAM_RANK_OPTIONS
        a=app()
        a._open_new_match_dialog()
        items=list(controls(a.page.dialog))
        teams=[c for c in items if isinstance(c,ft.Dropdown) and c.label=='Team / Age Group']
        self.assertEqual(len(teams),1)
        self.assertEqual([o.key for o in teams[0].options],TEAM_RANK_OPTIONS)
        self.assertFalse(any(isinstance(c,ft.TextField) and c.label=='SCC team age and type' for c in items))
        a._create_account_dialog()
        coach=next(c for c in controls(a.page.dialog) if isinstance(c,ft.Dropdown) and c.label=='Team / Age Group')
        self.assertEqual([o.key for o in coach.options],TEAM_RANK_OPTIONS)
