"""Fixed video and header above a separately scrolling portrait logger."""
import flet as ft
from ui_widgets import card, update_layout
from engine import generate_sequences

class PortraitMixin:
    def _portrait_fullscreen(self):
        width=self._layout_width()
        return width < 900 or width < float(getattr(self.page,'height',None) or 800)

    def _build_portrait_logging(self,m):
        basketball=m.sport=='BASKETBALL'
        clock=self._bb_clock_text if basketball else self.fs_clock_text
        buttons=self._bb_time_buttons()[1:] if basketball else []
        for button in buttons:
            button.disabled=self._live_guest()
            button.padding=ft.Padding.symmetric(horizontal=8,vertical=5)
        top=ft.Column([
            ft.Row([ft.IconButton(ft.Icons.FULLSCREEN_EXIT,on_click=self._exit_fullscreen_video,tooltip='Exit fullscreen'),
                ft.Text(f'{m.home_team.short_name} {m.home_score} : {m.away_score} {m.away_team.short_name}',size=16,weight=ft.FontWeight.BOLD,expand=True),
                ft.IconButton(ft.Icons.PAUSE if self._timer_running else ft.Icons.PLAY_ARROW,on_click=self._bb_toggle_timer if basketball else self._toggle_timer,tooltip='Pause' if self._timer_running else 'Start',disabled=self._live_guest()),clock],spacing=4),
            ft.Row(buttons,scroll=ft.ScrollMode.AUTO,spacing=4) if basketball else ft.Row([
                ft.TextButton('Half time',on_click=lambda _:self._mark_halftime()),ft.TextButton('Full time',on_click=lambda _:self._mark_fulltime())]),
            self._build_possession_row(m),
            ft.TextButton("Shared match",on_click=self._open_shared_match) if self._live_active() else ft.Container(),
        ],spacing=3)
        if basketball:
            actions=card(ft.Column([self._bb_tabs(),self._bb_grid(self._bb_action_tiles(lambda c:self._bb_log(c)))],spacing=6),padding=8)
            incomplete=self._bb_incompletes()
            sequences=self._bb_sequence_panel()
        else:
            actions=card(ft.Column([ft.Row([self._cat_tab(n,c) for n,c in [('Attack','#34d399'),('Defence','#818cf8'),('Cards','#fbbf24'),('Opposition','#f43f5e')]],wrap=True),self._build_category_grid(m)],spacing=6),padding=8)
            incomplete=self._build_incompletes_row()
            sequences=ft.Column([ft.Text(k.title()+': '+(v or '-'),selectable=True,size=11) for k,v in generate_sequences(m.events,'home').items()])
        self._portrait_clock=clock
        video_height=max(120,min(300,float(getattr(self.page,'height',None) or 800)*.28))
        view=ft.Container(content=ft.Column([
            top,
            ft.Container(content=ft.Stack([
                ft.Container(content=self._zoom_video_display_widget(),expand=True,alignment=ft.Alignment.CENTER,bgcolor='#000000'),
                ft.Container(content=ft.Row([
                    ft.IconButton(ft.Icons.ROTATE_RIGHT,tooltip='Rotate view',on_click=self._rotate_video_view),
                    ft.IconButton(ft.Icons.FLIP,tooltip='Mirror view',on_click=self._mirror_video_view),
                    self._video_zoom_buttons(),
                    ft.IconButton(ft.Icons.VIDEOCAM_OFF if self.camera_on else ft.Icons.VIDEOCAM,tooltip='Camera',on_click=self._stop_camera if self.camera_on else self._start_camera),
                ],spacing=2,scroll=ft.ScrollMode.AUTO),alignment=ft.Alignment.TOP_RIGHT),
            ],expand=True),height=video_height),
            ft.Column([actions,incomplete,sequences,ft.TextButton('Undo last event',on_click=lambda _:self._undo_last_event())],scroll=ft.ScrollMode.AUTO,expand=True,spacing=6),
        ],spacing=6,expand=True),padding=8,bgcolor='#020617',expand=True)
        return view
