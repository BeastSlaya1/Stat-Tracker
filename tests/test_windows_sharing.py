import asyncio
import ctypes
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, patch
import flet as ft
from test_app_integration import app, controls
from windows_sharing import SharingAccess, access


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.access=SharingAccess()
        self.access._kernel=Mock()
        self.access._handles=[101,102,103]
        self.access.address='192.168.1.2';self.access.port=8767

    def tearDown(self):self.access.stop()

    def test_stop_signals_helper_then_closes_every_handle(self):
        self.access.stop()
        self.access._kernel.SetEvent.assert_called_once_with(101)
        self.access._kernel.WaitForSingleObject.assert_called_once_with(103,3000)
        self.assertEqual([call.args[0] for call in self.access._kernel.CloseHandle.call_args_list],[101,102,103])
        self.assertFalse(self.access.active)
        self.assertIsNone(self.access.address)
        self.access.stop()
        self.assertEqual(self.access._kernel.SetEvent.call_count,1)

    def test_helper_exit_is_not_reported_as_enabled(self):
        self.access._kernel.WaitForSingleObject.return_value=0
        self.assertFalse(self.access.active)
        self.access._kernel.WaitForSingleObject.return_value=258
        self.assertTrue(self.access.active)

    def test_partial_launch_closes_events_without_waiting_for_missing_process(self):
        self.access._handles=[101,102]
        self.access.stop()
        self.access._kernel.WaitForSingleObject.assert_not_called()
        self.assertEqual(self.access._kernel.CloseHandle.call_count,2)


@unittest.skipUnless(os.name=='nt','Windows helper')
class NativeValidationTests(unittest.TestCase):
    def test_cancelled_windows_approval_releases_events(self):
        temporary=SharingAccess()
        temporary._kernel=Mock()
        temporary._kernel.CreateEventW.side_effect=[101,102]
        def cancel(_):
            ctypes.set_last_error(1223)
            return False
        shell=Mock();shell.ShellExecuteExW.side_effect=cancel
        with patch('local_network.local_ipv4_addresses',return_value=['192.168.1.2']),patch('windows_sharing.ctypes.WinDLL',return_value=shell):
            with self.assertRaisesRegex(RuntimeError,'cancelled'):
                temporary.enable('192.168.1.2')
        self.assertFalse(temporary.active)
        self.assertEqual(temporary._kernel.CloseHandle.call_count,2)
        temporary._kernel.SetEvent.assert_called_once_with(101)

    def test_success_requires_helper_ready_before_reporting_enabled(self):
        temporary=SharingAccess();temporary._kernel=Mock()
        temporary._kernel.CreateEventW.side_effect=[101,102]
        temporary._kernel.WaitForMultipleObjects.return_value=1
        def launch(info):
            info._obj.hProcess=103
            self.assertEqual(info._obj.lpVerb,'runas')
            self.assertEqual(info._obj.nShow,0)
            return True
        shell=Mock();shell.ShellExecuteExW.side_effect=launch
        try:
            with patch('local_network.local_ipv4_addresses',return_value=['192.168.1.2']),patch('windows_sharing.ctypes.WinDLL',return_value=shell):
                temporary.enable('192.168.1.2',8770)
            self.assertEqual(temporary.address,'192.168.1.2')
            self.assertEqual(temporary.port,8770)
            self.assertEqual(temporary._handles,[101,102,103])
        finally:temporary.stop()

    def test_invalid_or_public_address_cannot_enable_filters(self):
        helper=Path(__file__).resolve().parents[1]/'assets/local-sharing.exe'
        if not helper.exists():self.skipTest('Build the Windows helper first')
        for address in ('8.8.8.8','127.0.0.1','0.0.0.0','not-an-address'):
            result=subprocess.run([str(helper),str(os.getpid()),address,'stop','ready','8767'],
                timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode,2,address)


@unittest.skipUnless(os.name=='nt','Windows setup UI')
class SharingUITests(unittest.IsolatedAsyncioTestCase):
    async def test_enable_uses_selected_network_and_actual_host_port(self):
        a=app();a.is_web=False
        a._live_session={'host':True,'hub':Mock()}
        a._live_session['hub'].server.server_port=8770
        with patch('local_network.local_network_choices',return_value=[('192.168.1.2','USB')]),patch.object(access,'enable') as enable:
            rows=a._local_sharing_controls()
            items=list(controls(ft.Column(rows)))
            await next(c for c in items if isinstance(c,ft.Button) and c.content=='Enable local sharing').on_click(None)
            enable.assert_called_once_with('192.168.1.2',8770)

    async def test_multiple_networks_require_selection(self):
        a=app();a.is_web=False
        with patch('local_network.local_network_choices',return_value=[('192.168.1.2','USB'),('10.1.1.2','Wi-Fi')]),patch.object(access,'enable') as enable:
            items=list(controls(ft.Column(a._local_sharing_controls())))
            await next(c for c in items if isinstance(c,ft.Button) and c.content=='Enable local sharing').on_click(None)
            enable.assert_not_called()

