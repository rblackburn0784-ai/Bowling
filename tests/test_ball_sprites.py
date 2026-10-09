"""Regression tests: all ten ball variants, spinning path and zero RNG side effects."""
import random
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image

from services import ball_sprites
from services.dude_commentary import stage_line

class BallSpriteTests(unittest.TestCase):
    def test_mapping_all_ten_artworks(self):
        found={filename for names in ball_sprites.BALL_VARIANTS.values() for filename in names}
        self.assertEqual(len(found),10)
        self.assertEqual(set(ball_sprites.BALL_VARIANTS),{'solid','pearl','hybrid','urethane','plastic'})
        self.assertIsNone(ball_sprites.resolve_ball_variant('unknown','Bowler'))

    def test_stable_variants_and_path(self):
        a=ball_sprites.resolve_ball_variant('hybrid','TheDude')
        self.assertEqual(a,ball_sprites.resolve_ball_variant('hybrid','TheDude'))
        self.assertIn(a,ball_sprites.BALL_VARIANTS['hybrid'])
        event={'ball_key':'hybrid','bowler':'TheDude','handedness':'R','physics':{'miss':0,'metrics':{'entry_angle':4,'revs':285}}}
        points=ball_sprites.path_points(event)
        self.assertEqual(points[0],(340,640))
        self.assertEqual(points[-1][1],345)
        positions=[ball_sprites.point_on_path(points,t) for t in (0,.12,.32,.5,.7,.85,1)]
        self.assertTrue(all(a[1]>=b[1] for a,b in zip(positions,positions[1:])))
        self.assertGreater(ball_sprites._ball_size(640),ball_sprites._ball_size(345))
        self.assertNotEqual(ball_sprites._spin_angle(event,.12),ball_sprites._spin_angle(event,.32))

    def test_composite_and_missing_asset_fallback(self):
        event={'ball_key':'hybrid','bowler':'TheDude','handedness':'R','physics':{'miss':0,'metrics':{'entry_angle':4,'revs':285}}}
        with tempfile.TemporaryDirectory() as folder,patch.object(ball_sprites,'BALL_DIR',Path(folder)):
            ball_sprites._load.cache_clear()
            blank=Image.new('RGB',(680,760),(12,14,24))
            self.assertFalse(ball_sprites.draw_ball_sprite(blank,event,(340,560),.3))
            Image.new('RGBA',(80,80),(250,20,100,255)).save(Path(folder)/ball_sprites.resolve_ball_variant('hybrid','TheDude'))
            ball_sprites._load.cache_clear()
            self.assertTrue(ball_sprites.draw_ball_sprite(blank,event,(340,560),.3))
            self.assertNotEqual(blank.getpixel((340,560)),(12,14,24))
            fallback=Image.new('RGB',(680,760),(12,14,24))
            event['ball_key']='plastic'
            ball_sprites.draw_lane_ball(fallback,event,.4)
            self.assertNotEqual(fallback.getpixel((340,640)),(12,14,24))
            ball_sprites._load.cache_clear()

    def test_stage_comments_do_not_mutate_game_rng(self):
        session=SimpleNamespace(seed=1742,rng=random.Random(1742))
        before=session.rng.getstate()
        event={'bowler':'TheDude'}
        for stage in ('approach','path','breakpoint','impact'):
            first=stage_line(session,stage,event)
            self.assertEqual(stage_line(session,stage,event),first)
        self.assertEqual(before,session.rng.getstate())

if __name__=='__main__':
    unittest.main()
