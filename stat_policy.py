"""Actions retired from new logging; historical events remain readable."""
RETIRED_ACTIONS=frozenset({'PASS','SHORT_PASS','LONG_PASS','CROSS','DRIBBLE','GK_KICK','GK_THROW'})
def retired(code):
    return str(code).removeprefix('BB_').removesuffix('_INCOMPLETE') in RETIRED_ACTIONS

TEAM_ACTIONS={'TO','SUBSTITUTION','TIMEOUT','OVERTIME','END_QUARTER','FULL_TIME','LAYUP_AGAINST','SHOT_AGAINST','BA','OPPONENT_SCORE','ADJUSTMENT'}
