"""Offline v2.8.5b scene regression checks (no shipped art required)."""
import random
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image

from services import scene_renderer as scene

class SceneTests(unittest.TestCase):
    def test_both_decks_contain_all_ten_real_pin_numbers(self):
        self.assertEqual(set(scene.OVERHEAD),set(range(1,11)))
        self.assertEqual(set(scene.FRONT),set(range(1,11)))
        self.assertEqual(scene.OVERHEAD[1][0],scene.OVERHEAD[5][0])
        self.assertEqual(scene.FRONT[1][0],scene.FRONT[5][0])

    def test_before_impact_and_leave_consistent(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(scene,'PINS',Path(temp)):
            scene._pin.cache_clear()
            ev={'before':[1,2,3,7],'down':[1,7],'after':[2,3]}
            before=Image.new('RGBA',scene.SIZE,(10,10,10,255))
            leave=before.copy()
            scene.pin_layers(before,ev,'approach')
            scene.pin_layers(leave,ev,'leave')
            for p in (1,7):
                x,y=scene.OVERHEAD[p]
                self.assertNotEqual(before.getpixel((x,y)),leave.getpixel((x,y)))
            for p in (2,3):
                x,y=scene.OVERHEAD[p]
                self.assertEqual(before.getpixel((x,y)),leave.getpixel((x,y)))
            self.assertEqual(set(ev['before'])-set(ev['down']),set(ev['after']))
            scene._pin.cache_clear()

    def test_missing_lane_returns_none_to_activate_legacy_fallback(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(scene,'BG',Path(temp)/'missing.png'):
            scene._background.cache_clear()
            self.assertFalse(scene.available())
            scene._background.cache_clear()

    def test_rendering_does_not_advance_bowling_rng(self):
        with tempfile.TemporaryDirectory() as temp:
            bg=Path(temp)/'background.png'
            Image.new('RGB',scene.SIZE,(33,44,55)).save(bg)
            with patch.object(scene,'BG',bg),patch.object(scene,'PINS',Path(temp)/'empty_pins'),patch.object(scene,'OUT',Path(temp)):
                scene._background.cache_clear();scene._pin.cache_clear()
                bowler=SimpleNamespace(id=1,name='Test Bowler',sprite_key='none')
                game=SimpleNamespace(bowler=bowler)
                session=SimpleNamespace(players=[game],rng=random.Random(111),seed=111)
                initial=session.rng.getstate()
                event={'bowler_id':1,'bowler':'Test Bowler','before':[1,2,3],
                       'down':[1],'after':[2,3],'ball_key':'hybrid',
                       'handedness':'R','physics':{'metrics':{'entry_angle':4,'revs':250},'miss':0}}
                for stage in ('approach','path','breakpoint','impact','leave'):
                    fn=scene.render_scene(session,event,stage,sprite_frame=1,ball_frame=3,ball_progress=.7)
                    with Image.open(fn) as im:
                        self.assertEqual(im.size,scene.EXPORT_SIZE)
                self.assertEqual(session.rng.getstate(),initial)
                scene._background.cache_clear();scene._pin.cache_clear()

if __name__=='__main__':unittest.main()
