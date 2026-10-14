"""Outdoor field-hockey actions and SCC-only accounting."""
import json
from collections import Counter

# Event code, label, sequence symbol, supports incomplete, plain-language help.
GROUPS = {
 'Attack': [
  ('PASS','Short pass','Sp',True,'A short pass to a teammate.'),
  ('LONG_PASS','Long pass','Lp',True,'A pass over a longer distance to a teammate.'),
  ('DRIBBLE','Dribble','D',True,'Carry the ball with the stick while keeping control.'),
  ('CROSS','Cross','C',True,'Send the ball across the attacking circle to a teammate.'),
  ('CIRCLE_ENTRY','Circle entry','Ce',True,'Take or pass the ball into the attacking shooting circle.'),
  ('SHOT','Shot','S',True,'An attempt to score. Use Conversion if it scores, or Shot ! if it misses or is saved.'),
  ('FREE_HIT','Free hit','Fh',False,'A free hit awarded to SCC; does not add a goal.'),
  ('PENALTY_CORNER','Penalty corner','Pc',False,'A penalty corner awarded to SCC. Log the resulting shot separately.'),
  ('PENALTY_STROKE','Penalty stroke','Ps',False,'A penalty stroke awarded to SCC. Log its shot and result separately.'),
  ('LONG_CORNER','Long corner','Lc',False,'An attacking restart on the 23-metre line after an unintentional defender touch over the back-line.'),
  ('SIDE_IN','Side-line restart','Sr',True,'Put the ball back into play with the stick from the side-line.'),
  ('GOAL','Goal','G',False,'An SCC goal. Use this OR Shot followed by Conversion, never both for one goal.'),
  ('ASSIST','Assist','A',False,'The final pass that directly creates an SCC goal. Log once per assisted goal.'),
 ],
 'Defense': [
  ('TACKLE','Tackle','T',True,'Win the ball from an opponent controlling it.'),
  ('INTERCEPT','Intercept','I',True,'Cut out an opponent pass.'),
  ('BLOCK','Block','B',True,'An outfield player stops or deflects an opponent shot.'),
  ('SAVE','Save','Sv',True,'The goalkeeper prevents a goal.'),
  ('CLEAR','Clear','Cl',True,'Move the ball out of a dangerous defensive area.'),
  ('RECOVERY','Ball recovery','Br',True,'Gain control of a loose ball.'),
 ],
 'Cards': [
  ('GREEN_CARD','Green card','Gc',False,'A green card shown to SCC. Record the umpire’s decision.'),
  ('YELLOW_CARD','Yellow card','Yc',False,'A temporary suspension shown to SCC.'),
  ('RED_CARD','Red card','Rc',False,'A permanent dismissal shown to SCC.'),
 ],
 'Opposition': [
  ('SHOT_AGAINST','Shot against','As',True,'An opponent shot. Use Conversion if it scores, or Shot against ! if it does not.'),
  ('GOALS_GIVEN','Goal against','Ga',False,'An opponent goal. Use this OR Shot against followed by Conversion.'),
  ('FREE_HIT_AGAINST','Free hit against','Afh',False,'A free hit awarded against SCC.'),
  ('PENALTY_CORNER_AGAINST','Penalty corner against','Apc',False,'A penalty corner awarded against SCC; log its shot separately.'),
  ('PENALTY_STROKE_AGAINST','Penalty stroke against','Aps',False,'A penalty stroke awarded against SCC; log its shot separately.'),
 ]
}
ACTIONS={row[0]:row for rows in GROUPS.values() for row in rows}
INCOMPLETES={code for code,row in ACTIONS.items() if row[3]}
RULES=[('Hockey','Outdoor hockey with a stick and ball. Record SCC actions; use Opposition for awards and shots against SCC. No player details are needed.',False)] + [(r[1],r[4],r[3]) for rows in GROUPS.values() for r in rows] + [
 ('Conversion and incompletes','Conversion adds one goal to the team that took the latest shot. ! changes that shot to unsuccessful. Conversion does not automatically add an assist.',False),
 ('Match timing','Use the clock and period controls according to your school competition. Card suspension lengths follow the umpire’s decision.',False),
 ('Rates','Completion rate = successful actions divided by attempts. Shot conversion = scored shots divided by shot attempts. A dash means there are no attempts.',False)]

def outcomes(events):
    own=[e for e in events if e.team_id=='home']
    by_id={e.id:e for e in own}; failed=set(); converted=set()
    for e in own:
        target=by_id.get(e.target_id)
        if not target:continue
        if e.event_type==target.event_type+'_INCOMPLETE' and target.event_type in INCOMPLETES:failed.add(target.id)
        if e.event_type=='CONVERSION' and target.event_type in ('SHOT','SHOT_AGAINST'):converted.add(target.id)
    return own,failed,converted-failed

def statistics(match):
    events,failed,converted=outcomes(match.events)
    totals=Counter(e.event_type for e in events if e.event_type in ACTIONS)
    data={}
    for group,rows in GROUPS.items():
        if group=='Opposition':continue
        for code,label,_,inc,_ in rows:
            attempts=totals[code]; misses=sum(e.id in failed for e in events if e.event_type==code)
            successes=attempts-misses
            if code=='SHOT':
                attempts+=totals['GOAL']
                successes=totals['GOAL']+sum(e.id in converted for e in events if e.event_type==code)
            if code=='GOAL':successes=totals['GOAL']+sum(e.id in converted for e in events if e.event_type=='SHOT')
            data[code]=(label,attempts if code=='SHOT' else successes)
            if inc:
                data[code+'_INCOMPLETE']=(label+' incomplete',misses)
                if code=='SHOT':data['SHOT_UNRESOLVED']=('Shots awaiting result',sum(e.event_type=='SHOT' and e.id not in failed|converted for e in events))
                data[code+'_RATE']=(label+(' conversion %' if code=='SHOT' else ' completion %'),round(100*successes/attempts,1) if attempts else None)
    data['POSSESSION']=('Possession %',match.stats.home_possession)
    data['TURNOVER']=('Turnover',sum(e.event_type=='TURNOVER' for e in events))
    return data

def recalculate(match):
    from models import MatchStats
    old=match.stats; data=statistics(match)
    baseline=match.hockey_baseline or {'home':0,'away':0}
    match.home_score=baseline['home']+data['GOAL'][1]
    match.away_score=baseline['away']+conceded(match.events)
    match.stats=MatchStats(home_possession=old.home_possession,away_possession=old.away_possession,
        home_possession_seconds=old.home_possession_seconds,away_possession_seconds=old.away_possession_seconds,
        home_goals=match.home_score,home_shots=data['SHOT'][1],home_completed_passes=data['PASS'][1]+data['LONG_PASS'][1],
        home_tackles=data['TACKLE'][1],home_saves=data['SAVE'][1])
    return match

def sequences(events):
    own,failed,converted=outcomes(events); result={k.lower().replace('defense','defence'):[] for k in GROUPS}
    timing={'TURNOVER':'[TURN]','SUBSTITUTION':'[SUB]','END_QUARTER':'[TIME]','FULL_TIME':'[END]','TIMEOUT':'[STOP]'}
    for e in own:
        if e.event_type in timing:
            for values in result.values():values.append(timing[e.event_type])
        for group,rows in GROUPS.items():
            row=next((r for r in rows if r[0]==e.event_type),None)
            if row:result[group.lower().replace('defense','defence')].append(row[2]+('!' if e.id in failed else '^G' if e.id in converted else ''))
    return {k:' '.join(v) for k,v in result.items()}

def report(match):
    lines=['STAT TRACKER — HOCKEY',match.title,str(match.date),f'Score: {match.home_score} - {match.away_score}','','SCC STATISTICS']
    lines += [f'{label}: {value if value is not None else "—"}' for label,value in statistics(match).values()]
    lines += ['','SCC SEQUENCES']+[f'{k.replace("defence","defense").capitalize()}: {v}' for k,v in sequences(match.events).items()]
    lines += ['','EVENTS']+[f'{e.minute}:{e.second:02d} {e.description}' for e in match.events]
    lines += ['','=== STAT_TRACKER_MATCH_DATA_START ===',json.dumps(match.to_dict(),indent=2),'=== STAT_TRACKER_MATCH_DATA_END ===']
    return '\n'.join(lines)


def conceded(events):
    own,failed,converted=outcomes(events)
    return sum(e.event_type in ('GOALS_GIVEN','GOALS_GIVEN_CONVERSION') or (e.event_type=='SHOT_AGAINST' and e.id in converted) for e in own)


def ensure_baseline(match):
    if match.hockey_baseline is None:
        match.hockey_baseline={'home':match.home_score-statistics(match)['GOAL'][1],'away':match.away_score-conceded(match.events)}
