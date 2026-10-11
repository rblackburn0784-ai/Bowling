"""Bridge test: actual second-ball engine event -> photographic motion GIF.

Unlike synthetic event-only tests, this forces a first delivery to leave
pins, bowls the spare attempt, and feeds that exact event into the renderer.
"""
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch
import unittest
from PIL import Image,ImageChops

from models.bowler import Bowler
from services.game_engine import GameSession
from services import scene_renderer,shot_animation


class EndToEndSpareGraphics(unittest.TestCase):
    def test_second_ball_shows_ball_travel_and_pinfall_in_all_three_cameras(self):
        b=Bowler(id=99,name='Jesus',owner_id=99,sprite_key='jesus')
        s=GameSession([b],seed=4567)
        rolled=[7,2]
        def engine_roll(rng,bowler,standing,*args,**kwargs):
            n=rolled.pop(0)
            down=set(sorted(standing)[:n])
            physics={'miss':0,'ball':kwargs.get('ball_key','plastic'),
                     'target':1,'metrics':{'revs':215,'entry_angle':3.6},'tags':[]}
            return down,.8,physics
        with patch('services.game_engine.roll_pins',side_effect=engine_roll):
            first=s.bowl()
            second=s.bowl()
        self.assertEqual((first['frame'],first['ball']),(1,1))
        self.assertEqual((second['frame'],second['ball']),(1,2))
        self.assertEqual(second['before'],first['after'])
        self.assertEqual(set(second['before']),set(second['down'])|set(second['after']))
        self.assertEqual(second['ball_key'],'plastic')
        self.assertEqual(second['lane_no'],first['lane_no'])

        canvas=Image.new('RGBA',scene_renderer.SIZE,(90,79,65,255))
        overhead=Image.new('RGBA',(310,310),(62,46,27,255))
        pit=Image.new('RGBA',(310,310),(32,27,27,255))
        standing=Image.new('RGBA',(22,55),(248,230,210,255))
        fallen=Image.new('RGBA',(40,21),(196,35,35,255))
        bowling_ball=Image.new('RGBA',(85,85),(235,195,30,255))
        def pin(view,name):
            return fallen if name.startswith('fall_') else standing
        def camera(kind):return overhead if kind=='overhead' else pit
        # All frames come from the actual *second* delivery.
        with patch.object(scene_renderer,'_background',return_value=canvas), \
             patch.object(scene_renderer,'_camera_background',side_effect=camera), \
             patch.object(scene_renderer,'_pin',side_effect=pin), \
             patch.object(scene_renderer,'_bowler',return_value=False), \
             patch.object(scene_renderer.ball_sprites,'_load',return_value=bowling_ball):
            frames=shot_animation._frames(s,second,(340,300))
        self.assertEqual(len(frames),len(shot_animation.ANIMATION_SEQUENCE))
        different=lambda i,j: ImageChops.difference(frames[i],frames[j]).getbbox() is not None
        self.assertTrue(different(5,12),'Second-ball flight GIF froze')
        self.assertTrue(different(12,16),'Second-ball breakpoint GIF froze')
        self.assertTrue(different(18,22),'Knocked-over pins never moved')
        with patch.object(scene_renderer,'_background',return_value=canvas), \
             patch.object(scene_renderer,'_camera_background',side_effect=camera), \
             patch.object(scene_renderer,'_pin',side_effect=pin), \
             patch.object(scene_renderer,'_bowler',return_value=False), \
             patch.object(scene_renderer.ball_sprites,'_load',return_value=bowling_ball):
            leave=scene_renderer.render_scene_image(s,second,'leave',
                                                     output_size=(340,300))
        # Second-ball leave should only show remaining standing pins.
        self.assertNotEqual(frames[18].tobytes(),leave.tobytes())
        data=shot_animation._encode(frames)
        decoded=Image.open(BytesIO(data))
        self.assertGreaterEqual(decoded.n_frames,15)
        decoded.seek(decoded.n_frames-1)
        self.assertEqual(decoded.size,(340,300))


if __name__=='__main__':
    unittest.main()
