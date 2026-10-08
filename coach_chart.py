"""SCC match comparison radar and its shared legend."""
import colorsys
import math
import flet as ft
import flet.canvas as cv


def match_label(match):
    def label(team):
        from team_options import TEAM_RANK_OPTIONS
        raw = team.team_code or team.team_rank
        age = next((x for x in TEAM_RANK_OPTIONS if x.replace(" ", "").upper()==raw.replace(" ", "").upper()),raw)
        return f"{age} {team.name}".strip()
    return f"{label(match.home_team)} vs {label(match.away_team)}"


def match_colors(count):
    palette=['#818cf8','#34d399','#fbbf24','#38bdf8','#fb7185','#c084fc']
    for i in range(len(palette),count):
        rgb=colorsys.hsv_to_rgb((i*.61803398875)%1,.65,.95)
        palette.append('#'+''.join(f'{round(c*255):02x}' for c in rgb))
    return palette[:count]


def radar_data(matches):
    if matches[0].sport=='BASKETBALL':
        from basketball import summary
        keys=['PTS','REB','AST','STL','BLK','FGM']
        return ['Points','Rebounds','Assists','Steals','Blocks','FG made'],[[summary(m)['home']['team'][k] for k in keys] for m in matches]
    if matches[0].sport=='SOCCER':
        keys=['home_shots','home_possession','home_tackles','home_completed_passes','home_saves','home_goals']
        return ['Shots','Poss.%','Tackles','Passes','Saves','Goals'],[[getattr(m.stats,k) for k in keys] for m in matches]
    from match_statistics import match_statistics
    stats=[match_statistics(m) for m in matches]
    keys=list(dict.fromkeys(k for data in stats for k in data))[:6]
    labels=[next(data[k][0] for data in stats if k in data) for k in keys]
    while len(keys)<3:
        keys.append('_unused'+str(len(keys)));labels.append('')
    return labels,[[data.get(k,('',0))[1] or 0 for k in keys] for data in stats]


def comparison_chart(matches, colors, width=480):
    labels,series=radar_data(matches)
    maximum=max([v for values in series for v in values]+[1])
    height=width*.86
    cx,cy=width/2,height/2
    radius=width*.29
    angles=[-math.pi/2+i*2*math.pi/len(labels) for i in range(len(labels))]
    def point(angle,fraction):return cx+math.cos(angle)*radius*fraction,cy+math.sin(angle)*radius*fraction
    def path(values,paint):
        points=[point(a,v) for a,v in zip(angles,values)]
        return cv.Path([cv.Path.MoveTo(*points[0])]+[cv.Path.LineTo(*p) for p in points[1:]]+[cv.Path.Close()],paint=paint)
    shapes=[]
    grid=ft.Paint(style=ft.PaintingStyle.STROKE,color='#263247',stroke_width=1)
    for fraction in (.25,.5,.75,1):shapes.append(path([fraction]*len(labels),grid))
    for angle,label in zip(angles,labels):
        shapes.append(cv.Line(cx,cy,*point(angle,1),paint=grid))
        shapes.append(cv.Text(*point(angle,1.25),label,style=ft.TextStyle(size=11,color='#b8c4d8'),alignment=ft.Alignment.CENTER))
    for values,color in zip(series,colors):
        fractions=[max(0,v)/maximum for v in values]
        shapes.append(path(fractions,ft.Paint(style=ft.PaintingStyle.FILL,color=ft.Colors.with_opacity(.10,color))))
        shapes.append(path(fractions,ft.Paint(style=ft.PaintingStyle.STROKE,color=color,stroke_width=2)))
        shapes.extend(cv.Circle(*point(a,v),radius=3,paint=ft.Paint(color=color)) for a,v in zip(angles,fractions))
    legend=[ft.Row([ft.Container(width=14,height=14,bgcolor=color,border_radius=3),ft.Text(f'{match_label(m)} · {m.date}',expand=True)],spacing=10) for m,color in zip(matches,colors)]
    return ft.Column([ft.Text('SCC performance comparison',size=18,weight=ft.FontWeight.BOLD),
        ft.Container(content=cv.Canvas(shapes=shapes,width=width,height=height),width=width,height=height),
        *legend,ft.Text(f'Common chart scale: 0–{maximum:g}. Exact values are shown in the comparisons below.',size=12,color='#94a3b8')],spacing=12)
