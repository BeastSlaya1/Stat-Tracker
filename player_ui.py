"""Basketball jersey rosters and player summaries."""
import copy
import uuid
import flet as ft
from models import Player
from cloud_sync import api_request
from team_options import team_dropdown

from stat_policy import TEAM_ACTIONS
def team_key(team):return (team.team_code or team.team_rank).replace(' ','').upper()

class PlayerMixin:
    def _player_allowed(self,identity):
        if not self._live_guest():return True
        ids=self._live_session.get('permissions',{}).get('players')
        return ids is None or identity in ids

    def _selected_player(self):
        selected=getattr(self,'_selected_jerseys',{}).get(self.match.id)
        return next((p for p in self.match.home_team.players if p.id==selected and p.active and self._player_allowed(p.id)),None)

    def _jersey_selector(self):
        selected=self._selected_player()
        def choose(event):
            if not hasattr(self,'_selected_jerseys'):self._selected_jerseys={}
            self._selected_jerseys[self.match.id]=event.control.value
            self._full_refresh()
        return ft.Row([ft.Dropdown(label='Logging jersey',width=180,value=selected.id if selected else None,
            options=[ft.dropdown.Option(p.id,'#'+str(p.number)) for p in self.match.home_team.players if p.active and self._player_allowed(p.id)],on_select=choose),
            ft.TextButton('Team jerseys',on_click=self._open_team_jerseys,disabled=self._live_guest())],wrap=True)

    def _jersey_stats(self,match):
        from basketball import summary,display
        data=summary(match)['home']['players']
        from match_statistics import match_statistics
        keys={k:label for k,(label,_) in match_statistics(match).items() if k not in TEAM_ACTIONS and k not in ('PENALTIES_GIVEN','PF','TO','AST/TO','ORTG')}
        return ft.Column([ft.Text('Player statistics by jersey',size=16,weight=ft.FontWeight.BOLD),
            *[ft.ExpansionTile(title=ft.Text(row['name']),controls=[ft.Text(label+': '+display(row['stats'].get(key))) for key,label in keys.items()]) for row in data.values()]],spacing=6)

    def _apply_roster(self,code,players):
        if self._live_guest() or self._database_user.get('role')=='coach':return
        m=self.match
        if not m or m.sport!='BASKETBALL' or team_key(m.home_team)!=code:return
        old={p.id:p for p in m.home_team.players}
        for p in old.values():p.active=False
        for row in players:
            p=old.get(row['id'])
            if p:p.active=row['active'];p.number=row['number'];p.name='#'+str(p.number)
            else:m.home_team.players.append(Player(row['id'],row['number'],'#'+str(row['number']),'',active=row['active']))
        self._save();self._full_refresh()

    def _open_team_jerseys(self,_=None):
        if self._live_guest():self._snack('The host manages the shared match roster.');return
        user=self._database_user
        if not user.get('id'):self._snack('Sign in to manage team jerseys.');return
        if user.get('role')=='coach' and user.get('sport')!='BASKETBALL':self._snack('Player jerseys are available for basketball teams.');return
        token=self._database_token
        code=user.get('team_code') if user.get('role')=='coach' else team_key(self.match.home_team) if self.match and self.match.sport=='BASKETBALL' else '1STTEAM'
        selector=team_dropdown(code,disabled=user.get('role')=='coach')
        number=ft.TextField(label='Jersey number (0–9999)',width=200,keyboard_type=ft.KeyboardType.NUMBER)
        rows=ft.Column();status=ft.Text();state={'players':[],'version':0,'loaded':False,'busy':False}
        def key():return str(int(bool(user.get('hidden'))))+':'+selector.value.replace(' ','').upper()
        def allowed():return self._database_token==token and self._database_user.get('id')==user.get('id')
        def render():
            rows.controls=[ft.Row([ft.Text('#'+str(p['number']),expand=True),ft.TextButton('Remove' if p['active'] else 'Restore',on_click=lambda _,r=p:toggle(r))]) for p in sorted(state['players'],key=lambda p:p['number'])]
            self.page.update()
        def toggle(row):
            if state['busy']:return
            row['active']=not row['active'];render()
        def busy(value):
            state['busy']=value;selector.disabled=value or user.get('role')=='coach';number.disabled=value;self.page.update()
        async def load(_=None):
            if not allowed() or state['busy']:return
            busy(True);state['loaded']=False
            cache_key=key();code=selector.value.replace(' ','').upper()
            cache=getattr(self,'_team_rosters',{}).get(cache_key)
            try:
                try:
                    fresh=await api_request(self._database_url,'/rosters?team='+code,token)
                    if not allowed():return
                    state['pending']=False
                    state.update(copy.deepcopy(cache if cache and cache.get('pending') else fresh))
                    if not hasattr(self,'_team_rosters'):self._team_rosters={}
                    self._team_rosters[cache_key]=copy.deepcopy(cache if cache and cache.get('pending') else fresh)
                    await self._persist_database()
                    status.value='Unsynced changes on this device. Save to upload.' if state.get('pending') else ''
                except Exception as error:
                    if getattr(error,'status',0) in (400,401,403):status.value=str(error);return
                    if not cache:status.value='Could not load the team. Connect to the updated server first.';return
                    state.update(copy.deepcopy(cache));status.value='Offline — using this device’s saved roster.'
                if allowed():state['loaded']=True
            finally:busy(False);render()
        def add(_):
            if not state['loaded'] or state['busy']:return
            try:
                n=int(number.value)
                if n<0 or n>9999:raise ValueError()
            except (ValueError,TypeError):status.value='Enter a jersey number from 0 to 9999.';self.page.update();return
            row=next((p for p in state['players'] if p['number']==n),None)
            if row:row['active']=True
            else:state['players'].append({'id':uuid.uuid4().hex,'number':n,'active':True})
            number.value='';render()
        async def save(_):
            if not allowed() or not state['loaded'] or state['busy']:return
            busy(True);cache_key=key();code=selector.value.replace(' ','').upper()
            payload={'version':state['version'],'players':copy.deepcopy(state['players'])}
            try:
                try:
                    payload=await api_request(self._database_url,'/rosters?team='+code,token,method='PUT',body=payload)
                    status.value='Team jerseys saved.'
                except Exception as error:
                    if getattr(error,'status',0) in (400,401,403,409):status.value=str(error);return
                    payload['pending']=True;status.value='Saved on this device. Reopen Team jerseys and Save when online to upload.'
                if not allowed():return
                if not hasattr(self,'_team_rosters'):self._team_rosters={}
                self._team_rosters[cache_key]=copy.deepcopy(payload);state['pending']=False;state.update(payload)
                self._apply_roster(code,payload['players'])
                await self._persist_database()
            finally:busy(False);render()
        selector.on_select=load
        self.page.show_dialog(ft.AlertDialog(title=ft.Text('Basketball team jerseys'),scrollable=True,
            content=ft.Container(width=480,content=ft.Column([selector,status,rows,ft.Row([number,ft.Button('Add jersey',on_click=add)],wrap=True)],tight=True)),
            actions=[ft.TextButton('Reload',on_click=load),ft.Button('Save',on_click=save),ft.TextButton('Close',on_click=lambda _:self.page.pop_dialog())]))
        self.page.run_task(load)
