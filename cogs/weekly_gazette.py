"""Automatically archive last week's issue every Monday, with database deduplication."""
from datetime import datetime,timezone
import discord
from discord.ext import commands,tasks
from storage.database import connect
from services.season_gazette import publish_previous_week

class WeeklyGazette(commands.Cog):
 def __init__(self,bot):
  self.bot=bot
  self.weekly.start()
 def cog_unload(self):self.weekly.cancel()
 @tasks.loop(hours=1)
 async def weekly(self):
  now=datetime.now(timezone.utc)
  if now.weekday()!=0:return
  with connect() as db:
   seasons=[r['id'] for r in db.execute("SELECT id FROM seasons WHERE status IN ('active','completed')")]
  for sid in seasons:
   try:publish_previous_week(sid,now.date())
   except Exception:
    import logging
    logging.getLogger(__name__).exception('Weekly Gazette publication failed for season %s',sid)
 @weekly.before_loop
 async def ready(self):await self.bot.wait_until_ready()

async def setup(bot):await bot.add_cog(WeeklyGazette(bot))
