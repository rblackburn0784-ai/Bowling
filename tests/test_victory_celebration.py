"""Winner cheer.png integration and tie-safe presentation tests."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,AsyncMock

import discord
from PIL import Image
from models.bowler import Bowler
from services.game_engine import GameSession
from services import bowler_sprites
from services import scene_renderer as scene
from services.victory_presentation import winning_bowler
from cogs import games


def finished_player(bowler,score_first):
    game=SimpleNamespace(bowler=bowler,frames=[[score_first,0]]+[[0,0]]*9,
                         complete=True)
    return game


class CheerSelectionTests(unittest.TestCase):
    def test_unique_individual_wins(self):
        a=Bowler(id=1,name='Benny',owner_id=1,sprite_key='the_dude')
        b=Bowler(id=2,name='Josh',owner_id=2,sprite_key='jesus')
        session=SimpleNamespace(complete=True,players=[finished_player(a,9),finished_player(b,8)],
                                team_totals=lambda:{})
        self.assertEqual(winning_bowler(session).bowler.id,1)
        session.players[1].frames[0]=[9,0]
        self.assertIsNone(winning_bowler(session),'Tied solo result must not crown a random player')

    def test_team_winner_selects_winning_roster_mvp(self):
        a=Bowler(id=1,name='Benny',owner_id=1,team_name='The Saints')
        b=Bowler(id=2,name='Josh',owner_id=2,team_name='The Saints')
        c=Bowler(id=3,name='Other',owner_id=3,team_name='The Strikers')
        session=SimpleNamespace(complete=True,players=[
            finished_player(a,8),finished_player(b,9),finished_player(c,4)],
            team_totals=lambda:{'The Saints':17,'The Strikers':4})
        self.assertEqual(winning_bowler(session).bowler.id,2)

    def test_missing_or_invalid_cheer_is_safe(self):
        with tempfile.TemporaryDirectory() as d,patch.object(bowler_sprites,'SPRITE_DIR',Path(d)):
            bowler_sprites.celebration_image.cache_clear()
            self.assertIsNone(bowler_sprites.celebration_image('the_dude'))
            self.assertIsNone(bowler_sprites.celebration_image('invalid'))
            bowler_sprites.celebration_image.cache_clear()

    def test_custom_cheer_png_loads_both_characters(self):
        with tempfile.TemporaryDirectory() as d,patch.object(bowler_sprites,'SPRITE_DIR',Path(d)):
            for key in ('the_dude','jesus'):
                folder=Path(d)/key
                folder.mkdir()
                Image.new('RGBA',(440,700),(201,90,110,255)).save(folder/'cheer.png')
            bowler_sprites.celebration_image.cache_clear()
            for key in ('the_dude','jesus'):
                self.assertEqual(bowler_sprites.celebration_image(key).size,(440,700))
            bowler_sprites.celebration_image.cache_clear()

    def test_victory_stage_uses_cheer_pose_and_winner_identity(self):
        a=Bowler(id=1,name='Benny',owner_id=1,sprite_key='the_dude')
        b=Bowler(id=2,name='Josh',owner_id=2,sprite_key='jesus')
        session=SimpleNamespace(players=[
            SimpleNamespace(bowler=a),SimpleNamespace(bowler=b)])
        left=Image.new('RGBA',scene.SIZE,(50,60,70,255))
        cheer=Image.new('RGBA',(290,680),(230,45,40,255))
        drawn=[]
        def sprite_key(bowler): return bowler.sprite_key
        with patch.object(scene,'_background',return_value=left), \
             patch.object(scene,'pin_layers'), \
             patch.object(scene.bowler_sprites,'sprite_key',side_effect=sprite_key), \
             patch.object(scene.bowler_sprites,'has_sequence',return_value=True), \
             patch.object(scene.bowler_sprites,'celebration_image',return_value=cheer) as loaded, \
             patch.object(scene,'_paste',side_effect=lambda image,sprite,x,y:drawn.append((sprite.size,x,y))):
            frame=scene.render_scene_image(session,{'bowler_id':2},'victory',
                                          victor_id=1,output_size=scene.SIZE)
        self.assertEqual(frame.size,scene.SIZE)
        loaded.assert_called_once_with('the_dude')
        self.assertTrue(drawn)
        self.assertEqual(drawn[-1][0][1],851)


class VictoryPublishingTests(unittest.IsolatedAsyncioTestCase):
    async def test_final_live_card_is_edited_with_cheer(self):
        a=Bowler(id=1,name='Benny',owner_id=1,sprite_key='the_dude')
        b=Bowler(id=2,name='Josh',owner_id=2,sprite_key='jesus')
        session=SimpleNamespace(seed=42,complete=True,
                                players=[finished_player(a,9),finished_player(b,8)],
                                team_totals=lambda:{})
        message=SimpleNamespace(edit=AsyncMock())
        channel=SimpleNamespace(id=123,send=AsyncMock())
        games.LANE_MESSAGES[123]=message
        try:
            with tempfile.TemporaryDirectory() as directory:
                image_path=Path(directory)/'winner.png'
                Image.new('RGB',(100,100)).save(image_path)
                with patch('cogs.games.render_victory_scene',return_value=image_path), \
                     patch('cogs.games.scoreboard_embed',return_value=discord.Embed(title='Live Game')):
                    done=await games.publish_victory(channel,session,
                        {'before':[1],'down':[1],'after':[],'bowler_id':2})
            self.assertTrue(done)
            message.edit.assert_awaited_once()
            self.assertIsNone(message.edit.await_args.kwargs['view'])
            self.assertEqual(message.edit.await_args.kwargs['embed'].fields[-1].name,
                             '🏆 Match Winner')
            self.assertIn('Benny',message.edit.await_args.kwargs['embed'].fields[-1].value)
        finally:
            games.LANE_MESSAGES.pop(123,None)


if __name__=='__main__':
    unittest.main()
