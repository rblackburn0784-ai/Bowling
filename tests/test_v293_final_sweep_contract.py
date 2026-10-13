"""Pre-push checks that do not require importing discord.py.

These guard the slash-command path omitted from earlier broadcast tests.
"""
import ast
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class FinalSweepContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=(ROOT/'cogs/league.py').read_text(encoding='utf-8')
        cls.module=ast.parse(cls.source)
        cls.league=next(n for n in cls.module.body if isinstance(n,ast.ClassDef) and n.name=='League')

    def test_competition_mutations_have_runtime_permission_check(self):
        check=next(n for n in self.league.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='cog_app_command_check')
        src=ast.unparse(check)
        self.assertIn('admin_ok(i)',src)
        self.assertIn('league_table',src)
        self.assertIn('season_dashboard',src)
        self.assertIn('response.send_message',src)
        self.assertIn('return False',src)

    def test_old_fixture_slash_path_posts_intro_controls_and_finals(self):
        start=next(n for n in self.league.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='fixture_start')
        src=ast.unparse(start)
        self.assertIn('post_match_controls(i.channel, s, introduce=True)',src)
        self.assertIn('is_elimination_final(',src)
        self.assertIn("layout='finals' if championship else 'broadcast'",src)
        self.assertLess(src.index('await i.response.send_message'),src.index('await post_match_controls(i.channel, s, introduce=True)'))

if __name__=='__main__':unittest.main()

# Runtime permission checks run in the project's GitHub Actions environment.
try:
    import discord  # noqa: F401
except ImportError:
    discord=None

@unittest.skipIf(discord is None,'discord.py unavailable for local interaction tests')
class LeagueRuntimePermissions(unittest.IsolatedAsyncioTestCase):
    async def test_mutation_requires_manage_server(self):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        from cogs.league import League
        view=League(object())
        perms=SimpleNamespace(administrator=False,manage_guild=False)
        resp=SimpleNamespace(send_message=AsyncMock())
        interaction=SimpleNamespace(command=SimpleNamespace(name='fixture_start'),
                                    user=SimpleNamespace(guild_permissions=perms),response=resp)
        self.assertFalse(await view.cog_app_command_check(interaction))
        resp.send_message.assert_awaited_once()
        perms.manage_guild=True
        self.assertTrue(await view.cog_app_command_check(interaction))
        perms.manage_guild=False
        interaction.command.name='league_table'
        self.assertTrue(await view.cog_app_command_check(interaction))
