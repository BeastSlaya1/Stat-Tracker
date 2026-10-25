"""Basketball controls shared by browser, desktop and Android."""
import flet as ft
from basketball import ACTIONS, DEFINITIONS, summary, display, report, on_court, INCOMPLETE_TYPES, PENALTY_TYPES, sequences
from engine import make_event, recalculate_stats
from ui_widgets import update_layout, card, action_btn, dual_stat_bar, kit_dot


BASKETBALL_PERIODS = [p for i in range(1,5) for p in (f"Q{i}",f"OT{i}")] + ["FULL_TIME"]


class BasketballMixin:
    def _bb_toggle_timer(self, event=None):
        if not self._live_time_only(): return
        if not self._timer_running:
            self._bb_apply_starting_five(self.match.period)
        self._bb_conversion_target = None
        self._toggle_timer(event)
        self._save()

    def _bb_commit(self):
        recalculate_stats(self.match)
        self._save()
        self._full_refresh()

    def _bb_log(self, code, side="home", player_id="", tags=None, points=0):
        m = self.match
        if not self._live_require_key(code):return
        if code in ("TO","TIMEOUT","SUBSTITUTION","LINEUP","OVERTIME","END_QUARTER","FULL_TIME") and not self._live_time_only(): return
        from stat_policy import TEAM_ACTIONS
        player = self._selected_player() if code not in TEAM_ACTIONS else None
        if code not in TEAM_ACTIONS and player is None:
            self._snack('Select an assigned jersey before recording this stat.');return
        if code == "TO" and not self._live_guest():
            m.possession_team = "away" if m.possession_team != "away" else "home"
        if code == "TIMEOUT":
            with self._timer_lock:
                self._timer_running = False
                m.is_live = False
        if m.basketball_baseline is None:
            m.basketball_baseline = {"home": m.home_score, "away": m.away_score}
        self._bb_conversion_target = None
        if code == "ADJUSTMENT" and side == "away":
            code = "OPPONENT_SCORE"
        side = "home"  # All newly logged actions belong to SCC.
        team = m.home_team
        tags = list(tags or [])
        if player and not player.is_starter:
            tags.append("bench")
        label = next((label for c, label, _ in ACTIONS if c == code), "Score correction")
        ev = make_event(m, side, "BB_" + code, "#"+str(player.number) if player else team.short_name, label)
        ev.basketball = {"player_id": player.id if player else "", "jersey":player.number if player else None, "period": m.period, "tags": tags, "points": points, "elapsed": m.basketball_elapsed}
        m.events.append(ev)
        if code in ("SHOT", "SHOT_AGAINST"): self._bb_conversion_target = (m.id, ev.id)
        self._bb_commit()

    def _bb_set_lineup(self, side, ids, period=None, starting=False):
        m = self.match
        if not self._live_time_only(): return
        team = getattr(m, side + "_team")
        period = period or m.period
        active_ids = {p.id for p in team.players if p.active}
        if len(ids) != 5 or len(set(ids)) != 5 or not set(ids).issubset(active_ids):
            self._snack("Select exactly five different players for the on-court lineup.")
            return
        if starting and side == "home":
            m.basketball_starting_lineups = dict(getattr(m, "basketball_starting_lineups", {}) or {})
            m.basketball_starting_lineups[period] = list(ids)
        if period != m.period:
            ev = make_event(m, side, "BB_LINEUP_PLAN", "Team", "Starting five for " + period + ": " + ", ".join("#"+str(p.number) for p in team.players if p.id in ids))
            ev.basketball = {"lineup": list(ids), "period": period, "elapsed": m.basketball_elapsed}
            m.events.append(ev)
            self._save()
            self._full_refresh()
            return
        ev = make_event(m, side, "BB_LINEUP", "Team", "On court: " + ", ".join("#"+str(p.number) for p in team.players if p.id in ids))
        ev.basketball = {"lineup": list(ids), "period": period, "elapsed": m.basketball_elapsed}
        if m.basketball_baseline is None:
            m.basketball_baseline = {"home": m.home_score, "away": m.away_score}
        m.events.append(ev)
        self._bb_commit()

    def _bb_apply_starting_five(self, period):
        m = self.match
        if not m or period not in BASKETBALL_PERIODS[:-1]: return
        lineup = (getattr(m, "basketball_starting_lineups", {}) or {}).get(period)
        if not lineup:
            lineup = next((e.basketball.get("lineup", []) for e in reversed(m.events)
                           if e.team_id == "home" and e.event_type == "BB_LINEUP_PLAN"
                           and e.basketball.get("period") == period), [])
        if not lineup: return
        current = next((e.basketball.get("lineup", []) for e in reversed(m.events)
                        if e.team_id == "home" and e.event_type == "BB_LINEUP"
                        and e.basketball.get("period") == period), [])
        if current != lineup:
            self._bb_set_lineup("home", list(lineup), period=period)

    def _bb_starting_five_dialog(self, _=None, selected_period=None):
        if not self._live_time_only(): return
        m = self.match
        default_period = selected_period or (m.period if m.period in BASKETBALL_PERIODS[:-1] else "Q1")
        period = ft.Dropdown(label="Quarter", value=default_period,
            options=[ft.dropdown.Option(p,p.replace("OT","OT ").replace("Q","Q ")) for p in BASKETBALL_PERIODS[:-1]])
        checks = [ft.Checkbox(label="#"+str(p.number), value=False, data=p.id) for p in m.home_team.players if p.active]
        def load_period(_=None):
            target = period.value
            saved = (getattr(m,"basketball_starting_lineups",{}) or {}).get(target, [])
            if not saved:
                saved = next((e.basketball.get("lineup", []) for e in reversed(m.events)
                              if e.team_id == "home" and e.event_type == "BB_LINEUP_PLAN"
                              and e.basketball.get("period") == target), [])
            if target == m.period and not saved:
                saved = on_court(m,"home")
            for check in checks: check.value = check.data in saved
            self.page.update()
        period.on_select = load_period
        load_period()
        save = ft.Button("Save starting five", disabled=True)
        def update_save(_=None):
            save.disabled = sum(bool(c.value) for c in checks) != 5
            self.page.update()
        for check in checks: check.on_change = update_save
        def commit(_):
            ids = [c.data for c in checks if c.value]
            if len(ids) != 5: return
            self.page.pop_dialog()
            self._bb_set_lineup("home",ids,period=period.value,starting=True)
        save.on_click = commit
        update_save()
        self.page.show_dialog(ft.AlertDialog(title=ft.Text("Starting five by quarter"),
            content=ft.Column([period,ft.Text("Choose five active jerseys for SCC."),ft.Row(checks,wrap=True)],tight=True,scroll=ft.ScrollMode.AUTO),
            actions=[ft.TextButton("Cancel",on_click=lambda _:self.page.pop_dialog()),save]))

    def _bb_substitution_dialog(self, _=None):
        if not self._live_time_only() or not self._live_require_key("SUBSTITUTION"): return
        m = self.match
        current = next((e.basketball.get("lineup", []) for e in reversed(m.events)
                        if e.team_id == "home" and e.event_type == "BB_LINEUP"
                        and e.basketball.get("period") == m.period), [])
        saved = (getattr(m,"basketball_starting_lineups",{}) or {}).get(m.period, [])
        if not saved:
            saved = next((e.basketball.get("lineup", []) for e in reversed(m.events)
                          if e.team_id == "home" and e.event_type == "BB_LINEUP_PLAN"
                          and e.basketball.get("period") == m.period), [])
        if len(current) != 5 and len(saved) == 5:
            current = list(saved)
            self._bb_set_lineup("home",current)
        elif len(current) != 5:
            current = on_court(m,"home")
        roster = [p for p in m.home_team.players if p.active]
        outgoing = ft.Dropdown(label="Player leaving",options=[ft.dropdown.Option(p.id,"#"+str(p.number)) for p in roster if p.id in current])
        incoming = ft.Dropdown(label="Player entering",options=[ft.dropdown.Option(p.id,"#"+str(p.number)) for p in roster if p.id not in current])
        save = ft.Button("Record substitution",disabled=len(current)!=5)
        if len(current)!=5:
            hint=ft.Text("Set a starting five for this quarter before making a substitution.")
        else:
            hint=ft.Text("Choose one player on court and one active bench player.")
        def validate(_=None):
            save.disabled = len(current)!=5 or not outgoing.value or not incoming.value or outgoing.value==incoming.value
            self.page.update()
        outgoing.on_select=incoming.on_select=validate
        def commit(_):
            out_player=next((p for p in roster if p.id==outgoing.value),None)
            in_player=next((p for p in roster if p.id==incoming.value),None)
            if not out_player or not in_player or out_player.id not in current or in_player.id in current:return
            if not self._live_require_key("SUBSTITUTION"):return
            e=make_event(m,"home","BB_SUBSTITUTION",f"#{out_player.number} → #{in_player.number}",f"Substitution #{out_player.number} → #{in_player.number}")
            e.basketball={"player_out_id":out_player.id,"player_in_id":in_player.id,"player_out_jersey":out_player.number,"player_in_jersey":in_player.number,"period":m.period,"elapsed":m.basketball_elapsed}
            m.events.append(e)
            ids=[pid for pid in current if pid!=out_player.id]+[in_player.id]
            self.page.pop_dialog()
            self._bb_set_lineup("home",ids)
        save.on_click=commit
        def set_starting(_):
            self.page.pop_dialog()
            self._bb_starting_five_dialog(selected_period=m.period)
        actions=[ft.TextButton("Set starting five",on_click=set_starting),ft.TextButton("Cancel",on_click=lambda _:self.page.pop_dialog()),save]
        self.page.show_dialog(ft.AlertDialog(title=ft.Text("Substitution"),content=ft.Column([hint,outgoing,incoming],tight=True),actions=actions))

    def _bb_roster_dialog(self, side):
        self._open_team_jerseys()

    def _bb_end_quarter(self, _=None):
        if not self._live_time_only(): return
        m = self.match
        if m.period == "FULL_TIME": return
        quarter = int(m.period.removeprefix("OT").removeprefix("Q")) if m.period in BASKETBALL_PERIODS else 1
        with self._timer_lock:
            self._timer_running = False
            m.is_live = False
        if quarter < 4:
            self._bb_log('END_QUARTER')
        self._bb_choose_period(f"Q{quarter+1}" if quarter < 4 else "FULL_TIME")

    def _bb_overtime(self, _=None):
        if not self._live_time_only(): return
        m = self.match
        if m.period not in ("Q1", "Q2", "Q3", "Q4"): return
        target = "OT" + m.period[1:]
        self._bb_log("OVERTIME")
        with self._timer_lock:
            was_running = self._timer_running
            m.period = target
            m.minute = m.second = 0
            self._timer_running = True
            m.is_live = True
        self._bb_apply_starting_five(target)
        if not was_running: self._launch_timer_thread()
        self._save()
        self._full_refresh()

    def _bb_time_buttons(self):
        m = self.match
        finished = m.period == "FULL_TIME" or not self._live_controls('time')
        return [
            action_btn("Pause" if self._timer_running else "Start",ft.Icons.PAUSE if self._timer_running else ft.Icons.PLAY_ARROW,"#34d399",self._bb_toggle_timer,disabled=finished),
            action_btn("Timeout",ft.Icons.TIMER,"#38bdf8",lambda _:self._bb_log("TIMEOUT"),disabled=not self._live_controls('time')),
            action_btn("Turnover",ft.Icons.SYNC_ALT,"#f43f5e",lambda _:self._bb_log("TO"),disabled=not self._live_allows_key('TO')),
            action_btn("Substitution",ft.Icons.SWAP_HORIZ,"#38bdf8",self._bb_substitution_dialog,disabled=not self._live_controls('time')),
            action_btn("Starting 5",ft.Icons.GROUPS,"#818cf8",self._bb_starting_five_dialog,disabled=not self._live_controls('time')),
            action_btn("Overtime",ft.Icons.MORE_TIME,"#c084fc",self._bb_overtime,disabled=not self._live_controls('time') or m.period not in ("Q1","Q2","Q3","Q4")),
            action_btn("End of quarter",ft.Icons.TIMER,"#fbbf24",self._bb_end_quarter,disabled=finished),
            action_btn("Full time",ft.Icons.FLAG,"#f43f5e",lambda _:self._bb_choose_period("FULL_TIME"),disabled=finished),
        ]

    def _bb_choose_period(self, period):
        if not self._live_time_only(): return
        m = self.match
        self._bb_conversion_target = None
        with self._timer_lock:
            self._timer_running = False
        if period == "FULL_TIME" and m.period != "FULL_TIME": self._bb_log("FULL_TIME")
        m.period = period
        m.minute = m.second = 0
        m.is_live = False
        self._bb_apply_starting_five(period)
        self._save()
        self._full_refresh()

    def _build_basketball_scoreboard(self, m):
        return self._build_scoreboard_compact(m)

    def _bb_last_completable(self):
        m = self.match
        if not m or not m.events:
            return None
        own = self._live_events()
        if not own: return None
        e = own[-1]
        if e.team_id != "home":
            return None
        return e if e.event_type.removeprefix("BB_") in INCOMPLETE_TYPES else None

    def _bb_mark_incomplete(self, code):
        if not self._live_require_key(code):return
        self._bb_conversion_target = None
        original = self._bb_last_completable()
        if not original or original.event_type != "BB_" + code or not self._live_can_modify_event(original):
            return
        event = make_event(self.match, original.team_id, "BB_INCOMPLETE", original.player_name, "Marked incomplete: " + original.description)
        event.basketball = {**original.basketball, "target_id": original.id, "elapsed": self.match.basketball_elapsed}
        self.match.events.append(event)
        self._bb_commit()

    def _bb_tabs(self):
        return ft.Text("Overall",size=11,color="#34d399",weight=ft.FontWeight.BOLD)

    def _bb_action_tiles(self, log, width=None):
        actions = [("STL","#34d399"),("SHOT","#818cf8"),("REBOUND","#c084fc"),("BLK","#38bdf8"),("PF","#fbbf24")]
        labels = {code:label for code,label,_ in ACTIONS}
        tiles = [action_btn("Foul" if code=="PF" else "Steal" if code=="STL" else "Block" if code=="BLK" else labels[code], ft.Icons.SPORTS_BASKETBALL, color,lambda _,c=code:log(c),width=width) for code,color in actions if self._live_allows_key(code)]
        if self._live_allows_key("SHOT"):
            tiles.append(action_btn("Conversion", ft.Icons.CHECK_CIRCLE, "#34d399", self._bb_open_conversion, disabled=self._bb_conversion_event() is None, width=width))
        return tiles

    def _bb_conversion_event(self):
        m = self.match
        if not m or not m.events: return None
        own = self._live_events()
        if not own: return None
        e = own[-1]
        return e if e.event_type in ("BB_SHOT", "BB_SHOT_AGAINST") and e.team_id == "home" and getattr(self, "_bb_conversion_target", None) == (m.id, e.id) else None

    def _bb_open_conversion(self, _=None):
        original = self._bb_conversion_event()
        if original is None or not self._live_require_key(original.event_type.removeprefix("BB_")) or not self._live_can_modify_event(original): return
        m = self.match
        prefix = "As" if original.event_type == "BB_SHOT_AGAINST" else "S"
        self._bb_conversion_target = None  # Opening consumes the one-use opportunity.
        options = ft.RadioGroup(content=ft.Row([ft.Radio(value=str(n), label=f"{n} point" + ("s" if n != 1 else "")) for n in (1, 2, 3)]))
        assist = ft.Checkbox(label="Assist", value=False)
        assister = ft.Dropdown(label="Assisting jersey", visible=False, options=[ft.dropdown.Option(p.id,"#"+str(p.number)) for p in m.home_team.players if p.active and p.id != original.basketball.get("player_id") and self._player_allowed(p.id)])
        preview = ft.Text("Choose the point value")
        confirm = ft.Button("Record conversion", disabled=True)
        def choose(_):
            assister.visible = bool(assist.value) and prefix == "S"
            confirm.disabled = options.value not in ("1", "2", "3") or (assister.visible and not assister.value)
            preview.value = prefix + "^" + ("A" if assist.value else "") + options.value if not confirm.disabled else "Choose the point value"
            self.page.update()
        options.on_change = choose
        assist.on_change = choose
        assister.on_select = choose
        def record(_):
            if not self._live_require_key(original.event_type.removeprefix("BB_")):return
            if options.value not in ("1", "2", "3"): return
            if self.match is not m or not self._live_events() or self._live_events()[-1].id != original.id:
                self.page.pop_dialog(); return
            if assist.value and prefix == "S" and not any(p.active and p.id == assister.value and p.id != original.basketball.get("player_id") and self._player_allowed(p.id) for p in m.home_team.players):
                self._snack("Choose an assigned assisting jersey.");return
            points = int(options.value)
            code = prefix + "^" + ("A" if assist.value else "") + str(points)
            e = make_event(m, "home", "BB_CONVERSION", m.home_team.short_name, code)
            e.basketball = {**original.basketball, "target_id": original.id, "points": points, "assist": bool(assist.value), "assist_player_id": assister.value if assist.value and prefix == "S" else ""}
            m.events.append(e)
            recalculate_stats(m)
            self._save()
            self.page.pop_dialog()
            self._full_refresh()
            scoring_team = m.home_team.short_name if prefix == "S" else m.away_team.short_name
            self._snack(f"Conversion recorded — {scoring_team} +{points}")
        confirm.on_click = record
        self.page.show_dialog(ft.AlertDialog(title=ft.Text("Shot against conversion" if prefix == "As" else "Shot conversion"), content=ft.Column([options, assist, assister, preview], tight=True), actions=[ft.TextButton("Cancel", on_click=lambda _:self.page.pop_dialog()), confirm]))

    def _bb_penalty_button(self, direction, width=None):
        def opened(_):
            self._bb_conversion_target = None
        def record(code, label):
            if not self._live_require_key("PENALTY_ATTACK" if direction=="attack" else "PENALTY_OPPOSITION"):return
            m = self.match
            player=self._selected_player() if direction=='attack' else None
            if direction=='attack' and player is None:self._snack('Select an assigned jersey first.');return
            self._bb_conversion_target = None
            if m.basketball_baseline is None:
                m.basketball_baseline = {"home": m.home_score, "away": m.away_score}
            e = make_event(m, "home", "BB_PENALTY", m.home_team.short_name, label + (" awarded to SCC" if direction == "attack" else " awarded against SCC"))
            e.basketball = {"player_id":player.id if player else "", "jersey":player.number if player else None,"direction": direction, "penalty_type": code, "period": m.period, "elapsed": m.basketball_elapsed}
            m.events.append(e)
            self._bb_commit()
        return ft.PopupMenuButton(content=action_btn("Penalty", ft.Icons.FLAG, "#fbbf24", None, width=width), width=width, padding=0, tooltip="Awarded to SCC" if direction == "attack" else "Awarded against SCC", on_open=opened, on_cancel=lambda _:self._full_refresh(), items=[ft.PopupMenuItem(content=label, on_click=lambda _,c=code,l=label:record(c,l)) for code,label in PENALTY_TYPES])

    def _bb_sequence_panel(self):
        data=sequences(self.match.events)
        rows=[ft.Text("Player sequences",size=11,weight=ft.FontWeight.BOLD,color="#94a3b8")]
        rows += [ft.Text(f"#{item['jersey']}: {item['sequence']}",size=11,selectable=True)
                 for item in data["players"]]
        if not data["players"]: rows.append(ft.Text("No player stats recorded yet.",size=11,color="#64748b"))
        if data["match"]: rows.append(ft.Text("Match: "+data["match"],size=11,selectable=True))
        return ft.Column(rows,spacing=4)

    def _bb_grid(self, tiles):
        available = max(200, self._layout_width() - 92)
        columns = max(1, min(6, int(available // 130)))
        tile_width = (available - 6 * (columns - 1)) / columns
        tile_height = max(48, tile_width / 2.5)
        rows = (len(tiles) + columns - 1) // columns
        if getattr(self, "fullscreen_video", False) and self._portrait_fullscreen():
            from ui_widgets import portrait_grid
            return portrait_grid(tiles)
        return ft.GridView(controls=tiles,runs_count=columns,child_aspect_ratio=tile_width/tile_height,spacing=6,run_spacing=6,height=rows*(tile_height+6))

    def _bb_incompletes(self, vertical=False):
        last = self._bb_last_completable()
        code = last.event_type.removeprefix("BB_") if last else None
        labels = {"SHOT":"Shot"}
        labels = {k:v for k,v in labels.items() if self._live_allows_key(k)}
        tiles = [action_btn(label+" !",ft.Icons.CLOSE,"#f43f5e" if code==key else "#64748b",lambda _,k=key:self._bb_mark_incomplete(k),disabled=code!=key,width=150 if vertical else None) for key,label in labels.items()]
        status = "Mark " + labels[code] + " as incomplete" if code in labels else "Incompletes — press an action button in this section first"
        contents = [ft.Text("INCOMPLETES" if vertical else "Incompletes",size=12,weight=ft.FontWeight.BOLD,color="#94a3b8")]
        if not vertical: contents.append(ft.Text(status,size=9,color="#64748b"))
        contents += (tiles if vertical else [self._bb_grid(tiles)]) if tiles else [ft.Text("No incomplete actions in this section.",size=11,color="#94a3b8")]
        return ft.Container(content=ft.Column(contents,spacing=6,scroll=ft.ScrollMode.AUTO if vertical else None,expand=vertical),bgcolor="#0f172a",border=ft.Border.all(1,"#1e293b"),border_radius=10,padding=10,width=170 if vertical else None)

    def _build_basketball_logger(self, m):
        side = "home"
        team = getattr(m, side + "_team")
        def log(code):
            self._bb_log(code, side)
        period = ft.Dropdown(label="Period", value=m.period if m.period in BASKETBALL_PERIODS else None, options=[ft.dropdown.Option(p,p.replace("_"," ")) for p in BASKETBALL_PERIODS],on_select=lambda e:self._bb_choose_period(e.control.value))
        actions = card(ft.Column([
            ft.Row([ft.Icon(ft.Icons.GRID_VIEW,size=14,color="#818cf8"),ft.Text("Overall stats",size=13,weight=ft.FontWeight.BOLD)],spacing=8),
            self._jersey_selector(),ft.Divider(height=1,color="#1e293b"),self._bb_grid(self._bb_action_tiles(log)),
        ],spacing=10),padding=14)
        missed = self._bb_incompletes()
        # Match soccer's video-first layout, action cards, quick rows and time controls.
        rows = [
            self._build_live_video_panel(),
            ft.Text("Logging for SCC - St Charles College", weight=ft.FontWeight.BOLD),
            actions, missed, self._bb_sequence_panel(),
            card(ft.Column([
                self._build_possession_row(m),
                ft.Text("Time controls and match actions", weight=ft.FontWeight.BOLD),
                ft.Row(self._bb_time_buttons(),wrap=True), period,
            ], spacing=10), padding=14),
            ft.Row([action_btn("Undo last event", ft.Icons.UNDO, "#fbbf24", lambda _: self._undo_last_event()), ft.TextButton("Dictionary", on_click=self._open_dictionary_dialog)], wrap=True),
        ]
        # Detailed guidance belongs under Dictionary > Basketball rules.
        return ft.Container(content=ft.Column(rows, scroll=ft.ScrollMode.AUTO, spacing=8, expand=True), bgcolor="#020617", padding=12, expand=True)

    def _build_basketball_fullscreen(self, m):
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
        compact = [ft.TextButton(label, on_click=handler, disabled=disabled or not self._live_controls('time'),
                    style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=8,vertical=4)))
            for label,handler,disabled in [
                ("Timeout",lambda _:log("TIMEOUT"),False),
                ("Turnover",lambda _:log("TO"),False),
                ("Substitution",self._bb_substitution_dialog,False),
                ("Starting 5",self._bb_starting_five_dialog,False),
                ("Overtime",self._bb_overtime,m.period not in ("Q1","Q2","Q3","Q4")),
                ("End of quarter",self._bb_end_quarter,m.period=="FULL_TIME"),
                ("Full time",lambda _:self._bb_choose_period("FULL_TIME"),m.period=="FULL_TIME")]]
        top = panel(ft.Column([
            ft.Row([
                ft.IconButton(icon=ft.Icons.FULLSCREEN_EXIT,tooltip="Exit fullscreen",on_click=self._exit_fullscreen_video),
                *score_controls,
                ft.IconButton(icon=ft.Icons.PAUSE if self._timer_running else ft.Icons.PLAY_ARROW,
                    tooltip="Pause" if self._timer_running else "Start",on_click=self._bb_toggle_timer,disabled=m.period=="FULL_TIME" or not self._live_controls('time')),
                self._bb_clock_text,
                ft.Dropdown(value=m.period if m.period in BASKETBALL_PERIODS else "Q1",width=115,disabled=not self._live_controls('time'),
                    options=[ft.dropdown.Option(p) for p in BASKETBALL_PERIODS],on_select=lambda e:self._bb_choose_period(e.control.value)),
            ],spacing=4,scroll=ft.ScrollMode.AUTO,alignment=ft.MainAxisAlignment.CENTER),
            ft.Row(compact,spacing=4,scroll=ft.ScrollMode.AUTO,alignment=ft.MainAxisAlignment.CENTER),
            self._build_possession_row(m),
        ],spacing=2))
        right = panel(ft.Column([
            ft.Text("Overall stats — SCC", weight=ft.FontWeight.BOLD),
            self._jersey_selector(),ft.Divider(height=1,color=border),
            *[ft.Container(content=tile,height=48) for tile in self._bb_action_tiles(log,width=210)],
            ft.Divider(height=1,color=border),
            ft.TextButton("Dictionary",on_click=self._open_dictionary_dialog),
        ],spacing=6,scroll=ft.ScrollMode.AUTO,expand=True),230)
        bottom = panel(ft.Column([
            ft.Row([ft.Button("Undo Last",icon=ft.Icons.UNDO,on_click=lambda _:self._undo_last_event())],spacing=8,wrap=True),
            self._bb_sequence_panel(),
        ]))
        video = ft.Container(content=ft.Stack([
            ft.Container(content=self._zoom_video_display_widget(),bgcolor="#020617",border=ft.Border.all(1,border),border_radius=12,alignment=ft.Alignment.CENTER,expand=True),
            ft.Container(content=ft.Text("LIVE" if self.camera_on else "OFF",size=10),padding=10),
            ft.Container(content=ft.Row([self._rotate_view_button(),self._mirror_view_button(), self._video_zoom_buttons(),ft.IconButton(icon=ft.Icons.VIDEOCAM_OFF if self.camera_on else ft.Icons.VIDEOCAM,on_click=self._stop_camera if self.camera_on else self._start_camera)],tight=True),padding=8,alignment=ft.Alignment.TOP_RIGHT),
        ],expand=True),expand=True)
        self.fs_left_slot.content=update_layout(self.fs_left_slot.content, self._bb_incompletes(vertical=True))
        self.fs_top_slot.content=update_layout(self.fs_top_slot.content, top)
        self.fs_video_slot.content=update_layout(self.fs_video_slot.content, video)
        self.fs_bottom_slot.content=update_layout(self.fs_bottom_slot.content, bottom)
        self.fs_right_slot.content=update_layout(self.fs_right_slot.content, right)
        if self._portrait_fullscreen(): return self._build_portrait_logging(m)
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
        from export_utils import match_filename
        self.page.run_task(self._export_txt_async, match_filename(self.match), report(self.match))
