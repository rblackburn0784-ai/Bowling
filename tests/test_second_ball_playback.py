"""Second-ball regression: animation must show travel and a progressive pin hit.

These tests use synthetic graphics so GitHub CI does not need private PNG assets.
The bowling engine's before/down/after lists are unchanged.
"""
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
import unittest

from PIL import Image,ImageChops
from services import scene_renderer as scene
from services.shot_animation import ANIMATION_SEQUENCE,DURATION_SECONDS,DISCORD_PLAYBACK_HEADROOM_SECONDS
from cogs import games

class SecondBallPlaybackTests(unittest.TestCase):
 def test_travel_and_impact_have_distinct_presentation_frames(self):
  stages=[stage for stage,_,_,_,_ in ANIMATION_SEQUENCE]
  self.assertEqual(stages[:5],['approach']*5)
  self.assertGreaterEqual(stages.count('path'),8)
  self.assertGreaterEqual(stages.count('breakpoint'),5)
  self.assertGreaterEqual(stages.count('impact'),5)
  impacts=[x for x in ANIMATION_SEQUENCE if x[0]=='impact']
  self.assertEqual([x[3] for x in impacts],list(range(1,6)))
  self.assertGreaterEqual(impacts[-1][-1],450)
  self.assertGreaterEqual(DISCORD_PLAYBACK_HEADROOM_SECONDS,1.0)
  self.assertLess(DURATION_SECONDS,3.5)

 def test_second_ball_single_pin_has_progressive_knockdown(self):
  upright=Image.new('RGBA',(40,70),(241,238,220,255))
  fallen=Image.new('RGBA',(70,40),(164,20,30,255))
  event={'before':[1,3,7],'down':[3],'after':[1,7]}
  def sprite(view,name):
   return fallen if name.startswith('fall_') else upright
  frames=[]
  with patch.object(scene,'_pin',side_effect=sprite):
   for frame_index in range(1,6):
    canvas=Image.new('RGBA',scene.SIZE,(20,25,30,255))
    scene.pin_layers(canvas,event,'impact',frame_index)
    frames.append(canvas)
  def changed(a,b):
   return ImageChops.difference(a.convert('RGB'),b.convert('RGB')).getbbox() is not None
  self.assertTrue(changed(frames[0],frames[2]),'Mid-impact pin tilt was skipped')
  self.assertTrue(changed(frames[2],frames[4]),'Final fallen pin was not drawn')
  self.assertTrue(changed(frames[1],frames[3]),'Knockdown lacks intermediate motion')
  settled=Image.new('RGBA',scene.SIZE,(20,25,30,255))
  with patch.object(scene,'_pin',side_effect=sprite):
   scene.pin_layers(settled,event,'leave',5)
  self.assertTrue(changed(frames[-1],settled),'Fallen pin stays in final leave')
  self.assertEqual(event['before'],[1,3,7])
  self.assertEqual(event['down'],[3])
  self.assertEqual(event['after'],[1,7])

class SinglePlayDeliveryTests(unittest.IsolatedAsyncioTestCase):
 async def test_second_delivery_gets_new_gif_and_waits_for_playback(self):
  channel=SimpleNamespace(id=987)
  msg=SimpleNamespace(edit=AsyncMock())
  session=SimpleNamespace(seed=12345,ball_count=1)
  games.LANE_MESSAGES[channel.id]=msg
  try:
   with patch.object(games.asyncio,'to_thread',new_callable=AsyncMock) as thread, \
        patch.object(games.asyncio,'sleep',new_callable=AsyncMock) as sleep, \
        patch.object(games,'scoreboard_embed',return_value=None):
    thread.return_value=(BytesIO(b'GIF89a'),2.8)
    await games.animate_delivery(channel,session,{'ball_key':'hybrid'},[],{},1.0)
    first=msg.edit.await_args.kwargs['attachments'][0].filename
    self.assertIn('12345_1.gif',first)
    sleep.assert_awaited_with(2.8+DISCORD_PLAYBACK_HEADROOM_SECONDS)
    session.ball_count=2
    await games.animate_delivery(channel,session,{'ball_key':'plastic','ball':2},[],{},1.0)
    second=msg.edit.await_args.kwargs['attachments'][0].filename
    self.assertIn('12345_2.gif',second)
    self.assertNotEqual(first,second)
    self.assertEqual(msg.edit.await_count,2)
  finally:
   games.LANE_MESSAGES.pop(channel.id,None)

if __name__=='__main__':
 unittest.main()
