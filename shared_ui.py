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
                server=session['hub'].server if session and session['host'] else None
                from pairing_directory import directory
                port=server.server_port if server else directory.server.server_port if directory.server else 8767
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
    def _live_stream_only(self):
        return self._live_guest() and bool(self._live_session.get('permissions',{}).get('stream_only'))
    def _live_controls(self,kind):
        if not self._live_active():return True
        session=self._live_session
        controllers=session['hub'].controllers if session['host'] else session.get('controllers',{})
        return controllers.get(kind,'host')==session['device']
    def _live_time_only(self):
        if self._live_controls('time'):return True
        self._snack('The device assigned by the host controls match time.');return False
    def _live_video_role(self):return 'live-host' if self._live_controls('video') else 'live-guest'
    def _live_clock_body(self):
        return {'generation':self._live_session.get('control_generation',0),'running':self._timer_running,
            'clock':{k:getattr(self.match,k) for k in ('minute','second','period','basketball_elapsed')}}
    def _live_host_only(self):
        if self._live_guest():
            self._snack('The host controls score corrections and possession.')
            return False
        return True
    def _live_allows_key(self,key):
        from stat_policy import retired
        if retired(key):return False
        if self._live_stream_only():return False
        if key in ('TO','TURNOVER','SUBSTITUTION','LINEUP','TIMEOUT','OVERTIME','END_QUARTER','FULL_TIME'):return self._live_controls('time')
        if not self._live_guest():return True
        from shared_permissions import assignment
        return key in self._live_session.get('permissions',assignment(self.match.sport))['stats']
    def _live_require_key(self,key):
        if self._live_allows_key(key):return True
        self._snack('The host has not assigned this stat to your device.');return False
    def _live_can_modify_event(self,event):
        if not self._live_guest():return True
        from shared_permissions import permits,assignment
        if permits(self.match.sport,self._live_session.get('permissions',assignment(self.match.sport)),event,self.match.events):return True
        self._snack('This stat or jersey is not assigned to your device.');return False
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
        if self.match.sport=='BASKETBALL':
            labels.update({'steal':'STL','shot':'SHOT','rebound':'REBOUND','block':'BLK','foul':'PF','conversion':'SHOT','turnover':'TO'})
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
        from shared_permissions import assignment,catalog,section_names
        selected=initial or assignment(sport)
        stream_only=ft.Checkbox(label='Stream only (camera, no match controls)',value=bool(selected.get('stream_only')))
        available_sections=set(catalog(sport))
        valid_sections=section_names(sport)
        sections=set(selected.get('sections',valid_sections if selected['section']=='All' else [selected['section']])) & available_sections
        checked=set(selected['stats']);listing=ft.Column(spacing=4)
        def change_stat(key,value):
            if value:checked.add(key)
            else:checked.discard(key)
        def render():
            listing.controls=[]
            for choice in choices:choice.disabled=bool(stream_only.value)
            if stream_only.value:return
            for section,stats in catalog(sport).items():
                if section not in sections:continue
                listing.controls.append(ft.Text(section,weight=ft.FontWeight.BOLD))
                listing.controls += [ft.Checkbox(label=label,value=key in checked,on_change=lambda e,k=key:change_stat(k,e.control.value)) for key,label in stats.items()]
        def section_changed(section,value):
            keys=set(catalog(sport)[section])
            if value:sections.add(section);checked.update(keys)
            else:sections.discard(section);checked.difference_update(keys)
            render();self.page.update()
        choices=[ft.Checkbox(label=section,value=section in sections,on_change=lambda e,k=section:section_changed(k,e.control.value)) for section in valid_sections if section in available_sections]
        stream_only.on_change=lambda _:(render(),self.page.update())
        render()
        all_players=ft.Checkbox(label='All jerseys (including jerseys added later)',value=selected.get('players') is None)
        jerseys=[ft.Checkbox(label='#'+str(p.number),value=p.id in (selected.get('players') or []),data=p.id) for p in self.match.home_team.players if p.active] if sport=='BASKETBALL' else []
        def player_change(_):
            for item in jerseys:item.disabled=bool(all_players.value)
            self.page.update()
        all_players.on_change=player_change
        for item in jerseys:
            item.disabled=bool(all_players.value);item.on_change=lambda _:None
        def selection():
            if stream_only.value:return assignment(sport,[],[],True)
            allowed={key for group,values in catalog(sport).items() if group in sections for key in values}
            return assignment(sport,list(sections),sorted(checked & allowed),players=None if all_players.value or sport!='BASKETBALL' else [c.data for c in jerseys if c.value])
        return ft.Column([stream_only,*([ft.Text('Players this device can log'),all_players,ft.Row(jerseys,wrap=True)] if sport=='BASKETBALL' else []),ft.Text('Sections this device can control (choose any combination)'),ft.Row(choices,wrap=True),
            ft.ExpansionTile(title=ft.Text('Choose individual stats'),controls=[ft.Text('Conversions and incompletes follow their parent stat. The host assigns the whole time-control section and camera separately.',size=12),listing])],tight=True),selection
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
        if not session['host'] and self._live_controls('time'):
            session['pending_clock']=self._live_clock_body()
        if session['host']:
            hub=session['hub']
            hub.control(self.match,self._timer_running)
            hub.apply(hub.host_token,list(self._live_pending.values()),list(self._live_removed))
            self._live_pending.clear();self._live_removed.clear()
    def _live_adopt(self,data):
        session=self._live_session
        if not session:return
        old=self.match
        previous_video='live-host' if session.get('controllers',{}).get('video','host')==session['device'] else 'live-guest'
        previous_time=session.get('controllers',{}).get('time','host')
        next_controllers=data.get('controllers',{'video':'host','time':'host'})
        time_changed=(previous_time!=next_controllers['time'] or data.get('control_generation',0)!=session.get('control_generation',0))
        roles_changed=(next_controllers!=session.get('controllers',next_controllers) or time_changed)
        session['controllers']=next_controllers
        session['control_generation']=data.get('control_generation',0)
        if time_changed or not self._live_controls('time'):
            self._timer_running=False;session.pop('pending_clock',None)
        permissions_changed=data.get('permissions')!=session.get('permissions')
        if 'permissions' in data:session['permissions']=data['permissions']
        remote=Match.from_dict(data['match']);remote.local_shared_guest=not session['host']
        if old and self._live_controls('time') and not time_changed:
            for key in ('minute','second','period','basketball_elapsed','is_live'):setattr(remote,key,getattr(old,key))
        ids={e.id for e in remote.events}
        remote.events += [StatEvent.from_dict(e) for k,e in self._live_pending.items() if k not in ids]
        remote.events=[e for e in remote.events if e.id not in self._live_removed]
        recalculate_stats(remote)
        if remote.sport!='BASKETBALL':remote.away_score=data['match']['away_score']
        changed=(roles_changed or permissions_changed or not old or [e.to_dict() for e in old.events]!=[e.to_dict() for e in remote.events] or old.period!=remote.period or old.possession_team!=remote.possession_team or old.home_score!=remote.home_score or old.away_score!=remote.away_score or getattr(self,'_live_running',None)!=data['running'])
        self._live_running=data['running'];session['members']=data.get('members',[])
        self._live_applying=True
        try:
            if old:old.__dict__.update(remote.__dict__);remote=old
            else:self.matches.append(remote);self.active_match_idx=len(self.matches)-1
            self._live_observed={e.id for e in remote.events}
            if self._live_guest():
                for attr in (('_bb_category',) if remote.sport=='BASKETBALL' else ('action_category',)):
                    current=getattr(self,attr,'Attack')
                    if not self._live_section_allowed(current):
                        choices=('Overall',) if remote.sport=='BASKETBALL' else ('Attack','Defense','Cards','Opposition')
                        setattr(self,attr,next((c for c in choices if self._live_section_allowed(c)),choices[0]))
            if previous_video!=self._live_video_role():
                if self.camera_on:self._stop_camera()
                if not self._live_controls('video'):self._start_rtc_video('live-guest')
                else:self._snack('Your device is assigned to share video. Turn on the camera when ready.')
            if changed:self._full_refresh()
            # Refresh the displayed clock without rebuilding the logging panels.
            if self._live_stream_only():return
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
                    if session.get('controllers')!=session['hub'].controllers:
                        self._live_adopt(session['hub'].snapshot(session['token']))
                    session['hub'].control(self.match,self._timer_running)
                    data=session['hub'].snapshot(session['token'])
                else:
                    if self._live_controls('time'):
                        clock=session.get('pending_clock') or self._live_clock_body()
                        await self._shared_request(session['address'],'/control',session['token'],clock)
                        if session.get('pending_clock') is clock:session.pop('pending_clock',None)
                    added=copy.deepcopy(dict(list(self._live_pending.items())[:200]));removed=set(list(self._live_removed)[:200])
                    if added or removed:
                        data=await self._shared_request(session['address'],'/events',session['token'],{'added':list(added.values()),'removed':list(removed)})
                        for k,v in added.items():
                            if self._live_pending.get(k)==v:self._live_pending.pop(k)
                        self._live_removed.difference_update(removed)
                    else:data=await self._shared_request(session['address'],'/state',session['token'])
                if self._live_session is not session:return
                self._live_adopt(data)
                if session.get('address')=='peer':await self._peer_sync_source()
                if session['host']:self._show_live_approval(session,data.get('members',[]))
                waiting=sum(not m['approved'] for m in data.get('members',[]))
                self._live_status=(f'Sharing on local network — {waiting} device(s) waiting for approval' if waiting else 'Sharing on local network') if data['host_online'] else 'Host paused or disconnected — waiting'
            except SharedError as e:
                self._live_status=str(e)
                if not session['host'] and e.status in (403,409):
                    try:
                        data=await self._shared_request(session['address'],'/state',session['token'])
                        if self._live_session is session:self._live_adopt(data)
                        self._live_status='Some inputs need host permission. Ask the host to restore those stats; queued inputs are retained.'
                    except Exception:pass
            except Exception:
                if self._live_controls('time'):
                    self._timer_running=False;self.match.is_live=False;session.pop('pending_clock',None)
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
        self._live_session={'host':True,'hub':hub,'token':hub.host_token,'device':'host','address':f'http://127.0.0.1:{port}','addresses':addresses(port),'match_id':self.match.id,'members':[],'controllers':dict(hub.controllers),'control_generation':0}
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
        result=await self._shared_request(address,'/request-join' if discovery else '/join','',{'session':discovery,'code':code,'name':name,'hidden':bool(self._database_user.get('hidden'))})
        self._live_join={'address':address,**result}
    async def _finish_live_join(self):
        pending=self._live_join
        data=await self._shared_request(pending['address'],'/state',pending['token'])
        if getattr(self,'_live_join',None) is not pending:raise SharedError('Connection request cancelled.',409)
        self._timer_running=False
        if self.camera_on:self._stop_camera()
        self._live_original=[m for m in self.matches if m.id==data['match']['id']]
        self.matches=[m for m in self.matches if m.id!=data['match']['id']]
        self.active_match_idx=-1
        self._live_session={'host':False,'token':pending['token'],'device':pending['device'],'address':pending['address'],'match_id':data['match']['id']}
        self._live_pending={};self._live_removed=set();self._live_observed=set()
        self._live_adopt(data);self._set_fixture_open(self.match.id,True)
        self._live_status='Connected — the host assigns camera and timer devices.'
        self.page.run_task(self._live_loop)
        if not self._live_stream_only():self._start_rtc_video('live-guest')
        self._full_refresh()
    async def _end_live(self):
        session=self._live_session
        if not session:return
        if self._live_pending or self._live_removed:
            self._snack('Inputs are still waiting to reach the host. Reconnect before leaving; export the match if the host is unavailable.')
            return
        self._timer_running=False
        if self.camera_on:
            if session.get('address')=='peer':await self._peer_camera(False)
            else:self._stop_camera()
        if session['host']:
            session['hub'].assign_controllers(session['token'],'host','host')
            self.match.is_live=False
            session['hub'].control(self.match,False)
            data=session['hub'].snapshot(session['token']);self._live_adopt(data)
            if session.get('address')=='peer':session['hub'].closed=True
            else:await asyncio.to_thread(session['hub'].stop)
        else:
            try:await self._shared_request(session['address'],'/cancel-join',session['token'],{})
            except Exception:pass
            self.matches=[m for m in self.matches if m.id!=session['match_id']]+getattr(self,'_live_original',[])
            self.active_match_idx=-1
        if session.get('address')=='peer':await self._peer_close()
        self._live_session=None
        import os
        if os.name=='nt':
            from windows_sharing import access
            await asyncio.to_thread(access.stop)
        self._save();self._full_refresh();self._snack('Shared session ended. The host keeps the combined match.')
    def _open_shared_match(self,_=None):
        if not self._live_active() or self._live_session.get('address')=='peer':self._open_peer_pairing();return
        self._open_local_shared_match()

    def _open_local_shared_match(self,_=None,embedded=False):
        if self.is_web and not self._live_active():self._open_peer_pairing();return
        session=getattr(self,'_live_session',None)
        self._live_status_text=ft.Text(getattr(self,'_live_status','Use the same Wi-Fi, hotspot, USB tethering or Ethernet network. Internet is optional.'),size=12)
        async def end(_):
            await self._end_live()
            if not self._live_active():self.page.pop_dialog()
        if session:
            rows=[self._live_status_text]
            if not self.is_web and not embedded:rows.append(ft.Button('Device Wi-Fi link',on_click=self._open_wifi_point))
            if session['host']:
                hub=session['hub']
                if session.get('address')=='peer':
                    if not embedded:rows += [ft.Text('Offline connection-code session'),ft.Button('Pair another device',on_click=self._open_peer_pairing)]
                else:rows += [ft.Text('Host address: '+(' or '.join(session['addresses']) or f'Your local IP address:{hub.server.server_port}'),selectable=True),ft.Text('Join code: '+hub.join_code,selectable=True)]
                rows.append(ft.Text('Only approve devices you invited.'))
                choices=[ft.dropdown.Option('host','Host (this device)')]+[ft.dropdown.Option(m['id'],m['name']) for m in hub.members.values() if m['approved']]
                video_device=ft.Dropdown(label='Device sharing video',value=hub.controllers['video'],options=choices)
                time_choices=[ft.dropdown.Option('host','Host (this device)')]+[ft.dropdown.Option(m['id'],m['name']) for m in hub.members.values() if m['approved'] and not m['permissions'].get('stream_only')]
                time_device=ft.Dropdown(label='Device controlling time',value=hub.controllers['time'],options=time_choices)
                def save_devices(_):
                    try:
                        data=hub.assign_controllers(session['token'],video_device.value,time_device.value)
                        self._live_adopt(data)
                        self._snack('Device assignments saved. A timer handover pauses the clock; the new device can start it.')
                    except SharedError as error:self._snack(str(error))
                rows += [video_device,time_device,ft.Button('Save device assignments',on_click=save_devices),ft.Text('Choose the same device for both, or different devices. A newly selected video device must turn on its camera.',size=12)]
                for member in list(hub.members.values()):
                    def approve(_,identity=member['id']):hub.approve(identity);self.page.pop_dialog();self._open_shared_match()
                    def remove(_,identity=member['id']):hub.approve(identity,False);self.page.pop_dialog();self._open_shared_match()
                    rows.append(ft.Row([ft.Text(member['name'],expand=True),ft.Text('Connected') if member['approved'] else ft.TextButton('Approve',on_click=lambda _,m=member:self._edit_live_assignment(session,m)),ft.TextButton('Assign controls',on_click=lambda _,m=member:self._edit_live_assignment(session,m)),ft.TextButton('Remove',on_click=remove)]))
                rows.append(ft.TextButton('Refresh waiting devices',on_click=lambda _:(self.page.pop_dialog(),self._open_shared_match())))
            else:rows.append(ft.Text('Assigned controls: '+session.get('permissions',{}).get('section','All')+'. All shared stats and the selected camera remain visible.'))
            actions=[ft.TextButton('Close',on_click=lambda _:self.page.pop_dialog()),ft.TextButton('End sharing' if session['host'] else 'Leave session',on_click=end)]
        else:
            address=ft.TextField(label='Host IP address and port',hint_text='192.168.1.10:8767')
            code=ft.TextField(label='Join code (manual connection only)')
            name=ft.TextField(label='This device name',value=self._database_user.get('display_name') or 'Logger')
            message=self._live_status_text;found=ft.Column(spacing=6)
            active=True;joining=False
            async def cancel(pending):
                if pending:
                    try:await self._shared_request(pending['address'],'/cancel-join',pending['token'],{})
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
            rows=[message,ft.Button('Create device Wi-Fi link',on_click=self._open_wifi_point),host_button,ft.Button('Browser connection codes (offline)',on_click=self._open_peer_pairing),ft.Divider(),name,scan_button,found,
                ft.ExpansionTile(title=ft.Text('Manual connection'),controls=[address,code,manual_join])]
            rows+=self._local_sharing_controls()
            self.page.show_dialog(ft.AlertDialog(title=ft.Text('Shared match'),on_dismiss=dismissed,
                content=ft.Container(width=480,content=ft.Column(rows,tight=True,scroll=ft.ScrollMode.AUTO)),
                actions=[ft.TextButton('Cancel' if joining else 'Close',on_click=close)]))
            return
        if embedded:return rows,actions
        rows+=self._local_sharing_controls()
        self.page.show_dialog(ft.AlertDialog(title=ft.Text('Shared match'),content=ft.Container(width=480,content=ft.Column(rows,tight=True,scroll=ft.ScrollMode.AUTO)),actions=actions))
