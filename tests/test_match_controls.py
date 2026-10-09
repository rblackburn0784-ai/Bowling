"""Regression checks: cosmetic sprite assignment and one-click match controls."""
import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from models.bowler import Bowler
from services.bowler_sprites import assign_match_sprites
from services.game_engine import GameSession
from services.state import SESSIONS
from cogs.games import (AUTO_BETWEEN_BALLS, AUTO_FRAME_DELAY, MATCH_BUSY,
                        LiveMatchControls, Games, can_operate_match)


def bowler(number,name,sprite=None):
    return Bowler(id=number,name=name,owner_id=number,sprite_key=sprite)


class MatchSpriteTests(unittest.TestCase):
    def test_first_two_are_dude_and_jesus_without_rewriting_stats(self):
        left=bowler(1,'Benny')
        right=bowler(2,'Josh')
        before=(left.stat_total,right.stat_total)
        s=GameSession([left,right],seed=101)
        self.assertEqual([x.bowler.sprite_key for x in s.players],['the_dude','jesus'])
        self.assertEqual((left.stat_total,right.stat_total),before)
        self.assertEqual(s.seed,101)

    def test_explicit_selection_and_opt_out_survive(self):
        a=bowler(1,'One','jesus')
        b=bowler(2,'Two')
        c=bowler(3,'Three','none')
        result=assign_match_sprites([a,b,c])
        self.assertEqual(result,{1:'jesus',2:'the_dude',3:None})
        self.assertEqual(c.sprite_key,'none')

    def test_named_character_keeps_identity(self):
        player=bowler(1,'TheDude')
        challenger=bowler(2,'Someone Else')
        assigned=assign_match_sprites([player,challenger])
        self.assertEqual(assigned[1],'the_dude')
        self.assertEqual(assigned[2],'jesus')

    def test_player_permissions_are_consistent_for_buttons_and_commands(self):
        session=SimpleNamespace(players=[SimpleNamespace(
            bowler=SimpleNamespace(owner_id=123))])
        def member(ident,admin=False):
            return SimpleNamespace(id=ident,guild_permissions=SimpleNamespace(
                administrator=admin,manage_guild=False))
        self.assertTrue(can_operate_match(member(123),session))
        self.assertTrue(can_operate_match(member(999,admin=True),session))
        self.assertFalse(can_operate_match(member(999),session))

    def test_default_pacing(self):
        self.assertGreaterEqual(AUTO_BETWEEN_BALLS,.5)
        self.assertLessEqual(AUTO_BETWEEN_BALLS,3)
        self.assertGreaterEqual(AUTO_FRAME_DELAY,.8)


class LiveMatchTests(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        SESSIONS.clear()
        MATCH_BUSY.clear()

    async def test_live_view_buttons_and_authorization(self):
        session=SimpleNamespace(complete=False,players=[
            SimpleNamespace(bowler=SimpleNamespace(owner_id=123))])
        SESSIONS[777]=session
        view=LiveMatchControls(777,session)
        labels={item.label for item in view.children}
        self.assertIn('🎳 Bowl Next Ball',labels)
        self.assertIn('▶ Auto Play',labels)
        async def permission(user_id,admin=False):
            user=SimpleNamespace(id=user_id,guild_permissions=SimpleNamespace(
                administrator=admin,manage_guild=False))
            response=SimpleNamespace(send_message=AsyncMock())
            interaction=SimpleNamespace(channel_id=777,user=user,response=response)
            return await view.interaction_check(interaction),response
        self.assertTrue((await permission(123))[0])
        self.assertTrue((await permission(999,admin=True))[0])
        self.assertFalse((await permission(999))[0])
        session.complete=True
        self.assertFalse((await permission(123))[0])
        view.stop()

    async def test_busy_guard_prevents_duplicate_balls(self):
        channel=SimpleNamespace(id=554)
        session=SimpleNamespace(complete=False)
        SESSIONS[554]=session
        games=Games(bot=object())
        called=[]
        async def delivered(ch,s):
            called.append(1)
            self.assertIn(554,MATCH_BUSY)
            self.assertFalse(await games.play_one(ch,s))
        games._deliver=delivered
        self.assertTrue(await games.play_one(channel,session))
        self.assertEqual(called,[1])
        self.assertNotIn(554,MATCH_BUSY)

    async def test_auto_uses_same_delivery_function_and_stops(self):
        channel=SimpleNamespace(id=555)
        session=SimpleNamespace(complete=False)
        SESSIONS[555]=session
        games=Games(bot=object())
        count=[]
        async def deliver(ch,s):
            count.append(1)
            if len(count)==2:s.complete=True
        games._deliver=deliver
        self.assertTrue(await games.play_all(channel,session))
        self.assertEqual(len(count),2)
        self.assertNotIn(555,MATCH_BUSY)


if __name__=='__main__':
    unittest.main()
