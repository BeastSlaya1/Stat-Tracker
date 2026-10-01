"""One in-app camera transport and discovery list for native and browser devices."""
import asyncio
import json
import socket
import time
import flet as ft
from cloud_sync import api_request, ApiError
try:
    import stc_camera_preview as camera_package
except ImportError:
    camera_package = None


class CameraNetworkMixin:
    def _rtc_available(self):
        return camera_package is not None and hasattr(camera_package, 'StcRtcVideo')

    def _camera_device_kind(self):
        if self.is_web:
            return 'Browser'
        if getattr(self, 'is_ios', False):
            return 'iOS'
        if getattr(self, 'is_mobile', False):
            return 'Android'
        return 'Windows' if str(getattr(self.page, 'platform', '')).lower().endswith('windows') else 'Desktop'

    def _start_rtc_video(self, role, code=''):
        if role != 'preview' and not self._database_token:
            self._snack('Sign in using Database before connecting cameras.')
            self._open_database_dialog()
            return
        if not self._rtc_available():
            self._snack('Install the latest app update to connect this camera.')
            return
        if self.camera_on:
            self._stop_camera()
        kind = self._camera_device_kind()
        source = self.camera_source
        lens = source.split(':', 1)[1] if isinstance(source, str) and source.startswith('native:') else str(source) if isinstance(source, int) else 'back'
        name = (getattr(self, 'logger_name', '') or self._database_user.get('display_name') or 'Match')
        self._rtc_state = {'status': 'Starting camera…'}
        self._rtc_ctrl = camera_package.StcRtcVideo(
            server_url=self._database_url, token=self._database_token,
            role=role, room_code=code, lens=lens, device_kind=kind,
            device_label=f'{name} — {kind}'[:80], expand=True,
            on_state=self._on_rtc_state)
        self.camera_on = True
        self.camera_mode_streaming = role == 'send'
        self.camera_error = None
        self._full_refresh()

    def _on_rtc_state(self, event):
        if getattr(event, 'control', None) is not getattr(self, '_rtc_ctrl', None):
            return
        try:
            state = json.loads(event.data)
        except (ValueError, TypeError):
            return
        self._rtc_state = state
        if state.get('error'):
            self.camera_error = state['error']
            self.camera_on = False
            self.camera_mode_streaming = False
            self._rtc_ctrl = None
            self._full_refresh()  # A terminal failure removes the stopped camera once.
            return
        # Status events must never rebuild the video parent tree. Rebuilding here
        # unmounts the camera, which emits Starting again on its next mount.
        self._update_rtc_mode_status()
        self.page.update()

    def _approve_rtc_receiver(self, _=None):
        control = getattr(self, '_rtc_ctrl', None)
        if control is not None:
            control.approve_request += 1
            self.page.update()

    def _update_rtc_mode_status(self):
        state = getattr(self, '_rtc_state', {})
        if getattr(self, '_rtc_status_text', None) is not None:
            self._rtc_status_text.value = state.get('status') or 'Camera is off'
            self._rtc_pair_text.value = f"{state.get('receiver_name') or 'A staff member'} wants to receive this camera."
            self._rtc_pair_panel.visible = bool(state.get('receiver_name') and not state.get('approved'))
            self._rtc_stream_button.content = 'Stop Streaming' if self.camera_mode_streaming else 'Start Streaming'

    def _build_network_camera_mode(self):
        # Keep the entire ancestor chain of the video stable across status,
        # resize and database refreshes. Only sibling controls are rebuilt.
        if getattr(self, '_rtc_mode_screen', None) is None:
            self._rtc_status_text = ft.Text('Camera is off', color='#7dd3fc')
            self._rtc_pair_text = ft.Text('')
            self._rtc_pair_panel = ft.Container(visible=False, padding=12, bgcolor='#16344a', border_radius=10,
                content=ft.Column([self._rtc_pair_text, ft.Button('Approve receiver', on_click=self._approve_rtc_receiver)]))
            self._rtc_stream_button = ft.Button('Start Streaming', icon=ft.Icons.VIDEOCAM, on_click=self._toggle_camera_mode_stream)
            self._rtc_mode_video = ft.Container(bgcolor='#000000',height=360,alignment=ft.Alignment.CENTER,border_radius=12)
            self._rtc_mode_actions = ft.Row(wrap=True)
            self._rtc_source_slot = ft.Container()
            self._rtc_mode_screen = ft.Container(expand=True,padding=16,content=ft.Column([
                ft.Row([ft.Text('Camera Mode',size=22,weight=ft.FontWeight.BOLD),
                    ft.Button('Switch to Inputter Mode',on_click=self._switch_to_inputter_mode),
                    ft.Button('Account',icon=ft.Icons.ACCOUNT_CIRCLE,on_click=self._open_database_dialog)],wrap=True),
                ft.Text('Start streaming, then choose Scan for cameras on the receiving device. Approve the receiver here.'),
                self._rtc_mode_video,self._rtc_status_text,self._rtc_pair_panel,self._rtc_mode_actions,
                self.camera_error_text,self._rtc_source_slot,
                ft.Text('Sign in on both devices and keep Camera Mode open. The same Wi-Fi gives the most reliable connection.',size=12),
            ],spacing=12,scroll=ft.ScrollMode.AUTO,expand=True))
        self._rtc_mode_video.content = self._video_display_widget()
        self._rtc_mode_actions.controls = [self._rtc_stream_button,self._rotate_view_button(),self._mirror_view_button()]
        self._rtc_source_slot.content = self._build_camera_source_picker()
        self._update_rtc_mode_status()
        return self._rtc_mode_screen

    def _scan_lan_camera_devices(self):
        # Legacy app versions announce their MJPEG camera on the local network.
        from main import DISCOVERY_PORT, DISCOVERY_MAGIC
        found = {}
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(('0.0.0.0', DISCOVERY_PORT)); sock.settimeout(.5)
                deadline = time.monotonic() + 4
                while time.monotonic() < deadline:
                    try:
                        data, _ = sock.recvfrom(2048)
                        item = json.loads(data.decode('utf-8'))
                        url = item.get('url', '')
                        if item.get('magic') == DISCOVERY_MAGIC and url.startswith(('http://', 'https://')):
                            found[url] = {'name': item.get('name') or 'Local camera', 'url': url, 'kind': 'Local camera'}
                    except (socket.timeout, ValueError, UnicodeDecodeError):
                        continue
            except OSError:
                pass
        return list(found.values())

    async def _scan_camera_devices_async(self):
        token = self._database_token
        async def online():
            if not token:
                return [], 'Sign in using Database to discover cameras on all device types.'
            try:
                data = await api_request(self._database_url, '/camera/devices', token)
                own = getattr(self, '_rtc_state', {}).get('room_code')
                return [{'name': item['name'], 'url': 'rtc://' + item['code'], 'kind': item['kind']}
                        for item in data.get('devices', []) if item['code'] != own], ''
            except ApiError as error:
                return [], 'Staff sign-in expired. Open Database to sign in again.' if error.status == 401 else 'Online camera scan failed. Check your internet connection.'
            except Exception:
                return [], 'Online camera scan failed. Check your internet connection.'
        try:
            if self.is_web:
                (devices, message), local = await online(), []
            else:
                (devices, message), local = await asyncio.gather(online(), asyncio.to_thread(self._scan_lan_camera_devices))
            if token != self._database_token:
                return  # A sign-out must not reveal results from the previous account.
            self.discovered_cameras = devices + local
            self._camera_scan_message = message
        finally:
            self.wireless_discovering = False
            self._full_refresh()
