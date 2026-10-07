import json
import threading
import unittest
from unittest.mock import patch
import flet as ft
from models import Match, Team, Player
from engine import make_event, recalculate_stats
from basketball import box_score, summary, report, DEFINITIONS
from test_app_integration import app, controls


def match():
    teams = [Team(id=s, name=s, short_name=s, logo_color="#111111", secondary_color="#ffffff", badge_symbol="") for s in ("home", "away")]
    return Match("bb", "BASKETBALL", "Test", "2026-10-03", "Home", *teams, minute=0, period="Q1")


def event(m, code, side="home", pid="", tags=None):
    e = make_event(m, side, "BB_"+code, pid, code)
    e.basketball = {"player_id": pid, "tags": tags or [], "period": m.period}
    m.events.append(e)
    return e


class BasketballTests(unittest.TestCase):
    def test_shooting_math_and_both_scores(self):
        m = match()
        for c in ("2_MADE", "2_MISSED", "3_MADE", "3_MISSED", "FT_MADE", "FT_MISSED"):
            event(m,c)
        event(m,"3_MADE","away")
        recalculate_stats(m)
        self.assertEqual((m.home_score,m.away_score),(6,3))
        s=box_score(m.events[:-1])
        self.assertEqual((s["FGM"],s["FGA"],s["FG%"],s["eFG%"]),(2,4,50,62.5))
        self.assertAlmostEqual(s["TS%"],61.5)
        self.assertEqual(s["PTS"],6)

    def test_empty_rates_are_unavailable(self):
        s=box_score([])
        for k in ("FG%","FT%","TS%","AST/TO","ORTG"):
            self.assertIsNone(s[k])
        self.assertTrue(set(s).issubset(DEFINITIONS))

    def test_player_id_separates_duplicate_names(self):
        m=match()
        for pid in ("a","b"):
            m.home_team.players.append(Player(pid,1,"Same name","Guard"))
        event(m,"2_MADE",pid="a")
        event(m,"3_MADE",pid="b")
        event(m,"FT_MADE")
        s=summary(m)["home"]
        self.assertEqual(s["team"]["PTS"],6)
        self.assertEqual(s["players"]["a"]["stats"]["PTS"],2)
        self.assertEqual(s["players"]["b"]["stats"]["PTS"],3)

    def test_tags_do_not_invent_points_or_paint_threes(self):
        m=match()
        event(m,"2_MADE",tags=["paint","fastbreak"])
        event(m,"3_MADE",tags=["paint","secondchance"])
        event(m,"2_MISSED",tags=["paint","fastbreak"])
        s=box_score(m.events)
        self.assertEqual((s["PTS"],s["PAINT"],s["FASTBREAK"],s["SECONDCHANCE"]),(5,2,2,3))

    def test_fouls_rebounds_efficiency(self):
        m=match()
        for c in ("OREB","DREB","UF","DF","PF","TF","AST","TO","STL","BLK"):
            event(m,c)
        s=box_score(m.events)
        self.assertEqual((s["PF"],s["TF"],s["REB"],s["EFF"]),(3,1,2,4))

    def test_roundtrip_preserves_event_details(self):
        m=match();event(m,"3_MADE",pid="p",tags=["fastbreak"])
        restored=Match.from_dict(json.loads(json.dumps(m.to_dict())))
        self.assertEqual(restored.events[0].basketball,m.events[0].basketball)
        self.assertEqual(summary(restored),summary(m))
        self.assertIn("STAT_TRACKER_AI_MATCH_DATA_START",report(restored))
        self.assertIn("Three-point percentage",report(restored))

    def test_ui_undo_restores_baseline_and_bench_tags(self):
        a=app();m=match();m.home_score=7;a.matches=[m];a._save=lambda:None
        m.home_team.players=[Player("p",5,"Bench","Guard",is_starter=False)]
        a._bb_log("3_MADE","home","p")
        self.assertEqual(m.home_score,10)
        self.assertEqual(summary(m)["home"]["team"]["BENCH"],0)
        self.assertEqual(m.events[-1].basketball["player_id"],"")
        self.assertEqual(m.events[-1].player_name,m.home_team.short_name)
        a._undo_last_event()
        self.assertEqual(m.home_score,7)
        a._bb_log("ADJUSTMENT","away",points=2)
        self.assertEqual(m.away_score,2)
        self.assertEqual(summary(m)["away"]["team"]["FGA"],0)
        a._delete_event(m.events[0].id)
        self.assertEqual(m.away_score,0)

    def test_period_switch_stops_clock(self):
        a=app();a.matches=[match()];a._save=lambda:None;a._timer_lock=threading.Lock();a._timer_running=True
        a.match.minute=4
        a._bb_choose_period("Q2")
        self.assertFalse(a._timer_running)
        self.assertEqual((a.match.period,a.match.minute,a.match.second),("Q2",0,0))

    def test_basketball_ui_constructs_and_actions_work(self):
        a=app();a.matches=[match()];a._save=lambda:None;a._timer_running=False
        a._build_live_video_panel=lambda:ft.Text("Video")
        logger=a._build_logger_tab(a.match)
        buttons=[c for c in controls(logger) if isinstance(c,ft.Container) and c.on_click]
        next(c for c in buttons if any(isinstance(t,ft.Text) and t.value=="Layup" for t in controls(c))).on_click(None)
        self.assertEqual(a.match.home_score,2)
        a._build_stats_tab(a.match)
        a._build_scoreboard(a.match)
        a._open_dictionary_dialog()
        self.assertEqual(a.page.dialog.title.value,"Dictionary")
        selector=next(c for c in controls(a.page.dialog) if isinstance(c,ft.Dropdown))
        self.assertEqual(selector.value,"BASKETBALL")
        self.assertEqual([o.text for o in selector.options],["Soccer rules","Basketball rules"])

    def test_lineup_minutes_plusminus_and_substitution_undo(self):
        a=app();m=match();a.matches=[m];a._save=lambda:None
        m.home_team.players=[Player(str(i),i,str(i),"Guard") for i in range(6)]
        a._bb_set_lineup("home",[str(i) for i in range(5)])
        m.basketball_elapsed=60
        a._bb_log("3_MADE","home","0")
        event(m,"2_MADE","away")
        a._bb_set_lineup("home",[str(i) for i in range(1,6)])
        m.basketball_elapsed=90
        stats=summary(m)["home"]["players"]
        self.assertEqual((stats["0"]["stats"]["MIN"],stats["0"]["stats"]["+/-"]),("1:00",1))
        self.assertEqual(stats["5"]["stats"]["MIN"],"0:30")
        a._undo_last_event()
        stats=summary(m)["home"]["players"]
        self.assertEqual(stats["0"]["stats"]["MIN"],"1:30")
        self.assertIsNone(stats["5"]["stats"]["MIN"])

    def test_dictionary_switches_sports_without_changing_match(self):
        from types import SimpleNamespace
        a=app();a.matches=[match()]
        a._open_dictionary_dialog()
        selector=next(c for c in controls(a.page.dialog) if isinstance(c,ft.Dropdown))
        selector.value="SOCCER";selector.on_select(SimpleNamespace(control=selector))
        values=[c.value for c in controls(a.page.dialog) if isinstance(c,ft.Text)]
        self.assertIn("Conversion",values)
        self.assertNotIn("MIN — Minutes played (tracked)",values)
        self.assertEqual(a.match.sport,"BASKETBALL")
        selector.value="BASKETBALL";selector.on_select(SimpleNamespace(control=selector))
        values=[c.value for c in controls(a.page.dialog) if isinstance(c,ft.Text)]
        self.assertIn("Team-only recording",values)
        self.assertNotIn("MIN — Minutes played (tracked)",values)

    def test_categories_and_soccer_comparison_controls(self):
        a=app();a.matches=[match()];a._save=lambda:None;a._timer_running=False
        a._build_live_video_panel=lambda:ft.Text("Video")
        logger=a._build_logger_tab(a.match)
        def click_text(root,label):
            target=next(c for c in controls(root) if isinstance(c,ft.Container) and c.on_click and any(isinstance(t,ft.Text) and t.value==label for t in controls(c)))
            target.on_click(None)
        click_text(logger,"Defence")
        logger=a._build_logger_tab(a.match)
        click_text(logger,"Steal")
        self.assertEqual(a.match.events[-1].event_type,"BB_STL")
        values=[c.value for c in controls(a._build_stats_tab(a.match)) if isinstance(c,ft.Text)]
        self.assertIn("Radar Comparison",values)
        self.assertIn("LIVE STAT COMPARISON",values)
        self.assertNotIn("Player minutes and plus/minus are not measured.",values)

    def test_incomplete_corrects_one_attempt_and_undo_restores_outcome(self):
        for side in ("home",):
            for kind,points in (("2",2),("3",3),("FT",1)):
                a=app();m=match();a.matches=[m];a._save=lambda:None;a._bb_side=side
                a._bb_log(kind+"_MADE",side)
                a._bb_mark_incomplete(kind+"_MADE")
                stats=summary(m)[side]["team"]
                self.assertEqual((stats[kind+"A"],stats[kind+"M"],getattr(m,side+"_score")),(1,0,0))
                self.assertIsNone(a._bb_last_completable())
                a._undo_last_event()
                stats=summary(m)[side]["team"]
                self.assertEqual((stats[kind+"A"],stats[kind+"M"],getattr(m,side+"_score")),(1,1,points))

    def test_incomplete_defence_and_wrong_team(self):
        a=app();m=match();a.matches=[m];a._save=lambda:None
        a._bb_log("STL","home")
        a._bb_side="away";a._bb_mark_incomplete("STL")
        self.assertEqual(len(m.events),2)
        self.assertEqual(m.events[-1].team_id,"home")
        self.assertEqual(summary(m)["home"]["team"]["STL"],0)
        self.assertEqual(summary(m)["away"]["team"]["TO"],0)
        restored=Match.from_dict(m.to_dict())
        self.assertEqual(summary(restored),summary(m))

    def test_fullscreen_panels_match_soccer_and_keep_stable_skeleton(self):
        a=app();a.matches=[match()];a._timer_running=False;a.camera_on=False
        a.page.width=1920;a._fs_skeleton=None
        for name in ("left","top","video","bottom","right"):
            setattr(a,"fs_"+name+"_slot",ft.Container())
        a._video_display_widget=lambda:ft.Text("Video")
        a._rotate_view_button=lambda:ft.Button("Rotate")
        a._mirror_view_button=lambda:ft.Button("Mirror")
        layout=a._build_fullscreen_logger(a.match)
        self.assertIs(layout,a._build_fullscreen_logger(a.match))
        self.assertEqual(a.fs_left_slot.content.width,170)
        self.assertEqual(a.fs_right_slot.content.width,230)
        values=[c.value for c in controls(layout) if isinstance(c,ft.Text)]
        self.assertTrue(all(label in values for label in ("INCOMPLETES","Attack","Defence","Cards")))
        self.assertFalse(any(label in values for label in ("Add player","Credit to","On-court lineup / substitutions")))

    def test_football_unchanged(self):
        m=match();m.sport="SOCCER";m.away_score=2
        m.events=[make_event(m,"home","GOAL","p","Goal")]
        recalculate_stats(m)
        self.assertEqual((m.home_score,m.away_score,m.stats.home_goals),(1,2,1))

if __name__=="__main__": unittest.main()
