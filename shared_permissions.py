"""Host-authoritative assignments for shared-match input devices."""
SECTIONS=('All','Attack','Defense','Cards','Opposition')

def catalog(sport):
    if sport=='BASKETBALL':
        return {
            'Attack':dict(SHORT_PASS='Short pass',LONG_PASS='Long pass',DRIBBLE='Dribble',LAYUP='Layup',SHOT='Shot (including conversion)',OREB='Offensive rebound',PENALTY_ATTACK='Penalty'),
            'Defense':dict(DREB='Defensive rebound',STL='Steal',BLK='Block',DEFLECTION='Deflection',LOOSE='Loose ball recovered'),
            'Cards':dict(TF='Technical foul',UF='Unsportsmanlike foul',DF='Disqualifying foul'),
            'Opposition':dict(LAYUP_AGAINST='Layup against',SHOT_AGAINST='Shot against (including conversion)',BA='Shot blocked against',PENALTY_OPPOSITION='Penalty against'),
            'Match actions':dict(TO='Turnover',SUBSTITUTION='Substitution')}
    return {
        'Attack':dict(LONG_PASS='Long pass',PASS='Pass',CROSS='Cross',SHOT='Shot',CORNER='Corner',THROW_IN='Throw-in',DRIBBLE='Dribble',FOULS_WON='Fouls won',GK_KICK='Goalkeeper kick',GK_THROW='Goalkeeper throw',GOAL='Goal',ASSIST='Assist'),
        'Defense':dict(TACKLE='Tackle',SAVE='Save',BLOCK='Block',CLEAR='Clear',OFFSIDE='Offside received',INTERCEPT='Intercept'),
        'Cards':dict(YELLOW_CARD='Yellow card',RED_CARD='Red card'),
        'Opposition':dict(OFFSIDE_GIVEN='Offside given',GOALS_GIVEN='Goals given',FOULS_GIVEN='Fouls given',PENALTY='Penalty'),
        'Match actions':dict(TURNOVER='Turnover',SUBSTITUTION='Substitution')}

def assignment(sport,section='All',stats=None):
    if section not in SECTIONS:raise ValueError('Choose a valid section.')
    groups=catalog(sport)
    available={key for group,values in groups.items() if section=='All' or group==section for key in values}
    if stats is None:stats=sorted(available)
    if not isinstance(stats,list) or any(not isinstance(key,str) or key not in available for key in stats):raise ValueError('Choose stats from the assigned section.')
    return {'section':section,'stats':sorted(set(stats))}

def event_key(sport,event,events):
    code=event.event_type
    if sport=='BASKETBALL':
        if not code.startswith('BB_'):return None
        code=code[3:]
        if code in ('INCOMPLETE','CONVERSION'):
            target=next((e for e in events if e.id==event.basketball.get('target_id')),None)
            if target is None or target.event_type in ('BB_INCOMPLETE','BB_CONVERSION'):return None
            if code=='CONVERSION' and (target.event_type not in ('BB_SHOT','BB_SHOT_AGAINST') or type(event.basketball.get('points')) is not int or event.basketball['points'] not in (1,2,3)):return None
            if code=='INCOMPLETE':
                from basketball import INCOMPLETE_TYPES
                if target.event_type.removeprefix('BB_') not in INCOMPLETE_TYPES:return None
            return event_key(sport,target,[])
        if code=='PENALTY':return 'PENALTY_OPPOSITION' if event.basketball.get('direction') in ('opposition','defence') else 'PENALTY_ATTACK'
        return code
    if code=='GOALS_GIVEN_CONVERSION':return 'GOALS_GIVEN'
    if code=='CONVERSION':
        target=next((e for e in events if e.id==event.target_id),None)
        return target.event_type if target and target.event_type in catalog(sport)['Attack'] else None
    return code.removesuffix('_INCOMPLETE')

def permits(sport,permissions,event,events):
    return event_key(sport,event,events) in permissions['stats']
