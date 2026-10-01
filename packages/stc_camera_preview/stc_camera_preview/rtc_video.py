from typing import Optional
import flet as ft


@ft.control('StcRtcVideo')
class StcRtcVideo(ft.LayoutControl):
    """Embedded cross-platform preview, camera sender, or camera receiver."""
    server_url: str = ''
    token: str = ''
    role: str = 'preview'
    room_code: str = ''
    lens: str = 'back'
    device_label: str = 'Match camera'
    device_kind: str = 'Browser'
    approve_request: int = 0
    on_state: Optional[ft.EventHandler[str]] = None
