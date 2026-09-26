"""Browse shared games without changing the currently active match."""
import asyncio
import flet as ft


class GameBrowserMixin:
    async def _open_saved_games(self, _=None):
        if not self._can_manage_database():return
        token=self._database_token
        # Use the existing sync queue so offline edits and conflict handling are preserved.
        while self._database_busy:await asyncio.sleep(.05)
        if token!=self._database_token or not self._can_manage_database():return
        try:await self._sync_database_once()
        except Exception:self._database_message('Offline — showing games saved on this device.')
        if token!=self._database_token or not self._can_manage_database():return
        self.page.pop_dialog()
        self._show_saved_games()

    def _show_saved_games(self):
        if not self._can_manage_database():return
        token=self._database_token
        search=self._account_field('Search by team, date or sport')
        listing=ft.Column(tight=True,spacing=12)
        summary=ft.Text('');offset=0
        def allowed():return token==self._database_token and self._can_manage_database()
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
                    ft.Row([ft.Button('View game',on_click=lambda _,key=m.id:choose(key)),ft.TextButton('Edit details',on_click=lambda _,key=m.id:choose(key,True))],wrap=True)
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
        if not self._can_manage_database():return
        match=next((m for m in self.matches if m.id==key),None)
        if match is None:self._snack('This game is no longer available. Refresh the list.');return
        token=self._database_token
        def back(_):
            self.page.pop_dialog()
            if token==self._database_token:self._show_saved_games()
        def open_game(_,edit=False):
            if token==self._database_token:self._open_saved_game_workspace(key,edit_details=edit)
        stats=match.stats.to_dict()
        content=[ft.Text(f'{match.home_team.name} {match.home_score}–{match.away_score} {match.away_team.name}',size=20,weight=ft.FontWeight.BOLD),
            ft.Text(f'{match.date} · {match.sport} · {match.location}'),ft.Text(f'{match.period.replace("_"," ")} · {match.minute}:{match.second:02d}'),
            ft.Text('Statistics',weight=ft.FontWeight.BOLD)]
        content += [ft.Text(f'{name.replace("_"," ").title()}: {value}') for name,value in stats.items()]
        content += [ft.Text(f'Events ({len(match.events)})',weight=ft.FontWeight.BOLD)]
        content += [ft.Text(f'{e.minute}′ · {e.event_type.replace("_"," ")} · {e.player_name or ""} · {e.description or ""}') for e in match.events[-100:]]
        if len(match.events)>100:content.append(ft.Text('Showing the latest 100 events. Open the workspace for the full timeline.'))
        self.page.pop_dialog()
        self.page.show_dialog(ft.AlertDialog(title=ft.Text('View game'),scrollable=True,
            content=ft.Container(width=600,content=ft.Column(content,tight=True,spacing=8)),actions=[
                ft.TextButton('Back to games',on_click=back),ft.TextButton('Edit details',on_click=lambda e:open_game(e,True)),
                ft.Button('Open workspace',on_click=open_game)]))

    def _open_saved_game_workspace(self,key,edit_details=False):
        if not self._can_manage_database():return
        index=next((i for i,m in enumerate(self.matches) if m.id==key),None)
        if index is None:self._snack('This game is no longer available. Refresh the list.');return
        self.page.pop_dialog()
        self._timer_running=False
        self._stop_camera()
        self.app_mode='inputter';self.fullscreen_video=False;self.active_tab='LOGGER'
        self.active_match_idx=index;self.last_logged_action=None;self.can_convert=False
        self._full_refresh()
        if edit_details:self._open_edit_match_dialog()
