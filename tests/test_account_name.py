import unittest
import flet as ft
from unittest.mock import Mock
from test_app_integration import app, controls

class AccountNameTests(unittest.TestCase):
    def test_identity_follows_account_switch_and_sign_out(self):
        a=app()
        for name in ('Joshua Pieterse', 'Another User'):
            a._database_user={'id':name,'display_name':name}
            self.assertEqual(a.logger_name,name)
            self.assertIn(name,[c.value for c in controls(a._logger_name_pill()) if isinstance(c,ft.Text)])
        a._database_token=''
        self.assertEqual(a.logger_name,'')
        self.assertIn('Sign in',[c.value for c in controls(a._logger_name_pill()) if isinstance(c,ft.Text)])

    def test_name_area_opens_account_instead_of_name_editor(self):
        a=app();a._open_database_dialog=Mock()
        a._logger_name_pill().on_click(None)
        a._open_database_dialog.assert_called_once_with(None)

    def test_native_startup_never_asks_for_name(self):
        a=app();a._app_mode_ever_chosen=True;a._open_mode_dialog=Mock()
        a._show_startup_dialogs()
        a._open_mode_dialog.assert_not_called()
        self.assertFalse(hasattr(type(a),'_open_name_dialog'))
