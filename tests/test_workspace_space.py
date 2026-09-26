import unittest
from unittest.mock import Mock
import flet as ft
from test_app_integration import app


class WorkspaceSpaceTests(unittest.TestCase):
    def test_workspace_has_sixty_percent_with_separate_header_scroll(self):
        for width, height in ((320, 568), (768, 1024), (1366, 768), (1920, 1080)):
            instance = app()
            instance.page.width, instance.page.height = width, height
            instance._build_navbar = Mock(return_value=ft.Container(height=500))
            instance.scoreboard_ref = ft.Container(height=300)
            instance.tab_bar_ref = ft.Row()
            instance.tab_content_ref = ft.Container(expand=True)
            shell = instance._build_workspace_shell()
            header, workspace = shell.controls
            self.assertEqual(workspace.expand / (workspace.expand + header.expand), 0.6)
            self.assertEqual(header.content.controls[0].scroll, ft.ScrollMode.AUTO)
            self.assertIs(workspace.content, instance.tab_content_ref)
            self.assertIs(header.content.controls[1].content, instance.tab_bar_ref)

    def test_laptop_uses_compact_scoreboard(self):
        instance = app()
        instance.page.width, instance.page.height = 1366, 768
        instance._build_scoreboard_compact = Mock(return_value="compact")
        self.assertEqual(instance._build_scoreboard(None), "compact")
