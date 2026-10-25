"""Host-authoritative assignments for shared-match input devices."""
SECTIONS=('All','Attack','Defense','Cards','Opposition')

def _catalog(sport):
    if sport=='HOCKEY':
        from hockey import GROUPS
        return {**{group:{r[0]:r[1] for r in rows} for group,rows in GROUPS.items()},'Match actions':dict(TURNOVER='Turnover',SUBSTITUTION='Substitution')}
    if sport=='BASKETBALL':
        return {
            'Attack':dict(SHOT='Shots and conversions',OREB='Offensive rebound'),
            'Defense':dict(DREB='Defensive rebound',STL='Steal',PF='Foul'),
            'Match actions':dict(TIMEOUT='Timeout',SUBSTITUTION='Substitution',OVERTIME='Overtime',END_QUARTER='End of quarter',FULL_TIME='Full time')}
    return {
        'Attack':dict(LONG_PASS='Long pass',PASS='Pass',CROSS='Cross',SHOT='Shot',CORNER='Corner',THROW_IN='Throw-in',DRIBBLE='Dribble',FOULS_WON='Fouls won',GK_KICK='Goalkeeper kick',GK_THROW='Goalkeeper throw',GOAL='Goal',ASSIST='Assist'),
        'Defense':dict(TACKLE='Tackle',SAVE='Save',BLOCK='Block',CLEAR='Clear',OFFSIDE='Offside received',INTERCEPT='Intercept'),
        'Cards':dict(YELLOW_CARD='Yellow card',RED_CARD='Red card'),
        'Opposition':dict(OFFSIDE_GIVEN='Offside given',GOALS_GIVEN='Goals given',FOULS_GIVEN='Fouls given',PENALTY='Penalty'),
        'Match actions':dict(TURNOVER='Turnover',SUBSTITUTION='Substitution')}

def catalog(sport):
    from stat_policy import retired
    return {group:{key:label for key,label in values.items() if not retired(key)} for group,values in _catalog(sport).items()}

def assignment(sport,section='All',stats=None,stream_only=False,players=None):
    if stream_only:return {'section':'Stream only','sections':[],'stats':[],'stream_only':True}
    sections=list(SECTIONS[1:]) if section=='All' else [section] if isinstance(section,str) else section
    if not isinstance(sections,list) or any(value not in SECTIONS[1:] for value in sections):raise ValueError('Choose valid sections.')
    sections=[value for value in SECTIONS[1:] if value in sections]
    groups=catalog(sport)
    available={key for group,values in groups.items() if section=='All' or group in sections for key in values}
    if stats is None:stats=sorted(available)
    if not isinstance(stats,list) or any(not isinstance(key,str) or key not in available for key in stats):raise ValueError('Choose stats from the assigned sections.')
    label='All' if len(sections)==4 else ' + '.join(sections) or 'No stat sections'
    if players is not None and (sport!='BASKETBALL' or not isinstance(players,list) or any(not isinstance(p,str) or not p or len(p)>100 for p in players)):raise ValueError('Choose valid players.')
    return {'section':label,'sections':sections,'stats':sorted(set(stats)), 'players':None if players is None else sorted(set(players))}

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
    if sport=='HOCKEY' and (code=='CONVERSION' or code.endswith('_INCOMPLETE')):
        from hockey import INCOMPLETES
        target=next((e for e in events if e.id==event.target_id),None)
        if target is None:return None
        if code=='CONVERSION':return target.event_type if target.event_type in ('SHOT','SHOT_AGAINST') else None
        return target.event_type if target.event_type in INCOMPLETES and code==target.event_type+'_INCOMPLETE' else None
    if code=='GOALS_GIVEN_CONVERSION':return 'GOALS_GIVEN'
    if code=='CONVERSION':
        target=next((e for e in events if e.id==event.target_id),None)
        return target.event_type if target and target.event_type in catalog(sport)['Attack'] else None
    return code.removesuffix('_INCOMPLETE')

def permits(sport,permissions,event,events):
    if event_key(sport,event,events) not in permissions['stats']:return False
    if sport!='BASKETBALL':return True
    from stat_policy import TEAM_ACTIONS
    parent=next((e for e in events if e.id==event.basketball.get('target_id')),event)
    code=parent.event_type.removeprefix('BB_')
    if code in TEAM_ACTIONS or (code=='PENALTY' and parent.basketball.get('direction') in ('opposition','defence')):return True
    allowed=permissions.get('players')
    return (event.basketball.get('player_id','')==parent.basketball.get('player_id','') and
            (allowed is None or parent.basketball.get('player_id') in allowed) and
            (not event.basketball.get('assist_player_id') or allowed is None or event.basketball['assist_player_id'] in allowed))
