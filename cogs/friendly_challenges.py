import discord
from storage.database import connect
from services.state import SESSIONS
PENDING=set()

class OpponentSelect(discord.ui.Select):
 def __init__(self,view,owner):
  self.owner_view=view
  with connect() as db:rs=db.execute('SELECT id,name FROM bowlers WHERE owner_id>0 AND owner_id<>? ORDER BY name LIMIT 25',(owner,)).fetchall()
  super().__init__(placeholder='Choose opponent',options=[discord.SelectOption(label=r['name'][:100],value=str(r['id'])) for r in rs] or [discord.SelectOption(label='No linked opponents',value='0')])
 async def callback(self,i):
  if i.user.id!=self.owner_view.owner:return await i.response.send_message('Not your menu.',ephemeral=True)
  self.owner_view.target=int(self.values[0]);await i.response.defer()

class ChallengeComposer(discord.ui.View):
 def __init__(self,owner):
  super().__init__(timeout=300);self.owner=owner;self.target=None;self.add_item(OpponentSelect(self,owner))
 @discord.ui.button(label='Send Challenge',style=discord.ButtonStyle.success,row=1)
 async def send(self,i,b):
  if i.user.id!=self.owner:return await i.response.send_message('Not your menu.',ephemeral=True)
  if not self.target:return await i.response.send_message('Choose an opponent.',ephemeral=True)
  with connect() as db:
   a=db.execute('SELECT id,name FROM bowlers WHERE owner_id=?',(i.user.id,)).fetchone()
   z=db.execute('SELECT id,name,owner_id FROM bowlers WHERE id=? AND owner_id>0',(self.target,)).fetchone()
  if not a or not z or z['owner_id']==i.user.id:return await i.response.send_message('Both players must own different linked bowlers.',ephemeral=True)
  key=(i.guild_id,i.user.id,z['owner_id'])
  if key in PENDING:return await i.response.send_message('A challenge is already pending.',ephemeral=True)
  if i.channel_id in SESSIONS and not SESSIONS[i.channel_id].complete:return await i.response.send_message('Channel already has an active match.',ephemeral=True)
  PENDING.add(key)
  try:await i.channel.send(f"🎳 **FRIENDLY CHALLENGE**\\n<@{z['owner_id']}>: **{a['name']}** challenges **{z['name']}**!\\nUnranked • No standings or attributes • At most 1 non-ranking XP per day. Accept within 5 minutes.",view=ChallengeResponse(key,i.user.id,z['owner_id'],a['id'],z['id']),allowed_mentions=discord.AllowedMentions(users=True,roles=False,everyone=False))
  except Exception:
   PENDING.discard(key);return await i.response.send_message('Unable to post challenge here.',ephemeral=True)
  await i.response.send_message('Challenge posted.',ephemeral=True)

class ChallengeResponse(discord.ui.View):
 def __init__(self,key,challenger,target,a,b):
  super().__init__(timeout=300);self.key=key;self.challenger=challenger;self.target=target;self.a=a;self.b=b
 async def interaction_check(self,i):
  if i.user.id==self.target:return True
  await i.response.send_message('Only the challenged player can respond.',ephemeral=True);return False
 async def on_timeout(self):PENDING.discard(self.key)
 @discord.ui.button(label='Accept',style=discord.ButtonStyle.success)
 async def accept(self,i,b):
  if self.key not in PENDING:return await i.response.send_message('Challenge expired.',ephemeral=True)
  if i.channel_id in SESSIONS and not SESSIONS[i.channel_id].complete:return await i.response.send_message('Channel already has a match.',ephemeral=True)
  with connect() as db:rs=db.execute('SELECT * FROM bowlers WHERE id IN (?,?)',(self.a,self.b)).fetchall()
  by={r['id']:r for r in rs}
  if len(by)!=2 or by[self.a]['owner_id']!=self.challenger or by[self.b]['owner_id']!=self.target:return await i.response.send_message('Bowler ownership changed.',ephemeral=True)
  from cogs.games import rb
  from services.game_engine import GameSession
  from services.v271 import bowler_loadout
  from ui.embeds import scoreboard_embed
  players=[rb(by[x],by[x]['name']) for x in (self.a,self.b)]
  session=GameSession(players,lane='house');session.friendly_challenge=True
  for p in session.players:p.ball_key=bowler_loadout(p.bowler.id).get('primary_ball','hybrid')
  SESSIONS[i.channel_id]=session;PENDING.discard(self.key)
  for x in self.children:x.disabled=True
  await i.response.edit_message(content=f"✅ **Challenge accepted!** 🎳 **{players[0].name}** vs **{players[1].name}**. Use /game_bowl or /game_auto.",view=self)
  await i.channel.send(embed=scoreboard_embed(session))
 @discord.ui.button(label='Decline',style=discord.ButtonStyle.danger)
 async def decline(self,i,b):
  PENDING.discard(self.key)
  for x in self.children:x.disabled=True
  await i.response.edit_message(content='❌ Challenge declined.',view=self)
