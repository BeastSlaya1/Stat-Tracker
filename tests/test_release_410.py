import json
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import Mock
import flet as ft
from test_app_integration import app, controls
from models import Match


class Release410Tests(unittest.TestCase):
    def test_different_ages_survive_creation_edit_and_serialization(self):
        a = app(); a._save = Mock()
        a._open_new_match_dialog()
        items = list(controls(a.page.dialog))
        def field(label):
            return next(c for c in items if getattr(c, 'label', None) == label)
        field('Opponent team name (required)').value = 'St Charles College'
        field('SCC team / age group').value = 'U15A'
        field('Opponent team / age group').value = 'U16B'
        next(c for c in items if isinstance(c, ft.Button) and c.content == 'Create Match').on_click(None)
        m = Match.from_dict(a.match.to_dict())
        self.assertEqual((m.home_team.team_code, m.away_team.team_code), ('U15A', 'U16B'))
        self.assertEqual(m.away_team.name, 'St Charles College')
        a._open_edit_match_dialog()
        items = list(controls(a.page.dialog))
        self.assertEqual(field('Opponent team / age group').value, 'U16B')
        field('SCC team / age group').value = '1st Team'
        next(c for c in items if isinstance(c, ft.Button) and c.content == 'Save Changes').on_click(None)
        self.assertEqual((a.match.home_team.team_code, a.match.away_team.team_code), ('1STTEAM', 'U16B'))

    def test_reset_covers_both_realms_once_and_preserves_history(self):
        db = sqlite3.connect(':memory:')
        server = Path(__file__).resolve().parents[1] / 'server'
        db.executescript((server / 'rosters-migration.sql').read_text())
        players = [{'id': 'a'*32, 'number': 1234, 'active': True}]
        for team, hidden in [('U15A', 0), ('1STTEAM', 1)]:
            db.execute('INSERT INTO team_rosters VALUES(?,?,?,?)', (team, hidden, 4, json.dumps(players)))
        db.execute('CREATE TABLE matches (data TEXT)')
        db.execute('INSERT INTO matches VALUES (?)', ('historical match and jersey stats',))
        sql = (server / 'rosters-reset-410.sql').read_text()
        db.executescript(sql)
        for version, raw in db.execute('SELECT version,players FROM team_rosters'):
            self.assertEqual(version, 5)
            self.assertEqual(json.loads(raw), [{**players[0], 'active': False}])
        db.execute('UPDATE team_rosters SET players=? WHERE hidden=0', (json.dumps(players),))
        db.executescript(sql)
        self.assertTrue(json.loads(db.execute('SELECT players FROM team_rosters WHERE hidden=0').fetchone()[0])[0]['active'])
        self.assertEqual(db.execute('SELECT data FROM matches').fetchone()[0], 'historical match and jersey stats')
        db.close()


class EmptyJerseyStatsTests(unittest.TestCase):
    def test_old_roster_without_events_has_no_player_rows(self):
        from test_basketball import match
        from basketball import summary, report
        m = match()
        self.assertEqual(summary(m)['home']['players'], {})
        a = app()
        self.assertEqual(a._jersey_stats(m).value, 'No player statistics recorded for this match.')
        self.assertNotIn('PLAYER: #', report(m))

    def test_removed_player_with_events_keeps_history_and_undo_removes_empty_row(self):
        from test_basketball import match, event
        from basketball import summary
        m = match()
        m.home_team.players[0].active = False
        event(m, 'LAYUP', pid='0')
        data = summary(m)['home']['players']
        self.assertEqual(list(data), ['0'])
        self.assertEqual(data['0']['stats']['PTS'], 2)
        m.events.clear()
        self.assertEqual(summary(m)['home']['players'], {})
