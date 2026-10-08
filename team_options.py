"""Shared team choices for matches and coach accounts."""
import flet as ft

def _build_team_rank_options() -> list[str]:
    """Junior age groups and the eight senior teams."""
    return ([f"U{age}{code}" for age in (14,15,16) for code in "ABCDEFGHI"]
            + [f"{rank} Team" for rank in ("1st","2nd","3rd","4th","5th","6th","7th","8th")]
            + ["Other"])

TEAM_RANK_OPTIONS = _build_team_rank_options()

def team_dropdown(value=None, **kwargs):
    normalized=(value or "").replace(" ", "").upper()
    selected=next((x for x in TEAM_RANK_OPTIONS if x.replace(" ", "").upper()==normalized),value or None)
    options=list(TEAM_RANK_OPTIONS)
    if selected and selected not in options: options.append(selected)
    return ft.Dropdown(label="Team / Age Group",value=selected,options=[ft.dropdown.Option(x) for x in options],**kwargs)
