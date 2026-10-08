import os,logging,discord
from discord.ext import commands
from dotenv import load_dotenv
from storage.database import init_db
load_dotenv();logging.basicConfig(level=logging.INFO)
EXTENSIONS=['cogs.bowlers','cogs.teams','cogs.games','cogs.stats','cogs.admin','cogs.tournaments','cogs.series','cogs.awards','cogs.menu','cogs.director','cogs.features','cogs.av','cogs.simulation_lab','cogs.league','cogs.weekly_gazette']
class GutterSaints(commands.Bot):
 def __init__(self):super().__init__(command_prefix='!',intents=discord.Intents(guilds=True,members=True))
 async def setup_hook(self):
  init_db()
  self.add_view(__import__('cogs.menu',fromlist=['PublicMenu']).PublicMenu())
  for e in EXTENSIONS:await self.load_extension(e)
  guild=os.getenv('GUILD_ID')
  if guild:
   g=discord.Object(id=int(guild));self.tree.copy_global_to(guild=g);await self.tree.sync(guild=g)
  else:await self.tree.sync()
 async def on_ready(self):print(f'🎳 Logged in as {self.user} ({self.user.id})')
bot=GutterSaints();token=os.getenv('DISCORD_TOKEN')
if not token:raise RuntimeError('Set DISCORD_TOKEN in .env')
bot.run(token)
