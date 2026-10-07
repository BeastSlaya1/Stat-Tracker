"""Shared team choices for matches and coach accounts."""
import flet as ft

def _build_team_rank_options() -> list[str]:
    """The full U14-U19 age-group/team-name list, generated the same way
    the source database's Age_Groups x Team_Codes pairing defines it:
    U14-U16 use lettered squads (A-I), U17-U19 use "1st"-"8th" ordinal
    squads instead (that's what Age_Groups.Special_Lists / Team_Codes.
    Special encode in the source data) — this mirrors how the school
    actually names its teams, rather than the smaller hand-picked list
    ("U14A".."U16B", "1st Team", "2nd Team") this dropdown used to be
    limited to."""
    letter_ages = (14, 15, 16)
    letter_codes = "ABCDEFGHI"
    special_ages = (17, 18, 19)
    special_codes = ("1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th")
    options = [f"U{age}{code}" for age in letter_ages for code in letter_codes]
    options += [f"U{age} {code}" for age in special_ages for code in special_codes]
    # Generic fallbacks, kept alongside the generated list — some
    # opponents/coaches just say "1st Team" with no specific U-age
    # attached, and any match saved before this change already has
    # team_rank set to exactly one of these two strings, so keeping them
    # as real options (rather than only "Other") means editing an old
    # match still shows its actual current value as selected.
    options += ["1st Team", "2nd Team", "Other"]
    return options

TEAM_RANK_OPTIONS = _build_team_rank_options()

def team_dropdown(value=None, **kwargs):
    normalized=(value or "").replace(" ", "").upper()
    selected=next((x for x in TEAM_RANK_OPTIONS if x.replace(" ", "").upper()==normalized),value or None)
    options=list(TEAM_RANK_OPTIONS)
    if selected and selected not in options: options.append(selected)
    return ft.Dropdown(label="Team / Age Group",value=selected,options=[ft.dropdown.Option(x) for x in options],**kwargs)
