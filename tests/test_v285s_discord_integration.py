"""Runtime/interaction tests require discord.py and run in a deployed CI environment."""
import importlib.util
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch

@unittest.skipUnless(importlib.util.find_spec('discord') is not None,'discord.py unavailable in this environment')
class DiscordIntegrityTests(unittest.IsolatedAsyncioTestCase):
    async def test_director_view_denies_unprivileged_button_interactions(self):
        from cogs.director import DirectorView
        view=DirectorView('Cup')
        response=SimpleNamespace(send_message=AsyncMock())
        i=SimpleNamespace(user=SimpleNamespace(guild_permissions=SimpleNamespace(
            administrator=False,manage_guild=False)),response=response)
        self.assertFalse(await view.interaction_check(i))
        response.send_message.assert_awaited_once()
        i.user.guild_permissions.manage_guild=True
        self.assertTrue(await view.interaction_check(i))
        view.stop()

    async def test_legacy_start_refuses_existing_match_before_loading_rosters(self):
        from cogs.games import Games
        response=SimpleNamespace(send_message=AsyncMock())
        i=SimpleNamespace(channel_id=47,response=response)
        with patch('cogs.games.channel_has_active_match',return_value=True),\
             patch('cogs.games.team_roster') as roster:
            await Games.start.callback(Games(object()),i,'Left')
        roster.assert_not_called()
        self.assertIn('already active',response.send_message.await_args.args[0])

if __name__=='__main__':unittest.main()
