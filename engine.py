"""
StatTracker AI — Stats Engine & Initial Data (v4)
"""
from __future__ import annotations
import uuid
from datetime import date
from models import Match, Team, Player, MatchStats, StatEvent, SCC_COLORS


def recalculate_stats(match: Match) -> Match:
    """Recompute all stats and scores from the event log."""
    events = match.events
    home_score = away_score = 0
    home_shots = away_shots = 0
    home_sot = away_sot = 0
    home_inc_shots = away_inc_shots = 0
    home_passes = away_passes = 0
    home_comp_passes = away_comp_passes = 0
    home_inc_passes = away_inc_passes = 0
    home_crosses = away_crosses = 0
    home_comp_crosses = away_comp_crosses = 0
    home_inc_crosses = away_inc_crosses = 0
    home_goals = away_goals = 0
    home_assists = away_assists = 0
    home_conversions = away_conversions = 0
    home_xg = away_xg = 0.0
    home_fouls = away_fouls = 0
    home_tackles = away_tackles = 0
    home_inc_tackles = away_inc_tackles = 0
    home_saves = away_saves = 0
    home_corners = away_corners = 0
    home_yellow = away_yellow = 0
    home_red = away_red = 0

    for ev in events:
        is_home = ev.team_id == "home"
        desc = (ev.description or "").upper()
        is_unsuccessful = (
            "INCOMPLETE" in desc or "MISSED" in desc or
            "OFF TARGET" in desc or "FAILED" in desc or
            ev.event_type in ("SHOT_INCOMPLETE", "PASS_INCOMPLETE",
                              "LONG_PASS_INCOMPLETE",
                              "CROSS_INCOMPLETE", "TACKLE_INCOMPLETE",
                              "SAVE_INCOMPLETE", "INTERCEPT_INCOMPLETE",
                              "BLOCK_INCOMPLETE", "CLEAR_INCOMPLETE",
                              "THROW_IN_INCOMPLETE", "OFFSIDE_INCOMPLETE",
                              "OFFSIDE_GIVEN_INCOMPLETE")
        )
        t = ev.event_type

        if t == "GOAL":
            if is_home: home_score += 1; home_goals += 1; home_shots += 1; home_sot += 1; home_xg += ev.xg or 0.45
            else:       away_score += 1; away_goals += 1; away_shots += 1; away_sot += 1; away_xg += ev.xg or 0.45
            if ev.assisted_by or any(w in desc for w in ("PASS", "CROSS", "ASSIST", "CONVERSION")):
                if is_home: home_passes += 1; home_comp_passes += 1; home_assists += 1; home_conversions += 1
                else:       away_passes += 1; away_comp_passes += 1; away_assists += 1; away_conversions += 1

        elif t in ("SHOT", "SHOT_ON_TARGET", "SHOT_INCOMPLETE"):
            if is_unsuccessful:
                if is_home: home_inc_shots += 1
                else:       away_inc_shots += 1
            else:
                if is_home: home_shots += 1; home_xg += ev.xg or 0.15; home_sot += (1 if t == "SHOT_ON_TARGET" else 0)
                else:       away_shots += 1; away_xg += ev.xg or 0.15; away_sot += (1 if t == "SHOT_ON_TARGET" else 0)

        elif t in ("PASS", "PASS_INCOMPLETE", "LONG_PASS", "LONG_PASS_INCOMPLETE"):
            if is_unsuccessful:
                if is_home: home_inc_passes += 1
                else:       away_inc_passes += 1
            else:
                if is_home: home_passes += 1; home_comp_passes += 1
                else:       away_passes += 1; away_comp_passes += 1

        elif t in ("CROSS", "CROSS_INCOMPLETE"):
            if is_unsuccessful:
                if is_home: home_inc_crosses += 1
                else:       away_inc_crosses += 1
            else:
                if is_home: home_crosses += 1; home_comp_crosses += 1
                else:       away_crosses += 1; away_comp_crosses += 1

        elif t == "CONVERSION":
            # req 23: conversion increments goals, assists AND conversions
            if is_home: home_conversions += 1; home_goals += 1; home_assists += 1; home_score += 1; home_shots += 1
            else:       away_conversions += 1; away_goals += 1; away_assists += 1; away_score += 1; away_shots += 1

        elif t == "ASSIST":
            if is_home: home_assists += 1
            else:       away_assists += 1

        elif t in ("FOUL", "FOULS_GIVEN"):
            if is_home: home_fouls += 1
            else:       away_fouls += 1

        elif t == "FOULS_WON":
            # fouls won by home = fouls given by away
            if is_home: away_fouls += 1
            else:       home_fouls += 1

        elif t == "CORNER":
            if is_home: home_corners += 1
            else:       away_corners += 1

        elif t == "YELLOW_CARD":
            if is_home: home_yellow += 1
            else:       away_yellow += 1

        elif t == "RED_CARD":
            if is_home: home_red += 1
            else:       away_red += 1

        elif t in ("TACKLE", "TACKLE_INCOMPLETE"):
            if is_unsuccessful:
                if is_home: home_inc_tackles += 1
                else:       away_inc_tackles += 1
            else:
                if is_home: home_tackles += 1
                else:       away_tackles += 1

        elif t in ("SAVE", "SAVE_INCOMPLETE"):
            if is_home: home_saves += 1
            else:       away_saves += 1

    home_pass_total = home_passes + home_inc_passes
    home_pass_acc   = round(home_passes / home_pass_total * 100) if home_pass_total else 85
    away_pass_total = away_passes + away_inc_passes
    away_pass_acc   = round(away_passes / away_pass_total * 100) if away_pass_total else 82

    match.home_score = home_score
    # Only SCC (home) actions are ever logged as events — this app tracks
    # St Charles College only. away_score is managed entirely manually
    # (scoreboard +/-, and the "Goals Given" action) since there are no
    # away-team events to derive it from. Overwriting it here with the
    # always-zero event-derived count was wiping out manual adjustments
    # every time any new SCC event was logged.
    match.stats = MatchStats(
        home_possession=match.stats.home_possession,
        away_possession=match.stats.away_possession,
        home_possession_seconds=match.stats.home_possession_seconds,
        away_possession_seconds=match.stats.away_possession_seconds,
        home_shots=home_shots, away_shots=away_shots,
        home_shots_on_target=home_sot, away_shots_on_target=away_sot,
        home_incomplete_shots=home_inc_shots, away_incomplete_shots=away_inc_shots,
        home_passes=home_passes, away_passes=away_passes,
        home_completed_passes=home_comp_passes, away_completed_passes=away_comp_passes,
        home_incomplete_passes=home_inc_passes, away_incomplete_passes=away_inc_passes,
        home_pass_acc=home_pass_acc, away_pass_acc=away_pass_acc,
        home_crosses=home_crosses, away_crosses=away_crosses,
        home_completed_crosses=home_comp_crosses, away_completed_crosses=away_comp_crosses,
        home_incomplete_crosses=home_inc_crosses, away_incomplete_crosses=away_inc_crosses,
        home_goals=home_goals, away_goals=away_goals,
        home_assists=home_assists, away_assists=away_assists,
        home_conversions=home_conversions, away_conversions=away_conversions,
        home_xg=home_xg, away_xg=away_xg,
        home_fouls=home_fouls, away_fouls=away_fouls,
        home_tackles=home_tackles, away_tackles=away_tackles,
        home_incomplete_tackles=home_inc_tackles, away_incomplete_tackles=away_inc_tackles,
        home_saves=home_saves, away_saves=away_saves,
        home_corners=home_corners, away_corners=away_corners,
        home_yellow_cards=home_yellow, away_yellow_cards=away_yellow,
        home_red_cards=home_red, away_red_cards=away_red,
    )
    return match


def tally_action(events, base_type: str) -> tuple:
    home_c = home_i = away_c = away_i = 0
    inc_type = f"{base_type}_INCOMPLETE"
    for ev in events:
        is_home = ev.team_id == "home"
        if ev.event_type == base_type:
            if is_home: home_c += 1
            else:       away_c += 1
        elif ev.event_type == inc_type:
            if is_home: home_i += 1
            else:       away_i += 1
    return home_c, home_i, away_c, away_i


def advance_period(match: Match) -> Match:
    order = ["1ST_HALF", "HALF_TIME", "2ND_HALF", "OVERTIME", "FULL_TIME"]
    idx = order.index(match.period) if match.period in order else 0
    next_period = order[min(idx + 1, len(order) - 1)]
    match.period = next_period
    match.is_live = next_period not in ("FULL_TIME", "HALF_TIME")
    return match


def make_event(match: Match, team_id: str, event_type: str,
               player_name: str, description: str,
               xg: float = 0.0, assisted_by: str = None) -> StatEvent:
    from datetime import datetime
    return StatEvent(
        id=f"ev-{uuid.uuid4().hex[:8]}",
        timestamp=datetime.now().strftime("%H:%M"),
        minute=match.minute,
        second=getattr(match, "second", 0),
        team_id=team_id,
        event_type=event_type,
        player_name=player_name,
        description=description,
        pitch_x=80.0 if event_type in ("GOAL", "SHOT", "SHOT_ON_TARGET") else 50.0,
        pitch_y=50.0,
        xg=xg,
        assisted_by=assisted_by,
    )


def build_scc_team(team_id: str = "home") -> Team:
    """Create the default St Charles College team (req 9, 14)."""
    return Team(
        id=team_id,
        name="St Charles College",
        short_name="SCC",
        logo_color=SCC_COLORS[0],
        secondary_color=SCC_COLORS[1],
        badge_symbol="",
        school_name="St Charles College",
        team_rank="1st Team",
        kit_color_primary=SCC_COLORS[0],
        kit_color_secondary=SCC_COLORS[1],
        kit_colors=list(SCC_COLORS),  # locked to 3 colours
        logo_base64=None,
        players=[],
    )


def generate_sequences(events: list, team_id: str) -> dict:
    """
    Build the attack/defence/cards sequence strings from the event log.
    Returns {"attack": str, "defence": str, "cards": str}.

    Symbol scheme:
    - Single-word actions: first letter of the action, capitalised
      (Pass -> P, Shot -> S, Cross -> C, Tackle -> T, etc.)
    - Two-word actions that can happen from either side: first letter of
      each word (Long Pass -> LP, Offside Given -> OG, GK Kick -> GK,
      Yellow Card -> YC).
    - Explicit overrides: Goals Given -> Ga, Substitution -> SUB,
      Turnover -> TURN, Fouls Won/Given stay F+/F- unchanged.
    - Conversion is always "^" followed by the resulting goal-event's own
      symbol: "^AG" for an attacking conversion (turnover, assist, goal —
      matches the original sample report), "^Ga" for a defensive
      conversion (a Save/Block that still results in a goal against).
    - "!" suffix marks an incomplete action, as before.
    """
    ATTACK_MAP = {
        # Each action button press logs its own event and contributes its
        # own letter to the sequence. "Mark Incomplete" logs a *separate*
        # follow-up event on top of that (so stats like shot accuracy can
        # tell attempts from completions) — its code must be just "!",
        # not the parent's letter *and* "!", or the sequence ends up with
        # the letter twice: Shot -> "S", then Incomplete -> "S!" makes
        # "S"+"S!" = "SS!" instead of the intended "S!".
        "PASS": "P",               "PASS_INCOMPLETE": "!",
        "LONG_PASS": "LP",         "LONG_PASS_INCOMPLETE": "!",
        "CROSS": "C",              "CROSS_INCOMPLETE": "!",
        "SHOT": "S",               "SHOT_ON_TARGET": "S",   "SHOT_INCOMPLETE": "!",
        "DRIBBLE": "D",
        "CORNER": "C",
        "THROW_IN": "TI",          "THROW_IN_INCOMPLETE": "!",
        "GK_KICK": "GK",
        "GK_THROW": "GT",
        "OFFSIDE_GIVEN": "OG",     "OFFSIDE_GIVEN_INCOMPLETE": "!",
        "FOULS_WON": "F+",
        "GOAL": "G",
        "ASSIST": "A",
        "CONVERSION": "^AG",      # attacking conversion: turnover + assist + goal
        "TURNOVER": "TURN",
    }
    DEFENCE_MAP = {
        "TACKLE": "T",             "TACKLE_INCOMPLETE": "!",
        "INTERCEPT": "I",          "INTERCEPT_INCOMPLETE": "!",
        "BLOCK": "B",              "BLOCK_INCOMPLETE": "!",
        "SAVE": "S",               "SAVE_INCOMPLETE": "!",
        "CLEAR": "C",              "CLEAR_INCOMPLETE": "!",
        "OFFSIDE": "O",            "OFFSIDE_INCOMPLETE": "!",
        "PENALTY": "P",
        "FOULS_GIVEN": "F-",
        "FOUL": "F-",
        "GOALS_GIVEN": "Ga",                    # explicit override, not derived from the two-word rule
        "GOALS_GIVEN_CONVERSION": "^Ga",        # defensive conversion: turnover + the Goals-Given symbol
    }
    CARDS_MAP = {
        "YELLOW_CARD": "YC",
        "RED_CARD": "RC",
    }
    atk = def_ = crd = ""
    for ev in sorted(events, key=lambda e: (e.minute, getattr(e, "second", 0))):
        if ev.team_id != team_id:
            continue
        if ev.event_type in ATTACK_MAP:
            atk += ATTACK_MAP[ev.event_type]
        elif ev.event_type in DEFENCE_MAP:
            def_ += DEFENCE_MAP[ev.event_type]
        elif ev.event_type in CARDS_MAP:
            crd += CARDS_MAP[ev.event_type]
    return {"attack": atk, "defence": def_, "cards": crd}
