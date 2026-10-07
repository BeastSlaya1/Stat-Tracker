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
        self.assertEqual(generate_sequences(events,'home'),dict.fromkeys(('attack','defence','cards'),'[TURN][SUB][STOP][TIME][FT]'))
        for e in events:e.event_type='BB_'+('TO' if e.event_type=='TURNOVER' else e.event_type)
        self.assertEqual(sequences(events),dict.fromkeys(('attack','defence','cards'),'[TURN][SUB][STOP][TIME][FT]'))

    def test_coach_account_requires_team_and_sport_controls(self):
        a=app();a._create_account_dialog()
        items=list(controls(a.page.dialog));role=next(c for c in items if isinstance(c,ft.Dropdown) and c.label=='Account type')
        role.value='coach';role.on_select(None)
        self.assertTrue(next(c for c in items if isinstance(c,ft.Dropdown) and c.label=='Team / Age Group').visible)
        self.assertTrue(next(c for c in items if isinstance(c,ft.Dropdown) and c.label=='Coached sport').visible)

    def test_shared_team_choices_restore_normalized_assignments(self):
        from team_options import team_dropdown, TEAM_RANK_OPTIONS
        self.assertEqual(team_dropdown("U171ST").value,"U171ST")
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

    def test_defence_incompletes_stay_in_defence_and_preserve_order(self):
        m=match()
        for code,symbol in [('DREB','Dr'),('STL','S'),('BLK','B'),('DEFLECTION','D'),('LOOSE','Lb'),('SHOT_AGAINST','As')]:
            with self.subTest(code=code):
                action=make_event(m,'home','BB_'+code,'SCC',code)
                marker=make_event(m,'home','BB_TIMEOUT','SCC','timeout')
                correction=make_event(m,'home','BB_INCOMPLETE','SCC','incomplete')
                correction.basketball={'target_id':action.id}
                self.assertEqual(sequences([action,marker,correction]),{'attack':'[STOP]','defence':symbol+'![STOP]','cards':'[STOP]'})

    def test_comparison_legend_and_radar_use_same_series(self):
        from coach_chart import comparison_chart, match_colors, radar_data, match_label
        from team_options import TEAM_RANK_OPTIONS
        import flet.canvas as cv
        first=match();first.home_team.team_code='U15A';first.away_team.team_rank='U15A'
        second=replace(first,id='second',away_team=replace(first.away_team,name='Kearsney'))
        colors=match_colors(9)
        self.assertEqual(len(set(colors)),9)
        chart=comparison_chart([first,second],colors[:2])
        items=list(controls(chart))
        self.assertTrue(any(isinstance(c,ft.Text) and match_label(second) in c.value for c in items))
        canvas=next(c for c in items if isinstance(c,cv.Canvas))
        strokes=[s.paint.color for s in canvas.shapes if isinstance(s,cv.Path) and s.paint.stroke_width==2]
        self.assertEqual(strokes,colors[:2])
        self.assertEqual(radar_data([first,second])[0],['Points','Rebounds','Assists','Steals','Blocks','FG made'])
        self.assertTrue(all(f'{n} Team' in TEAM_RANK_OPTIONS for n in ['1st','2nd','3rd','4th','5th','6th','7th','8th']))
        self.assertFalse(any(x.startswith(('U17','U18','U19')) for x in TEAM_RANK_OPTIONS))
