"""Runs in GitHub Actions with discord.py; skips if dependency unavailable."""
import unittest
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace
from models.bowler import Bowler
from services.game_engine import GameSession
try:
    import discord
    from cogs import games
except ImportError:
    discord=None
    games=None


@unittest.skipIf(discord is None, 'discord.py is installed in GitHub CI')
class BroadcastDiscordTests(unittest.IsolatedAsyncioTestCase):
    def make_session(self, layout='broadcast'):
        a=Bowler(1,'Benny',51,'R',1,15,15,15,15,15,15)
        b=Bowler(2,'Josh',52,'L',1,15,15,15,15,15,15)
        a.team_name='The Saints';b.team_name='The Sinners'
        return GameSession([a,b],seed=314,layout=layout)

    async def test_new_match_intro_sent_once(self):
        s=self.make_session()
        ch=SimpleNamespace(id=1337,send=AsyncMock())
        with patch.object(games,'scoreboard_embed',return_value=discord.Embed(title='Game')):
            try:
                await games.post_match_controls(ch,s,introduce=True)
                self.assertEqual(ch.send.await_count,2)  # intro + live controls
                self.assertTrue(ch.send.await_args.kwargs['view'])
                await games.post_match_controls(ch,s,introduce=True)
                self.assertEqual(ch.send.await_count,3)  # no second intro
                await games.post_match_controls(ch,s) # recovery path
                self.assertEqual(ch.send.await_count,4)
            finally:
                games.LANE_MESSAGES.pop(ch.id,None)

    async def test_final_card_for_finals_and_no_duplicate_standard(self):
        s=self.make_session('finals')
        ch=SimpleNamespace(id=55,send=AsyncMock())
        with patch('cogs.games.play_sound',new_callable=AsyncMock) as audio:
            self.assertTrue(await games.publish_match_final(ch,s,'The Saints'))
        audio.assert_awaited_once_with(ch,'champion')
        self.assertEqual(ch.send.await_count,1)
        self.assertIsInstance(ch.send.await_args.kwargs['file'],discord.File)
        s.layout='broadcast'
        self.assertFalse(await games.publish_match_final(ch,s,'The Saints'))
        self.assertEqual(ch.send.await_count,1)

    async def test_intro_failure_cannot_stop_live_controls(self):
        s=self.make_session()
        ch=SimpleNamespace(id=617,send=AsyncMock())
        calls=0
        async def send(*args,**kwargs):
            nonlocal calls
            calls+=1
            if calls==1:raise RuntimeError('missing upload permission')
            return SimpleNamespace(edit=AsyncMock())
        ch.send.side_effect=send
        with patch.object(games,'scoreboard_embed',return_value=discord.Embed(title='Game')):
            try:
                await games.post_match_controls(ch,s,introduce=True)
            finally:
                games.LANE_MESSAGES.pop(ch.id,None)
        self.assertEqual(calls,2)

if __name__=='__main__':unittest.main()
