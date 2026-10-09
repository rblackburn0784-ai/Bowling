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

    def test_strike_and_spare_ball_emerge_beside_bowler_not_over_torso(self):
        # Recreate both characters at cinematic size. The torso occupies
        # x=300..640, y=950..1670 and must remain in front of the ball.
        # Early released balls must still be visible OUTSIDE that region.
        background=Image.new('RGBA',scene.SIZE,(165,118,79,255))
        balls={
            'plastic_cream_black.png':Image.new('RGBA',(80,80),(249,237,212,255)),
            'hybrid_pink_black.png':Image.new('RGBA',(80,80),(225,45,120,255)),
        }
        def giant_bowler(canvas,*unused):
            ImageDraw.Draw(canvas).rectangle((300,950,640,1670),
                                             fill=(55,11,13,255))
            return True
        for ball_key,filename,expected in (
            ('plastic','plastic_cream_black.png',(249,237,212)),
            ('hybrid','hybrid_pink_black.png',(225,45,120)),
        ):
            with self.subTest(ball=ball_key), \\
                 patch.object(scene,'_background',return_value=background), \\
                 patch.object(scene,'pin_layers'), \\
                 patch.object(scene,'_bowler',side_effect=giant_bowler), \\
                 patch.object(scene.ball_sprites,'resolve_ball_variant',return_value=filename), \\
                 patch.object(scene.ball_sprites,'_load',return_value=balls[filename]):
                event=dict(self.spare,ball_key=ball_key,ball=2 if ball_key=='plastic' else 1)
                approach=scene.render_scene_image(self.session,event,'approach',
                                                  sprite_frame=5,output_size=scene.SIZE)
                travel=scene.render_scene_image(self.session,event,'path',
                                                ball_progress=.12,output_size=scene.SIZE)
                x,y,size=scene._projected_ball(event,.12)
                self.assertGreater(x,640+size/2)
                self.assertEqual(approach.getpixel((470,1434)),(55,11,13))
                # No floating ball painted on the bowler's clothes.
                self.assertEqual(travel.getpixel((470,1434)),(55,11,13))
                self.assertEqual(travel.getpixel((round(x),round(y))),expected)

    def test_release_offset_is_smooth_and_ends_at_real_physics_line(self):
        event=dict(self.spare)
        projected=[scene._projected_ball(event,p) for p in (.05,.12,.35,.53,.61,.67,.73,.79,.84,1.)]
        self.assertTrue(all(a[1]>b[1] for a,b in zip(projected,projected[1:])))
        points=scene.ball_sprites.path_points(event)
        for p in (.82,.93,1.):
            x,y=scene.ball_sprites.point_on_path(points,p)
            fraction=max(0.,min(1.,(640-y)/295))
            expected=470+(x-340)*(1.3-.55*fraction)
            actual,_,_=scene._projected_ball(event,p)
            self.assertAlmostEqual(expected,actual,places=5)
        x_before,_,_=scene._projected_ball(event,.62)
        x_after,_,_=scene._projected_ball(event,.621)
        self.assertLess(abs(x_after-x_before),3.)

    def test_real_plastic_art_can_be_loaded_from_expected_asset_path(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            filename='plastic_cream_black.png'
            Image.new('RGBA',(356,356),(240,223,198,255)).save(
                Path(directory)/filename)
            with patch.object(scene.ball_sprites,'BALL_DIR',Path(directory)):
                scene.ball_sprites._load.cache_clear()
                self.assertIsNotNone(scene.ball_sprites._load(filename))
                self.assertTrue(scene.ball_sprites.has_ball_sprite('plastic','Test'))
                scene.ball_sprites._load.cache_clear()

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
        # Identical synthetic poses are legitimately coalesced by GIF
        # optimisation; the final decoded frame still shows the spare ball.
        self.assertGreaterEqual(output.n_frames,2)
        output.seek(output.n_frames-1)
        rendered=output.convert('RGB')
        r,g,b=rendered.getpixel((90,179))
        self.assertGreater(r,210)
        self.assertGreater(g,200)
        self.assertGreater(b,170)

if __name__=='__main__':
    unittest.main()
