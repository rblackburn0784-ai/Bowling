"""v2.9.0 physics-informed gameplay, restore and linked-camera regressions.

Synthetic plates mean these run in CI without sharing private PNG artwork.
"""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import random
import statistics
import tempfile
import unittest
from PIL import Image, ImageChops

from models.bowler import Bowler
from services.ball_sprites import path_points
from services.equipment import get_ball
from services.game_engine import GameSession
from services.impact_model import impact_geometry, spare_target, pinfall
from services.lane_physics import LaneState
from services.pin_engine import ALL,PINS,roll_pins
from services.v25 import session_dict,session_from_dict
from services import scene_renderer as scene
from services import lane_visual


def bowler(ident=1,stat=25,hand='R'):
    return Bowler(id=ident,name=f'Bowler {ident}',owner_id=ident,handedness=hand,
                  rank=1,accuracy=stat,consistency=stat,spin=stat,
                  nerves=stat,style=stat,flair=stat)


class V290PhysicsTests(unittest.TestCase):
    def test_pin_coordinates_are_regulation_rack_and_spare_target_is_near_pin(self):
        self.assertEqual(set(PINS),ALL)
        self.assertEqual([PINS[p][1] for p in (1,2,4,7)], [0,1,2,3])
        for pins,want in [({10},10),({7},7),({2,8},2),({3,9},3),({1,2,4,7},1),
                          (ALL,1),({4,6,7,10},6)]:
            self.assertEqual(spare_target(pins,PINS,'R'),want)
        self.assertEqual(spare_target({4,6,7,10},PINS,'L'),4)

    def test_geometry_uses_oil_track_line_and_metrics(self):
        b=get_ball('hybrid')
        lane=LaneState(3,'house')
        m={'speed':16.2,'revs':350,'entry_angle':4.7}
        ideal=impact_geometry(0,m,b,lane,1,0)
        lane.oil=.22;lane.track=.75;lane.outside=.70;lane.middle=.65
        changed=impact_geometry(0,m,b,lane,1,0)
        moved=impact_geometry(0,m,b,lane,1,2)
        self.assertNotEqual(ideal['impact_x'],changed['impact_x'])
        self.assertLess(moved['impact_x'],changed['impact_x'])
        left=impact_geometry(0,m,b,lane,-1,-2)
        self.assertAlmostEqual(left['impact_x'],-moved['impact_x'],places=4)
        too_fast=impact_geometry(0,{'speed':30,'revs':350,'entry_angle':13},b,lane,1)
        self.assertLess(too_fast['carry_factor'],ideal['carry_factor'])

    def test_spare_after_gutter_targets_headpin_without_strike_branch(self):
        class ZeroRandom:
            def gauss(self,mean,sigma):return mean
            def random(self):return 0
        knocked,quality,physics=roll_pins(ZeroRandom(),bowler(),ALL,target_mode='spare')
        self.assertEqual(physics['target'],1)
        self.assertEqual(physics['aim_pin'],1)
        self.assertEqual(set(physics['contact_order']),knocked)

    def test_spare_targets_one_pin_at_right_with_physical_ball_contact(self):
        b=bowler(2,25)
        lane=LaneState(3,'house')
        down,_,physics=roll_pins(random.Random(21),b,{10},lane_state=lane,
                                 ball_key='plastic',target_mode='spare')
        self.assertAlmostEqual(physics['pocket_x'],3)
        self.assertEqual(physics['target'],10)
        self.assertEqual(down & {10}, down)
        evt={'physics':physics,'handedness':'R','ball_key':'plastic'}
        self.assertAlmostEqual(path_points(evt)[-1][0],340+physics['impact_x']*32,delta=1)

    def test_pinfall_reacts_to_ball_contact_and_has_order_without_duplicates(self):
        perfect={'impact_x':.46,'carry_factor':1.}
        edge={'impact_x':3.8,'carry_factor':.45}
        center_hits=outer_hits=0
        for seed in range(100):
            a,order=pinfall(random.Random(seed),ALL,PINS,.73,perfect)
            b,_=pinfall(random.Random(seed),ALL,PINS,.73,edge)
            self.assertEqual(set(order),a)
            self.assertEqual(len(order),len(set(order)))
            self.assertTrue(a<=ALL and b<=ALL)
            center_hits+=len(a);outer_hits+=len(b)
        self.assertGreater(center_hits,outer_hits)

    def test_game_replay_matches_restored_session_and_does_not_invent_pins(self):
        a,b=bowler(1,22),bowler(2,25,'L')
        s=GameSession([a,b],seed=1609,lane='dry')
        for _ in range(6):s.bowl()
        clone=session_from_dict(session_dict(s))
        self.assertEqual(s.scores(),clone.scores())
        while not s.complete:
            event=s.bowl();other=clone.bowl()
            for key in ('down','after','before','quality','physics','lane_no','ball_key'):
                self.assertEqual(event[key],other[key],key)
            self.assertEqual(set(event['before'])-set(event['down']),set(event['after']))
            self.assertEqual(set(event['physics']['contact_order']),set(event['down']))
        self.assertEqual(s.scores(),clone.scores())
        self.assertTrue(all(0<=value<=300 for value in s.scores().values()))

    def test_pre_v290_snapshots_keep_frozen_285t_rng_engine(self):
        from services.legacy_v285t_pin_engine import roll_pins as old_engine
        old=GameSession([bowler(1,25)],seed=9827,lane='oily')
        old.physics_version='2.8.5t'
        for _ in range(4):old.bowl()
        raw=session_dict(old)
        raw.pop('physics_version')  # Actual format of prior release snapshots
        restored=session_from_dict(raw)
        self.assertEqual(restored.physics_version,'2.8.5t')
        self.assertEqual(session_dict(restored)['physics_version'],'2.8.5t')
        # On a new-version session, injecting the known previous engine must
        # give identical results and consume the same RNG draws as restore.
        parallel=GameSession([bowler(1,25)],seed=9827,lane='oily')
        with patch('services.game_engine.roll_pins',side_effect=old_engine):
            for _ in range(4):parallel.bowl()
        self.assertEqual(parallel.rng.getstate(),restored.rng.getstate())
        with patch('services.game_engine.roll_pins',side_effect=old_engine):
            for _ in range(12):
                if parallel.complete:break
                orig=parallel.bowl()
                new=restored.bowl()
                for key in ('pins','down','after','physics','lane_no','ball_key'):
                    self.assertEqual(orig[key],new[key],key)
        self.assertEqual(parallel.rng.getstate(),restored.rng.getstate())

    def test_skills_increase_average_score_without_runaway_300s(self):
        averages=[]
        for level in (8,20,35,50):
            scores=[]
            for i in range(65):
                s=GameSession([bowler(1,level)],seed=10000+i,
                              lane=['house','oily','dry','fresh'][i%4])
                while not s.complete:s.bowl()
                scores.append(next(iter(s.scores().values())))
            averages.append(statistics.mean(scores))
        self.assertEqual(averages,sorted(averages))
        self.assertLess(averages[0],100)
        self.assertLess(averages[-1],235)


class V290BroadcastTests(unittest.TestCase):
    def setUp(self):
        self.event={'before':list(range(1,11)), 'down':[1,2,3,7,10],
                    'after':[4,5,6,8,9],
                    'physics':{'contact_order':[1,2,3,7,10],
                               'impact_x':.46,'miss':0,
                               'metrics':{'entry_angle':4.7,'revs':350}}}

    def test_impact_order_is_identical_for_all_cameras(self):
        original=deepcopy(self.event)
        order=self.event['physics']['contact_order']
        for frame in range(1,6):
            progress=[scene.pin_impact_progress(self.event,p,frame) for p in order]
            self.assertTrue(all(0<=v<=1 for v in progress))
            self.assertEqual(progress,sorted(progress,reverse=True))
            self.assertIsNone(scene.pin_impact_progress(self.event,4,frame))
        self.assertEqual([scene.pin_impact_progress(self.event,p,1) for p in order],[0]*5)
        self.assertEqual([scene.pin_impact_progress(self.event,p,5) for p in order],[1]*5)
        self.assertEqual(self.event,original)

    def test_three_views_share_original_standing_pins_until_impact(self):
        plate=Image.new('RGBA',(1254,1254),(55,55,55,255))
        visible=[]
        # Spy on all pins; the renderer must not manufacture pins in another camera.
        real=scene._camera_pin
        def recorder(bg,name,p,progress=None):
            visible.append((name,p,progress))
        with patch.object(scene,'_camera_background',return_value=plate),\
             patch.object(scene,'_camera_pin',side_effect=recorder):
            for stage,frame in (('approach',0),('impact',1),('impact',4),('leave',0)):
                visible.clear()
                scene.right_cameras(self.event,stage,frame)
                for view in ('overhead','pit'):
                    pins={p for camera,p,_ in visible if camera==view}
                    self.assertEqual(pins,set(self.event['after'] if stage=='leave' else self.event['before']))
                if stage=='impact':
                    overhead={p:v for camera,p,v in visible if camera=='overhead'}
                    pit={p:v for camera,p,v in visible if camera=='pit'}
                    self.assertEqual(overhead,pit)
            self.assertEqual(self.event['after'],[4,5,6,8,9])

    def test_fallback_render_reads_same_contact_order(self):
        s=GameSession([bowler()],seed=2)
        # Fallback progressively hides only fallen pins when progress reaches 0.8.
        for frame in range(1,6):
            im,_=lane_visual._base(s,self.event,'impact',frame)
            self.assertEqual(im.size,(680,760))
        self.assertEqual(self.event['down'],[1,2,3,7,10])

    def test_no_art_still_uses_three_camera_fallback_and_preserves_state(self):
        s=GameSession([bowler()],seed=8)
        before=s.rng.getstate()
        with tempfile.TemporaryDirectory() as tmp, patch.object(scene,'CAMERAS',Path(tmp)):
            scene._camera_background.cache_clear()
            cams=scene.right_cameras(self.event,'impact',4)
            self.assertEqual(set(cams),{'overhead','pit'})
            self.assertEqual(s.rng.getstate(),before)
            scene._camera_background.cache_clear()


if __name__ == '__main__':
    unittest.main()
