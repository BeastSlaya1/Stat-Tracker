"""Short help for the active basketball logger controls."""
ENTRIES = [
    ("Player jerseys", "Choose a jersey before recording an SCC player stat. Shot, conversion, rebound, steal and foul events are credited to that jersey. The team roster can be edited offline and synchronized later."),
    ("Shots and conversions", "Press Shot for an SCC attempt, then Conversion to record 1, 2 or 3 points. Mark Shot ! for an unconverted miss. A made conversion and its shot stay with the selected jersey."),
    ("Rebounds", "Offensive rebound records an SCC recovery after an SCC miss. Defensive rebound records a recovery after an opponent miss. Both are credited to the selected jersey."),
    ("Steals and fouls", "Steal records a player winning possession from the opponent. Foul records a personal foul for the selected jersey."),
    ("Time controls", "Timeout [STOP] pauses the clock. Overtime [OVER] enters the current quarter’s overtime. End of quarter [TIME] advances to the next quarter; after Q4 or OT4 it ends the match [END]. Substitution [SUB] records a team change."),
    ("Shooting rates", "Made shots, attempts and shooting percentages are calculated from recorded conversions and incompletes. A dash means there were no attempts to calculate a rate."),
]
