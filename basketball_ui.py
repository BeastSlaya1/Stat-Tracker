"""Basketball controls shared by browser, desktop and Android."""
import flet as ft
from basketball import ACTIONS, DEFINITIONS, summary, display, report, on_court, INCOMPLETE_TYPES
from engine import make_event, recalculate_stats
from ui_widgets import card, action_btn, dual_stat_bar, kit_dot


class BasketballMixin:
    def _bb_toggle_timer(self, event=None):
        self._toggle_timer(event)
        self._save()

    def _bb_commit(self):
        recalculate_stats(self.match)
        self._save()
        self._full_refresh()

    def _bb_log(self, code, side="home", player_id="", tags=None, points=0):
        m = self.match
        if m.basketball_baseline is None:
            m.basketball_baseline = {"home": m.home_score, "away": m.away_score}
        team = getattr(m, side + "_team")
        player = None  # Basketball logging is team-only.
        tags = list(tags or [])
        if player and not player.is_starter:
            tags.append("bench")
        label = next((label for c, label, _ in ACTIONS if c == code), "Score correction")
        ev = make_event(m, side, "BB_" + code, team.short_name, label)
        ev.basketball = {"player_id": player.id if player else "", "period": m.period, "tags": tags, "points": points, "elapsed": m.basketball_elapsed}
        m.events.append(ev)
        self._bb_commit()

    def _bb_set_lineup(self, side, ids):
        m = self.match
        team = getattr(m, side + "_team")
        if len(ids) != 5 or len(set(ids)) != 5 or not set(ids).issubset({p.id for p in team.players}):
            self._snack("Select exactly five different players for the on-court lineup.")
            return
        ev = make_event(m, side, "BB_LINEUP", "Team", "On court: " + ", ".join(p.name for p in team.players if p.id in ids))
        ev.basketball = {"lineup": list(ids), "period": m.period, "elapsed": m.basketball_elapsed}
        if m.basketball_baseline is None:
            m.basketball_baseline = {"home": m.home_score, "away": m.away_score}
        m.events.append(ev)
        self._bb_commit()

    def _bb_roster_dialog(self, side):
        team = getattr(self.match, side + "_team")
        number = ft.TextField(label="Jersey number", keyboard_type=ft.KeyboardType.NUMBER)
        name = ft.TextField(label="Player name")
        position = ft.Dropdown(label="Position", value="Guard", options=[ft.dropdown.Option(p) for p in ("Point guard", "Shooting guard", "Guard", "Small forward", "Power forward", "Forward", "Center")])
        starter = ft.Checkbox(label="Started the game (uncheck for bench player)", value=True)
        error = ft.Text(color="#f43f5e")
        def add(_):
            from models import Player
            import uuid
            try:
                n = int(number.value)
                if n < 0 or n > 99 or not (name.value or "").strip():
                    raise ValueError()
                if any(p.number == n for p in team.players):
                    error.value = "That jersey number is already used on this team."
                    self.page.update()
                    return
            except (ValueError, TypeError):
                error.value = "Enter a name and a jersey number from 0 to 99."
                self.page.update()
                return
            team.players.append(Player(uuid.uuid4().hex, n, name.value.strip(), position.value, is_starter=starter.value))
            self.page.pop_dialog()
            self._save()
            self._full_refresh()
        self.page.show_dialog(ft.AlertDialog(title=ft.Text("Add basketball player — " + team.name), content=ft.Column([name, number, position, starter, error], tight=True), actions=[ft.TextButton("Cancel", on_click=lambda _: self.page.pop_dialog()), ft.Button("Add player", on_click=add)]))

    def _bb_choose_period(self, period):
        m = self.match
        with self._timer_lock:
            self._timer_running = False
        m.period = period
        m.minute = m.second = 0
        m.is_live = False
        self._save()
        self._full_refresh()

    def _build_basketball_scoreboard(self, m):
        return self._build_scoreboard_compact(m)

    def _bb_last_completable(self):
        m = self.match
        if not m or not m.events:
            return None
        e = m.events[-1]
        if e.team_id != getattr(self, "_bb_side", "home"):
            return None
        return e if e.event_type.removeprefix("BB_") in INCOMPLETE_TYPES else None

    def _bb_mark_incomplete(self, code):
        original = self._bb_last_completable()
        if not original or original.event_type != "BB_" + code:
            return
        event = make_event(self.match, original.team_id, "BB_INCOMPLETE", original.player_name, "Marked incomplete: " + original.description)
        event.basketball = {**original.basketball, "target_id": original.id, "elapsed": self.match.basketball_elapsed}
        self.match.events.append(event)
        self._bb_commit()

    def _bb_tabs(self):
        current = getattr(self, "_bb_category", "Attack")
        def select(value):
            self._bb_category = value
            self._full_refresh()
        return ft.Row([ft.Container(content=ft.Text(name, size=10, color=color if current == name else "#64748b", weight=ft.FontWeight.BOLD), bgcolor=color+"22" if current == name else "transparent", border=ft.Border.all(1,color+"44" if current == name else "#1e293b"), border_radius=8, padding=ft.Padding.symmetric(horizontal=10,vertical=4), on_click=lambda _,n=name:select(n),ink=True) for name,color in [("Attack","#34d399"),("Defence","#818cf8"),("Cards","#fbbf24")]],spacing=6)

    def _bb_action_tiles(self, log, width=None):
        groups = {
            "Attack": [("2_MADE","#34d399"),("3_MADE","#818cf8"),("FT_MADE","#38bdf8"),("AST","#22d3ee"),("OREB","#c084fc"),("FD","#fbbf24")],
            "Defence": [("DREB","#818cf8"),("STL","#34d399"),("BLK","#38bdf8"),("BA","#f43f5e"),("CHARGE","#fbbf24"),("DEFLECTION","#22d3ee"),("LOOSE","#c084fc"),("PF","#f87171")],
            "Cards": [("TF","#fbbf24"),("UF","#fb923c"),("DF","#f43f5e")],
        }
        labels = {code:label for code,label,_ in ACTIONS}
        return [action_btn(labels[code], ft.Icons.SPORTS_BASKETBALL if code.endswith("MADE") else ft.Icons.STYLE if code in ("TF","UF","DF") else ft.Icons.SPORTS, color,lambda _,c=code:log(c),width=width) for code,color in groups.get(getattr(self,"_bb_category","Attack"),groups["Attack"])]

    def _bb_grid(self, tiles):
        available = max(200, self._layout_width() - 92)
        columns = max(1, min(6, int(available // 150)))
        tile_width = (available - 6 * (columns - 1)) / columns
        tile_height = max(48, tile_width / 2.5)
        rows = (len(tiles) + columns - 1) // columns
        return ft.GridView(controls=tiles,runs_count=columns,child_aspect_ratio=tile_width/tile_height,spacing=6,run_spacing=6,height=rows*(tile_height+6))

    def _bb_incompletes(self, vertical=False):
        last = self._bb_last_completable()
        code = last.event_type.removeprefix("BB_") if last else None
        labels = {"2_MADE":"2-point shot", "3_MADE":"3-point shot", "FT_MADE":"Free throw", "STL":"Steal", "BLK":"Block", "OREB":"Off. rebound", "DREB":"Def. rebound", "DEFLECTION":"Deflection", "LOOSE":"Loose ball"}
        tiles = [action_btn(label+" ✗",ft.Icons.CLOSE,"#f43f5e" if code==key else "#64748b",lambda _,k=key:self._bb_mark_incomplete(k),disabled=code!=key,width=150 if vertical else None) for key,label in labels.items()]
        status = "Mark " + labels[code] + " as incomplete" if code else "Incompletes — press an action button first"
        contents = [ft.Text("INCOMPLETES" if vertical else "Incompletes",size=12,weight=ft.FontWeight.BOLD,color="#94a3b8")]
        if not vertical: contents.append(ft.Text(status,size=9,color="#64748b"))
        contents += tiles if vertical else [self._bb_grid(tiles)]
        return ft.Container(content=ft.Column(contents,spacing=6,scroll=ft.ScrollMode.AUTO if vertical else None,expand=vertical),bgcolor="#0f172a",border=ft.Border.all(1,"#1e293b"),border_radius=10,padding=10,width=170 if vertical else None)

    def _build_basketball_logger(self, m):
        side = getattr(self, "_bb_side", "home")
        team = getattr(m, side + "_team")
        def change_team(e):
            self._bb_side = e.control.value
            self._full_refresh()
        tags = [ft.Checkbox(label=label, value=False) for label in ("In the paint (2-point shots)", "Fast break", "Second chance", "After turnover")]
        tag_keys = ["paint", "fastbreak", "secondchance", "offturnover"]
        def log(code):
            selected_tags = [k for k, c in zip(tag_keys, tags) if c.value]
            self._bb_log(code, side, tags=selected_tags)
        period_values = ["Q1", "Q2", "Q3", "Q4"] + [f"OT{i}" for i in range(1, 11)] + ["FULL_TIME"]
        period = ft.Dropdown(label="Period", value=m.period if m.period in period_values else None, options=[ft.dropdown.Option(p, p.replace("_", " ")) for p in period_values], on_select=lambda e: self._bb_choose_period(e.control.value))
        correction = ft.TextField(label="Score correction (+ or − points)", value="0", keyboard_type=ft.KeyboardType.NUMBER, width=200, on_focus=self._mark_input_focused, on_blur=self._mark_input_blurred)
        def correct(_):
            try:
                n = int(correction.value)
                if not -1000 <= n <= 1000 or getattr(m, side + "_score") + n < 0:
                    raise ValueError()
            except (ValueError, TypeError):
                self._snack("Enter whole points; the score cannot become negative.")
                return
            if n:
                self._bb_log("ADJUSTMENT", side, points=n)
        labels = {c: label for c, label, _ in ACTIONS}
        def button(code, color):
            return action_btn(labels[code],ft.Icons.SPORTS_BASKETBALL,color,lambda _:log(code))
        actions = card(ft.Column([
            ft.Row([ft.Icon(ft.Icons.GRID_VIEW,size=14,color="#818cf8"),ft.Text("Actions",size=13,weight=ft.FontWeight.BOLD),self._bb_tabs()],spacing=8),
            ft.Divider(height=1,color="#1e293b"),self._bb_grid(self._bb_action_tiles(log)),
        ],spacing=10),padding=14)
        missed = self._bb_incompletes()
        # Match soccer's video-first layout, action cards, quick rows and time controls.
        rows = [
            self._build_live_video_panel(),
            ft.Row([ft.Dropdown(label="Logging for", value=side, width=220, options=[ft.dropdown.Option("home", m.home_team.name), ft.dropdown.Option("away", m.away_team.name)], on_select=change_team)], wrap=True),
            actions, missed,
            self._quick_row("Turnover", "🔁", "#f43f5e", lambda _: log("TO")),
            card(ft.Column([ft.Text("Scoring context", weight=ft.FontWeight.BOLD), ft.Row(tags, wrap=True)]), padding=14),
            card(ft.Column([
                ft.Text("Time Controllers", weight=ft.FontWeight.BOLD),
                ft.Row([action_btn("Pause" if self._timer_running else "Start", ft.Icons.PAUSE if self._timer_running else ft.Icons.PLAY_ARROW, "#34d399", self._bb_toggle_timer, disabled=m.period == "FULL_TIME"),
                    action_btn("Full Time", ft.Icons.FLAG, "#f43f5e", lambda _: self._bb_choose_period("FULL_TIME")), button("TIMEOUT", "#818cf8")], wrap=True), period,
            ], spacing=10), padding=14),
            ft.Row([action_btn("Undo last event", ft.Icons.UNDO, "#fbbf24", lambda _: self._undo_last_event()), ft.TextButton("Dictionary", on_click=self._open_dictionary_dialog)], wrap=True),
            ft.ExpansionTile(title=ft.Text("Score correction"), controls=[ft.Row([correction, ft.TextButton("Apply correction", on_click=correct)], wrap=True)]),
        ]
        # Detailed guidance belongs under Dictionary > Basketball rules.
        return ft.Container(content=ft.Column(rows, scroll=ft.ScrollMode.AUTO, spacing=8, expand=True), bgcolor="#020617", padding=12, expand=True)

    def _build_basketball_fullscreen(self, m):
        if self._layout_width() < 900:
            return ft.Container(content=ft.Column([ft.TextButton("Exit fullscreen", on_click=self._exit_fullscreen_video), self._responsive_controls(self._build_basketball_logger(m))], expand=True), expand=True)
        side = getattr(self, "_bb_side", "home")
        def log(code):
            self._bb_log(code, side)
        def change_team(e):
            self._bb_side = e.control.value
            self._full_refresh()
        panel_color, border = "#0f172acc", "#1e293b99"
        def panel(content, width=None):
            return ft.Container(content=content, bgcolor=panel_color, border=ft.Border.all(1,border), border_radius=10, padding=10, width=width if width is not None else float("inf"))
        self._bb_clock_text = ft.Text(f"{m.period} • {m.minute}'{m.second:02d}\"", size=14, weight=ft.FontWeight.BOLD)
        score_controls = []
        for team, color in [("home","#818cf8"),("away","#34d399")]:
            score_controls += [ft.Text(getattr(m,team+"_team").short_name,color=color),ft.IconButton(icon=ft.Icons.REMOVE,on_click=lambda _,t=team:self._update_score(t,-1)),ft.Text(str(getattr(m,team+"_score")),size=22,weight=ft.FontWeight.BOLD,color=color),ft.IconButton(icon=ft.Icons.ADD,on_click=lambda _,t=team:self._update_score(t,1))]
        top = panel(ft.Row([
            ft.IconButton(icon=ft.Icons.FULLSCREEN_EXIT,tooltip="Exit fullscreen",on_click=self._exit_fullscreen_video),
            *score_controls,
            ft.IconButton(icon=ft.Icons.PAUSE if self._timer_running else ft.Icons.PLAY_ARROW,on_click=self._bb_toggle_timer,disabled=m.period=="FULL_TIME"),self._bb_clock_text,
            ft.Dropdown(value=m.period if m.period in ["Q1","Q2","Q3","Q4"]+[f"OT{i}" for i in range(1,11)]+["FULL_TIME"] else "Q1",width=115,options=[ft.dropdown.Option(p) for p in ["Q1","Q2","Q3","Q4"]+[f"OT{i}" for i in range(1,11)]+["FULL_TIME"]],on_select=lambda e:self._bb_choose_period(e.control.value)),
            ft.Button("Full Time",on_click=lambda _:self._bb_choose_period("FULL_TIME")),
        ],spacing=6,wrap=True,alignment=ft.MainAxisAlignment.CENTER))
        right = panel(ft.Column([
            ft.Dropdown(label="Logging for",value=side,options=[ft.dropdown.Option("home",m.home_team.name),ft.dropdown.Option("away",m.away_team.name)],on_select=change_team),
            self._bb_tabs(),ft.Divider(height=1,color=border),
            *[ft.Container(content=tile,height=48) for tile in self._bb_action_tiles(log,width=210)],
            ft.Divider(height=1,color=border),
            action_btn("Turnover",ft.Icons.SYNC_ALT,"#f43f5e",lambda _:log("TO"),width=210),
            action_btn("Timeout",ft.Icons.TIMER,"#38bdf8",lambda _:log("TIMEOUT"),width=210),
            ft.TextButton("Dictionary",on_click=self._open_dictionary_dialog),
        ],spacing=6,scroll=ft.ScrollMode.AUTO,expand=True),230)
        bottom = panel(ft.Row([
            ft.Text("CARDS",size=9,color="#94a3b8"),
            action_btn("Technical",ft.Icons.STYLE,"#fbbf24",lambda _:log("TF"),width=130),
            action_btn("Unsportsmanlike",ft.Icons.STYLE,"#fb923c",lambda _:log("UF"),width=170),
            action_btn("Disqualifying",ft.Icons.STYLE,"#f43f5e",lambda _:log("DF"),width=150),
            ft.Button("Undo Last",icon=ft.Icons.UNDO,on_click=lambda _:self._undo_last_event()),
        ],spacing=8,wrap=True))
        video = ft.Container(content=ft.Stack([
            ft.Container(content=self._zoom_video_display_widget(),bgcolor="#020617",border=ft.Border.all(1,border),border_radius=12,alignment=ft.Alignment.CENTER,expand=True),
            ft.Container(content=ft.Text("LIVE" if self.camera_on else "OFF",size=10),padding=10),
            ft.Container(content=ft.Row([self._rotate_view_button(),self._mirror_view_button(), self._video_zoom_buttons(),ft.IconButton(icon=ft.Icons.VIDEOCAM_OFF if self.camera_on else ft.Icons.VIDEOCAM,on_click=self._stop_camera if self.camera_on else self._start_camera)],tight=True),padding=8,alignment=ft.Alignment.TOP_RIGHT),
        ],expand=True),expand=True)
        self.fs_left_slot.content=self._bb_incompletes(vertical=True)
        self.fs_top_slot.content=top
        self.fs_video_slot.content=video
        self.fs_bottom_slot.content=bottom
        self.fs_right_slot.content=right
        if self._fs_skeleton is None:
            self._fs_skeleton=ft.Container(content=ft.Row([
                ft.Container(content=self.fs_left_slot),
                ft.Container(content=ft.Column([self.fs_top_slot,self.fs_video_slot,self.fs_bottom_slot],spacing=8,expand=True),expand=True),
                ft.Container(content=self.fs_right_slot),
            ],spacing=8,expand=True),bgcolor="#020617",padding=8,expand=True)
        return self._fs_skeleton

    def _build_basketball_stats(self, m):
        data = summary(m)
        ht, at = m.home_team, m.away_team
        header = ft.Row([
            ft.Row([kit_dot(ht.logo_color), ft.Text(ht.short_name, weight=ft.FontWeight.BOLD)]),
            ft.Text("LIVE STAT COMPARISON", expand=True, text_align=ft.TextAlign.CENTER, size=10, color="#94a3b8"),
            ft.Row([ft.Text(at.short_name, weight=ft.FontWeight.BOLD), kit_dot(at.logo_color)]),
        ])
        def bar(key):
            h, a = data["home"]["team"][key], data["away"]["team"][key]
            # Missing rates remain a dash; negative efficiency values do not become bar widths.
            return dual_stat_bar(DEFINITIONS[key][0], display(h), display(a), max(0, h or 0), max(0, a or 0), ht.logo_color, at.logo_color)
        primary = ["PTS", "FGM", "FGA", "FG%", "3M", "3A", "3%", "FTM", "FTA", "FT%", "OREB", "DREB", "REB", "AST", "STL", "BLK", "TO", "PF"]
        extra = [k for k in data["home"]["team"] if k not in primary and k not in ("DD", "TD", "BENCH")]
        rows = [
            card(ft.Column([
                ft.Row([ft.Icon(ft.Icons.RADAR, size=14, color="#818cf8"), ft.Text("Radar Comparison", weight=ft.FontWeight.BOLD)]),
                ft.Divider(height=1, color="#1e293b"),
                ft.Row([self._build_radar_chart_canvas(m), ft.Column([
                    ft.Row([kit_dot(ht.logo_color), ft.Text(ht.short_name)]), ft.Row([kit_dot(at.logo_color), ft.Text(at.short_name)]),
                    ft.Text("Points · Rebounds · Assists\nSteals · Blocks · Field goals made", size=10, color="#94a3b8"),
                ])], wrap=True),
            ], spacing=10)),
            card(ft.Column([header, ft.Divider(height=1, color="#1e293b"), *[bar(k) for k in primary]], spacing=10)),
            card(ft.ExpansionTile(title=ft.Text("More basketball stats"), controls=[ft.Column([bar(k) for k in extra], spacing=10)])),
        ]
        if m.basketball_baseline and any(m.basketball_baseline.values()):
            rows.append(ft.Text("Historical score carried forward: " + str(m.basketball_baseline)))
        rows.append(card(ft.Column([ft.Text("Score by period", weight=ft.FontWeight.BOLD), *[ft.Text(f"{getattr(m, side + '_team').short_name}: " + " · ".join(f"{period}: {points}" for period, points in info["periods"].items())) for side, info in data.items()]])))
        return ft.Column(rows, scroll=ft.ScrollMode.AUTO, spacing=8, expand=True)

    def _export_basketball(self):
        self.page.run_task(self._export_txt_async, f"basketball-{self.match.id}.txt", report(self.match))
