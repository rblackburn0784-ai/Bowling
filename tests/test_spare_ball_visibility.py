"""Visual regression: second delivery's plastic spare ball must stay in view."""
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from PIL import Image,ImageDraw
from services import scene_renderer as scene
from services import shot_animation

class SpareBallVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.bowler=SimpleNamespace(id=1,name='Test',sprite_key='jesus')
        self.session=SimpleNamespace(players=[SimpleNamespace(bowler=self.bowler)])
        self.spare={'bowler_id':1,'bowler':'Test','ball_key':'plastic',
                    'frame':1,'ball':2,'before':[1,3,5],'down':[3],
                    'after':[1,5],'physics':{'miss':0,'metrics':{'revs':210,'entry_angle':3}},
                    'handedness':'R'}

    def test_spare_ball_is_on_top_of_large_bowler_during_early_travel(self):
        # A near-camera 760px bowler used to be composited LAST, hiding the
        # moving ball for almost all path frames. Marker covers ball's path.
        background=Image.new('RGBA',scene.SIZE,(165,118,79,255))
        source=Image.new('RGBA',(80,80),(249,237,212,255))
        def giant_bowler(canvas,*unused):
            ImageDraw.Draw(canvas).rectangle((300,900,640,1670),
                                             fill=(55,11,13,255))
            return True
        with patch.object(scene,'_background',return_value=background), \
             patch.object(scene,'pin_layers'), \
             patch.object(scene,'_bowler',side_effect=giant_bowler), \
             patch.object(scene.ball_sprites,'resolve_ball_variant',return_value='plastic_cream_black.png'), \
             patch.object(scene.ball_sprites,'_load',return_value=source):
            approach=scene.render_scene_image(self.session,self.spare,'approach',
                                               sprite_frame=5,output_size=scene.SIZE)
            travel=scene.render_scene_image(self.session,self.spare,'path',
                                             ball_progress=.12,output_size=scene.SIZE)
        # At this progress the bowling ball is near the feet, precisely where
        # the old character-first/ball-first z-order made a difference.
        self.assertEqual(approach.getpixel((470,1470)),(55,11,13))
        # Ball is light cream; test a representative centre pixel based on
        # actual existing path mapping without hardcoding its y-coordinate.
        _,path_y=scene.ball_sprites.point_on_path(
             scene.ball_sprites.path_points(self.spare),.12)
        amount=max(0.,min(1.,(640-path_y)/295))
        projected_y=round(1535-795*amount)
        self.assertEqual(travel.getpixel((470,projected_y)),(249,237,212))

    def test_second_delivery_gif_preserves_spare_ball_frames(self):
        # Test the encoder independently of artwork on GitHub: an approaching
        # player doesn't carry a plastic spare ball in the first frame.
        frames=[]
        for stage,pose,progress,impact,ms in shot_animation.ANIMATION_SEQUENCE:
            frame=Image.new('RGB',(180,240),(180,127,89))
            ImageDraw.Draw(frame).rectangle((40,180,140,239),fill=(45,35,35))
            if stage!='approach':
                ImageDraw.Draw(frame).ellipse((80,170,101,191),
                                              fill=(247,239,215),outline=(3,3,3),width=3)
            frames.append(frame)
        gif=shot_animation._encode(frames)
        from io import BytesIO
        output=Image.open(BytesIO(gif))
        # GIF colours vary slightly because of quantisation but the spare
        # ball's black outline and cream interior must remain visually distinct.
        output.seek(7)
        rendered=output.convert('RGB')
        r,g,b=rendered.getpixel((90,179))
        self.assertGreater(r,210)
        self.assertGreater(g,200)
        self.assertGreater(b,170)
        self.assertGreaterEqual(output.n_frames,15)

if __name__=='__main__':
    unittest.main()
