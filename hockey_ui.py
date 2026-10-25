"""Field hockey logging with the same section layout as the other sports."""
import flet as ft
from hockey import GROUPS, ACTIONS, INCOMPLETES, outcomes, sequences, report, ensure_baseline
from engine import make_event, recalculate_stats
from ui_widgets import card, action_btn, portrait_grid

class HockeyMixin:
    def _hockey_buttons(self, category=None):
        group=(category or self.action_category).replace('Defence','Defense')
        color={'Attack':'#34d399','Defense':'#38bdf8','Cards':'#fbbf24','Opposition':'#fb7185'}[group]
        return [(r[1],r[0],ft.Icons.SPORTS_HOCKEY,'#fbbf24' if 'PENALTY' in r[0] or 'FREE_HIT' in r[0] else color) for r in GROUPS[group] if self._live_allows_key(r[0])]

    def _hockey_target(self):
        own=self._live_events()
        if not own:return None
        last=own[-1]
        return last if last.event_type in INCOMPLETES else None

    def _hockey_action(self,code):
        m=self.match
        parent=self._hockey_target()
        if code=='CONVERSION':
            if not parent or parent.event_type not in ('SHOT','SHOT_AGAINST'):return
            key=parent.event_type
        elif code.endswith('_INCOMPLETE'):
            key=code.removesuffix('_INCOMPLETE')
            if not parent or parent.event_type!=key:return
        else:
            key=code
            if code not in ACTIONS:return
        if not self._live_require_key(key):return
        ensure_baseline(m)
        label='Conversion' if code=='CONVERSION' else ACTIONS[key][1]+(' incomplete' if code.endswith('_INCOMPLETE') else '')
        event=make_event(m,'home',code,m.home_team.short_name,label)
        if code=='CONVERSION' or code.endswith('_INCOMPLETE'):event.target_id=parent.id
        m.events.append(event)
        self.last_logged_action=code if code in INCOMPLETES else None
        self.can_convert=code in ('SHOT','SHOT_AGAINST')
        recalculate_stats(m);self._save();self._full_refresh()

    def _hockey_grid(self, sidebar=False):
        tiles=[action_btn(label,icon,color,lambda _,c=code:self._hockey_action(c)) for label,code,icon,color in self._hockey_buttons() if self._live_allows_key(code)]
        if self.action_category in ('Attack','Opposition'):
            key='SHOT' if self.action_category=='Attack' else 'SHOT_AGAINST'
            target=self._hockey_target()
            if self._live_allows_key(key):tiles.append(action_btn('Conversion',ft.Icons.CHECK_CIRCLE,'#34d399' if key=='SHOT' else '#fb7185',lambda _:self._hockey_action('CONVERSION'),disabled=not target or target.event_type!=key))
        if sidebar:
            # ResponsiveRow breakpoints follow the window, not this narrow sidebar.
            # A full-width vertical list keeps every label visible at desktop sizes.
            for tile in tiles:tile.height=48
            return ft.Column(tiles,spacing=6,horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        return portrait_grid(tiles)

    def _hockey_incompletes(self):
        target=self._hockey_target()
        rows=GROUPS[self.action_category.replace('Defence','Defense')]
        tiles=[action_btn(label+' !',ft.Icons.CLOSE,'#fb7185',lambda _,c=code:self._hockey_action(c+'_INCOMPLETE'),disabled=not target or target.event_type!=code) for code,label,_,inc,_ in rows if inc and self._live_allows_key(code)]
        return card(ft.Column([ft.Text('Incompletes'),portrait_grid(tiles) if tiles else ft.Text('No incomplete actions in this section.')],spacing=6))

    def _build_hockey_logger(self,m):
        if self.fullscreen_video:return self._build_fullscreen_logger(m)
        tabs=ft.Row([self._cat_tab(n,c) for n,c in [('Attack','#34d399'),('Defence','#38bdf8'),('Cards','#fbbf24'),('Opposition','#fb7185')]],wrap=True)
        return ft.Column([
            self._build_live_video_panel(),self._build_possession_row(m),
            card(ft.Column([tabs,self._hockey_grid()])),self._hockey_incompletes(),
            ft.Row([ft.TextButton('Turnover',on_click=self._log_turnover,visible=self._live_allows_key('TURNOVER')),
                ft.TextButton('Substitution',on_click=lambda _:self._quick_action('SUBSTITUTION','Substitution'),visible=self._live_allows_key('SUBSTITUTION')),
                ft.TextButton('Start / pause',on_click=self._toggle_timer,disabled=not self._live_controls('time')),
                ft.TextButton('Half time',on_click=lambda _:self._mark_halftime(),disabled=not self._live_controls('time')),
                ft.TextButton('Full time',on_click=lambda _:self._mark_fulltime(),disabled=not self._live_controls('time'))],wrap=True),
            ft.Column([ft.Text(k.replace('defence','defense').capitalize()+': '+(v or '—'),selectable=True) for k,v in sequences(m.events).items()]),
            ft.TextButton('Undo last event',on_click=lambda _:self._undo_last_event())
        ],scroll=ft.ScrollMode.AUTO,expand=True,spacing=8,horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    def _export_hockey(self):
        from export_utils import match_filename
        self.page.run_task(self._export_txt_async,match_filename(self.match),report(self.match))
