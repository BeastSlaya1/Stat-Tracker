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
    def _select_local_camera(self, source):
        sending = bool(getattr(self, 'camera_mode_streaming', False))
        self.camera_source = source
        if self.camera_on:
            self._stop_camera()
        if self._rtc_available():
            self._start_rtc_video('send' if sending else 'preview')
        else:
            self._start_camera()

    def _select_camera_source(self, source):
        label = getattr(self, '_camera_labels', {}).get(source, '')
        if 'windows virtual camera' in label.lower():
            self.page.run_task(self._open_remote_camera_dialog, source, label)
        else:
            self._select_local_camera(source)

    async def _open_remote_camera_dialog(self, connected_source=None, device_name='Phone or tablet'):
        # Remote cameras now join the same match and receive a host assignment.
        if connected_source is not None:
            self._select_local_camera(connected_source)
        else:
            self._open_shared_match()

    def _detect_rtc_cameras(self):
        if self.camera_scanning:
            return
        self.camera_scanning = True
        self._camera_scan_ran_once = True
        self._camera_scan_request = getattr(self, '_camera_scan_request', 0) + 1
        self._camera_detector = camera_package.StcRtcVideo(
            role='enumerate', scan_request=self._camera_scan_request,
            width=1, height=1, on_state=self._on_detected_rtc_cameras)
        self._full_refresh()

    def _on_detected_rtc_cameras(self, event):
        if event.control is not getattr(self, '_camera_detector', None):
            return
        try:
            result = json.loads(event.data)
            if 'devices' not in result and not result.get('error'):
                return
            if result.get('error'):
                raise ValueError(result['error'])
            devices = result['devices']
            self._camera_labels = {'device:' + d['id']: d.get('label') or f'Camera {i+1}'
                                   for i, d in enumerate(devices) if d.get('id')}
            self.detected_cameras = list(self._camera_labels)
            self.camera_error = None
        except (ValueError, TypeError, KeyError) as error:
            self.camera_error = str(error)
        self.camera_scanning = False
        self._camera_detector = None
        self._full_refresh()

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
        session=getattr(self,'_live_session',None)
        if session and session.get('address')=='peer':
            if self._live_controls('video'):self.page.run_task(self._peer_camera,True)
            else:self.camera_on=True;self._full_refresh()
            return
        if session: role=self._live_video_role()
        if role != 'preview' and not session and not self._database_token:
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
            server_url=session["address"] if session else self._database_url, token=session["token"] if session else self._database_token,
            role=role, room_code=code, lens=lens, device_kind=kind,
            device_id=source[7:] if isinstance(source, str) and source.startswith('device:') else '',
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
            self._rtc_status_text.value = (state.get('status') or 'Camera is starting') if self.camera_on else 'Camera is off'
            self._rtc_stream_button.content = 'Stop streaming' if self.camera_on else 'Start streaming'

    def _toggle_shared_stream(self, _=None):
        if not self._live_stream_only() or not self._live_controls('video'):
            self._snack('The host must assign this device to stream only.');return
        if self.camera_on:
            self._stop_camera();self._full_refresh()
        else:self._start_rtc_video('live-host')

    def _build_network_camera_mode(self):
        # Stable video parents keep the stream alive while match updates arrive.
        if getattr(self, '_rtc_mode_screen', None) is None:
            self._rtc_status_text = ft.Text('Camera is off', color='#7dd3fc')
            self._rtc_stream_button = ft.Button('Start streaming',icon=ft.Icons.VIDEOCAM,on_click=self._toggle_shared_stream)
            self._rtc_mode_video = ft.Container(bgcolor='#000000',height=360,alignment=ft.Alignment.CENTER,border_radius=12)
            self._rtc_mode_actions = ft.Row(wrap=True)
            self._rtc_source_slot = ft.Container()
            self._rtc_mode_screen = ft.Container(expand=True,padding=16,content=ft.Column([
                ft.Row([ft.Text('Stream only',size=22,weight=ft.FontWeight.BOLD),
                    ft.Button('Shared match',on_click=self._open_shared_match)],wrap=True),
                ft.Text('The host assigned this device to film the match. Start streaming when ready; all connected devices receive the feed.'),
                self._rtc_mode_video,self._rtc_status_text,self._rtc_mode_actions,
                self.camera_error_text,self._rtc_source_slot,
                ft.Text('Keep this screen open. To log stats instead, ask the host to change your assignment. You can leave through Shared match.',size=12),
            ],spacing=12,scroll=ft.ScrollMode.AUTO,expand=True))
        self._rtc_mode_video.content = self._zoom_video_display_widget()
        self._rtc_mode_actions.controls = [self._rtc_stream_button,self._rotate_view_button(),self._mirror_view_button(),self._video_zoom_buttons()]
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
