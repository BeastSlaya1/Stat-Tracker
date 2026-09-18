"""
StatTracker AI — Data Models (v4)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List

SPORTS = ["SOCCER", "HOCKEY", "BASKETBALL", "RUGBY", "RUGBY_SEVENS", "WATERPOLO", "CRICKET"]

EVENT_TYPES = [
    "GOAL", "SHOT", "SHOT_ON_TARGET", "SHOT_INCOMPLETE",
    "PASS", "PASS_INCOMPLETE", "LONG_PASS", "LONG_PASS_INCOMPLETE",
    "CROSS", "CROSS_INCOMPLETE",
    "FOUL", "FOULS_WON", "FOULS_GIVEN",
    "YELLOW_CARD", "RED_CARD", "CORNER", "OFFSIDE", "OFFSIDE_INCOMPLETE",
    "OFFSIDE_GIVEN", "OFFSIDE_GIVEN_INCOMPLETE",
    "SUBSTITUTION", "SAVE", "SAVE_INCOMPLETE",
    "TACKLE", "TACKLE_INCOMPLETE", "CONVERSION", "ASSIST",
    "THROW_IN", "THROW_IN_INCOMPLETE",
    "INTERCEPT", "INTERCEPT_INCOMPLETE",
    "BLOCK", "BLOCK_INCOMPLETE",
    "CLEAR", "CLEAR_INCOMPLETE",
    "GK_KICK", "GK_THROW",
    "DRIBBLE", "TURNOVER", "PENALTY",
]

PERIODS = ["SCHEDULED", "1ST_HALF", "HALF_TIME", "2ND_HALF", "OVERTIME", "FULL_TIME"]

PERIOD_LABELS = {
    "SCHEDULED":  "PRE-MATCH",
    "1ST_HALF":   "1ST HALF",
    "HALF_TIME":  "HALF TIME",
    "2ND_HALF":   "2ND HALF",
    "OVERTIME":   "OVERTIME",
    "FULL_TIME":  "FULL TIME",
}

# St Charles College locked colours (req 14)
SCC_COLORS = ["#1E3A8A", "#FFFFFF", "#FFD700"]
SCC_NAMES = {"st charles", "st charles college", "scc"}


@dataclass
class Player:
    id: str
    number: int
    name: str
    position: str
    goals: int = 0
    assists: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    rating: float = 0.0
    is_starter: bool = True
    scan_video_path: Optional[str] = None   # temp path, not persisted

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d.pop("scan_video_path", None)   # never persist scan path (req 17)
        return d

    @staticmethod
    def from_dict(d: dict) -> "Player":
        return Player(**{k: v for k, v in d.items() if k in Player.__dataclass_fields__})


@dataclass
class Team:
    id: str          # 'home' or 'away'
    name: str
    short_name: str
    logo_color: str
    secondary_color: str
    badge_symbol: str
    players: List[Player] = field(default_factory=list)
    school_name: str = ""
    team_rank: str = "1st Team"
    kit_color_primary: str = "#1E3A8A"
    kit_color_secondary: str = "#FFFFFF"
    # req 13/15: full list of kit colours (min 2, no max)
    kit_colors: List[str] = field(default_factory=list)
    # req 19: base64 logo (None = render short_name text)
    logo_base64: Optional[str] = None

    def __post_init__(self):
        # Migrate old 2-colour model → kit_colors list
        if not self.kit_colors:
            self.kit_colors = [self.kit_color_primary, self.kit_color_secondary]

    @property
    def is_scc(self) -> bool:
        return self.name.lower() in SCC_NAMES or self.school_name.lower() in SCC_NAMES

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["players"] = [p.to_dict() for p in self.players]
        return d

    @staticmethod
    def from_dict(d: dict) -> "Team":
        players = [Player.from_dict(p) for p in d.get("players", [])]
        fields = {k: v for k, v in d.items()
                  if k in Team.__dataclass_fields__ and k != "players"}
        t = Team(players=players, **fields)
        # Ensure kit_colors populated
        if not t.kit_colors:
            t.kit_colors = [t.kit_color_primary, t.kit_color_secondary]
        return t


@dataclass
class StatEvent:
    id: str
    timestamp: str
    minute: int
    team_id: str       # 'home' or 'away'
    event_type: str
    player_name: str
    description: str
    pitch_x: float = 50.0
    pitch_y: float = 50.0
    xg: float = 0.0
    assisted_by: Optional[str] = None
    tactical_note: Optional[str] = None
    second: int = 0

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @staticmethod
    def from_dict(d: dict) -> "StatEvent":
        return StatEvent(**{k: v for k, v in d.items()
                            if k in StatEvent.__dataclass_fields__})


@dataclass
class MatchStats:
    home_possession: int = 50
    away_possession: int = 50
    home_possession_seconds: int = 0   # accumulated real seconds SCC has had the ball
    away_possession_seconds: int = 0   # accumulated real seconds opponent has had the ball
    home_shots: int = 0
    away_shots: int = 0
    home_shots_on_target: int = 0
    away_shots_on_target: int = 0
    home_incomplete_shots: int = 0
    away_incomplete_shots: int = 0
    home_passes: int = 0
    away_passes: int = 0
    home_completed_passes: int = 0
    away_completed_passes: int = 0
    home_incomplete_passes: int = 0
    away_incomplete_passes: int = 0
    home_pass_acc: int = 80
    away_pass_acc: int = 80
    home_crosses: int = 0
    away_crosses: int = 0
    home_completed_crosses: int = 0
    away_completed_crosses: int = 0
    home_incomplete_crosses: int = 0
    away_incomplete_crosses: int = 0
    home_goals: int = 0
    away_goals: int = 0
    home_assists: int = 0
    away_assists: int = 0
    home_conversions: int = 0
    away_conversions: int = 0
    home_xg: float = 0.0
    away_xg: float = 0.0
    home_fouls: int = 0
    away_fouls: int = 0
    home_tackles: int = 0
    away_tackles: int = 0
    home_incomplete_tackles: int = 0
    away_incomplete_tackles: int = 0
    home_saves: int = 0
    away_saves: int = 0
    home_corners: int = 0
    away_corners: int = 0
    home_yellow_cards: int = 0
    away_yellow_cards: int = 0
    home_red_cards: int = 0
    away_red_cards: int = 0

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @staticmethod
    def from_dict(d: dict) -> "MatchStats":
        return MatchStats(**{k: v for k, v in d.items()
                             if k in MatchStats.__dataclass_fields__})


@dataclass
class Match:
    id: str
    sport: str
    title: str
    date: str
    location: str
    home_team: Team
    away_team: Team
    home_score: int = 0
    away_score: int = 0
    minute: int = 1
    second: int = 0          # req 10: track seconds within the minute
    period: str = "1ST_HALF"
    is_live: bool = True
    stats: MatchStats = field(default_factory=MatchStats)
    events: List[StatEvent] = field(default_factory=list)
    possession_team: Optional[str] = None   # "home" | "away" | None — who currently has the ball
    logged_by: str = ""      # name of the person logging this match

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["home_team"] = self.home_team.to_dict()
        d["away_team"] = self.away_team.to_dict()
        d["stats"] = self.stats.to_dict()
        d["events"] = [e.to_dict() for e in self.events]
        return d

    @staticmethod
    def from_dict(d: dict) -> "Match":
        home_team = Team.from_dict(d["home_team"])
        away_team = Team.from_dict(d["away_team"])
        stats = MatchStats.from_dict(d.get("stats", {}))
        events = [StatEvent.from_dict(e) for e in d.get("events", [])]
        fields = {k: v for k, v in d.items()
                  if k in Match.__dataclass_fields__
                  and k not in ("home_team", "away_team", "stats", "events")}
        return Match(
            home_team=home_team, away_team=away_team,
            stats=stats, events=events, **fields
        )
