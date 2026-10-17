"""Offline browser/native pairing over WebRTC data channels; no signalling server."""
import asyncio
import json
import secrets
import flet as ft
from models import Match
from shared_match import SharedMatch, SharedError, local_request

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
            result=await self._peer_rpc('/join',{'name':self._database_user.get('display_name') or 'Browser','hidden':bool(self._database_user.get('hidden'))})
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
        try:await self._peer_command('close')
        finally:
            self.page.overlay.remove(self._peer_link);self._peer_link=None;self._peer_view=None;self._peer_source=None

    def _open_peer_pairing(self,_=None):
        if self._database_user.get('role')=='coach':self._snack('Coach accounts are read-only.');return
        if self._live_active() and self._live_session.get('address')!='peer':self._snack('Leave local sharing before using browser connection codes.');return
        self._ensure_peer_link()
        self._peer_status=ft.Text('Use the same Wi-Fi, Feem, Zapya or hotspot. No internet is used for pairing or the shared match.')
        output=ft.TextField(label='Your connection code — copy the whole value',read_only=True,multiline=True,min_lines=2,max_lines=3)
        incoming=ft.TextField(label='Paste the other device’s code',multiline=True,min_lines=2,max_lines=3)
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
                self.page.update()
            except Exception as error:self._peer_message(str(error))
            finally:busy=False
        async def offer(_):await action('offer')
        async def answer(_):await action('answer')
        async def accept(_):await action('accept')
        async def offline(_):await self.page.launch_url('/offline.html')
        def controls(_):self.page.pop_dialog();self._open_shared_match()
        self.page.show_dialog(ft.AlertDialog(title=ft.Text('Offline browser connection codes'),scrollable=True,
            content=ft.Container(width=560,content=ft.Column([
                ft.Text('Before going offline, save the website for offline use and sign in. Keep all browser tabs open during the match. Create a separate invitation for each joining device.'),
                *([ft.TextButton('Save website for offline use',on_click=offline)] if self.is_web else []),
                self._peer_status,ft.Button('Host: create invitation',on_click=offer,disabled=not bool(self.match) or (self._live_active() and not self._live_session['host'])),
                output,incoming,ft.Row([ft.Button('Join: create reply',on_click=answer),ft.Button('Host: accept reply',on_click=accept)],wrap=True),
                ft.Text('Copy codes through a local messenger/file transfer or shared clipboard. Connection codes grant a pairing opportunity; only share them with the intended device. The host still approves access.',size=12)
            ],tight=True)),actions=[ft.TextButton('Match controls',on_click=controls),ft.TextButton('Close',on_click=lambda _:self.page.pop_dialog())]))
