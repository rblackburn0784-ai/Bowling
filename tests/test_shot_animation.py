"""Regression tests for v2.8.5f single-upload, non-spoiler GIFs."""
from io import BytesIO
import unittest
from unittest.mock import patch
from PIL import Image,ImageDraw
from services import shot_animation

class ShotAnimationTests(unittest.TestCase):
 def test_timeline_contains_full_approach_and_travel(self):
  steps=shot_animation.ANIMATION_SEQUENCE
  self.assertEqual([s[1] for s in steps[:5]],[1,2,3,4,5])
  self.assertEqual([s[0] for s in steps[:5]],['approach']*5)
  self.assertEqual(steps[-1][0],'impact')
  self.assertGreaterEqual(len(steps),20)
  self.assertTrue(2.0 <= shot_animation.DURATION_SECONDS <= 3.5)
  progress=[s[2] for s in steps if s[2] is not None]
  self.assertEqual(progress,sorted(progress))
  self.assertAlmostEqual(progress[-1],1.0)

 def test_gif_is_short_compact_and_nonlooping(self):
  count=[0]
  def fake_render(*args,**kwargs):
   size=kwargs['output_size']
   im=Image.new('RGB',size,(25,28,35))
   draw=ImageDraw.Draw(im)
   x=5+count[0]*3
   draw.ellipse((x,10,x+16,26),fill=(198,45,45))
   count[0]+=1
   return im
  with patch.object(shot_animation.scene_renderer,'available',return_value=True), \
       patch.object(shot_animation.scene_renderer,'render_scene_image',side_effect=fake_render), \
       patch.object(shot_animation,'SIZES',((170,250),)):
   gif,seconds=shot_animation.animated_shot(object(),{'bowler':'Test'})
  self.assertIsInstance(gif,BytesIO)
  self.assertLess(len(gif.getvalue()),1000000)
  im=Image.open(gif)
  self.assertGreaterEqual(im.n_frames,15)
  self.assertEqual(im.info.get('loop'),None)  # play once, then leave result image
  self.assertAlmostEqual(seconds,shot_animation.DURATION_SECONDS)

 def test_missing_background_returns_fallback(self):
  with patch.object(shot_animation.scene_renderer,'available',return_value=False):
   gif,duration=shot_animation.animated_shot(object(),{})
  self.assertIsNone(gif)
  self.assertEqual(duration,0)

if __name__=='__main__':
 unittest.main()
