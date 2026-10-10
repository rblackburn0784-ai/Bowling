"""v2.8.5o left-hero reanchor and independent right-camera regressions."""
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from PIL import Image, ImageChops

from services import scene_renderer as scene
from services import hybrid_broadcast


def different(a,b):
    return ImageChops.difference(a.convert('RGB'),b.convert('RGB')).getbbox() is not None


class HeroReanchorTests(unittest.TestCase):
    def setUp(self):
        self.background=Image.new('RGBA',scene.SIZE,(110,82,56,255))
        self.event={'bowler_id':1,'bowler':'Tester','ball_key':'plastic',
                    'before':[1,2,3,7],'down':[1,7],'after':[2,3],
                    'handedness':'R',
                    'physics':{'miss':0,'metrics':{'revs':210,'entry_angle':3}}}
        self.session=SimpleNamespace(players=[])
        self.vert=Image.new('RGBA',(26,68),(242,235,205,255))
        self.over=Image.new('RGBA',(44,68),(240,218,180,255))

    def test_hero_contains_vertical_pins_but_no_embedded_overhead(self):
        with patch.object(scene,'_background',return_value=self.background), \
             patch.object(scene,'_pin',side_effect=lambda view,name:self.over if view=='overhead' else self.vert), \
             patch.object(scene,'_bowler',return_value=False):
            # Crop-independent raw left view (no GIF layout).
            result=scene.render_scene_image(self.session,self.event,'approach',
                                            output_size=scene.SIZE)
        x,y=scene.HERO_FRONT[1]
        self.assertNotEqual(result.getpixel((x,y-20)),(110,82,56))
        x,y=scene.OVERHEAD[7]
        self.assertEqual(result.getpixel((x,y)),(110,82,56))
        self.assertLessEqual(max(y for x,y in scene.HERO_FRONT.values()),500)
        self.assertTrue(all(y>=450 for x,y in scene.HERO_FRONT.values()))

    def test_ball_reaches_new_lane_pit_at_impact(self):
        # The shot's physics-derived x-path is unchanged; only its screen y
        # projection now reaches the new head-on pin deck.
        x0,y0,size0=scene._projected_ball(self.event,0)
        x1,y1,size1=scene._projected_ball(self.event,1)
        self.assertGreater(y0,1450)
        self.assertTrue(485<=y1<=505)
        self.assertGreater(y0-y1,900)
        self.assertGreater(size0,size1)
        self.assertLess(abs(x1-scene.HERO_FRONT[1][0]),150)

    def test_right_camera_positions_do_not_follow_hero_change(self):
        self.assertEqual(scene.FRONT[1],(465,735))
        self.assertEqual(scene.HERO_FRONT[1],(465,500))
        self.assertEqual(scene.OVERHEAD[1],(462,352))
        blank=Image.new('RGBA',scene.SIZE,(0,0,0,0))
        with patch.object(scene,'_pin',return_value=self.vert):
            scene.pin_layers(blank,self.event,stage='approach',
                             views=('vertical',),front_positions=scene.HERO_FRONT)
        self.assertIsNotNone(blank.getbbox())
        self.assertEqual(blank.getpixel((465,700))[3],0)

    def test_right_panels_identical_when_hero_lane_background_changes(self):
        old=Image.new('RGBA',scene.SIZE,(12,33,45,255))
        changed=Image.new('RGBA',scene.SIZE,(210,90,55,255))
        right_base=Image.new('RGBA',(430,372),(90,45,25,255))
        pit_base=Image.new('RGBA',(314,290),(25,25,30,255))
        def cameras(key):
            return right_base if key=='overhead' else pit_base
        with patch.object(scene,'_pin',side_effect=lambda view,name:self.over if view=='overhead' else self.vert), \
             patch.object(scene,'_camera_background',side_effect=cameras), \
             patch.object(scene,'_bowler',return_value=False):
            first=scene.right_cameras(self.event,'impact',impact_frame=5)
            second=scene.right_cameras(self.event,'impact',impact_frame=5)
        self.assertEqual(first['overhead'].tobytes(),second['overhead'].tobytes())
        self.assertEqual(first['pit'].tobytes(),second['pit'].tobytes())
        screen1=hybrid_broadcast.compose_hybrid_broadcast(old,cameras=first)
        screen2=hybrid_broadcast.compose_hybrid_broadcast(changed,cameras=second)
        for box in (hybrid_broadcast.OVERHEAD_BOX,hybrid_broadcast.PIT_BOX):
            self.assertFalse(different(screen1.crop(box),screen2.crop(box)),
                             'Right pin camera changed with left background')
        self.assertTrue(different(screen1.crop(hybrid_broadcast.HERO_BOX),
                                  screen2.crop(hybrid_broadcast.HERO_BOX)))


if __name__=='__main__':
    unittest.main()
