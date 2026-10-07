"""Basketball event accounting. Derived values never invent missing observations."""
from collections import Counter
import json

# code, friendly name, short explanation (also used as button help)
ACTIONS = [
    ("SUBSTITUTION", "Substitution", "An SCC substitution, recorded without player details: [SUB]."),
    ("END_QUARTER", "End of quarter", "End of the current quarter: [TIME]. Stops the clock; choose the next period when ready."),
    ("FULL_TIME", "Full time", "The match has ended: [FT]."),
    ("SHORT_PASS", "Short pass", "A completed SCC pass travelling half the court or less. Mark incomplete if it does not reach a teammate."),
    ("LONG_PASS", "Long pass", "A completed SCC pass travelling half the court or more. Mark incomplete if it does not reach a teammate."),
    ("DRIBBLE", "Dribble", "An SCC dribble completed while retaining control of the ball. Mark incomplete if the dribble is unsuccessful. Record a turnover separately if possession is lost."),
    ("SHOT_AGAINST", "Shot against (As)", "An opponent shot against SCC. Conversion adds 1, 2 or 3 points to the opponent; mark incomplete for a miss. Assist refers to the opponent on this shot."),
    ("SHOT", "Shot", "An SCC shot. Use Conversion once for 1, 2 or 3 points, or Shot incomplete for a miss."),
    ("LAYUP", "Layup", "A completed SCC layup adds two points and one two-point attempt. Layup incomplete removes the points and records a miss."),
    ("2_MADE", "2 points made", "A successful shot worth two points. Also adds one field-goal attempt."),
    ("2_MISSED", "2 points missed", "An unsuccessful two-point shot. Adds an attempt, not points."),
    ("3_MADE", "3 points made", "A successful shot worth three points. Also adds one field-goal attempt."),
    ("3_MISSED", "3 points missed", "An unsuccessful three-point shot. Adds an attempt, not points."),
    ("FT_MADE", "Free throw made", "One successful free throw: one point and one free-throw attempt."),
    ("FT_MISSED", "Free throw missed", "An unsuccessful free throw: one attempt and no points."),
    ("OREB", "Offensive rebound", "Recovering the ball after your own team misses a shot."),
    ("DREB", "Defensive rebound", "Recovering the ball after the other team misses a shot."),
    ("AST", "Assist", "A pass directly creating a score. Recorded for SCC. Conversion with Assist checked already adds one assist; do not log it again."),
    ("STL", "Steal", "A defensive action that wins possession. Recorded for SCC only."),
    ("BLK", "Block", "Deflecting an opponent shot. Recorded for SCC only."),
    ("BA", "Shot blocked against", "One of this team's shots was blocked. This does not add another shot attempt."),
    ("TO", "Turnover", "Losing possession before getting a shot away, for example a bad pass or travelling."),
    ("PF", "Personal foul", "A personal foul charged to the SCC. Offensive fouls also need a turnover entry."),
    ("TF", "Technical foul", "A technical foul. Kept separate from personal fouls in this tracker."),
    ("UF", "Unsportsmanlike foul", "An unsportsmanlike foul; included in the personal-foul total."),
    ("DF", "Disqualifying foul", "A disqualifying foul; included in the personal-foul total."),
    ("FD", "Foul drawn", "The opponent fouled a member of this team. Use Attack Penalty to record the award to SCC."),
    ("CHARGE", "Charge drawn", "This team drew an offensive charging foul. Record foul drawn, opponent foul and turnover separately."),
    ("DEFLECTION", "Deflection", "A touch that disrupts an opponent pass without necessarily winning the ball."),
    ("LOOSE", "Loose ball recovered", "Winning control of a loose ball. Add a rebound or steal separately only if appropriate."),
    ("TIMEOUT", "Timeout", "A timeout used by this team. Record for the team that called it."),
]
BASE = ["SUBSTITUTION", "END_QUARTER", "FULL_TIME","SHORT_PASS", "SHORT_PASS_INCOMPLETE", "LONG_PASS", "LONG_PASS_INCOMPLETE", "DRIBBLE", "DRIBBLE_INCOMPLETE","SHOTS_AGAINST", "MISSES_AGAINST", "UNRESOLVED_AGAINST", "POINTS_AGAINST","SHOTS", "SHOT_MISSES", "UNRESOLVED", "LAYUPS", "LAYUP_MISSES", "PENALTIES_WON", "PENALTIES_GIVEN","PTS", "2M", "2A", "3M", "3A", "FTM", "FTA", "FGM", "FGA", "OREB", "DREB", "REB", "AST", "STL", "BLK", "BA", "TO", "PF", "TF", "UF", "DF", "FD", "CHARGE", "DEFLECTION", "LOOSE", "TIMEOUT", "PAINT", "FASTBREAK", "SECONDCHANCE", "OFFTURNOVER", "BENCH", "ADJUSTMENT"]
DEFINITIONS = {
    "SHORT_PASS_INCOMPLETE": ("Incomplete short passes", "SCC passes travelling half the court or less that did not reach a teammate. Replaces the completed pass; adds no points or automatic turnover."),
    "LONG_PASS_INCOMPLETE": ("Incomplete long passes", "SCC passes travelling half the court or more that did not reach a teammate. Replaces the completed pass; adds no points or automatic turnover."),
    "DRIBBLE_INCOMPLETE": ("Incomplete dribbles", "Unsuccessful SCC dribbles. Replaces the completed dribble; record a turnover separately if possession is lost."),
    "SHOTS_AGAINST": ("Shots against SCC", "Opponent shot actions, including converted, missed and unresolved shots."),
    "MISSES_AGAINST": ("Missed shots against SCC", "Opponent shot actions marked incomplete."),
    "UNRESOLVED_AGAINST": ("Unresolved shots against SCC", "Opponent shots without a conversion or incomplete result."),
    "POINTS_AGAINST": ("Points conceded from shots", "Opponent points recorded through Shot against and Conversion. Excludes manual score corrections."),
    "SHOTS": ("Shot actions", "Times the Shot button was pressed, including converted, missed and unresolved shots."),
    "SHOT_MISSES": ("Unclassified missed shots", "Shot actions marked incomplete without a known point value; excluded from two-point, three-point and free-throw percentages."),
    "UNRESOLVED": ("Unresolved shots", "Shot actions with no conversion or incomplete result. No points or classified shooting attempt is assumed."),
    "LAYUPS": ("Layup actions", "Recorded layup actions, including incomplete layups."),
    "LAYUP_MISSES": ("Incomplete layups", "Layup actions marked unsuccessful."),
    "PENALTIES_WON": ("Penalties awarded to SCC", "Penalty decisions in SCC's favour, classified by type. An award does not automatically add points."),
    "PENALTIES_GIVEN": ("Penalties awarded against SCC", "Penalty decisions awarded to the opponent against SCC. An award does not automatically add opponent points."),
    "PTS": ("Points", "2 × two-pointers made + 3 × three-pointers made + free throws made. Score corrections are shown separately."),
    "2M": ("Two-pointers made", "Number of successful two-point shots."),
    "2A": ("Two-pointers attempted", "Two-point shots made plus missed."),
    "3M": ("Three-pointers made", "Number of successful three-point shots."),
    "3A": ("Three-pointers attempted", "Three-point shots made plus missed."),
    "FTM": ("Free throws made", "Number of successful one-point free throws."),
    "FTA": ("Free throws attempted", "Free throws made plus missed."),
    "FGM": ("Field goals made", "Two-pointers made + three-pointers made; excludes free throws."),
    "FGA": ("Field goals attempted", "Two-point attempts + three-point attempts; excludes free throws."),
    "REB": ("Total rebounds", "Offensive rebounds + defensive rebounds."),
    "PAINT": ("Points in the paint", "Points from made two-point shots tagged In the paint."),
    "FASTBREAK": ("Fast-break points", "Points from scoring events tagged Fast break."),
    "SECONDCHANCE": ("Second-chance points", "Points from scoring events tagged Second chance, after an offensive rebound."),
    "OFFTURNOVER": ("Points off turnovers", "Points tagged After turnover, on the possession after an opponent turnover."),
    "BENCH": ("Bench points", "Points scored by players marked as non-starters when the score was recorded."),
    "ADJUSTMENT": ("Score corrections", "Manual additions or deductions. Included in the scoreboard, excluded from shooting and efficiency calculations."),
    "2%": ("Two-point percentage", "100 × two-pointers made / two-point attempts."),
    "3%": ("Three-point percentage", "100 × three-pointers made / three-point attempts."),
    "FT%": ("Free-throw percentage", "100 × free throws made / free-throw attempts."),
    "FG%": ("Field-goal percentage", "100 × field goals made / field-goal attempts."),
    "eFG%": ("Effective field-goal percentage", "100 × (FGM + 0.5 × 3M) / FGA. Gives extra credit for three-pointers."),
    "TS%": ("True shooting percentage (estimate)", "100 × points / [2 × (FGA + 0.44 × FTA)]. Estimates shooting efficiency including free throws."),
    "AST/TO": ("Assist-to-turnover ratio", "Assists / turnovers. A dash means there are no turnovers to divide by."),
    "EFF": ("Simple efficiency", "Points + rebounds + assists + steals + blocks − missed field goals − missed free throws − turnovers. Not PER or an official rating."),
    "POSS": ("Estimated possessions", "FGA − offensive rebounds + turnovers + 0.44 × FTA. An estimate that needs complete team logging."),
    "ORTG": ("Points per 100 estimated possessions", "100 × points / estimated possessions. Only meaningful with complete events for the team."),
    "3RATE": ("Three-point attempt rate", "100 × three-point attempts / all field-goal attempts."),
    "FTR": ("Free-throw attempt rate", "Free-throw attempts / field-goal attempts."),
    "DD": ("Double-double", "At least 10 in two or more of points, rebounds, assists, steals and blocks; player rows only."),
    "TD": ("Triple-double", "At least 10 in three or more of points, rebounds, assists, steals and blocks; player rows only."),
}
DEFINITIONS.update({
    "MIN": ("Minutes played (tracked)", "Running-clock time after a player is placed in a recorded on-court lineup. Unrecorded time is not estimated; — means no lineup entry."),
    "+/-": ("Plus/minus (tracked)", "Team points minus opponent points while the player is in a recorded lineup. Includes score corrections recorded while on court."),
})


def on_court(match, side):
    lineup = []
    for e in match.events:
        if e.team_id == side and e.event_type == "BB_LINEUP":
            lineup = e.basketball.get("lineup", [])
    return lineup


def playing_stats(match, side):
    elapsed, lineup = 0, []
    seconds, plusminus = Counter(), Counter()
    for e in effective_events(match.events):
        at = max(elapsed, min(match.basketball_elapsed, e.basketball.get("elapsed", 0)))
        for pid in lineup:
            seconds[pid] += at - elapsed
        elapsed = at
        if e.team_id == side and e.event_type == "BB_LINEUP":
            lineup = e.basketball.get("lineup", [])
            for pid in lineup:
                seconds[pid] += 0
                plusminus[pid] += 0
        points = {"BB_2_MADE": 2, "BB_3_MADE": 3, "BB_FT_MADE": 1}.get(e.event_type, 0)
        if e.event_type == "BB_ADJUSTMENT":
            points = e.basketball.get("points", 0)
        for pid in lineup:
            plusminus[pid] += points if e.team_id == side else -points
    for pid in lineup:
        seconds[pid] += max(0, match.basketball_elapsed - elapsed)
    return {pid: {"MIN": f"{sec // 60}:{sec % 60:02d}", "+/-": plusminus[pid]} for pid, sec in seconds.items()}

for code, label, definition in ACTIONS:
    if code not in ("2_MADE", "2_MISSED", "3_MADE", "3_MISSED", "FT_MADE", "FT_MISSED"):
        DEFINITIONS[code] = (label, definition)
TAGS = {"paint": "PAINT", "fastbreak": "FASTBREAK", "secondchance": "SECONDCHANCE", "offturnover": "OFFTURNOVER", "bench": "BENCH"}


def ratio(n, d, scale=1):
    return round(scale * n / d, 1) if d > 0 else None


INCOMPLETE_TYPES = {"SHORT_PASS": "SHORT_PASS_INCOMPLETE", "LONG_PASS": "LONG_PASS_INCOMPLETE", "DRIBBLE": "DRIBBLE_INCOMPLETE","SHOT_AGAINST": "SHOT_AGAINST_MISSED","SHOT": "SHOT_MISSED", "LAYUP": "LAYUP_MISSED","2_MADE": "2_MISSED", "3_MADE": "3_MISSED", "FT_MADE": "FT_MISSED", "STL": "STL_INCOMPLETE", "BLK": "BLK_INCOMPLETE", "OREB": "OREB_INCOMPLETE", "DREB": "DREB_INCOMPLETE", "DEFLECTION": "DEFLECTION_INCOMPLETE", "LOOSE": "LOOSE_INCOMPLETE"}


def effective_events(events):
    """Apply reversible outcome corrections without adding a second attempt."""
    from dataclasses import replace
    corrected = {e.basketball.get("target_id") for e in events if e.event_type == "BB_INCOMPLETE"}
    conversions = {}
    originals = {e.id: e for e in events if e.event_type in ("BB_SHOT", "BB_SHOT_AGAINST")}
    for marker in events:
        target = marker.basketball.get("target_id")
        if marker.event_type == "BB_CONVERSION" and target in originals and marker.team_id == originals[target].team_id and marker.basketball.get("points") in (1, 2, 3):
            conversions.setdefault(target, marker)
    result = []
    for e in events:
        if e.event_type in ("BB_INCOMPLETE", "BB_CONVERSION"):
            continue
        key = e.event_type.removeprefix("BB_")
        if e.id in corrected and key in INCOMPLETE_TYPES:
            e = replace(e, event_type="BB_" + INCOMPLETE_TYPES[key])
        elif e.id in conversions:
            marker = conversions[e.id]
            kind = {1: "FT", 2: "2", 3: "3"}[marker.basketball["points"]]
            e = replace(e, event_type="BB_SHOT_AGAINST_MADE" if e.event_type == "BB_SHOT_AGAINST" else "BB_" + kind + "_MADE", basketball={**e.basketball, "shot_action": True, "points": marker.basketball["points"], "assist": bool(marker.basketball.get("assist"))})
        result.append(e)
    return result


def box_score(events):
    s = dict.fromkeys(BASE, 0)
    for ev in effective_events(events):
        if not ev.event_type.startswith("BB_"):
            continue
        t = ev.event_type[3:]
        points = 0
        if t in ("SHOT_AGAINST", "SHOT_AGAINST_MISSED", "SHOT_AGAINST_MADE"):
            s["SHOTS_AGAINST"] += 1
            s["MISSES_AGAINST"] += int(t == "SHOT_AGAINST_MISSED")
            s["UNRESOLVED_AGAINST"] += int(t == "SHOT_AGAINST")
            if t == "SHOT_AGAINST_MADE": s["POINTS_AGAINST"] += ev.basketball["points"]
            continue  # Opponent outcomes must not count as SCC shooting or assists.
        if t in ("SHOT", "SHOT_MISSED") or ev.basketball.get("shot_action"):
            s["SHOTS"] += 1
        if ev.basketball.get("shot_action") and ev.basketball.get("assist"):
            s["AST"] += 1
        if t == "SHOT": s["UNRESOLVED"] += 1
        if t == "SHOT_MISSED": s["SHOT_MISSES"] += 1
        if t in ("LAYUP", "LAYUP_MISSED"):
            s["LAYUPS"] += 1
            s["LAYUP_MISSES"] += int(t == "LAYUP_MISSED")
            s["2A"] += 1
            if t == "LAYUP":
                s["2M"] += 1
                points = 2
        if t == "PENALTY":
            given = ev.basketball.get("direction") == "defence"
            s["PENALTIES_GIVEN" if given else "PENALTIES_WON"] += 1
            penalty = ev.basketball.get("penalty_type")
            if given and penalty in ("PF", "SHOOTING", "OFFENSIVE", "BLOCKING", "HOLDING", "UF", "DF"):
                s["PF"] += 1
            if given and penalty in ("TF", "UF", "DF"): s[penalty] += 1
            if not given and penalty in ("PF", "SHOOTING", "OFFENSIVE", "BLOCKING", "HOLDING", "UF", "DF"): s["FD"] += 1
        if t in ("2_MADE", "2_MISSED", "3_MADE", "3_MISSED", "FT_MADE", "FT_MISSED"):
            kind, result = t.split("_")
            s[kind + "A"] += 1
            if result == "MADE":
                s[kind + "M"] += 1
                points = {"2": 2, "3": 3, "FT": 1}[kind]
        elif t == "ADJUSTMENT":
            s["ADJUSTMENT"] += ev.basketball.get("points", 0)
        elif t in s:
            s[t] += 1
            if t in ("UF", "DF"):
                s["PF"] += 1
        s["PTS"] += points
        for tag, key in TAGS.items():
            if tag in ev.basketball.get("tags", []) and (tag != "paint" or t in ("2_MADE", "LAYUP")):
                s[key] += points
    s["FGM"] = s["2M"] + s["3M"]
    s["FGA"] = s["2A"] + s["3A"]
    s["REB"] = s["OREB"] + s["DREB"]
    for kind in ("2", "3", "FT", "FG"):
        s[kind + "%"] = ratio(s[kind + "M"], s[kind + "A"], 100)
    s["eFG%"] = ratio(s["FGM"] + 0.5 * s["3M"], s["FGA"], 100)
    s["TS%"] = ratio(s["PTS"], 2 * (s["FGA"] + 0.44 * s["FTA"]), 100)
    s["AST/TO"] = ratio(s["AST"], s["TO"])
    s["EFF"] = sum(s[k] for k in ("PTS", "REB", "AST", "STL", "BLK")) - (s["FGA"]-s["FGM"]) - (s["FTA"]-s["FTM"]) - s["TO"]
    possessions = s["FGA"] - s["OREB"] + s["TO"] + 0.44*s["FTA"]
    s["POSS"] = round(possessions, 2) if possessions >= 0 else None
    s["ORTG"] = ratio(s["PTS"], possessions, 100)
    s["3RATE"] = ratio(s["3A"], s["FGA"], 100)
    s["FTR"] = ratio(s["FTA"], s["FGA"])
    doubles = sum(s[k] >= 10 for k in ("PTS", "REB", "AST", "STL", "BLK"))
    s["DD"], s["TD"] = int(doubles >= 2), int(doubles >= 3)
    return s


def summary(match):
    result = {}
    for side in ("home", "away"):
        events = [e for e in effective_events(match.events) if e.team_id == side and e.event_type.startswith("BB_")]
        team = getattr(match, side + "_team")
        ids = {p.id: p.name for p in team.players}
        ids.update({e.basketball["player_id"]: e.player_name for e in events if e.basketball.get("player_id")})
        result[side] = {"team": box_score(events), "players": {pid: {"name": name, "stats": box_score([e for e in events if e.basketball.get("player_id") == pid])} for pid, name in ids.items()}, "periods": {p: box_score([e for e in events if e.basketball.get("period") == p])["PTS"] + box_score([e for e in events if e.basketball.get("period") == p])["ADJUSTMENT"] for p in dict.fromkeys(e.basketball.get("period", "Unspecified") for e in events)}}
    for side in ("home", "away"):
        playing = playing_stats(match, side)
        for pid, player in result[side]["players"].items():
            player["stats"].update(playing.get(pid, {"MIN": None, "+/-": None}))
    return result


def recalculate(match):
    for side in ("home", "away"):
        s = box_score([e for e in match.events if e.team_id == side])
        if match.basketball_baseline is not None:
            setattr(match, side + "_score", match.basketball_baseline.get(side, 0) + s["PTS"] + s["ADJUSTMENT"])
        elif any(e.event_type.startswith("BB_") for e in match.events):
            setattr(match, side + "_score", s["PTS"] + s["ADJUSTMENT"])
    match.away_score += box_score([e for e in match.events if e.team_id == "home"])["POINTS_AGAINST"]
    match.away_score += sum(e.basketball.get("points", 0) for e in match.events if e.event_type == "BB_OPPONENT_SCORE" and e.team_id == "home")
    return match


def display(value):
    return "—" if value is None else str(value)


def report(match):
    lines = ["STAT TRACKER — BASKETBALL", match.title, match.date, f"Score: {match.home_score} – {match.away_score}", "Only recorded events are counted. — means a rate or playing time cannot be calculated.", "Historical score carried forward: " + str(match.basketball_baseline or {})]
    for side, data in summary(match).items():
        if side != "home": continue
        lines += ["", getattr(match, side + "_team").name, "Period points: " + str(data["periods"])]
        lines += [f"{k} ({DEFINITIONS[k][0]}): {display(v)}" for k, v in data["team"].items() if k not in ("DD", "TD", "BENCH")]
    lines += ["", "SCC SEQUENCES"] + [key.upper() + ": " + value for key, value in sequences(match.events).items()]
    lines += ["", "EVENTS"] + [f"{e.basketball.get('period', '')} {e.minute}:{e.second:02d} {e.team_id}: {e.player_name} — {e.description}" for e in match.events]
    lines += ["", "STAT DEFINITIONS"] + [f"{k} — {name}: {definition}" for k, (name, definition) in DEFINITIONS.items() if k not in ("MIN", "+/-", "BENCH", "DD", "TD")]
    lines += ["", "=== STAT_TRACKER_AI_MATCH_DATA_START ===", json.dumps(match.to_dict(), indent=2), "=== STAT_TRACKER_AI_MATCH_DATA_END ==="]
    return "\n".join(lines)


PENALTY_TYPES = [("FT", "Free throw"), ("PF", "Personal foul"), ("SHOOTING", "Shooting foul"), ("OFFENSIVE", "Offensive foul / charge"), ("BLOCKING", "Blocking foul"), ("HOLDING", "Holding foul"), ("TF", "Technical foul"), ("UF", "Unsportsmanlike foul"), ("DF", "Disqualifying foul"), ("TEAM", "Team-foul penalty"), ("VIOLATION", "Violation"), ("OTHER", "Other penalty")]

def sequences(events):
    result = {"attack": "", "defence": "", "cards": ""}
    symbols = {"TF":"Tf", "UF":"Uf", "DF":"Df", "PF":"Pf", "FD":"Fd", "CHARGE":"Cd","SHORT_PASS": "Sp", "SHORT_PASS_INCOMPLETE": "Sp!", "LONG_PASS": "Lp", "LONG_PASS_INCOMPLETE": "Lp!", "DRIBBLE": "D", "DRIBBLE_INCOMPLETE": "D!","SHOT_AGAINST": "As", "SHOT_AGAINST_MISSED": "As!","SHOT": "S", "SHOT_MISSED": "S!", "LAYUP": "L", "LAYUP_MISSED": "L!", "AST": "A", "OREB": "Or", "DREB": "Dr", "STL": "S", "BLK": "B", "BA": "Sb", "DEFLECTION": "D", "LOOSE": "Lb", "TO": "[TURN]", "TIMEOUT": "[STOP]", "SUBSTITUTION": "[SUB]", "END_QUARTER": "[TIME]", "FULL_TIME": "[FT]"}
    defence = {"SHOT_AGAINST", "SHOT_AGAINST_MISSED", "SHOT_AGAINST_MADE","DREB", "STL", "BLK", "BA", "CHARGE", "DEFLECTION", "LOOSE", "PF"}
    for e in effective_events(events):
        if e.team_id != "home": continue
        key = e.event_type.removeprefix("BB_")
        group = "cards" if key in ("TF", "UF", "DF") else "defence" if key in defence else "attack"
        if key == "PENALTY":
            group = "defence" if e.basketball.get("direction") == "defence" else "attack"
            symbol = "P[" + e.basketball.get("penalty_type", "OTHER") + "]"
        elif key == "SHOT_AGAINST_MADE":
            symbol = "As^" + ("A" if e.basketball.get("assist") else "") + str(e.basketball["points"])
        elif e.basketball.get("shot_action"):
            symbol = "S^" + ("A" if e.basketball.get("assist") else "") + str({"FT_MADE": 1, "2_MADE": 2, "3_MADE": 3}[key])
        elif key.endswith("_INCOMPLETE"):
            symbol = symbols.get(key.removesuffix("_INCOMPLETE"),key.removesuffix("_INCOMPLETE")) + "!"
        else:
            symbol = symbols.get(key, key if key not in ("ADJUSTMENT", "OPPONENT_SCORE", "LINEUP") else "")
        result[group] += symbol
    return result
