"""Host/join controls for LAN match logging, on Windows, Android and iOS."""
import asyncio
import copy
import flet as ft
from models import Match, StatEvent
from engine import recalculate_stats
from shared_match import SharedMatch, SharedError, local_request, local_address, addresses

class SharedMixin:
    def _local_sharing_controls(self):
        import os
        if os.name!='nt' or self.is_web:return []
        from local_network import local_network_choices
        from windows_sharing import access
        networks=local_network_choices()
        selector=ft.Dropdown(label='Network for local sharing',options=[ft.dropdown.Option(ip,label) for ip,label in networks],
            value=access.address if access.address in dict(networks) else (networks[0][0] if len(networks)==1 else None))
        status=ft.Text('Local access enabled on '+access.address if access.active else 'Choose your USB, Ethernet or Wi-Fi network. Windows will ask for administrator approval.',size=12)
        async def enable(_):
            if not selector.value:
                status.value='Select the network connected to your other devices first.';self.page.update();return
            button.disabled=disable.disabled=selector.disabled=True
            status.value='Waiting for Windows approval…';self.page.update()
            try:
                session=getattr(self,'_live_session',None)
                port=session['hub'].server.server_port if session and session['host'] else 8767
                await asyncio.to_thread(access.enable,selector.value,port)
                status.value='Local access enabled. Other devices on this network can connect while this app is open.'
            except Exception as error:status.value=str(error)
            finally:
                button.disabled=selector.disabled=False;disable.disabled=not access.active;self.page.update()
        async def stop(_):
            await asyncio.to_thread(access.stop)
            status.value='Temporary local access stopped.';disable.disabled=True;self.page.update()
        button=ft.Button('Enable local sharing',on_click=enable,disabled=not bool(networks))
        disable=ft.TextButton('Disable local access',on_click=stop,disabled=not access.active)
        return [ft.Divider(),selector,status,ft.Text('Access ends when you end sharing or close the app. Approve each joining device separately.',size=12),ft.Row([button,disable],wrap=True)]

    def _open_cable_help(self, _=None):
        from local_network import CABLE_HELP
        self.page.show_dialog(ft.AlertDialog(title=ft.Text('Cable / offline sharing'),
            content=ft.Container(width=520,height=420,content=ft.Column([
                ft.Column([ft.Text(title,weight=ft.FontWeight.BOLD),ft.Text(body)]) for title,body in CABLE_HELP
            ],scroll=ft.ScrollMode.AUTO,spacing=16)),
            actions=[ft.TextButton('Close',on_click=lambda _:self.page.pop_dialog())]))

    def _live_active(self):return getattr(self,'_live_session',None) is not None
    def _live_guest(self):return self._live_active() and not self._live_session['host']
    def _live_host_only(self):
        if self._live_guest():
            self._snack('The host controls the camera, possession and match timer.')
            return False
        return True
    def _live_allows_key(self,key):
        if not self._live_guest():return True
        from shared_permissions import assignment
        return key in self._live_session.get('permissions',assignment(self.match.sport))['stats']
    def _live_require_key(self,key):
        if self._live_allows_key(key):return True
        self._snack('The host has not assigned this stat to your device.');return False
    def _live_can_modify_event(self,event):
        if not self._live_guest():return True
        from shared_permissions import event_key
        return self._live_require_key(event_key(self.match.sport,event,self.match.events))
    def _live_section_allowed(self,section):
        if not self._live_guest():return True
        from shared_permissions import catalog
        return any(self._live_allows_key(key) for key in catalog(self.match.sport).get(section.replace('Defence','Defense'),{}))
    def _filter_live_controls(self):
        if not self._live_guest():return
        from shared_permissions import catalog
        def normalize(text):return ''.join(c for c in text.lower() if c.isalnum())
        labels={normalize(label.split(' (')[0]):key for group in catalog(self.match.sport).values() for key,label in group.items()}
        labels.update({'offrebound':'OREB','defrebound':'DREB','looseball':'LOOSE','technical':'TF','unsportsmanlike':'UF','disqualifying':'DF',
            'longpass':'LONG_PASS','gkkick':'GK_KICK','gkthrow':'GK_THROW','offsiderec':'OFFSIDE','offsidegvn':'OFFSIDE_GIVEN','offgiven':'OFFSIDE_GIVEN',
            'yellow':'YELLOW_CARD','red':'RED_CARD','goal':'GOAL','goalsgiven':'GOALS_GIVEN','layupagainstal':'LAYUP_AGAINST','shotagainstas':'SHOT_AGAINST'})
        category=getattr(self,'_bb_category','Attack') if self.match.sport=='BASKETBALL' else self.action_category
        if self.match.sport=='BASKETBALL':
            labels['penalty']='PENALTY_ATTACK' if category=='Attack' else 'PENALTY_OPPOSITION'
            labels['conversion']='SHOT' if category=='Attack' else 'SHOT_AGAINST'
        else:
            own=self._live_events();labels['conversion']=own[-1].event_type if own else 'SHOT'
            labels['conversiongiven']='GOALS_GIVEN'
        def visit(control):
            data=getattr(control,'data',None)
            if isinstance(data,dict) and 'stat_label' in data:
                control.visible=self._live_allows_key(labels.get(normalize(data['stat_label']),''))
            content=getattr(control,'content',None)
            if isinstance(content,ft.Control):visit(content)
            for child in getattr(control,'controls',[]) or []:visit(child)
        for control in self.page.controls:visit(control)

    def _live_assignment_controls(self,sport,initial=None):
        from shared_permissions import assignment,catalog,SECTIONS
        selected=initial or assignment(sport)
        checked=set(selected['stats']);listing=ft.Column(spacing=4)
        def change_stat(key,value):
            if value:checked.add(key)
            else:checked.discard(key)
        def render():
            listing.controls=[]
            for section,stats in catalog(sport).items():
                if selector.value!='All' and selector.value!=section:continue
                listing.controls.append(ft.Text(section,weight=ft.FontWeight.BOLD))
                listing.controls += [ft.Checkbox(label=label,value=key in checked,on_change=lambda e,k=key:change_stat(k,e.control.value)) for key,label in stats.items()]
        def section_changed(_):
            checked.clear();checked.update(assignment(sport,selector.value)['stats']);render();self.page.update()
        selector=ft.Dropdown(label='Controls this section',value=selected['section'],options=[ft.dropdown.Option(section) for section in SECTIONS],on_select=section_changed)
        render()
        return ft.Column([selector,ft.ExpansionTile(title=ft.Text('Choose individual stats'),controls=[ft.Text('Conversions and incompletes follow their parent stat. Camera and timer stay with the host.',size=12),listing])],tight=True),lambda:assignment(sport,selector.value,sorted(checked))
    def _edit_live_assignment(self,session,member):
        panel,selection=self._live_assignment_controls(session['hub'].match.sport,member.get('permissions'))
        def save(_):
            if self._live_session is session:session['hub'].approve(member['id'],True,selection())
            self.page.pop_dialog()
        self.page.show_dialog(ft.AlertDialog(title=ft.Text('Assign controls: '+member['name']),scrollable=True,
            content=ft.Container(content=panel,width=460),actions=[ft.TextButton('Cancel',on_click=lambda _:self.page.pop_dialog()),ft.Button('Save controls',on_click=save)]))

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
        permissions_changed=data.get('permissions')!=session.get('permissions')
        if 'permissions' in data:session['permissions']=data['permissions']
        remote=Match.from_dict(data['match']);remote.local_shared_guest=not session['host']
        ids={e.id for e in remote.events}
        remote.events += [StatEvent.from_dict(e) for k,e in self._live_pending.items() if k not in ids]
        remote.events=[e for e in remote.events if e.id not in self._live_removed]
        recalculate_stats(remote)
        if remote.sport!='BASKETBALL':remote.away_score=data['match']['away_score']
        changed=(permissions_changed or not old or [e.to_dict() for e in old.events]!=[e.to_dict() for e in remote.events] or old.period!=remote.period or old.possession_team!=remote.possession_team or old.home_score!=remote.home_score or old.away_score!=remote.away_score or getattr(self,'_live_running',None)!=data['running'])
        self._live_running=data['running'];session['members']=data.get('members',[])
        self._live_applying=True
        try:
            if old:old.__dict__.update(remote.__dict__);remote=old
            else:self.matches.append(remote);self.active_match_idx=len(self.matches)-1
            self._live_observed={e.id for e in remote.events}
            if self._live_guest():
                for attr in ('_bb_category','action_category'):
                    current=getattr(self,attr,'Attack')
                    if not self._live_section_allowed(current):
                        setattr(self,attr,next((c for c in ('Attack','Defence','Cards','Opposition') if self._live_section_allowed(c)),'Attack'))
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
                if session['host']:self._show_live_approval(session,data.get('members',[]))
                waiting=sum(not m['approved'] for m in data.get('members',[]))
                self._live_status=(f'Sharing on local network — {waiting} device(s) waiting for approval' if waiting else 'Sharing on local network') if data['host_online'] else 'Host paused or disconnected — waiting'
            except SharedError as e:
                self._live_status=str(e)
                if not session['host'] and e.status==403:
                    try:
                        data=await asyncio.to_thread(local_request,session['address'],'/state',session['token'])
                        if self._live_session is session:self._live_adopt(data)
                        self._live_status='Some inputs need host permission. Ask the host to restore those stats; queued inputs are retained.'
                    except Exception:pass
            except Exception:
                self._live_status='Connection lost — keep this match open; your inputs will retry.'
            status=getattr(self,'_live_status_text',None)
            if status is not None:
                status.value=self._live_status
                try:status.update()
                except Exception:pass
            await asyncio.sleep(.75)
    def _show_live_approval(self,session,members):
        if getattr(self,'_live_approval_dialog',None):return
        seen=getattr(self,'_live_approval_seen',set())
        pending=next((m for m in members if not m['approved'] and m['id'] not in seen),None)
        if pending is None:return
        seen.add(pending['id']);self._live_approval_seen=seen
        panel,selection=self._live_assignment_controls(session['hub'].match.sport,pending.get('permissions'))
        def dismissed(_=None):self._live_approval_dialog=None
        def respond(allowed):
            if self._live_session is session:session['hub'].approve(pending['id'],allowed,selection() if allowed else None)
            self.page.pop_dialog();dismissed()
            self._snack('Device approved — stats and video connect automatically.' if allowed else 'Connection request declined.')
        dialog=ft.AlertDialog(modal=True,title=ft.Text('Device wants to join'),
            scrollable=True,content=ft.Container(width=460,content=ft.Column([ft.Text(pending['name']+' wants to join. Choose which stats this device can log. All devices see the shared stats and camera feed.'),panel],tight=True)),
            actions=[ft.TextButton('Decline',on_click=lambda _:respond(False)),ft.Button('Approve connection',on_click=lambda _:respond(True))],on_dismiss=dismissed)
        self._live_approval_dialog=dialog;self.page.show_dialog(dialog)

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
        self._live_approval_seen=set();self._live_approval_dialog=None
        self._live_status='Sharing — other devices can scan for this match. Connection requests appear automatically.'
        self._live_capture();self.page.run_task(self._live_loop)
        if self.camera_on:self._start_rtc_video('live-host')
        self._full_refresh()
    async def _join_live(self,address,code,name,discovery=None):
        if self._live_active():raise SharedError('Leave the current session first.')
        if self._database_user.get('role')=='coach':raise SharedError('Coach accounts are read-only.')
        address=local_address(address)
        result=await asyncio.to_thread(local_request,address,'/request-join' if discovery else '/join','',{'session':discovery,'code':code,'name':name,'hidden':bool(self._database_user.get('hidden'))})
        self._live_join={'address':address,**result}
    async def _finish_live_join(self):
        pending=self._live_join
        data=await asyncio.to_thread(local_request,pending['address'],'/state',pending['token'])
        if getattr(self,'_live_join',None) is not pending:raise SharedError('Connection request cancelled.',409)
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
        self._live_session=None
        import os
        if os.name=='nt':
            from windows_sharing import access
            await asyncio.to_thread(access.stop)
        self._save();self._full_refresh();self._snack('Shared session ended. The host keeps the combined match.')
    def _open_shared_match(self,_=None):
        if self.is_web:
            self.page.show_dialog(ft.AlertDialog(title=ft.Text('Multiple-device logging'),content=ft.Text('Use the installed Windows, Android or iOS app to host or join a local shared match. All devices must use the same Wi-Fi, hotspot, USB tethering or Ethernet network; internet is optional.'),actions=[ft.TextButton('Close',on_click=lambda _:self.page.pop_dialog())]));return
        session=getattr(self,'_live_session',None)
        self._live_status_text=ft.Text(getattr(self,'_live_status','Use the same Wi-Fi, hotspot, USB tethering or Ethernet network. Internet is optional.'),size=12)
        async def end(_):
            await self._end_live()
            if not self._live_active():self.page.pop_dialog()
        if session:
            rows=[self._live_status_text]
            if session['host']:
                hub=session['hub']
                rows += [ft.Text('Host address: '+(' or '.join(session['addresses']) or f'Your local IP address:{hub.server.server_port}'),selectable=True),ft.Text('Join code: '+hub.join_code,selectable=True),ft.Text('Only approve devices you invited.')]
                for member in list(hub.members.values()):
                    def approve(_,identity=member['id']):hub.approve(identity);self.page.pop_dialog();self._open_shared_match()
                    def remove(_,identity=member['id']):hub.approve(identity,False);self.page.pop_dialog();self._open_shared_match()
                    rows.append(ft.Row([ft.Text(member['name'],expand=True),ft.Text('Connected') if member['approved'] else ft.TextButton('Approve',on_click=lambda _,m=member:self._edit_live_assignment(session,m)),ft.TextButton('Assign controls',on_click=lambda _,m=member:self._edit_live_assignment(session,m)),ft.TextButton('Remove',on_click=remove)]))
                rows.append(ft.TextButton('Refresh waiting devices',on_click=lambda _:(self.page.pop_dialog(),self._open_shared_match())))
            else:rows.append(ft.Text('Assigned controls: '+session.get('permissions',{}).get('section','All')+'. All shared stats and the host camera remain visible.'))
            actions=[ft.TextButton('Close',on_click=lambda _:self.page.pop_dialog()),ft.TextButton('End sharing' if session['host'] else 'Leave session',on_click=end)]
        else:
            address=ft.TextField(label='Host IP address and port',hint_text='192.168.1.10:8767')
            code=ft.TextField(label='Join code (manual connection only)')
            name=ft.TextField(label='This device name',value=self._database_user.get('display_name') or 'Logger')
            message=self._live_status_text;found=ft.Column(spacing=6)
            active=True;joining=False
            async def cancel(pending):
                if pending:
                    try:await asyncio.to_thread(local_request,pending['address'],'/cancel-join',pending['token'],{})
                    except Exception:pass
            def dismissed(_=None):
                nonlocal active
                if not active:return
                active=False
                if not self._live_active():
                    pending=getattr(self,'_live_join',None);self._live_join=None
                    self.page.run_task(cancel,pending)
            def close(_):dismissed();self.page.pop_dialog()
            async def host(_):
                if joining:return
                try:self._start_live_host();dismissed();self.page.pop_dialog();self._open_shared_match()
                except Exception as e:message.value=str(e);self.page.update()
            async def request(address_value,discovery=None):
                nonlocal joining
                if joining or not active:return
                joining=True;scan_button.disabled=True;host_button.disabled=True;manual_join.disabled=True;found.disabled=True
                message.value='Sending a connection request…';self.page.update()
                try:
                    await self._join_live(address_value,code.value or '',name.value or '',discovery=discovery)
                    pending=self._live_join
                    if not active:
                        self._live_join=None;await cancel(pending);return
                    message.value='Waiting for the host to approve. This match will open automatically.';self.page.update()
                    for attempt in range(120):
                        if not active:return
                        try:
                            await self._finish_live_join()
                            if active:dismissed();self.page.pop_dialog()
                            return
                        except SharedError as e:
                            if e.status!=425:raise
                        await asyncio.sleep(1)
                    raise SharedError('The host did not approve in time. Connect again to send a new request.',408)
                except Exception as e:
                    pending=getattr(self,'_live_join',None);self._live_join=None;await cancel(pending)
                    if active:message.value=str(e)
                finally:
                    joining=False
                    if active:
                        scan_button.disabled=False;host_button.disabled=not bool(self.match);manual_join.disabled=False;found.disabled=False;self.page.update()
            async def manual(_):await request(address.value or '')
            async def scan(_):
                if joining or self._database_user.get('hidden'):return
                from shared_match import discover_matches
                scan_button.disabled=True;found.controls=[]
                message.value='Looking for shared matches on this local network…';self.page.update()
                try:
                    matches=await asyncio.to_thread(discover_matches)
                    if not active:return
                    async def connect(item):
                        if not item.get('session'):
                            address.value=item['address'];message.value='This host needs the updated v4.0.30 app for one-click requests. You can use Manual connection instead.';self.page.update();return
                        await request(item['address'],item['session'])
                    def handler(item):
                        async def click(_):await connect(item)
                        return click
                    found.controls=[ft.Container(content=ft.Column([
                        ft.Text(item['name'],weight=ft.FontWeight.BOLD),ft.Text(item['sport'].capitalize(),size=12),
                        ft.Button('Connect to this match',on_click=handler(item))],spacing=6),padding=10,border_radius=10,bgcolor='#142238') for item in matches]
                    message.value='Choose a match. Its host will receive an approval request.' if matches else 'No shared matches found. Use the same local network and start sharing on the host, or use Manual connection.'
                except Exception:
                    if active:message.value='Could not scan this network. Use Manual connection instead.'
                finally:
                    if active:scan_button.disabled=False;self.page.update()
            scan_button=ft.Button('Scan for shared matches',on_click=scan,visible=not bool(self._database_user.get('hidden')))
            host_button=ft.Button('Host this match',on_click=host,disabled=not bool(self.match))
            manual_join=ft.Button('Request connection',on_click=manual)
            rows=[message,host_button,ft.Divider(),name,scan_button,found,
                ft.TextButton('Cable / offline setup',on_click=self._open_cable_help),
                ft.ExpansionTile(title=ft.Text('Manual connection'),controls=[address,code,manual_join])]
            rows+=self._local_sharing_controls()
            self.page.show_dialog(ft.AlertDialog(title=ft.Text('Shared match'),on_dismiss=dismissed,
                content=ft.Container(width=480,content=ft.Column(rows,tight=True,scroll=ft.ScrollMode.AUTO)),
                actions=[ft.TextButton('Cancel' if joining else 'Close',on_click=close)]))
            return
        rows+=self._local_sharing_controls()
        self.page.show_dialog(ft.AlertDialog(title=ft.Text('Multiple-device logging'),content=ft.Container(width=480,content=ft.Column(rows,tight=True,scroll=ft.ScrollMode.AUTO)),actions=actions))
