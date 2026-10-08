"""Browse shared games without changing the currently active match."""
import asyncio
import flet as ft
from coach_chart import comparison_chart, match_label, match_colors


class GameBrowserMixin:
    def _can_edit_saved_match(self, match):
        user=self._database_user
        return user.get('role') in ('owner','admin','staff') or (user.get('role')=='user' and match.created_by_id==user.get('id'))

    def _open_owner_comparisons(self, _=None):
        if self._database_user.get('role')!='owner':return
        from models import SPORTS
        if not hasattr(self,'_owner_comparison_sport'):self._owner_comparison_sport='BASKETBALL'
        def change(e):
            self._owner_comparison_sport=e.control.value
            self._open_owner_comparisons()
        self.page.pop_dialog()
        self.page.show_dialog(ft.AlertDialog(title=ft.Text('Owner match comparisons'),
            content=ft.Container(width=1000,height=650,content=ft.Column([
                ft.Dropdown(label='Sport',value=self._owner_comparison_sport,options=[ft.dropdown.Option(x) for x in SPORTS],on_select=change),
                self._build_coach_dashboard()],expand=True)),
            actions=[ft.TextButton('Close',on_click=lambda _:self.page.pop_dialog())]))

    def _build_coach_dashboard(self):
        from match_statistics import match_statistics
        from ui_widgets import card
        user=self._database_user
        games=[m for m in self.matches if m.sport==user.get('sport') and (m.home_team.team_code or m.home_team.team_rank).replace(' ','').upper()==user.get('team_code')]
        if user.get('role')=='owner': games=[m for m in self.matches if m.sport==getattr(self,'_owner_comparison_sport','BASKETBALL')]
        games.sort(key=lambda m:(m.date,m.id),reverse=True)
        if not hasattr(self,'_coach_preferences'): self._coach_preferences={}
        prefs=self._coach_preferences.setdefault(user['id'],{'matches':[], 'metrics':None})
        available={}
        for m in games: available.update({k:label for k,(label,value) in match_statistics(m).items()})
        selected=[m for m in games if m.id in prefs['matches']]
        metrics=list(available) if prefs['metrics'] is None else [k for k in prefs['metrics'] if k in available]
        def choose(kind,key,value):
            current=list(available) if kind=='metrics' and prefs[kind] is None else list(prefs[kind])
            if value and key not in current: current.append(key)
            if not value: current=[item for item in current if item!=key]
            prefs[kind]=current
            self.page.run_task(self._persist_database)
            if user.get('role')=='owner':self._open_owner_comparisons()
            else:self._full_refresh()
        choices=[ft.Row([ft.Checkbox(label=f'{match_label(m)} · {m.date}',value=m.id in prefs['matches'],on_change=lambda e,k=m.id:choose('matches',k,e.control.value)),ft.TextButton('View match',on_click=lambda _,k=m.id:self._view_saved_game(k))],wrap=True) for m in games]
        rows=[ft.Text(f"{user.get('team_code','')} · {user.get('sport','').replace('_',' ').capitalize()}",size=20,weight=ft.FontWeight.BOLD),ft.Text('All visible matches — normal and hidden' if user.get('role')=='owner' else 'Your team — read-only matches and comparisons'),card(ft.Column([ft.Text('Choose matches to compare'),*choices] if choices else [ft.Text('No matches are assigned to this team and sport yet. Ask an administrator to set the SCC team code on its matches.')],spacing=8)),ft.Text(f'{len(selected)} matches selected')]
        if available: rows.append(card(ft.ExpansionTile(title=ft.Text('Choose statistics'),controls=[ft.Checkbox(label=label,value=k in metrics,on_change=lambda e,k=k:choose('metrics',k,e.control.value)) for k,label in available.items()])))
        if len(selected)<2: rows.append(ft.Text('Select two or more matches to compare. You can select as many as you need.'))
        else:
            stats={m.id:match_statistics(m) for m in selected}
            colors=match_colors(len(selected))
            rows.append(card(comparison_chart(selected, colors, min(480,max(240,self._layout_width()-80)))))
            for key in metrics:
                values=[stats[m.id].get(key,('',None))[1] for m in selected]
                maximum=max([abs(v) for v in values if isinstance(v,(int,float))]+[1])
                items=[ft.Text(available[key],weight=ft.FontWeight.BOLD)]
                for i,(m,value) in enumerate(zip(selected,values)):
                    items.append(ft.Row([ft.Text(f'{match_label(m)} · {m.date}',width=220),ft.ProgressBar(value=abs(value)/maximum if isinstance(value,(int,float)) else 0,color=colors[i%len(colors)],expand=True),ft.Text('—' if value is None else str(value),width=65)],spacing=12))
                rows.append(card(ft.Column(items,spacing=10)))
        return ft.Column(rows,scroll=ft.ScrollMode.AUTO,expand=True,spacing=12)

    def _fixture_state(self):
        if not hasattr(self, '_fixture_workspaces'): self._fixture_workspaces = {}
        key = self._database_user.get('id') or 'local'
        return self._fixture_workspaces.setdefault(key, {'opened': [], 'closed': []})

    def _fixture_visible(self, match):
        state = self._fixture_state()
        user = self._database_user.get('id')
        return match.id not in state['closed'] and (match.id in state['opened'] or bool(user and match.created_by_id == user))

    def _set_fixture_open(self, key, opened):
        state = self._fixture_state()
        for name in ('opened', 'closed'):
            state[name] = [item for item in state[name] if item != key]
        state['opened' if opened else 'closed'].append(key)
        if getattr(self, '_database', None) is not None:
            self.page.run_task(self._persist_database)

    def _sport_stat_controls(self, match):
        from match_statistics import match_statistics
        return [ft.Text(match.sport.replace('_',' ').capitalize())] + [ft.Text(label + ': ' + ('—' if value is None else str(value))) for label,value in match_statistics(match).values()]

    def _build_scc_stats(self, match):
        from match_statistics import match_statistics
        from ui_widgets import card
        rows = [ft.Text('SCC statistics', size=18, weight=ft.FontWeight.BOLD)]
        if match.sport in ('SOCCER','BASKETBALL'):
            rows.append(card(ft.Column([ft.Text('SCC performance'),self._build_radar_chart_canvas(match)])))
        rows.append(card(ft.Column([ft.Row([ft.Text(label,expand=True),ft.Text('—' if value is None else str(value),weight=ft.FontWeight.BOLD)]) for label,value in match_statistics(match).values()],spacing=10)))
        return ft.Column(rows,scroll=ft.ScrollMode.AUTO,expand=True,spacing=10)

    async def _open_saved_games(self, _=None):
        if not bool(self._database_token):return
        token=self._database_token
        # Use the existing sync queue so offline edits and conflict handling are preserved.
        while self._database_busy:await asyncio.sleep(.05)
        if token!=self._database_token or not bool(self._database_token):return
        try:await self._sync_database_once()
        except Exception:self._database_message('Offline — showing games saved on this device.')
        if token!=self._database_token or not bool(self._database_token):return
        self.page.pop_dialog()
        self._show_saved_games()

    def _show_saved_games(self):
        if not bool(self._database_token):return
        token=self._database_token
        search=self._account_field('Search by team, date or sport')
        listing=ft.Column(tight=True,spacing=12)
        summary=ft.Text('');offset=0
        def allowed():return token==self._database_token and bool(self._database_token)
        def choose(key,edit=False):
            if not allowed():return
            if edit:self._open_saved_game_workspace(key,edit_details=True)
            else:self._view_saved_game(key)
        def render(_=None):
            if not allowed():return
            term=(search.value or '').strip().casefold()
            games=sorted([m for m in self.matches if term in f'{m.title} {m.home_team.name} {m.away_team.name} {m.date} {m.sport}'.casefold()],key=lambda m:(m.date,m.id),reverse=True)
            listing.controls=[]
            for m in games[offset:offset+20]:
                listing.controls.append(ft.Container(padding=10,border_radius=10,bgcolor='#142238',content=ft.Column([
                    ft.Text(f'{m.home_team.name} {m.home_score}–{m.away_score} {m.away_team.name}',weight=ft.FontWeight.BOLD),
                    ft.Text(f'{m.date} · {m.sport} · {m.location} · {m.period.replace("_"," ")}',size=12),
                    ft.Row([ft.Button('View game',on_click=lambda _,key=m.id:choose(key)),ft.TextButton('Edit details',visible=self._can_edit_saved_match(m),on_click=lambda _,key=m.id:choose(key,True))],wrap=True)
                ],tight=True)))
            if not games:listing.controls=[ft.Text('No games match your search.' if term else 'No saved games yet. Games created by any account appear here after syncing.')]
            summary.value=f'{len(games)} game(s) · Showing {min(offset+1,len(games))}–{min(offset+20,len(games))}'
            previous.disabled=offset==0;following.disabled=offset+20>=len(games)
            self.page.update()
        def query(_):
            nonlocal offset
            offset=0;render()
        def move(amount):
            nonlocal offset
            offset=max(0,offset+amount);render()
        search.on_change=query
        previous=ft.TextButton('Previous',on_click=lambda _:move(-20));following=ft.TextButton('Next',on_click=lambda _:move(20))
        self.page.show_dialog(ft.AlertDialog(title=ft.Text('Saved games'),scrollable=True,
            content=ft.Container(width=620,content=ft.Column([ft.Text('View games from all accounts. Viewing does not change a game. Edit details or open the workspace to make changes.'),
                ft.Text(self._database_status.value,size=12),search,summary,listing,ft.Row([previous,following])],tight=True)),
            actions=[ft.TextButton('Close',on_click=lambda _:self.page.pop_dialog()),ft.Button('Refresh games',on_click=self._open_saved_games)]))
        render()

    def _view_saved_game(self,key):
        if not bool(self._database_token):return
        match=next((m for m in self.matches if m.id==key),None)
        if match is None:self._snack('This game is no longer available. Refresh the list.');return
        token=self._database_token
        def back(_):
            self.page.pop_dialog()
            if token==self._database_token:self._show_saved_games()
        def open_game(_,edit=False):
            if token==self._database_token:self._open_saved_game_workspace(key,edit_details=edit)
        content=[ft.Text(f'{match.home_team.name} {match.home_score}–{match.away_score} {match.away_team.name}',size=20,weight=ft.FontWeight.BOLD),
            ft.Text(f'{match.date} · {match.sport} · {match.location}'),ft.Text(f'{match.period.replace("_"," ")} · {match.minute}:{match.second:02d}'),
            ft.Text(self._match_credit(match)),ft.Text('Statistics',weight=ft.FontWeight.BOLD)]
        content += self._sport_stat_controls(match)
        content += [ft.Text(f'Events ({len(match.events)})',weight=ft.FontWeight.BOLD)]
        content += [ft.Text(f'{e.minute}′ · {e.event_type.replace("_"," ")} · {e.player_name or ""} · {e.description or ""}') for e in match.events[-100:]]
        if len(match.events)>100:content.append(ft.Text('Showing the latest 100 events. Open the workspace for the full timeline.'))
        self.page.pop_dialog()
        self.page.show_dialog(ft.AlertDialog(title=ft.Text('View game'),scrollable=True,
            content=ft.Container(width=600,content=ft.Column(content,tight=True,spacing=8)),actions=[
                ft.TextButton('Back to games',on_click=back),ft.TextButton('Edit details',visible=self._can_edit_saved_match(match),on_click=lambda e:open_game(e,True)),
                ft.Button('Open workspace',visible=self._can_edit_saved_match(match),on_click=open_game)]))

    def _open_saved_game_workspace(self,key,edit_details=False):
        target=next((m for m in self.matches if m.id==key),None)
        if target and not self._can_edit_saved_match(target):return self._view_saved_game(key)
        if not bool(self._database_token):return
        index=next((i for i,m in enumerate(self.matches) if m.id==key),None)
        if index is None:self._snack('This game is no longer available. Refresh the list.');return
        self.page.pop_dialog()
        self._timer_running=False
        self._stop_camera()
        self.app_mode='inputter';self.fullscreen_video=False;self.active_tab='LOGGER'
        self._set_fixture_open(key, True)
        self.active_match_idx=index;self.last_logged_action=None;self.can_convert=False
        self._full_refresh()
        if edit_details:self._open_edit_match_dialog()
