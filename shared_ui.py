"""Host/join controls for LAN match logging, on Windows, Android and iOS."""
import asyncio
import copy
import flet as ft
from models import Match, StatEvent
from engine import recalculate_stats
from shared_match import SharedMatch, SharedError, local_request, local_address, addresses

class SharedMixin:
    def _live_active(self):return getattr(self,'_live_session',None) is not None
    def _live_guest(self):return self._live_active() and not self._live_session['host']
    def _live_host_only(self):
        if self._live_guest():
            self._snack('The host controls the camera, possession and match timer.')
            return False
        return True
    def _live_events(self):
        if not self.match:return []
        if not self._live_active():return self.match.events
        return [e for e in self.match.events if e.source_device==self._live_session['device']]
    def _live_capture(self):
        if not self._live_active() or getattr(self,'_live_applying',False) or not self.match:return
        session=self._live_session
        if self.match.id!=session['match_id']:return
        current={e.id:e for e in self.match.events}
        for identity,e in current.items():
            if identity not in self._live_observed:
                e.source_device=session['device']
                self._live_pending[identity]=e.to_dict()
        self._live_removed.update(self._live_observed-set(current))
        self._live_observed=set(current)
        if session['host']:
            hub=session['hub']
            hub.control(self.match,self._timer_running)
            hub.apply(hub.host_token,list(self._live_pending.values()),list(self._live_removed))
            self._live_pending.clear();self._live_removed.clear()
    def _live_adopt(self,data):
        session=self._live_session
        if not session:return
        old=self.match
        remote=Match.from_dict(data['match']);remote.local_shared_guest=not session['host']
        ids={e.id for e in remote.events}
        remote.events += [StatEvent.from_dict(e) for k,e in self._live_pending.items() if k not in ids]
        remote.events=[e for e in remote.events if e.id not in self._live_removed]
        recalculate_stats(remote)
        if remote.sport!='BASKETBALL':remote.away_score=data['match']['away_score']
        changed=(not old or [e.to_dict() for e in old.events]!=[e.to_dict() for e in remote.events] or old.period!=remote.period or old.possession_team!=remote.possession_team or old.home_score!=remote.home_score or old.away_score!=remote.away_score or getattr(self,'_live_running',None)!=data['running'])
        self._live_running=data['running'];session['members']=data.get('members',[])
        self._live_applying=True
        try:
            if old:old.__dict__.update(remote.__dict__);remote=old
            else:self.matches.append(remote);self.active_match_idx=len(self.matches)-1
            self._live_observed={e.id for e in remote.events}
            if changed:self._full_refresh()
            # Refresh the displayed clock without rebuilding the logging panels.
            if self.fullscreen_video:
                clock=getattr(self,'_bb_clock_text',None) if remote.sport=='BASKETBALL' else self.fs_clock_text
                if clock is not None:
                    clock.value=f'{remote.period} • {remote.minute}:{remote.second:02d}'
                    try:clock.update()
                    except Exception:pass
            else:
                self.scoreboard_ref.content=self._build_scoreboard(remote)
                try:self.scoreboard_ref.update()
                except Exception:pass
            if changed:self._save()
        finally:self._live_applying=False
    async def _live_loop(self):
        session=self._live_session
        while self._live_session is session:
            try:
                if session['host']:
                    session['hub'].control(self.match,self._timer_running)
                    data=session['hub'].snapshot(session['token'])
                else:
                    added=copy.deepcopy(dict(list(self._live_pending.items())[:200]));removed=set(list(self._live_removed)[:200])
                    if added or removed:
                        data=await asyncio.to_thread(local_request,session['address'],'/events',session['token'],{'added':list(added.values()),'removed':list(removed)})
                        for k,v in added.items():
                            if self._live_pending.get(k)==v:self._live_pending.pop(k)
                        self._live_removed.difference_update(removed)
                    else:data=await asyncio.to_thread(local_request,session['address'],'/state',session['token'])
                if self._live_session is not session:return
                self._live_adopt(data)
                waiting=sum(not m['approved'] for m in data.get('members',[]))
                self._live_status=(f'Sharing on local Wi-Fi — {waiting} device(s) waiting for approval' if waiting else 'Sharing on local Wi-Fi') if data['host_online'] else 'Host paused or disconnected — waiting'
            except SharedError as e:
                self._live_status=str(e)
            except Exception:
                self._live_status='Connection lost — keep this match open; your inputs will retry.'
            status=getattr(self,'_live_status_text',None)
            if status is not None:
                status.value=self._live_status
                try:status.update()
                except Exception:pass
            await asyncio.sleep(.75)
    def _start_live_host(self):
        if self._live_active():return
        if not self.match:raise SharedError('Open the match you want to host first.')
        if self._database_user.get('role')=='coach':raise SharedError('Coach accounts are read-only.')
        source=getattr(self,'camera_source',0)
        if isinstance(source,str) and source.startswith(('http://','https://','rtc://')):
            raise SharedError('Choose a camera connected to the host device before sharing. Remote camera relaying is not supported.')
        hub=SharedMatch(self.match,bool(self._database_user.get('hidden')));port=hub.start()
        self._live_session={'host':True,'hub':hub,'token':hub.host_token,'device':'host','address':f'http://127.0.0.1:{port}','addresses':addresses(port),'match_id':self.match.id,'members':[]}
        self._live_pending={};self._live_removed=set();self._live_observed={e.id for e in self.match.events}
        for e in self.match.events:e.source_device='host'
        self._live_status='Share the address and join code, then approve each device.'
        self._live_capture();self.page.run_task(self._live_loop)
        if self.camera_on:self._start_rtc_video('live-host')
        self._full_refresh()
    async def _join_live(self,address,code,name):
        if self._live_active():raise SharedError('Leave the current session first.')
        if self._database_user.get('role')=='coach':raise SharedError('Coach accounts are read-only.')
        address=local_address(address)
        result=await asyncio.to_thread(local_request,address,'/join','',{'code':code,'name':name,'hidden':bool(self._database_user.get('hidden'))})
        self._live_join={'address':address,**result}
    async def _finish_live_join(self):
        pending=self._live_join
        data=await asyncio.to_thread(local_request,pending['address'],'/state',pending['token'])
        self._timer_running=False
        if self.camera_on:self._stop_camera()
        self._live_original=[m for m in self.matches if m.id==data['match']['id']]
        self.matches=[m for m in self.matches if m.id!=data['match']['id']]
        self.active_match_idx=-1
        self._live_session={'host':False,'token':pending['token'],'device':pending['device'],'address':pending['address'],'match_id':data['match']['id']}
        self._live_pending={};self._live_removed=set();self._live_observed=set()
        self._live_adopt(data);self._set_fixture_open(self.match.id,True)
        self._live_status='Connected — the host controls the camera and timer.'
        self.page.run_task(self._live_loop);self._start_rtc_video('live-guest');self._full_refresh()
    async def _end_live(self):
        session=self._live_session
        if not session:return
        if self._live_pending or self._live_removed:
            self._snack('Inputs are still waiting to reach the host. Reconnect before leaving; export the match if the host is unavailable.')
            return
        self._timer_running=False
        if self.camera_on:self._stop_camera()
        if session['host']:
            self.match.is_live=False
            session['hub'].control(self.match,False)
            data=session['hub'].snapshot(session['token']);self._live_adopt(data)
            await asyncio.to_thread(session['hub'].stop)
        else:
            self.matches=[m for m in self.matches if m.id!=session['match_id']]+getattr(self,'_live_original',[])
            self.active_match_idx=-1
        self._live_session=None;self._save();self._full_refresh();self._snack('Shared session ended. The host keeps the combined match.')
    def _open_shared_match(self,_=None):
        if self.is_web:
            self.page.show_dialog(ft.AlertDialog(title=ft.Text('Multiple-device logging'),content=ft.Text('Use the installed Windows, Android or iOS app to host or join a local shared match. All devices must use the same Wi-Fi or hotspot; internet is optional.'),actions=[ft.TextButton('Close',on_click=lambda _:self.page.pop_dialog())]));return
        session=getattr(self,'_live_session',None)
        self._live_status_text=ft.Text(getattr(self,'_live_status','Use the same Wi-Fi or hotspot. Internet is optional.'),size=12)
        async def end(_):
            await self._end_live()
            if not self._live_active():self.page.pop_dialog()
        if session:
            rows=[self._live_status_text]
            if session['host']:
                hub=session['hub']
                rows += [ft.Text('Host address: '+(' or '.join(session['addresses']) or f'Your Wi-Fi IP address:{hub.server.server_port}'),selectable=True),ft.Text('Join code: '+hub.join_code,selectable=True),ft.Text('Only approve devices you invited.')]
                for member in list(hub.members.values()):
                    def approve(_,identity=member['id']):hub.approve(identity);self.page.pop_dialog();self._open_shared_match()
                    def remove(_,identity=member['id']):hub.approve(identity,False);self.page.pop_dialog();self._open_shared_match()
                    rows.append(ft.Row([ft.Text(member['name'],expand=True),ft.Text('Connected') if member['approved'] else ft.TextButton('Approve',on_click=approve),ft.TextButton('Remove',on_click=remove)]))
                rows.append(ft.TextButton('Refresh waiting devices',on_click=lambda _:(self.page.pop_dialog(),self._open_shared_match())))
            else:rows.append(ft.Text('You can log stats. Camera and time controls belong to the host.'))
            actions=[ft.TextButton('Close',on_click=lambda _:self.page.pop_dialog()),ft.TextButton('End sharing' if session['host'] else 'Leave session',on_click=end)]
        else:
            address=ft.TextField(label='Host IP address and port',hint_text='192.168.1.10:54321');code=ft.TextField(label='Join code');name=ft.TextField(label='Device name',value=self._database_user.get('display_name','Logger'))
            message=self._live_status_text
            async def host(_):
                try:self._start_live_host();self.page.pop_dialog();self._open_shared_match()
                except Exception as e:message.value=str(e);self.page.update()
            async def join(_):
                try:
                    await self._join_live(address.value or '',code.value or '',name.value or '')
                    message.value='Ask the host to approve this device, then press Connect.';connect.visible=True;self.page.update()
                except Exception as e:message.value=str(e);self.page.update()
            async def finish(_):
                try:await self._finish_live_join();self.page.pop_dialog()
                except Exception as e:message.value=str(e);self.page.update()
            connect=ft.Button('Connect after approval',on_click=finish,visible=False)
            rows=[message,ft.Button('Host this match',on_click=host,disabled=not bool(self.match)),ft.Divider(),address,code,name,ft.Button('Request to join',on_click=join),connect]
            actions=[ft.TextButton('Close',on_click=lambda _:self.page.pop_dialog())]
        self.page.show_dialog(ft.AlertDialog(title=ft.Text('Multiple-device logging'),content=ft.Container(width=480,content=ft.Column(rows,tight=True,scroll=ft.ScrollMode.AUTO)),actions=actions))
