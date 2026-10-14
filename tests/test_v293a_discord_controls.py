"""Discord-only interaction regression tests (run in GitHub CI with discord.py)."""
import importlib.util
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch


@unittest.skipUnless(importlib.util.find_spec('discord'), 'discord.py not installed locally')
class GameStopDiscordTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from cogs.games import MATCH_BUSY,STOP_REQUESTS
        from services.state import SESSIONS
        MATCH_BUSY.clear();STOP_REQUESTS.clear();SESSIONS.clear()

    async def asyncTearDown(self):
        from cogs.games import MATCH_BUSY,STOP_REQUESTS
        from services.state import SESSIONS
        MATCH_BUSY.clear();STOP_REQUESTS.clear();SESSIONS.clear()

    async def test_live_match_stop_button_and_admin_permission(self):
        from cogs.games import LiveMatchControls,StopMatchConfirm
        from services.state import SESSIONS
        session=SimpleNamespace(session_uid='abc',complete=False,players=[SimpleNamespace(bowler=SimpleNamespace(owner_id=10))])
        SESSIONS[123]=session
        live=LiveMatchControls(123,session)
        self.assertIn('🛑 Stop Game',[x.label for x in live.children])
        confirm=StopMatchConfirm(123,session)
        async def authorized(user_id,manage=False):
            resp=SimpleNamespace(send_message=AsyncMock())
            i=SimpleNamespace(channel_id=123,user=SimpleNamespace(id=user_id,
                guild_permissions=SimpleNamespace(administrator=False,manage_guild=manage)),response=resp)
            return await confirm.interaction_check(i),resp
        self.assertFalse((await authorized(10))[0], 'Players must not be able to cancel a game')
        self.assertTrue((await authorized(99,manage=True))[0])
        confirm.stop();live.stop()

    async def test_autoplay_stop_is_queued_and_no_second_ball_runs(self):
        from cogs.games import Games, MATCH_BUSY,STOP_REQUESTS
        from services.state import SESSIONS
        session=SimpleNamespace(complete=False,session_uid='matchabc')
        channel=SimpleNamespace(id=889)
        SESSIONS[889]=session
        games=Games(bot=object())
        calls=[]
        async def fake_delivery(ch,s):
            calls.append(1)
            STOP_REQUESTS[ch.id]=(s.session_uid,777)
        async def cancel(ch,s,actor):
            self.assertEqual(actor,777)
            self.assertEqual(len(calls),1)
            STOP_REQUESTS.pop(ch.id,None)
            SESSIONS.pop(ch.id,None)
            return True,'cancelled'
        with patch('cogs.games.stop_active_match',side_effect=cancel),\
             patch('cogs.games.asyncio.sleep',new_callable=AsyncMock):
            games._deliver=fake_delivery
            self.assertTrue(await games.play_all(channel,session))
        self.assertEqual(calls,[1])
        self.assertNotIn(889,MATCH_BUSY)

    async def test_final_delivery_stop_prevents_postgame_awards(self):
        from cogs.games import Games,STOP_REQUESTS
        from services.state import SESSIONS
        from services.game_engine import GameSession
        from models.bowler import Bowler
        session=GameSession([Bowler(id=25,name='FinalStop',owner_id=25)],seed=999)
        session.friendly_challenge=True
        session.practice_no_rewards=True
        channel=SimpleNamespace(id=887)
        SESSIONS[887]=session
        # Simulate the last delivery completing while the admin presses Stop
        # during the animation. No finalisation function is allowed to run.
        def last_bowl():
            session.ball_count+=1
            session.players[0].frame=11
            session.players[0].frames=[[0,0]]*10
            return {'bowler':'FinalStop','bowler_id':25,'down':[],
                    'before':[1],'after':[1],'pins':0}
        session.bowl=last_bowl
        async def show_animation(*args,**kwargs):
            STOP_REQUESTS[887]=(session.session_uid,2)
        async def cancel(ch,s,actor):
            SESSIONS.pop(ch.id,None)
            STOP_REQUESTS.pop(ch.id,None)
            return True,'cancelled'
        cog=Games(bot=object())
        with patch('cogs.games.save_snapshot'),\
             patch('cogs.games.animate_delivery',side_effect=show_animation),\
             patch('cogs.games.stop_active_match',side_effect=cancel),\
             patch.object(cog,'finish',new_callable=AsyncMock) as finish,\
             patch('cogs.games.update_lane',new_callable=AsyncMock) as update:
            self.assertTrue(await cog.play_one(channel,session))
            finish.assert_not_awaited()
            update.assert_not_awaited()
        self.assertNotIn(887,SESSIONS)

    async def test_confirmation_while_busy_queues_uid_not_immediate_recovery(self):
        from cogs.games import StopMatchConfirm,MATCH_BUSY,STOP_REQUESTS
        from services.state import SESSIONS
        session=SimpleNamespace(session_uid='confirmed',complete=False)
        SESSIONS[991]=session
        MATCH_BUSY.add(991)
        view=StopMatchConfirm(991,session)
        try:
            i=SimpleNamespace(channel_id=991,user=SimpleNamespace(id=123,
                guild_permissions=SimpleNamespace(administrator=True,manage_guild=True)),
                response=SimpleNamespace(defer=AsyncMock()),followup=SimpleNamespace(send=AsyncMock()))
            confirm=next(x for x in view.children if x.label=='🛑 Confirm Stop')
            await confirm.callback(i)
            self.assertEqual(STOP_REQUESTS[991],('confirmed',123))
            self.assertEqual(i.followup.send.await_count,1)
        finally:
            view.stop()


if __name__=='__main__':unittest.main()
