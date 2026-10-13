"""Concise help for the basketball controls currently available."""
ENTRIES = [
    ("Shot and conversion", "Shot records an attempt. Immediately use Conversion for 1, 2 or 3 points; tick Assist if a pass created the score. S^A2 = 2 points with an assist; S^2 = without. Shot ! records a miss."),
    ("Layup", "A made close-range shot: adds 2 points. Layup ! removes those points and records a miss."),
    ("Short pass, long pass and dribble", "Short pass: half court or shorter. Long pass: half court or longer. Dribble: move while bouncing the ball and keeping control. Mark an unsuccessful action with !."),
    ("Rebounds", "Offensive rebound: recover an SCC miss. Defensive rebound: recover an opponent miss. Total rebounds adds both."),
    ("Steal, block and deflection", "Steal: win the ball from the opponent. Block: stop or deflect their shot. Deflection: disrupt their pass. Loose ball recovered: gain a ball neither team controls."),
    ("Opposition", "Shot against (As) uses Conversion for opponent points. Layup against (Al) adds 2 opponent points; Al! removes them. Shot blocked against records an SCC shot blocked by the opponent."),
    ("Penalty and Cards", "Attack Penalty: awarded to SCC. Opposition Penalty: awarded against SCC. Select the free throw or foul type; this does not add points. Cards records technical, unsportsmanlike and disqualifying fouls. Log each decision once."),
    ("Incompletes and corrections", "Press the matching ! after an unsuccessful action. It changes that action, not its section. Undo last event removes a mistaken entry. No player details are recorded."),
    ("Possession and turnover", "Select the team holding the ball. Turnover [TURN] changes possession; it is not added automatically by an incomplete."),
    ("Time controls", "Timeout [STOP] pauses the clock. Overtime [OVER] enters the current quarter’s OT. End of quarter [TIME] moves to the next quarter; after Q4 or OT4 it ends the match [END]. Substitution [SUB] records a team change."),
    ("Shooting totals and percentages", "Made = successful shots; attempted = made + classified misses. FG includes 2- and 3-point shots; FT means free throws. Each shooting percentage is made ÷ attempted × 100. Unclassified misses and unresolved shots are excluded, so incomplete logging can inflate these rates. A dash means no usable attempts."),
    ("Other rates", "Effective FG% gives extra credit to 3-pointers. True shooting% estimates scoring efficiency including free throws. Assist/turnover ratio divides assists by turnovers. Three-point and free-throw attempt rates compare those attempts with field-goal attempts. Points per 100 possessions is an estimate, not a measured possession count."),
]
