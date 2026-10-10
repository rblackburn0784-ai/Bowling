"""v2.8.5c visual scale regression tests; no artwork files required."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
from services import scene_renderer as scene


class SceneScaleTests(unittest.TestCase):
    def test_bowler_approach_size_and_floor_anchor(self):
        session=SimpleNamespace(players=[SimpleNamespace(
            bowler=SimpleNamespace(id=42,name='TheDude',sprite_key='the_dude'))])
        event={'bowler_id':42}
        sample=Image.new('RGBA',(300,600),(255,255,255,255))
        recorded=[]

        with patch.object(scene.bowler_sprites,'sprite_key',return_value='the_dude'), \
             patch.object(scene.bowler_sprites,'has_sequence',return_value=True), \
             patch.object(scene.bowler_sprites,'_image',return_value=sample), \
             patch.object(scene,'_paste',side_effect=lambda base,img,x,y: recorded.append((img.size,x,y))):
            for frame,expected_height,expected_floor in [
                (1,851,1660),(2,851,1655),(3,851,1650),
                (4,851,1645),(5,851,1640)
            ]:
                self.assertTrue(scene._bowler(Image.new('RGBA',scene.SIZE),session,event,frame))
                size,x,y=recorded[-1]
                self.assertEqual(size[1],expected_height)
                self.assertEqual(round(y)+size[1],expected_floor)
                self.assertGreater(size[1],440)
                self.assertGreaterEqual(x,0)
                self.assertLessEqual(x+size[0],scene.SIZE[0])

    def test_jesus_second_pose_receives_visible_held_ball(self):
        bowler=SimpleNamespace(id=9,name='Jesus',sprite_key='jesus')
        session=SimpleNamespace(players=[SimpleNamespace(bowler=bowler)])
        source=Image.new('RGBA',(354,694),(0,0,0,0))
        ball=Image.new('RGBA',(90,90),(215,30,45,255))
        renders=[]
        with patch.object(scene.bowler_sprites,'sprite_key',return_value='jesus'), \
             patch.object(scene.bowler_sprites,'has_sequence',return_value=True), \
             patch.object(scene.bowler_sprites,'_image',return_value=source), \
             patch.object(scene.ball_sprites,'_load',return_value=ball) as loaded, \
             patch.object(scene,'_paste',side_effect=lambda base,img,x,y: renders.append(img.copy())):
            self.assertTrue(scene._bowler(Image.new('RGBA',scene.SIZE),session,{'bowler_id':9},2))
            loaded.assert_called_once_with('urethane_black.png')
            self.assertTrue(renders[-1].getbbox())
            self.assertTrue(scene._bowler(Image.new('RGBA',scene.SIZE),session,{'bowler_id':9},5))
            loaded.assert_called_once()

    def test_fallen_pin_scales_but_upright_is_unchanged(self):
        img=Image.new('RGBA',(60,30),(255,255,255,255))
        recorded=[]
        with patch.object(scene,'_pin',return_value=img), \
             patch.object(scene,'_paste',side_effect=lambda base,sprite,x,y: recorded.append(sprite.size)):
            for view,scale in [('vertical',1.12),('overhead',1.10)]:
                scene._fall(Image.new('RGBA',scene.SIZE),view,1,1.0)
                self.assertEqual(recorded[-1],(round(60*scale),round(30*scale)))
                scene._fall(Image.new('RGBA',scene.SIZE),view,1,0.0)
                if view=='overhead':
                    self.assertEqual(recorded[-1],(60,30))
                else:
                    # Upright vertical uses the existing per-pin perspective adjustment.
                    self.assertEqual(recorded[-1],(round(60*1.08),round(30*1.08)))

    def test_visual_changes_do_not_modify_pin_state(self):
        event={'before':[1,2,3,7,10],'down':[1,7],'after':[2,3,10]}
        before={key:list(value) for key,value in event.items()}
        with patch.object(scene,'_pin',return_value=None):
            scene.pin_layers(Image.new('RGBA',scene.SIZE),event,'impact',impact_frame=3)
        self.assertEqual(event,before)


if __name__=='__main__':
    unittest.main()
