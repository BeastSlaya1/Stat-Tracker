"""SCC-only statistics shared by match views and comparisons."""
from collections import Counter

def match_statistics(match):
    if match.sport == 'BASKETBALL':
        from basketball import summary, DEFINITIONS
        return {key:(DEFINITIONS[key][0],value) for key,value in summary(match)['home']['team'].items() if key not in ('DD','TD','BENCH')}
    if match.sport == 'SOCCER':
        return {key:(key.removeprefix('home_').replace('_',' ').capitalize(),value) for key,value in match.stats.to_dict().items() if key.startswith('home_')}
    counts=Counter(e.event_type for e in match.events if e.team_id=='home')
    return {'score':('SCC score',match.home_score),**{key:(key.replace('_',' ').capitalize(),value) for key,value in counts.items()}}
