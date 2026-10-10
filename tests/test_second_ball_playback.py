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

class EncodedSecondBallTests(unittest.TestCase):
 def test_spare_gif_encodes_visible_travel_and_falling_pin(self):
  from services import shot_animation
  bowler=SimpleNamespace(id=101,name='Test',sprite_key='jesus')
  session=SimpleNamespace(players=[SimpleNamespace(bowler=bowler)])
  event={'bowler_id':101,'bowler':'Test','ball_key':'plastic','ball':2,
         'before':[1,3,5],'down':[3],'after':[1,5],
         'handedness':'R','physics':{'miss':0,'metrics':{'revs':210,'entry_angle':3}}}
  bg=Image.new('RGBA',scene.SIZE,(112,86,66,255))
  pin_standing=Image.new('RGBA',(36,64),(246,243,228,255))
  pin_fallen=Image.new('RGBA',(70,38),(205,28,38,255))
  bowling_ball=Image.new('RGBA',(90,90),(245,235,200,255))
  dummy_person=Image.new('RGBA',(260,600),(70,35,127,255))
  def pin(view,name):
   return pin_fallen if name.startswith('fall_') else pin_standing
  with patch.object(scene,'_background',return_value=bg), \
       patch.object(scene,'_pin',side_effect=pin), \
       patch.object(scene.bowler_sprites,'sprite_key',return_value='jesus'), \
       patch.object(scene.bowler_sprites,'has_sequence',return_value=True), \
       patch.object(scene.bowler_sprites,'_image',return_value=dummy_person), \
       patch.object(scene.ball_sprites,'_load',return_value=bowling_ball):
   frames=shot_animation._frames(session,event,(840,630))
  self.assertEqual(len(frames),len(ANIMATION_SEQUENCE))
  diff=lambda a,b: ImageChops.difference(a,b).getbbox() is not None
  self.assertTrue(diff(frames[5],frames[12]),'GIF source lacks visible ball movement')
  self.assertTrue(diff(frames[-5],frames[-1]),'GIF source lacks visible pin fall')
  gif=shot_animation._encode(frames)
  from PIL import Image as PillowImage
  decoded=PillowImage.open(BytesIO(gif))
  self.assertGreaterEqual(decoded.n_frames,15)
  decoded.seek(0)
  first=decoded.convert('RGB')
  decoded.seek(decoded.n_frames-1)
  last=decoded.convert('RGB')
  # In v2.8.5o the top-down pin deck is an independent right-hand
  # camera, not drawn across the top of the LEFT lane. Compare its actual
  # encoded GIF pixels rather than looking at the obsolete left coordinate.
  from services.hybrid_broadcast import OVERHEAD_BOX
  sx=840/1000;sy=630/750
  box=tuple(round(value*(sx if i%2==0 else sy))
            for i,value in enumerate(OVERHEAD_BOX))
  a=first.crop(box);z=last.crop(box)
  self.assertIsNotNone(ImageChops.difference(a,z).getbbox(),
                       'Final GIF has no pin motion in overhead camera')
  self.assertEqual(first.size,(840,630))


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
