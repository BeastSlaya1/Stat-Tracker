import asyncio
import json
import unittest
from unittest.mock import Mock, AsyncMock
from test_app_integration import app


class StartupTests(unittest.IsolatedAsyncioTestCase):
    def make_app(self, value):
        instance = app()
        instance.is_web = True
        instance._web_loaded = False
        instance.logger_name = ""
        instance.app_mode = "inputter"
        instance._app_mode_ever_chosen = False
        instance._web_prefs = Mock(get=AsyncMock(return_value=value), set=AsyncMock())
        instance._open_name_dialog = Mock()
        instance._open_mode_dialog = Mock()
        return instance

    async def test_saved_name_is_restored_before_deciding_to_prompt(self):
        instance = self.make_app(json.dumps({"settings": {
            "logger_name": "Joshua Pieterse", "app_mode": "inputter"}}))
        await instance._load_web_data_async()
        self.assertEqual(instance.logger_name, "Joshua Pieterse")
        instance._open_name_dialog.assert_not_called()
        instance._open_mode_dialog.assert_not_called()

    async def test_new_browser_still_gets_welcome_prompt(self):
        instance = self.make_app(None)
        await instance._load_web_data_async()
        instance._open_name_dialog.assert_called_once_with(first_launch=True)

    async def test_slow_storage_does_not_prompt_or_overwrite_saved_data(self):
        instance = self.make_app(None)
        ready = asyncio.Event()
        async def load(_):
            await ready.wait()
            return json.dumps({"settings": {"logger_name": "Joshua", "app_mode": "inputter"}})
        instance._web_prefs.get.side_effect = load
        task = asyncio.create_task(instance._load_web_data_async())
        await asyncio.sleep(0)
        await instance._save_web_async()
        instance._open_name_dialog.assert_not_called()
        instance._web_prefs.set.assert_not_called()
        ready.set()
        await task
        instance._open_name_dialog.assert_not_called()

    async def test_failed_storage_is_not_treated_as_first_launch(self):
        instance = self.make_app(None)
        instance._web_prefs.get.side_effect = OSError("storage unavailable")
        await instance._load_web_data_async()
        await instance._save_web_async()
        instance._open_name_dialog.assert_not_called()
        instance._web_prefs.set.assert_not_called()
