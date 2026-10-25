# Stat Tracker 4.0.25

Removed Scoring context, Score correction and the standalone Assist action. The assist checkbox remains in shot conversion.

Turnover is grouped with Time controls in normal and fullscreen views. Overtime records [OVER] in all sequences, enters the matching overtime period (Q2 to OT2), resets the displayed clock and starts it. Pressing Overtime again during overtime does nothing.

End of quarter records [TIME] before Q4, advances Q1/OT1 to Q2, Q2/OT2 to Q3, Q3/OT3 to Q4, and finishes after Q4/OT4 with [END]. Timeout pauses the clock at its current value. Sequence entries are separated by spaces; suffixes stay attached (S^A2, Sp!, P[PF]). The next quarter starts paused at zero. Period choices are ordered Q1, OT1, Q2, OT2, Q3, OT3, Q4, OT4, Full time.

Upload source contents through GitHub and deploy the web build. Publish Windows and Android files as v4.0.25 (Android build 26). No additional server change is required for this update.

112 app tests passed, including every quarter/overtime transition and timer start/repeated-button behavior. Android hardware interaction has not been tested.
