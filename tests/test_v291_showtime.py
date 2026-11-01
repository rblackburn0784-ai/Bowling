"""v2.9.1: non-spoiler presentation, deterministic extras, broadcast card QA."""
import io
import random
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
from models.bowler import Bowler
from services.game_engine import GameSession
from services.showtime import (stage_cue,result_cue,crowd_cue,celebration_worthy,
                               group_rosters,STAGE_LABELS)
from services.showtime_graphics import (intro_card,final_card,transition_ribbon,WIDTH,HEIGHT)
from services.dude_commentary import stage_line
from services import shot_animation


def session(layout='broadcast',seed=851):
    a=Bowler(1,'TheDude',10,'R',1,19,15,11,17,16,12)
    b=Bowler(2,'Jesus',11,'L',1,17,19,9,15,20,10)
    a.team_name='Saints';b.team_name='Sinners'
    s=GameSession([a,b],seed=seed,layout=layout)
    return s

class ShowtimeContentTests(unittest.TestCase):
    def test_before_reveal_never_uses_pinfall(self):
        s=session('finals')
        e={'bowler':'TheDude','bowler_id':1,'frame':10,'ball':2,
           'before':[7,10],'pins':10,'down':[7,10],'after':[],
           'split_conversion':True,'split_name':'7–10 Split','strike_streak':12}
        for stage in STAGE_LABELS:
            cue=stage_cue(s,stage,e)
            self.assertEqual(cue,stage_cue(s,stage,e))
            self.assertNotIn('7–10',cue)
            self.assertNotIn('300',cue)
            self.assertNotIn('STRIKE',cue.upper())
            self.assertNotIn('converted',cue.lower())
            shown=stage_line(s,stage,e)
            self.assertEqual(shown,stage_line(s,stage,e))
            self.assertNotIn('7–10',shown)
            self.assertNotIn('300',shown)

    def test_result_is_named_and_repeat_safe(self):
        s=session('finals')
        for label,key in [('7–10 Split','7–10'),('Big Four','Big Four'),
                          ('Greek Church','Greek Church')]:
            e={'bowler':'TheDude','bowler_id':1,'split_conversion':True,
               'split_name':label,'before':[7,10]}
            cue=result_cue(s,e)
            self.assertIn(key,cue)
            self.assertEqual(cue,result_cue(s,e))
        e={'bowler':'Jesus','bowler_id':2,'strike_streak':12}
        self.assertIn('300',result_cue(s,e))
        e={'bowler':'Jesus','bowler_id':2,'strike_streak':11}
        self.assertIn('ELEVEN',result_cue(s,e))
        e={'bowler':'Jesus','bowler_id':2,'frame':10,'spare':True}
        self.assertIn('tenth-frame',result_cue(s,e))

    def test_no_gameplay_rng_advance(self):
        s=session('finals')
        before=s.rng.getstate()
        e={'bowler':'Jesus','bowler_id':2,'frame':10,'ball':1,'pins':10,
           'strike_streak':3,'before':list(range(1,11))}
        for stage in STAGE_LABELS:
            stage_cue(s,stage,e);stage_line(s,stage,e)
        result_cue(s,e);crowd_cue(s,e)
        intro_card(s);final_card(s,'Saints')
        self.assertEqual(before,s.rng.getstate())

    def test_gutter_then_ten_is_spare_not_strike_commentary(self):
        from services.commentary import event_text
        s=session()
        event={'bowler':'TheDude','bowler_id':1,'pins':10,'spare':True,
               'frame':3,'ball':2}
        with patch('services.commentary.event_line',return_value='Spare called') as narrator:
            spoken=event_text(s,event)
        self.assertEqual(spoken,'Spare called')
        self.assertEqual(narrator.call_args.args[1],'spare')

    def test_final_detection_only_for_real_elimination_final(self):
        from services.showtime import is_elimination_final
        rows=[{'id':1,'stage_id':1,'bracket':'main','round_no':1},
              {'id':2,'stage_id':1,'bracket':'main','round_no':1},
              {'id':3,'stage_id':1,'bracket':'main','round_no':2}]
        self.assertTrue(is_elimination_final(rows[2],'single_elimination',rows))
        self.assertFalse(is_elimination_final(rows[0],'single_elimination',rows))
        self.assertFalse(is_elimination_final(rows[2],'round_robin',rows))
        self.assertTrue(is_elimination_final({'bracket':'grand_final'},'double_elimination',[]))

    def test_crowd_only_finals_and_not_each_ball(self):
        s=session('finals')
        e={'frame':10,'pins':10,'strike_streak':12}
        s.ball_count=3;self.assertIsNotNone(crowd_cue(s,e))
        s.ball_count=4;self.assertIsNone(crowd_cue(s,e))
        s.ball_count=7;self.assertIsNotNone(crowd_cue(s,e))
        s.layout='broadcast';s.ball_count=12;self.assertIsNone(crowd_cue(s,e))

    def test_celebration_only_result_and_special(self):
        self.assertTrue(celebration_worthy({'pins':10,'spare':False}))
        self.assertTrue(celebration_worthy({'split_conversion':True}))
        self.assertTrue(celebration_worthy({'strike_streak':3}))
        self.assertFalse(celebration_worthy({'pins':10,'spare':True}))
        self.assertFalse(celebration_worthy({'pins':5,'spare':False}))

    def test_groups_dont_reclassify_solo_bowlers(self):
        s=session();self.assertEqual(list(group_rosters(s)),['Saints','Sinners'])
        for p in s.players:p.bowler.team_name=None
        self.assertEqual(len(group_rosters(s)),1)

class ShowtimeVisualTests(unittest.TestCase):
    def test_introduction_and_final_are_valid_pngs(self):
        s=session('finals')
        for out in [intro_card(s),final_card(s,'Saints')]:
            self.assertIsInstance(out,io.BytesIO)
            image=Image.open(out);image.verify()
            out.seek(0)
            self.assertEqual(Image.open(out).size,(WIDTH,HEIGHT))
            # v2.9.6c uses detailed 1672×941 photographic neon scoreboards.
            # Keep the image below the typical 8 MB Discord upload threshold.
            self.assertLess(len(out.getvalue()),8_000_000)

    def test_long_names_and_12_bowlers_stay_in_frame(self):
        s=session()
        for p in s.players:p.bowler.name='ExtremelyLongBowlerNameWhichWillNotFitTheGivenCard'*3
        s.players *= 6
        with Image.open(intro_card(s)) as im:self.assertEqual(im.size,(WIDTH,HEIGHT))

    def test_transition_does_not_modify_original_or_geometry(self):
        src=Image.new('RGB',(850,750),(40,60,80))
        before=src.tobytes()
        marked=transition_ribbon(src,'impact',True)
        self.assertEqual(src.tobytes(),before)
        self.assertEqual(marked.size,src.size)
        self.assertNotEqual(marked.tobytes(),before)
        self.assertEqual(marked.getpixel((100,100)),src.getpixel((100,100)))
        # Tiny test renders retain their previous presentation unchanged.
        small=Image.new('RGB',(170,250),(2,3,4))
        self.assertIs(transition_ribbon(small,'impact'),small)

    def test_animation_timing_and_shared_renderer_remain_unchanged(self):
        self.assertAlmostEqual(shot_animation.DURATION_SECONDS,2.795,places=3)
        stage=[row[0] for row in shot_animation.ANIMATION_SEQUENCE]
        self.assertEqual(stage[:5],['approach']*5)
        self.assertEqual(stage[-1],'impact')
        self.assertEqual(len(stage),23)

if __name__=='__main__':unittest.main()
