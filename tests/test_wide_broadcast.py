"""v2.8.5l wide multi-camera bowling presentation regressions."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image,ImageChops
from services import scene_renderer as scene
from services.broadcast_layout import BASE_SIZE,compose_broadcast
from services import shot_animation


class WideBroadcastTests(unittest.TestCase):
    def test_broadcast_is_wider_without_distorting_master_lane_source(self):
        self.assertEqual(scene.SIZE,(941,1672))
        self.assertEqual(BASE_SIZE,(900,800))
        self.assertEqual(scene.EXPORT_SIZE,BASE_SIZE)
        self.assertTrue(all(abs(w/h-1.125)<.005 for w,h in shot_animation.SIZES))
        source=Image.new('RGB',scene.SIZE,(90,80,70))
        out=compose_broadcast(source)
        self.assertEqual(out.size,BASE_SIZE)
        self.assertEqual(out.getpixel((100,500)),(90,80,70))

    def test_both_pin_views_show_actual_second_delivery_fall(self):
        bg=Image.new('RGBA',scene.SIZE,(30,35,44,255))
        upright=Image.new('RGBA',(40,70),(246,240,219,255))
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
        self.assertNotEqual(ImageChops.difference(before.crop((0,33,446,241)),
                                              after.crop((0,33,446,241))).getbbox(),None)
        self.assertNotEqual(ImageChops.difference(before.crop((454,33,900,241)),
                                              after.crop((454,33,900,241))).getbbox(),None)
        self.assertEqual(event['after'],[1,5])

    def test_plastic_spare_ball_visible_in_action_camera(self):
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
        x,y,radius=scene._projected_ball(ev,.30)
        self.assertGreaterEqual(radius,38)
        rx=round(x*900/941)
        ry=250+round((y-825)*550/(1672-825))
        self.assertTrue(250<=ry<800)
        self.assertNotEqual(travel.getpixel((rx,ry)),approach.getpixel((rx,ry)))
        self.assertGreater(travel.getpixel((rx,ry))[0],210)
        self.assertEqual(travel.size,(900,800))

if __name__=='__main__':
    unittest.main()
