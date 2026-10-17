"""Opt-in, temporary Windows network access for the current app process."""
import atexit
import ctypes
from ctypes import wintypes as w
import os
from pathlib import Path
import subprocess
import threading
import uuid


class SharingAccess:
    def __init__(self):
        self._handles = []
        self.address = None
        self.port = None
        self._lock = threading.Lock()
        if os.name == 'nt':
            self._kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            for name, args, result in (
                ('CreateEventW', [ctypes.c_void_p, w.BOOL, w.BOOL, w.LPCWSTR], w.HANDLE),
                ('SetEvent', [w.HANDLE], w.BOOL),
                ('CloseHandle', [w.HANDLE], w.BOOL),
                ('WaitForSingleObject', [w.HANDLE, w.DWORD], w.DWORD),
                ('WaitForMultipleObjects', [w.DWORD, ctypes.POINTER(w.HANDLE), w.BOOL, w.DWORD], w.DWORD),
                ('GetExitCodeProcess', [w.HANDLE, ctypes.POINTER(w.DWORD)], w.BOOL),
            ):
                fn = getattr(self._kernel, name); fn.argtypes = args; fn.restype = result
        atexit.register(self.stop)

    @property
    def active(self):
        return bool(len(self._handles) == 3 and self._kernel.WaitForSingleObject(self._handles[2], 0) == 258)

    def _stop(self):
        if self._handles:
            self._kernel.SetEvent(self._handles[0])
            if len(self._handles) == 3:
                self._kernel.WaitForSingleObject(self._handles[2], 3000)
            for handle in self._handles:
                self._kernel.CloseHandle(handle)
        self._handles = []; self.address = self.port = None

    def stop(self):
        with self._lock:
            self._stop()

    def enable(self, address, port=8767):
        if os.name != 'nt':
            raise RuntimeError('This setup is only needed on Windows.')
        from local_network import local_ipv4_addresses
        if address not in local_ipv4_addresses() or not 1024 <= int(port) <= 65535:
            raise RuntimeError('The selected network is no longer connected. Reopen this screen.')
        helper = Path(__file__).resolve().parent / 'assets' / 'local-sharing.exe'
        if not helper.is_file():
            raise RuntimeError('The local-sharing helper is missing. Reinstall the latest Windows release.')
        with self._lock:
            self._stop()
            token = uuid.uuid4().hex
            stop_name, ready_name = (f'Local\\StatTracker-{token}-{kind}' for kind in ('stop', 'ready'))
            try:
                for name in (stop_name, ready_name):
                    handle = self._kernel.CreateEventW(None, True, False, name)
                    if not handle:
                        raise ctypes.WinError(ctypes.get_last_error())
                    self._handles.append(handle)
                class ShellInfo(ctypes.Structure):
                    _fields_ = [('cbSize', w.DWORD), ('fMask', w.ULONG), ('hwnd', w.HWND),
                        ('lpVerb', w.LPCWSTR), ('lpFile', w.LPCWSTR), ('lpParameters', w.LPCWSTR),
                        ('lpDirectory', w.LPCWSTR), ('nShow', ctypes.c_int), ('hInstApp', w.HINSTANCE),
                        ('lpIDList', ctypes.c_void_p), ('lpClass', w.LPCWSTR), ('hkeyClass', w.HKEY),
                        ('dwHotKey', w.DWORD), ('hIcon', w.HANDLE), ('hProcess', w.HANDLE)]
                info = ShellInfo(); info.cbSize = ctypes.sizeof(info)
                info.fMask = 0x40 | 0x100 | 0x400  # process handle, no async, no error UI
                info.lpVerb = 'runas'; info.lpFile = str(helper); info.nShow = 0
                info.lpParameters = subprocess.list2cmdline([str(os.getpid()), address, stop_name, ready_name, str(port)])
                shell = ctypes.WinDLL('shell32', use_last_error=True).ShellExecuteExW
                shell.argtypes = [ctypes.POINTER(ShellInfo)]; shell.restype = w.BOOL
                if not shell(ctypes.byref(info)):
                    error = ctypes.get_last_error()
                    if error == 1223:
                        raise RuntimeError('Windows approval was cancelled. Local access was not enabled.')
                    raise ctypes.WinError(error)
                self._handles.append(info.hProcess)
                # Put process first so a helper that exits immediately never appears enabled.
                wait = (w.HANDLE * 2)(info.hProcess, self._handles[1])
                result = self._kernel.WaitForMultipleObjects(2, wait, False, 15000)
                if result != 1:
                    code = w.DWORD()
                    self._kernel.GetExitCodeProcess(info.hProcess, ctypes.byref(code))
                    raise RuntimeError('Windows could not enable local sharing (code '+str(code.value)+'). Check the selected network and administrator approval.')
                self.address = address; self.port = int(port)
            except BaseException:
                self._stop()
                raise


access = SharingAccess()
