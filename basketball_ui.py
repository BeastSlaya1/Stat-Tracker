"""Basketball controls shared by browser, desktop and Android."""
import flet as ft
from basketball import ACTIONS, DEFINITIONS, summary, display, report, on_court, INCOMPLETE_TYPES, PENALTY_TYPES, sequences
from engine import make_event, recalculate_stats
from ui_widgets import card, action_btn, dual_stat_bar, kit_dot


class BasketballMixin:
    def _bb_toggle_timer(self, event=None):
        self._bb_conversion_target = None
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
        self._bb_conversion_target = None
        if code == "ADJUSTMENT" and side == "away":
            code = "OPPONENT_SCORE"
        side = "home"  # All newly logged actions belong to SCC.
        team = m.home_team
        player = None  # Basketball logging is team-only.
        tags = list(tags or [])
        if player and not player.is_starter:
            tags.append("bench")
        label = next((label for c, label, _ in ACTIONS if c == code), "Score correction")
        ev = make_event(m, side, "BB_" + code, team.short_name, label)
        ev.basketball = {"player_id": player.id if player else "", "period": m.period, "tags": tags, "points": points, "elapsed": m.basketball_elapsed}
        m.events.append(ev)
        if code in ("SHOT", "SHOT_AGAINST"): self._bb_conversion_target = (m.id, ev.id)
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

    def _bb_end_quarter(self, _=None):
        self._timer_running = False
        self.match.is_live = False
        self._bb_log('END_QUARTER')

    def _bb_choose_period(self, period):
        m = self.match
        self._bb_conversion_target = None
        with self._timer_lock:
            self._timer_running = False
        if period == "FULL_TIME" and m.period != "FULL_TIME": self._bb_log("FULL_TIME")
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
        if e.team_id != "home":
            return None
        return e if e.event_type.removeprefix("BB_") in INCOMPLETE_TYPES else None

    def _bb_mark_incomplete(self, code):
        self._bb_conversion_target = None
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
            self._bb_conversion_target = None
            self._bb_category = value
            self._full_refresh()
        return ft.Row([ft.Container(content=ft.Text(name, size=10, color=color if current == name else "#64748b", weight=ft.FontWeight.BOLD), bgcolor=color+"22" if current == name else "transparent", border=ft.Border.all(1,color+"44" if current == name else "#1e293b"), border_radius=8, padding=ft.Padding.symmetric(horizontal=10,vertical=4), on_click=lambda _,n=name:select(n),ink=True) for name,color in [("Attack","#34d399"),("Defence","#818cf8"),("Cards","#fbbf24")]],spacing=6)

    def _bb_action_tiles(self, log, width=None):
        groups = {
            "Attack": [("SHORT_PASS","#22d3ee"),("LONG_PASS","#818cf8"),("DRIBBLE","#fbbf24"),("LAYUP","#34d399"),("SHOT","#818cf8"),("AST","#22d3ee"),("OREB","#c084fc")],
            "Defence": [("SHOT_AGAINST","#818cf8"),("DREB","#818cf8"),("STL","#34d399"),("BLK","#38bdf8"),("BA","#f43f5e"),("DEFLECTION","#22d3ee"),("LOOSE","#c084fc")],
            "Cards": [("TF","#fbbf24"),("UF","#fb923c"),("DF","#f43f5e")],
        }
        labels = {code:label for code,label,_ in ACTIONS}
        tiles = [action_btn(labels[code], ft.Icons.SPORTS_BASKETBALL if code.endswith("MADE") else ft.Icons.STYLE if code in ("TF","UF","DF") else ft.Icons.SPORTS, color,lambda _,c=code:log(c),width=width) for code,color in groups.get(getattr(self,"_bb_category","Attack"),groups["Attack"])]
        category = getattr(self, "_bb_category", "Attack")
        if category in ("Attack", "Defence"):
            tiles.append(action_btn("Conversion", ft.Icons.CHECK_CIRCLE, "#34d399", self._bb_open_conversion, disabled=self._bb_conversion_event() is None, width=width))
        if category in ("Attack", "Defence"):
            tiles.append(self._bb_penalty_button(category.lower(), width))
        return tiles

    def _bb_conversion_event(self):
        m = self.match
        if not m or not m.events: return None
        e = m.events[-1]
        return e if e.event_type in ("BB_SHOT", "BB_SHOT_AGAINST") and e.team_id == "home" and getattr(self, "_bb_conversion_target", None) == (m.id, e.id) else None

    def _bb_open_conversion(self, _=None):
        original = self._bb_conversion_event()
        if original is None: return
        m = self.match
        prefix = "As" if original.event_type == "BB_SHOT_AGAINST" else "S"
        self._bb_conversion_target = None  # Opening consumes the one-use opportunity.
        options = ft.RadioGroup(content=ft.Row([ft.Radio(value=str(n), label=f"{n} point" + ("s" if n != 1 else "")) for n in (1, 2, 3)]))
        assist = ft.Checkbox(label="Assist", value=False)
        preview = ft.Text("Choose the point value")
        confirm = ft.Button("Record conversion", disabled=True)
        def choose(_):
            confirm.disabled = options.value not in ("1", "2", "3")
            preview.value = prefix + "^" + ("A" if assist.value else "") + options.value if not confirm.disabled else "Choose the point value"
            self.page.update()
        options.on_change = choose
        assist.on_change = choose
        def record(_):
            if options.value not in ("1", "2", "3"): return
            if self.match is not m or not m.events or m.events[-1].id != original.id:
                self.page.pop_dialog(); return
            points = int(options.value)
            code = prefix + "^" + ("A" if assist.value else "") + str(points)
            e = make_event(m, "home", "BB_CONVERSION", m.home_team.short_name, code)
            e.basketball = {**original.basketball, "target_id": original.id, "points": points, "assist": bool(assist.value)}
            m.events.append(e)
            self.page.pop_dialog()
            self._bb_commit()
        confirm.on_click = record
        self._full_refresh()
        self.page.show_dialog(ft.AlertDialog(title=ft.Text("Shot against conversion" if prefix == "As" else "Shot conversion"), content=ft.Column([options, assist, preview], tight=True), actions=[ft.TextButton("Cancel", on_click=lambda _:self.page.pop_dialog()), confirm]))

    def _bb_penalty_button(self, direction, width=None):
        def opened(_):
            self._bb_conversion_target = None
        def record(code, label):
            m = self.match
            self._bb_conversion_target = None
            if m.basketball_baseline is None:
                m.basketball_baseline = {"home": m.home_score, "away": m.away_score}
            e = make_event(m, "home", "BB_PENALTY", m.home_team.short_name, label + (" awarded to SCC" if direction == "attack" else " awarded against SCC"))
            e.basketball = {"direction": direction, "penalty_type": code, "period": m.period, "elapsed": m.basketball_elapsed}
            m.events.append(e)
            self._bb_commit()
        return ft.PopupMenuButton(content=action_btn("Penalty", ft.Icons.FLAG, "#fbbf24", None, width=width), width=width, padding=0, tooltip="Awarded to SCC" if direction == "attack" else "Awarded against SCC", on_open=opened, on_cancel=lambda _:self._full_refresh(), items=[ft.PopupMenuItem(content=label, on_click=lambda _,c=code,l=label:record(c,l)) for code,label in PENALTY_TYPES])

    def _bb_sequence_panel(self):
        data = sequences(self.match.events)
        return ft.Column([ft.Text(label.title() + ": " + (value or "-"), size=11, selectable=True) for label,value in data.items()], spacing=4)

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
        labels = {"SHORT_PASS":"Short pass", "LONG_PASS":"Long pass", "DRIBBLE":"Dribble", "LAYUP":"Layup", "SHOT":"Shot", "SHOT_AGAINST":"Shot against", "2_MADE":"2-point shot", "3_MADE":"3-point shot", "FT_MADE":"Free throw", "STL":"Steal", "BLK":"Block", "OREB":"Off. rebound", "DREB":"Def. rebound", "DEFLECTION":"Deflection", "LOOSE":"Loose ball"}
        labels = {k:v for k,v in labels.items() if k not in ("2_MADE","3_MADE","FT_MADE") or code == k}
        tiles = [action_btn(label+" !",ft.Icons.CLOSE,"#f43f5e" if code==key else "#64748b",lambda _,k=key:self._bb_mark_incomplete(k),disabled=code!=key,width=150 if vertical else None) for key,label in labels.items()]
        status = "Mark " + labels[code] + " as incomplete" if code else "Incompletes — press an action button first"
        contents = [ft.Text("INCOMPLETES" if vertical else "Incompletes",size=12,weight=ft.FontWeight.BOLD,color="#94a3b8")]
        if not vertical: contents.append(ft.Text(status,size=9,color="#64748b"))
        contents += tiles if vertical else [self._bb_grid(tiles)]
        return ft.Container(content=ft.Column(contents,spacing=6,scroll=ft.ScrollMode.AUTO if vertical else None,expand=vertical),bgcolor="#0f172a",border=ft.Border.all(1,"#1e293b"),border_radius=10,padding=10,width=170 if vertical else None)

    def _build_basketball_logger(self, m):
        side = "home"
        team = getattr(m, side + "_team")
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
            ft.Text("Logging for SCC - St Charles College", weight=ft.FontWeight.BOLD),
            actions, missed, self._bb_sequence_panel(),
            self._quick_row("Turnover", "🔁", "#f43f5e", lambda _: log("TO")),
            card(ft.Column([ft.Text("Scoring context", weight=ft.FontWeight.BOLD), ft.Row(tags, wrap=True)]), padding=14),
            card(ft.Column([
                ft.Text("Time Controllers", weight=ft.FontWeight.BOLD),
                ft.Row([action_btn("Pause" if self._timer_running else "Start", ft.Icons.PAUSE if self._timer_running else ft.Icons.PLAY_ARROW, "#34d399", self._bb_toggle_timer, disabled=m.period == "FULL_TIME"),
                    action_btn("Full time", ft.Icons.FLAG, "#f43f5e", lambda _: self._bb_choose_period("FULL_TIME")), button("TIMEOUT", "#818cf8"), button("SUBSTITUTION", "#38bdf8"), action_btn("End of quarter",ft.Icons.TIMER,"#fbbf24",self._bb_end_quarter)], wrap=True), period,
            ], spacing=10), padding=14),
            ft.Row([action_btn("Undo last event", ft.Icons.UNDO, "#fbbf24", lambda _: self._undo_last_event()), ft.TextButton("Dictionary", on_click=self._open_dictionary_dialog)], wrap=True),
            ft.ExpansionTile(title=ft.Text("Score correction"), controls=[ft.Row([correction, ft.TextButton("Apply correction", on_click=correct)], wrap=True)]),
        ]
        # Detailed guidance belongs under Dictionary > Basketball rules.
        return ft.Container(content=ft.Column(rows, scroll=ft.ScrollMode.AUTO, spacing=8, expand=True), bgcolor="#020617", padding=12, expand=True)

    def _build_basketball_fullscreen(self, m):
        if self._layout_width() < 900:
            return ft.Container(content=ft.Column([ft.TextButton("Exit fullscreen", on_click=self._exit_fullscreen_video), self._responsive_controls(self._build_basketball_logger(m))], expand=True), expand=True)
        side = "home"
        def log(code):
            self._bb_log(code, side)
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
            ft.Button("Full time",on_click=lambda _:self._bb_choose_period("FULL_TIME")),
        ],spacing=6,wrap=True,alignment=ft.MainAxisAlignment.CENTER))
        right = panel(ft.Column([
            ft.Text("SCC - St Charles College", weight=ft.FontWeight.BOLD),
            self._bb_tabs(),ft.Divider(height=1,color=border),
            *[ft.Container(content=tile,height=48) for tile in self._bb_action_tiles(log,width=210)],
            ft.Divider(height=1,color=border),
            action_btn("Turnover",ft.Icons.SYNC_ALT,"#f43f5e",lambda _:log("TO"),width=210),
            action_btn("Timeout",ft.Icons.TIMER,"#38bdf8",lambda _:log("TIMEOUT"),width=210),
            action_btn("Substitution",ft.Icons.SWAP_HORIZ,"#38bdf8",lambda _:log("SUBSTITUTION"),width=210),
            action_btn("End of quarter",ft.Icons.TIMER,"#fbbf24",self._bb_end_quarter,width=210),
            ft.TextButton("Dictionary",on_click=self._open_dictionary_dialog),
        ],spacing=6,scroll=ft.ScrollMode.AUTO,expand=True),230)
        bottom = panel(ft.Column([ft.Row([
            ft.Text("CARDS",size=9,color="#94a3b8"),
            action_btn("Technical",ft.Icons.STYLE,"#fbbf24",lambda _:log("TF"),width=130),
            action_btn("Unsportsmanlike",ft.Icons.STYLE,"#fb923c",lambda _:log("UF"),width=170),
            action_btn("Disqualifying",ft.Icons.STYLE,"#f43f5e",lambda _:log("DF"),width=150),
            ft.Button("Undo Last",icon=ft.Icons.UNDO,on_click=lambda _:self._undo_last_event()),
        ],spacing=8,wrap=True), self._bb_sequence_panel()]))
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
        return self._build_scc_stats(m)

    def _export_basketball(self):
        self.page.run_task(self._export_txt_async, f"basketball-{self.match.id}.txt", report(self.match))
