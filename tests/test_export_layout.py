import json
import unittest
from pathlib import Path
from basketball import report
from test_basketball import match, event
from models import Match

class ExportLayoutTests(unittest.TestCase):
    def test_matches_supplied_layout(self):
        m=match();m.title='St Charles College vs Example';m.date='2026-10-12';m.home_team.name='St Charles College'
        text=report(m)
        header=text.split('=== STAT_TRACKER_MATCH_DATA_START ===')[0].rstrip()
        expected=Path(__file__).with_name('basketball_export_header.txt').read_text(encoding='utf-8').rstrip()
        self.assertEqual(header,expected)
        self.assertNotIn('STAT DEFINITIONS',text)
        self.assertEqual(text.count('=== STAT_TRACKER_MATCH_DATA_START ==='),1)

    def test_export_preserves_nonzero_data_for_reimport(self):
        m=match();event(m,'3_MADE',pid='p',tags=['fastbreak'])
        text=report(m)
        raw=text.split('=== STAT_TRACKER_MATCH_DATA_START ===')[1].split('=== STAT_TRACKER_MATCH_DATA_END ===')[0]
        restored=Match.from_dict(json.loads(raw))
        self.assertEqual(restored.to_dict(),m.to_dict())
        self.assertIn('3M (Three-pointers made): 1',text)
        self.assertNotIn('FASTBREAK (',text)

    def test_import_entry_point_accepts_new_and_legacy_markers(self):
        import asyncio
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, Mock
        from test_app_integration import app
        m=match();event(m,'LAYUP')
        for marker in ('STAT_TRACKER_MATCH_DATA','STAT_TRACKER_AI_MATCH_DATA'):
            a=app();a._save=Mock();a._full_refresh=Mock()
            content=report(m).replace('STAT_TRACKER_MATCH_DATA',marker)
            picker=SimpleNamespace(pick_files=AsyncMock(return_value=[SimpleNamespace(bytes=content.encode('utf-8'))]))
            a._ensure_file_picker=lambda:picker
            asyncio.run(a._import_txt_async())
            self.assertEqual(len(a.matches),1)
            self.assertEqual(a.matches[0].to_dict(),m.to_dict())
            a._save.assert_called_once()
