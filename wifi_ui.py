"""Create and stop the app's temporary Wi-Fi Direct link."""
import asyncio
import json
import os
import secrets
import flet as ft
class WifiMixin:
    async def _wifi_event(self,event):
        try:data=json.loads(event.data)
        except Exception:return
        future=getattr(self,'_wifi_pending',{}).get(data.get('id'))
        if future and not future.done():
            if data.get('error'):future.set_exception(RuntimeError(data['error']))
            else:future.set_result(data.get('result') or {})
    async def _wifi_command(self,op):
        if os.name=='nt' and not self.is_web:
            from wifi_point import point
            if op=='start':await point.start()
            else:await asyncio.to_thread(point.stop)
            return {'ssid':point.ssid,'password':point.password}
        if not getattr(self,'_wifi_control',None):
            from stc_camera_preview import StcWifiPoint
            self._wifi_pending={}
            self._wifi_control=StcWifiPoint(on_event=self._wifi_event,width=1,height=1)
            self.page.overlay.append(self._wifi_control);self.page.update()
        identity=secrets.token_hex(8);future=asyncio.get_running_loop().create_future();self._wifi_pending[identity]=future
        self._wifi_control.command=json.dumps({'id':identity,'op':op});self.page.update()
        try:return await asyncio.wait_for(future,60)
        finally:self._wifi_pending.pop(identity,None)
    def _open_wifi_point(self,_=None):
        if self.is_web or self.page.platform not in (ft.PagePlatform.WINDOWS,ft.PagePlatform.ANDROID):
            self._snack('Create the Wi-Fi link in the Windows or Android app, then join it in this device’s Wi-Fi settings.');return
        status=ft.Text('Create a local Wi-Fi link without internet. Other devices join it through their Wi-Fi settings, then connect through Shared match. Creating it may disconnect your current Wi-Fi.')
        credentials=ft.Text(selectable=True)
        current=getattr(self,'_wifi_credentials',{})
        if current.get('ssid'):credentials.value='Network: '+current['ssid']+'\nPassword: '+current['password']
        async def run(op):
            start.disabled=stop.disabled=True;status.value='Starting Wi-Fi…' if op=='start' else 'Stopping Wi-Fi…';self.page.update()
            try:
                data=await self._wifi_command(op);self._wifi_credentials=data
                credentials.value=('Network: '+data['ssid']+'\nPassword: '+data['password']) if data.get('ssid') else ''
                status.value='Wi-Fi link ready. Keep this app open. Join this network on the other devices, then host and scan for your match. On Windows, enable local sharing for the new network.' if op=='start' else 'Wi-Fi link stopped.'
            except Exception as error:status.value=str(error)
            finally:start.disabled=False;stop.disabled=False;self.page.update()
        async def create(_):await run('start')
        async def close_link(_):await run('stop')
        start=ft.Button('Create Wi-Fi link',on_click=create);stop=ft.TextButton('Stop Wi-Fi link',on_click=close_link)
        self.page.show_dialog(ft.AlertDialog(title=ft.Text('Device Wi-Fi link'),content=ft.Container(width=460,content=ft.Column([status,credentials,ft.Row([start,stop],wrap=True)],tight=True)),actions=[ft.TextButton('Close',on_click=lambda _:self.page.pop_dialog())]))
