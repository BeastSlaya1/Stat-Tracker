import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock, patch
import flet as ft
from test_app_integration import app, controls
from test_basketball import match
from match_statistics import match_statistics
from shared_match import SharedMatch, SharedError, local_request, discover_matches

class LatestUpdates(unittest.TestCase):
    def test_stats_hide_retired_metrics_but_keep_zero_counts_and_rates(self):
        data=match_statistics(match())
        for key in ('PAINT','FASTBREAK','SECONDCHANCE','OFFTURNOVER','BENCH','ADJUSTMENT','CHARGE','EFF','POSS','POINTS_AGAINST'):
            self.assertNotIn(key,data)
        for key in ('PTS','SHORT_PASS','LAYUPS','AST','FG%','2%','3%','FT%','3RATE','FTR','ORTG'):
            self.assertIn(key,data)
        self.assertEqual(data['PTS'][1],0)

    def test_comparison_changes_keep_dialog_and_selectors(self):
        a=app();a._database_user={'id':'owner','role':'owner'}
        first=match();first.id='first';a.matches=[first,replace(first,id='second')]
        a._full_refresh=Mock();a._open_owner_comparisons()
        dialog=a.page.dialog
        tile=next(c for c in controls(dialog) if isinstance(c,ft.ExpansionTile))
        boxes=[c for c in controls(dialog) if isinstance(c,ft.Checkbox)]
        for box in boxes[:2]:
            box.value=True;box.on_change(SimpleNamespace(control=box))
        for box in tile.controls[:3]:
            box.value=False;box.on_change(SimpleNamespace(control=box))
        self.assertIs(a.page.dialog,dialog)
        self.assertIs(next(c for c in controls(dialog) if isinstance(c,ft.ExpansionTile)),tile)
        self.assertEqual(len(a._coach_preferences['owner']['matches']),2)
        self.assertTrue(all(not c.value for c in tile.controls[:3]))
        a._full_refresh.assert_not_called()
        self.assertIn('2 matches selected',[c.value for c in controls(dialog) if isinstance(c,ft.Text)])

    def test_discovery_is_public_metadata_only_and_hidden_sessions_are_private(self):
        hub=SharedMatch(match());port=hub.start()
        try:
            address=f'127.0.0.1:{port}'
            data=local_request(address,'/discover')
            self.assertEqual(set(data),{'protocol','name','sport'})
            with self.assertRaises(SharedError):local_request(address,'/state')
            hub.hidden=True
            with self.assertRaises(SharedError):local_request(address,'/discover')
        finally:hub.stop()

    def test_scan_does_not_probe_public_or_loopback_networks(self):
        with patch('shared_match.addresses',return_value=['8.8.8.8:8767','127.0.0.1:8767']),patch('shared_match.build_opener') as opener:
            self.assertEqual(discover_matches(),[])
            opener.assert_not_called()

    def test_discovery_selection_fills_address_without_bypassing_join(self):
        import asyncio
        a=app();a.matches=[match()];a._open_shared_match()
        dialog=a.page.dialog
        button=next(c for c in controls(dialog) if isinstance(c,ft.Button) and c.content=='Scan for shared matches')
        with patch('shared_match.discover_matches',return_value=[{'address':'http://192.168.1.5:8767','name':'SCC vs Hilton','sport':'BASKETBALL'}]):
            asyncio.run(button.on_click(None))
        result=next(c for c in controls(dialog) if isinstance(c,ft.TextButton) and str(c.content).startswith('SCC vs Hilton'))
        result.on_click(None)
        fields={c.label:c for c in controls(dialog) if isinstance(c,ft.TextField)}
        self.assertEqual(fields['Host IP address and port'].value,'http://192.168.1.5:8767')
        self.assertFalse(fields['Join code'].value)
        self.assertIs(a.page.dialog,dialog)
        a._database_user['hidden']=True;a._open_shared_match()
        scan=next(c for c in controls(a.page.dialog) if isinstance(c,ft.Button) and c.content=='Scan for shared matches')
        self.assertFalse(scan.visible)
