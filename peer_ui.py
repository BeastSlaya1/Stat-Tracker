"""Offline browser/native pairing over WebRTC data channels; no signalling server."""
import asyncio
import base64
import json
import secrets
import struct
import zlib
import flet as ft
import qrcode
from models import Match
from shared_match import SharedMatch, SharedError, local_request


def _connection_qr(code):
    """Render an offline pairing code as a PNG data URL without Pillow."""
    qr=qrcode.QRCode(border=4,error_correction=qrcode.constants.ERROR_CORRECT_L,box_size=5)
    qr.add_data(code);qr.make(fit=True)
    matrix=qr.get_matrix();scale=5;size=len(matrix)*scale
    raw=b''.join((b'\x00'+b''.join((b'\x00' if cell else b'\xff')*scale for cell in row))*scale for row in matrix)
    def chunk(kind,body):return struct.pack('!I',len(body))+kind+body+struct.pack('!I',zlib.crc32(kind+body)&0xffffffff)
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',size,size,8,0,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')
    return 'data:image/png;base64,'+base64.b64encode(png).decode('ascii')

class PeerMixin:
    def _peer_active(self):
        return bool(getattr(self,'_peer_link',None))

    def _ensure_peer_link(self):
        if self._peer_active():return
        from stc_camera_preview import StcPeerLink, StcPeerView
        self._peer_id=secrets.token_hex(16);self._peer_futures={};self._peer_requests={};self._peer_members={}
        self._peer_lock=asyncio.Lock();self._peer_source=None;self._peer_host=False
        self._peer_link=StcPeerLink(bridge_id=self._peer_id,on_event=self._on_peer_event,width=1,height=1)
        self._peer_view=StcPeerView(bridge_id=self._peer_id,expand=True)
        self.page.overlay.append(self._peer_link);self.page.update()

    async def _peer_command(self,op,**values):
        self._ensure_peer_link()
        async with self._peer_lock:
            identity=secrets.token_hex(12);future=asyncio.get_running_loop().create_future()
            self._peer_futures[identity]=future
            self._peer_link.command=json.dumps({'id':identity,'op':op,**values})
            self.page.update()
            try:return await asyncio.wait_for(future,30)
            finally:self._peer_futures.pop(identity,None)

    async def _peer_rpc(self,path,body=None):
        identity=secrets.token_hex(12);future=asyncio.get_running_loop().create_future()
        self._peer_requests[identity]=future
        try:
            await self._peer_command('send',peer=self._peer_remote,payload=json.dumps({'request':identity,'path':path,'body':body}))
            return await asyncio.wait_for(future,12)
        finally:self._peer_requests.pop(identity,None)

    async def _shared_request(self,address,path,token='',body=None):
        if address=='peer':return await self._peer_rpc(path,body)
        return await asyncio.to_thread(local_request,address,path,token,body)

    async def _on_peer_event(self,event):
        if event.control is not getattr(self,'_peer_link',None):return
        try:data=json.loads(event.data)
        except (ValueError,TypeError):return
        if data.get('kind')=='reply':
            future=self._peer_futures.get(data.get('id'))
            if future and not future.done():
                if data.get('error'):future.set_exception(SharedError(data['error']))
                else:future.set_result(data.get('result',{}))
            return
        if data.get('kind')=='open':
            if not self._peer_host:
                self._peer_remote=data['peer'];self.page.run_task(self._peer_complete_join)
            return
        if data.get('kind')=='connection':
            if any(word in data.get('state','').lower() for word in ('failed','disconnected','closed')):
                self._peer_message('A device disconnected. Keep the match open; reconnect using new codes if it does not recover.')
            return
        if data.get('kind')!='message':return
        try:message=json.loads(data['payload'])
        except (ValueError,TypeError,KeyError):return
        if 'response' in message:
            future=self._peer_requests.get(message['response'])
            if future and not future.done():
                if message.get('error'):future.set_exception(SharedError(message['error'],message.get('status',400)))
                else:future.set_result(message.get('result',{}))
            return
        if not self._peer_host or not self._live_active():return
        reply={'response':message.get('request')}
        try:reply['result']=self._peer_dispatch(data['peer'],message.get('path'),message.get('body'))
        except SharedError as error:reply.update(error=str(error),status=error.status)
        except Exception:reply.update(error='Invalid shared-match request.',status=400)
        try:await self._peer_command('send',peer=data['peer'],payload=json.dumps(reply))
        except SharedError:pass

    def _peer_dispatch(self,peer,path,body):
        hub=self._live_session['hub'];body=body or {}
        if path=='/join':
            if peer not in self._peer_members or self._peer_members[peer]['token'] not in hub.members:
                self._peer_members[peer]=hub.join(hub.join_code,body.get('name'),body.get('hidden'))
            return self._peer_members[peer]
        member=self._peer_members.get(peer)
        if not member:raise SharedError('Request approval first.',403)
        token=member['token']
        if path=='/state':return hub.snapshot(token)
        if path=='/events':return hub.apply(token,body.get('added',[]),body.get('removed',[]))
        if path=='/control':return hub.delegated_control(token,body)
        if path=='/cancel-join':return hub.cancel_join(token)
        raise SharedError('Unknown shared-match action.',404)

    async def _peer_complete_join(self):
        try:
            result=await self._peer_rpc('/join',{'name':self._database_user.get('display_name') or 'Device','hidden':bool(self._database_user.get('hidden'))})
            self._live_join={'address':'peer',**result}
            self._peer_message('Connected. Waiting for host approval…')
            for _ in range(120):
                if not self._peer_active() or self._live_active():return
                try:
                    await self._finish_live_join()
                    self._peer_message('Approved. Close this panel to use the match.');return
                except SharedError as error:
                    if error.status!=425:raise
                await asyncio.sleep(1)
            raise SharedError('Approval timed out. Ask the host for a new connection code.')
        except Exception as error:self._peer_message(str(error))

    def _peer_message(self,message):
        label=getattr(self,'_peer_status',None)
        if label is not None:label.value=message;self.page.update()

    async def _peer_start_host(self):
        if self._live_active():return
        if not self.match:raise SharedError('Open or create a match first.')
        if self._database_user.get('role')=='coach':raise SharedError('Coach accounts are read-only.')
        # Release the standalone preview before the shared video owns the camera.
        if self.camera_on:self._stop_camera()
        self._ensure_peer_link();self._peer_host=True
        hub=SharedMatch(self.match,bool(self._database_user.get('hidden')))
        self._live_session={'host':True,'hub':hub,'token':hub.host_token,'device':'host','address':'peer','addresses':[], 'match_id':self.match.id,'members':[],'controllers':dict(hub.controllers),'control_generation':0}
        self._live_pending={};self._live_removed=set();self._live_observed={e.id for e in self.match.events}
        for event in self.match.events:event.source_device='host'
        self._live_approval_seen=set();self._live_approval_dialog=None;self._live_status='Sharing through offline connection codes'
        self._live_capture();self.page.run_task(self._live_loop);self._full_refresh()
        await self._peer_sync_source()
        await self._directory_publish()

    async def _peer_sync_source(self):
        session=getattr(self,'_live_session',None)
        if not session or session.get('address')!='peer':return
        video=session.get('controllers',{}).get('video','host')
        if session['host']:
            video=session['hub'].controllers['video']
            source='self' if video=='host' else next((p for p,m in self._peer_members.items() if m['device']==video),'')
            # Pending devices must not receive video until approved.
            allowed={m['id'] for m in session['hub'].members.values() if m['approved']}
            viewers=[p for p,m in self._peer_members.items() if m['device'] in allowed]
        else:
            source='self' if video==session['device'] else self._peer_remote;viewers=[]
        key=(source,tuple(sorted(viewers)))
        if key==self._peer_source:return
        await self._peer_command('source',source=source,viewers=viewers)
        self._peer_source=key

    async def _peer_camera(self,enabled):
        if not self._peer_active() or not self._live_active() or self._live_session.get('address')!='peer':return
        try:
            await self._peer_sync_source()
            source=getattr(self,'camera_source','native:back')
            await self._peer_command('camera',enabled=enabled,lens=source.split(':',1)[1] if isinstance(source,str) and source.startswith('native:') else 'back',device_id=source[7:] if isinstance(source,str) and source.startswith('device:') else '')
            self.camera_on=enabled or (self._live_active() and not self._live_controls('video'));self.camera_error=None
            self._rtc_state={'status':'Streaming on the local network' if enabled else 'Camera is off'}
        except Exception as error:self.camera_error=str(error);self.camera_on=False
        self._full_refresh()

    async def _peer_close(self):
        if not self._peer_active():return
        await self._directory_leave()
        try:await self._peer_command('close')
        finally:
            self.page.overlay.remove(self._peer_link);self._peer_link=None;self._peer_view=None;self._peer_source=None;self._pairing_codes={}

    def _open_peer_pairing(self,_=None):
        if self._database_user.get('role')=='coach':self._snack('Coach accounts are read-only.');return
        if self._live_active() and self._live_session.get('address')!='peer':self._snack('End the current sharing session before creating a new one.');return
        self._ensure_peer_link()
        self._peer_status=ft.Text('Use the same Wi-Fi, Feem, Zapya or hotspot. No internet is used for pairing or the shared match.')
        feem_help=ft.Container(
            content=ft.Column([
                ft.Text('For offline sharing, connect each device to the same Wi-Fi or Feem hotspot. Feem is optional; it can help create a shared local network.'),
                ft.TextButton('Get Feem',url='https://feem.io/en',icon=ft.Icons.OPEN_IN_NEW),
            ],tight=True,spacing=4),
            bgcolor='#142238',border=ft.Border.all(1,'#27364c'),border_radius=10,padding=12)
        codes=getattr(self,'_pairing_codes',{});self._pairing_codes=codes
        output=ft.TextField(label='Your connection code',value=codes.get('output',''),read_only=True,multiline=True,min_lines=2,max_lines=3,expand=True)
        incoming=ft.TextField(label='Paste the other device’s code',value=codes.get('incoming',''),multiline=True,min_lines=2,max_lines=3,on_change=lambda e:codes.update(incoming=e.control.value))
        def show_qr(_=None):
            if not output.value:self._peer_message('Create an invitation or reply first.');return
            try:image=_connection_qr(output.value)
            except Exception:self._peer_message('This connection code is too large for a QR code. Copy the code instead.');return
            self.page.show_dialog(ft.AlertDialog(title=ft.Text('Scan connection code'),content=ft.Column([
                ft.Image(src=image,width=300,height=300,fit=ft.ImageFit.CONTAIN),
                ft.Text('Scan with the other device’s camera, copy the decoded text, then paste it into the connection-code box.',size=12),
            ],tight=True,horizontal_alignment=ft.CrossAxisAlignment.CENTER),actions=[ft.TextButton('Close',on_click=lambda _:self.page.pop_dialog())]))
        async def copy_code(_):
            if not output.value:self._peer_message('Create an invitation or reply first.');return
            try:
                if not getattr(self,'_pairing_clipboard',None):self._pairing_clipboard=ft.Clipboard()
                await self._pairing_clipboard.set(output.value)
                self._peer_message('Connection code copied.')
            except Exception:self._peer_message('Clipboard unavailable. Select and copy the whole code manually.')
        found=ft.Column(spacing=6)
        helper=ft.TextField(label='Local directory address (only if not found)',hint_text='192.168.137.1:8767',value=getattr(self,'_directory_hint',''),on_change=lambda e:setattr(self,'_directory_hint',e.control.value))
        async def scan(_=None):
            scan_button.disabled=True;found.controls=[];self._peer_message('Looking for shared matches on this network…');self.page.update()
            try:
                from directory_client import find,request
                bases=await find(self.is_web,helper.value or '')
                for base in bases:
                    result=await request(self.is_web,base,'/list')
                    for row in result['matches']:
                        if row['id']==(getattr(self,'_directory_registration',None) or {}).get('id'):continue
                        async def connect(_,address=base,identity=row['id']):
                            self._peer_message('Connecting to the host…')
                            try:await self._directory_join(address,identity)
                            except Exception as error:self._peer_message(str(error))
                        found.controls.append(ft.Row([ft.Text(row['name'],expand=True),ft.Button('Connect',on_click=connect)]))
                self._peer_message('Choose a match; its host approves access.' if found.controls else 'No directory-hosted matches found. Allow local-network access and scan again. Browser-hosted matches can always be joined with an invitation/reply code; a browser tab cannot advertise itself as a Wi-Fi discovery server.')
            except Exception as error:self._peer_message(str(error))
            finally:scan_button.disabled=False;self.page.update()
        scan_button=ft.Button('Find shared matches',on_click=scan,disabled=self._live_active(),visible=not bool(self._database_user.get('hidden')))
        local_info=[]
        if not self.is_web:
            try:
                from shared_match import addresses
                directory=self._ensure_directory()
                local_info=[ft.Text('Local directory: '+(' or '.join(addresses(directory.server.server_port)) or 'Connect to Wi-Fi first'),selectable=True,size=12)]
            except Exception as error:local_info=[ft.Text('Local directory unavailable: '+str(error),size=12)]
        busy=False
        async def action(op):
            nonlocal busy
            if busy:return
            busy=True;self._peer_message('Preparing connection…')
            try:
                if op=='offer':
                    await self._peer_start_host()
                    result=await self._peer_command('offer',peer=secrets.token_hex(16));output.value=result['code']
                    self._peer_message('Send this invitation to one device. Paste its reply here, then press Accept reply.')
                elif op=='answer':
                    if self._live_active():raise SharedError('Leave the current match before joining another.')
                    result=await self._peer_command('answer',code=(incoming.value or '').strip());self._peer_remote=result['peer'];output.value=result['code']
                    self._peer_message('Send this reply back to the host. Keep this page open while the host accepts and approves you.')
                else:
                    await self._peer_command('accept',code=(incoming.value or '').strip())
                    self._peer_message('Connecting. Approve the device when its request appears.')
                codes.update(output=output.value,incoming=incoming.value)
                self.page.update()
            except Exception as error:self._peer_message(str(error))
            finally:busy=False
        async def host(_):
            try:
                await self._peer_start_host();self.page.pop_dialog();self._open_shared_match()
            except Exception as error:self._peer_message(str(error))
        async def offer(_):await action('offer')
        async def answer(_):await action('answer')
        async def accept(_):await action('accept')
        async def offline(_):await self.page.launch_url('/offline.html')
        def controls(_):self.page.pop_dialog();self._open_shared_match()
        session_rows,session_actions=self._open_local_shared_match(embedded=True) if self._live_active() else ([],[])
        self.page.show_dialog(ft.AlertDialog(title=ft.Text('Shared match'),scrollable=True,
            content=ft.Container(width=560,content=ft.Column([
                ft.Text(('Before going offline, save the website for offline use and sign in. Keep this tab open. ' if self.is_web else 'Keep this app open. ')+'Host a match or choose one found on this network. Connection codes are available below if needed.'),
                feem_help,
                *([ft.TextButton('Save website for offline use',on_click=offline)] if self.is_web else []),
                *([ft.Button('Device Wi-Fi link',on_click=self._open_wifi_point)] if not self.is_web else []),
                *local_info,*self._local_sharing_controls(),
                scan_button,found,ft.ExpansionTile(title=ft.Text('Browser / network connection'),controls=[helper,ft.Text('The browser scan checks common hotspot addresses for a Stat Tracker local directory. Allow the browser’s local-network prompt if shown. A normal browser tab cannot run that directory service itself, so use invitation/reply codes to join a browser-hosted match.',size=12)]),
                self._peer_status,ft.Button('Host this match',on_click=host,disabled=not bool(self.match) or self._live_active()),
                ft.ExpansionTile(title=ft.Text('Connection codes (fallback)'),controls=[ft.Button('Create invitation',on_click=offer,disabled=not bool(self.match) or (self._live_active() and not self._live_session['host'])),
                ft.Row([output,ft.Column([ft.Button('Copy',icon=ft.Icons.CONTENT_COPY,tooltip='Copy connection code',on_click=copy_code),ft.Button('Show QR',icon=ft.Icons.QR_CODE,tooltip='Show a QR code for this connection code',on_click=show_qr)],spacing=6)]),incoming,ft.Row([ft.Button('Join: create reply',on_click=answer),ft.Button('Host: accept reply',on_click=accept)],wrap=True),
                ft.Text('Copy codes through a local messenger/file transfer or shared clipboard. Connection codes grant a pairing opportunity; only share them with the intended device. The host still approves access.',size=12)]),
                *([ft.Divider(),ft.Text('Devices and controls'),*session_rows] if session_rows else [])
            ],tight=True)),actions=[*session_actions] if session_actions else [ft.TextButton('Close',on_click=lambda _:self.page.pop_dialog())]))
        if not self._live_active() and not self._database_user.get('hidden'):self.page.run_task(scan)
