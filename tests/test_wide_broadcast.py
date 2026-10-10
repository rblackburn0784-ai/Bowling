"""v2.8.5m hybrid layout and shot/pin visual regressions."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image, ImageChops
from services import scene_renderer as scene
from services.hybrid_broadcast import (
    BASE_SIZE,HERO_BOX,OVERHEAD_BOX,PIT_BOX,
    SOURCE_SIZE, fit_rectangle, compose_hybrid_broadcast
)
from services import shot_animation


def changed(a,b):
    return ImageChops.difference(a.convert('RGB'),b.convert('RGB')).getbbox() is not None


class HybridBroadcastTests(unittest.TestCase):
    def test_main_lane_fills_hero_panel_without_crop_or_gaps(self):
        self.assertEqual(SOURCE_SIZE,(941,1672))
        self.assertEqual(scene.SIZE,SOURCE_SIZE)
        self.assertEqual(scene.EXPORT_SIZE,(850,750))
        self.assertEqual(BASE_SIZE,(850,750))
        self.assertTrue(all(abs(w/h-17/15)<.005 for w,h in shot_animation.SIZES))
        left,top,right,bottom=HERO_BOX
        self.assertEqual((left,top,bottom),(0,0,750))
        self.assertLess(abs((right-left)/(bottom-top)-941/1672),.0005)
        art=Image.new('RGB',SOURCE_SIZE,(90,80,70))
        output=compose_hybrid_broadcast(art)
        self.assertEqual(output.size,BASE_SIZE)
        for pt in ((0,0),(right-1,0),(0,bottom-1),(right-1,bottom-1),(right//2,bottom//2)):
            self.assertEqual(output.getpixel(pt),(90,80,70),pt)

    def test_overhead_and_pit_panels_follow_same_spare_pinfall(self):
        bg=Image.new('RGBA',scene.SIZE,(30,35,44,255))
        upright=Image.new('RGBA',(40,70),(245,240,218,255))
        fallen=Image.new('RGBA',(70,40),(190,38,44,255))
        event={'before':[1,3,5],'down':[3],'after':[1,5],
               'bowler_id':1,'ball_key':'plastic','bowler':'Josh',
               'handedness':'R','physics':{'miss':0,'metrics':{'revs':190,'entry_angle':3}}}
        session=SimpleNamespace(players=[])
        def pin(view,name):
            return fallen if name.startswith('fall_') else upright
        with patch.object(scene,'_background',return_value=bg), \
             patch.object(scene,'_pin',side_effect=pin), \
             patch.object(scene,'_bowler',return_value=False), \
             patch.object(scene,'_ball'):
            before=scene.render_scene_image(session,event,'impact',ball_frame=1)
            after=scene.render_scene_image(session,event,'impact',ball_frame=5)
        self.assertEqual(before.size,BASE_SIZE)
        self.assertTrue(changed(before.crop(OVERHEAD_BOX),after.crop(OVERHEAD_BOX)),
                        'Overhead camera did not show pin 3 falling')
        self.assertTrue(changed(before.crop(PIT_BOX),after.crop(PIT_BOX)),
                        'Pit camera did not show pin 3 falling')
        self.assertEqual(event['after'],[1,5])

    def test_spare_ball_stays_visible_in_unstretched_hero_lane(self):
        bg=Image.new('RGBA',scene.SIZE,(130,100,65,255))
        cream=Image.new('RGBA',(90,90),(248,239,211,255))
        ev={'before':[1,3],'down':[3],'after':[1],
            'bowler_id':1,'bowler':'Josh','ball_key':'plastic',
            'handedness':'R','physics':{'miss':0,'metrics':{'revs':210,'entry_angle':3}}}
        session=SimpleNamespace(players=[])
        with patch.object(scene,'_background',return_value=bg), \
             patch.object(scene,'_pin',return_value=None), \
             patch.object(scene,'_bowler',return_value=False), \
             patch.object(scene.ball_sprites,'_load',return_value=cream):
            approach=scene.render_scene_image(session,ev,'approach')
            travel=scene.render_scene_image(session,ev,'path',ball_progress=.30)
        px,py,size=scene._projected_ball(ev,.30)
        x=round(HERO_BOX[0]+px*(HERO_BOX[2]-HERO_BOX[0])/SOURCE_SIZE[0])
        y=round(HERO_BOX[1]+py*(HERO_BOX[3]-HERO_BOX[1])/SOURCE_SIZE[1])
        self.assertGreaterEqual(size,38)
        self.assertTrue(HERO_BOX[0]<=x<HERO_BOX[2])
        self.assertTrue(HERO_BOX[1]<=y<HERO_BOX[3])
        self.assertNotEqual(approach.getpixel((x,y)),travel.getpixel((x,y)))
        self.assertGreater(travel.getpixel((x,y))[0],210)
        self.assertEqual(travel.size,BASE_SIZE)

    def test_camera_geometry_and_fallback_scale(self):
        art=Image.new('RGB',SOURCE_SIZE,(95,75,65))
        small=compose_hybrid_broadcast(art,(680,600))
        self.assertEqual(small.size,(680,600))
        self.assertLess(HERO_BOX[2],OVERHEAD_BOX[0])
        self.assertEqual(OVERHEAD_BOX[2],PIT_BOX[2])
        self.assertLess(OVERHEAD_BOX[3],PIT_BOX[1])
        with self.assertRaises(ValueError):
            fit_rectangle((0,0),HERO_BOX)
        with self.assertRaises(ValueError):
            compose_hybrid_broadcast(art,(0,0))


if __name__=='__main__':
    unittest.main()
