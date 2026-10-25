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
    async def _wifi_command(self,op,**settings):
        if os.name=='nt' and not self.is_web:
            from wifi_point import point
            if op=='start':await point.start(**settings)
            else:await asyncio.to_thread(point.stop)
            return {'ssid':point.ssid,'password':point.password}
        if not getattr(self,'_wifi_control',None):
            from stc_camera_preview import StcWifiPoint
            self._wifi_pending={}
            self._wifi_control=StcWifiPoint(on_event=self._wifi_event,width=1,height=1)
            self.page.overlay.append(self._wifi_control);self.page.update()
        identity=secrets.token_hex(8);future=asyncio.get_running_loop().create_future();self._wifi_pending[identity]=future
        self._wifi_control.command=json.dumps({'id':identity,'op':op,**settings});self.page.update()
        try:return await asyncio.wait_for(future,60)
        finally:self._wifi_pending.pop(identity,None)
    def _open_wifi_point(self,_=None):
        if self.is_web or self.page.platform not in (ft.PagePlatform.WINDOWS,ft.PagePlatform.ANDROID):
            self._snack('Create the Wi-Fi link in the Windows or Android app, then join it in this device’s Wi-Fi settings.');return
        from wifi_settings import load,save,validate,qr_image
        try:current=load(android=self.page.platform==ft.PagePlatform.ANDROID)
        except Exception as error:self._snack('Could not read saved Wi-Fi settings: '+str(error));return
        name=ft.TextField(label='Wi-Fi network name',value=current['ssid'])
        password=ft.TextField(label='Wi-Fi password',value=current['password'],password=True,can_reveal_password=True)
        status=ft.Text('Settings stay saved on this device. Apply changes restarts an active link and disconnects its devices. Scan the QR with the other device’s camera/Wi-Fi scanner, then open Shared match to pair.')
        qr=ft.Image(src=qr_image(current),width=240,height=240)
        active=getattr(self,'_wifi_credentials',{})
        caption=ft.Text('Scan to join the active Wi-Fi link.' if active.get('ssid') else 'Saved network — start the link before scanning.')
        if active.get('ssid'):qr.src=qr_image(active)
        async def run(op):
            start.disabled=stop.disabled=True;name.disabled=password.disabled=True;self.page.update()
            try:
                if op=='start':
                    settings=validate(name.value or '',password.value or '',self.page.platform==ft.PagePlatform.ANDROID)
                    save(settings);name.value=settings['ssid']
                    if getattr(self,'_wifi_credentials',{}).get('ssid'):
                        await self._wifi_command('stop');self._wifi_credentials={}
                    caption.value='Saved network — starting…';qr.src=qr_image(settings)
                    data=await self._wifi_command('start',**settings)
                    self._wifi_credentials=data;qr.src=qr_image(data)
                    self._ensure_directory()
                    caption.value='Scan to join '+data['ssid']
                    status.value='Wi-Fi ready. Keep this app open. After joining the network, use Shared match on each device.'
                else:
                    await self._wifi_command('stop');self._wifi_credentials={}
                    caption.value='Wi-Fi stopped. Your saved name and password are unchanged.'
            except Exception as error:status.value=str(error)
            finally:start.disabled=stop.disabled=False;name.disabled=password.disabled=False;self.page.update()
        async def create(_):await run('start')
        async def close_link(_):await run('stop')
        start=ft.Button('Start / apply changes',on_click=create);stop=ft.TextButton('Stop Wi-Fi link',on_click=close_link)
        self.page.show_dialog(ft.AlertDialog(title=ft.Text('Device Wi-Fi link'),scrollable=True,content=ft.Container(width=460,content=ft.Column([name,password,status,ft.Row([start,stop],wrap=True),caption,qr],tight=True)),actions=[ft.TextButton('Close',on_click=lambda _:self.page.pop_dialog())]))
