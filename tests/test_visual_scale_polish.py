"""v2.8.5q sprite scaling and photographic marker alignment tests.

All checks are visual-only: shot stages, game-engine events and pin truth
continue to work exactly as before.
"""
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image

from services import scene_renderer as scene
from services import shot_animation
from services import hybrid_broadcast


class VisualPolishTests(unittest.TestCase):
    def setUp(self):
        self.plate=Image.new('RGBA',(1254,1254),(40,30,24,255))
        self.pin_over=Image.new('RGBA',(44,68),(240,210,190,255))
        self.pin_front=Image.new('RGBA',(26,68),(240,240,220,255))
        self.pin_fallen=Image.new('RGBA',(62,26),(230,40,40,255))

    def test_hero_sprite_is_twelve_percent_larger_and_keeps_floor_anchor(self):
        bowler=SimpleNamespace(id=8,name='Jesus',sprite_key='jesus')
        session=SimpleNamespace(players=[SimpleNamespace(bowler=bowler)])
        samples=[]
        with patch.object(scene.bowler_sprites,'sprite_key',return_value='jesus'), \
             patch.object(scene.bowler_sprites,'has_sequence',return_value=True), \
             patch.object(scene.bowler_sprites,'_image',
                          return_value=Image.new('RGBA',(300,600),(220,220,220,255))), \
             patch.object(scene,'_paste',side_effect=lambda bg,img,x,y:
                          samples.append((img.size,x,y))):
            for frame in (1,2,3,4,5):
                self.assertTrue(scene._bowler(Image.new('RGBA',scene.SIZE),
                                              session,{'bowler_id':8},frame))
        self.assertEqual([height for (width,height),x,y in samples],[851]*5)
        self.assertTrue(all(728>=size[0] for size,x,y in samples))
        self.assertEqual([round(y)+size[1] for size,x,y in samples],
                         [1660,1655,1650,1645,1640])
        self.assertAlmostEqual(scene.HERO_BOWLER_SCALE,1.12)

    def test_left_pins_rest_on_lower_deck_and_ball_reaches_them(self):
        self.assertEqual(scene.HERO_FRONT[7][1],484)
        self.assertEqual(scene.HERO_FRONT[1][1],526)
        self.assertEqual(scene._projected_ball({'physics':{'miss':0},
                           'handedness':'R'},1)[1],521)
        # The old rack ended at 500; this moves the WHOLE rack down 26px.
        for p in range(1,11):
            self.assertGreater(scene.HERO_FRONT[p][1],
                               scene.FRONT[p][1]-250)

    def test_left_upright_and_tip_are_enlarged_consistently(self):
        records=[]
        def pin(view,name):
            return self.pin_fallen if name.startswith('fall_') else self.pin_front
        with patch.object(scene,'_pin',side_effect=pin), \
             patch.object(scene,'_paste',side_effect=lambda base,img,x,y:
                          records.append(img.size)):
            base=Image.new('RGBA',scene.SIZE)
            scene._upright(base,'vertical',1,scene.HERO_FRONT)
            upright=records[-1]
            scene._fall(base,'vertical',1,.5,scene.HERO_FRONT)
            tip=records[-1]
            scene._fall(base,'vertical',1,1,scene.HERO_FRONT)
            fallen=records[-1]
        self.assertGreater(upright[1],round(self.pin_front.height*1.08))
        self.assertGreater(tip[1],self.pin_front.height)
        self.assertGreater(fallen[0],round(self.pin_fallen.width*1.12))

    def test_overhead_markers_match_exact_photo_circle_centres(self):
        # Measurements from the new 1254x1254 deck background. The photo's
        # ten circles are decorative (5-3-2) rather than regulation 4-3-2-1.
        circles={(281,386),(470,386),(628,386),(805,386),(974,386),
                 (418,602),(621,599),(837,601),(515,833),(735,833)}
        located={(round(x*1254),round(y*1254))
                 for x,y in scene.CAMERA_OVERHEAD.values()}
        self.assertEqual(located,circles)
        self.assertEqual(set(scene.CAMERA_OVERHEAD),set(range(1,11)))

    def test_camera_scales_with_proper_anchor_and_larger_fallen_pin(self):
        def fake_pin(view,name):
            if name.startswith('fall_'):
                return self.pin_fallen
            return self.pin_over if view=='overhead' else self.pin_front
        def position(name,p,progress=None):
            pasted=[]
            with patch.object(scene,'_pin',side_effect=fake_pin), \
                 patch.object(scene,'_paste',
                              side_effect=lambda canvas,img,x,y:
                              pasted.append((img.size,x,y))):
                scene._camera_pin(self.plate.copy(),name,p,progress)
            self.assertEqual(len(pasted),1)
            return pasted[0]
        (ow,oh),ox,oy=position('overhead',7)
        x,y=scene.CAMERA_OVERHEAD[7]
        self.assertAlmostEqual(ox+ow/2,x*1254,delta=1)
        self.assertAlmostEqual(oy+oh/2,y*1254,delta=1)
        self.assertGreater(oh,140)
        (pw,ph),px,py=position('pit',1)
        self.assertGreater(ph,210)
        (fw,fh),_,_=position('pit',1,1)
        self.assertGreater(fw,round(1254*.15))
        self.assertGreater(scene.PIT_FALLEN_SCALE,scene.PIT_PIN_SCALE)

    def test_gameplay_event_and_animation_sequence_not_modified(self):
        event={'before':[1,3,7],'down':[3],'after':[1,7]}
        initial=deepcopy(event)
        with patch.object(scene,'_camera_background',return_value=self.plate), \
             patch.object(scene,'_pin',return_value=self.pin_front):
            for stage,frame in (('approach',0),('impact',2),
                                ('impact',5),('leave',0)):
                cameras=scene.right_cameras(event,stage,frame)
                self.assertEqual(set(cameras),{'overhead','pit'})
        self.assertEqual(event,initial)
        self.assertEqual(len(shot_animation.ANIMATION_SEQUENCE),21)
        self.assertEqual(hybrid_broadcast.BASE_SIZE,(850,750))


if __name__=='__main__':
    unittest.main()
