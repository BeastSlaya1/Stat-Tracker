import asyncio
import unittest
from unittest.mock import Mock
import flet as ft
from test_app_integration import app, controls


class ResponsiveTests(unittest.TestCase):
    def test_download_button_only_visible_in_browser(self):
        for web in (False, True):
            instance = app()
            instance.logger_name = "Joshua"
            instance.is_web = web
            instance.page.width = 320
            navbar = instance._build_navbar()
            button = next(c for c in controls(navbar)
                          if isinstance(c, ft.Button) and c.content == "Get the app")
            self.assertEqual(button.visible, web)
            self.assertTrue(navbar.content.controls[0].wrap)
            self.assertLessEqual(instance.match_dd.width, 272)

    def test_action_grid_has_room_for_every_row_at_each_size(self):
        instance = app()
        instance.action_category = "Attack"
        for width in (320, 390, 768, 1024, 1366, 1920):
            instance.page.width = width
            grid = instance._build_category_grid(None)
            tile_width = (width - 92 - 6 * (grid.runs_count - 1)) / grid.runs_count
            tile_height = tile_width / grid.child_aspect_ratio
            rows = (len(grid.controls) + grid.runs_count - 1) // grid.runs_count
            self.assertGreaterEqual(tile_height, 48)
            self.assertGreaterEqual(grid.height, rows * tile_height)

    def test_narrow_rows_wrap_and_buttons_keep_their_contents(self):
        instance = app()
        button = ft.Button(content=ft.Row([ft.Text("Action")]))
        row = ft.Row([ft.Text("Actions"), ft.Container(expand=True), button])
        instance._responsive_controls(row)
        self.assertTrue(row.wrap)
        self.assertEqual(len(row.controls), 2)
        self.assertFalse(button.content.wrap)

    def test_resize_burst_rebuilds_only_once(self):
        instance = app()
        instance._full_refresh = Mock()
        async def resize():
            await asyncio.gather(instance._on_layout_resize(None), instance._on_layout_resize(None))
        asyncio.run(resize())
        instance._full_refresh.assert_called_once()
