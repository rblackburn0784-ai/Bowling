"""v2.9.6d: player navigation edits one Discord ephemeral message."""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import discord
from cogs.menu import PublicMenu, HomeView, CareerView
from services.menu_navigation import edit_panel, modal_panel

def interaction():
    response=SimpleNamespace(edit_message=AsyncMock(),send_message=AsyncMock(),send_modal=AsyncMock())
    user=SimpleNamespace(id=42,guild_permissions=SimpleNamespace(administrator=False,manage_guild=False))
    return SimpleNamespace(response=response,user=user)

async def click(view,label,i):
    button=next(x for x in view.children if isinstance(x,discord.ui.Button) and x.label==label)
    await button.callback(i)

class MainMenuNavigation(unittest.IsolatedAsyncioTestCase):
    async def test_competitions_replace_original_message_and_home_reuses_it(self):
        i=interaction()
        with patch('cogs.competition_ui.my_competitions_embed',return_value=discord.Embed(title='My Competitions')):
            await click(PublicMenu(),'My Competition',i)
        i.response.send_message.assert_not_called()
        kwargs=i.response.edit_message.call_args.kwargs
        self.assertEqual(kwargs['embed'].title,'My Competitions')
        self.assertEqual(kwargs['attachments'],[])
        self.assertIsInstance(kwargs['view'],HomeView)
        await click(kwargs['view'],'🏠 Main Menu',i)
        self.assertIsNone(i.response.edit_message.call_args.kwargs['embed'])
        self.assertEqual(i.response.edit_message.call_args.kwargs['attachments'],[])
        self.assertIsInstance(i.response.edit_message.call_args.kwargs['view'],PublicMenu)
        i.response.send_message.assert_not_called()

    async def test_bowler_profile_and_change_sprite_use_same_message(self):
        i=interaction()
        bowler=SimpleNamespace(id=17,name='My Bowler',sprite_key='01_cardigan_classic')
        file=object()
        with patch('cogs.menu.get_bowler_by_owner',return_value=bowler),\
             patch('cogs.menu.bowler_embed',return_value=discord.Embed(title='My Bowler')),\
             patch('cogs.menu.bowler_art_file',return_value=file),\
             patch('cogs.menu.installed_sprites',return_value=('01_cardigan_classic',)):
            await click(PublicMenu(),'My Bowler',i)
            kwargs=i.response.edit_message.call_args.kwargs
            self.assertIsInstance(kwargs['view'],CareerView)
            self.assertEqual(kwargs['attachments'],[file])
            self.assertEqual(kwargs['embed'].image.url,'attachment://gs_bowler_sprite.png')
            await click(kwargs['view'],'Change Sprite',i)
            self.assertEqual(i.response.edit_message.call_args.kwargs['attachments'],[file])
        i.response.send_message.assert_not_called()

    async def test_every_public_navigation_option_replaces_panel(self):
        i=interaction()
        with patch('cogs.menu.get_bowler_by_owner',return_value=SimpleNamespace(id=5,name='Test',sprite_key=None)),\
             patch('cogs.menu.bowler_embed',return_value=discord.Embed(title='Stats')),\
             patch('cogs.menu.list_bowlers',return_value=[]),\
             patch('cogs.menu.bowler_loadout',return_value={'primary_ball':'hybrid'}),\
             patch('services.gazette.latest_gazette',return_value=None),\
             patch('services.gazette.format_gazette',return_value='No edition'),\
             patch('services.gazette.gazette_archive',return_value=[]),\
             patch('cogs.season_ui.connect') as db:
            db.return_value.__enter__.return_value.execute.return_value.fetchall.return_value=[]
            for label in ('My Stats','My Arsenal','Browse Bowlers','Season Hub','Gutter Gazette','Career Records'):
                await click(PublicMenu(),label,i)
                self.assertEqual(i.response.edit_message.call_args.kwargs['attachments'],[],label)
                self.assertIsNotNone(i.response.edit_message.call_args.kwargs['view'],label)
        i.response.send_message.assert_not_called()
        self.assertEqual(i.response.edit_message.await_count,6)

    async def test_season_hub_home_returns_same_panel(self):
        i=interaction()
        from cogs.season_ui import SeasonExperience
        with patch('cogs.season_ui.connect') as db:
            db.return_value.__enter__.return_value.execute.return_value.fetchall.return_value=[]
            view=SeasonExperience()
        await click(view,'🏠 Main Menu',i)
        self.assertIsInstance(i.response.edit_message.call_args.kwargs['view'],PublicMenu)
        i.response.send_message.assert_not_called()

    async def test_modal_updates_parent_when_message_available(self):
        i=interaction();i.message=object()
        await modal_panel(i,content='Character selected',view=HomeView())
        i.response.edit_message.assert_awaited_once()
        i.response.send_message.assert_not_called()

    async def test_modal_without_parent_has_safe_ephemeral_fallback(self):
        i=interaction();i.message=None
        await modal_panel(i,content='Character selected',view=HomeView())
        i.response.edit_message.assert_not_called()
        self.assertTrue(i.response.send_message.call_args.kwargs['ephemeral'])

    async def test_attachment_cleanup_on_plain_navigation(self):
        i=interaction()
        await edit_panel(i,embed=discord.Embed(title='Profile'),view=HomeView(),file=object())
        self.assertEqual(len(i.response.edit_message.call_args.kwargs['attachments']),1)
        await edit_panel(i,content='My Competition',view=HomeView())
        args=i.response.edit_message.call_args.kwargs
        self.assertEqual(args['attachments'],[])
        self.assertIsNone(args['embed'])
        i.response.send_message.assert_not_called()

if __name__=='__main__':unittest.main()
