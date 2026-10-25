from typing import Optional
import flet as ft

@ft.control('StcPeerLink')
class StcPeerLink(ft.LayoutControl):
    bridge_id: str = ''
    command: str = ''
    on_event: Optional[ft.EventHandler[str]] = None

@ft.control('StcPeerView')
class StcPeerView(ft.LayoutControl):
    bridge_id: str = ''

@ft.control('StcWifiPoint')
class StcWifiPoint(ft.LayoutControl):
    command: str = ''
    on_event: Optional[ft.EventHandler[str]] = None
