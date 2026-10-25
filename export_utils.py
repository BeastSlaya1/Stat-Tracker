"""Portable, human-readable default export filenames."""
import re

def match_filename(match):
    title=(match.title or f'{match.home_team.name} vs {match.away_team.name}').strip()
    title=re.sub(r'[<>:"/\\|?*\x00-\x1f]','-',title)
    title=re.sub(r'\s+',' ',title).strip(' .')[:150].rstrip(' .') or 'Match'
    if title.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}:title='Match '+title
    return title+'.txt'
