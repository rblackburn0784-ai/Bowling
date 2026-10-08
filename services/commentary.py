import random
from services.analytics import named_leave
from services.dude_commentary import event_line
LINES={
'strike':['💥 **{name} buries the pocket — STRIKE!**','⚡ Ten back in a hurry! **{name}** has all of them.','🔥 **{name}** sends the rack into orbit!'],
'spare':['🧹 **{name}** cleans it up for the spare.','🎯 No loose ends — spare converted by **{name}**.'],
'split':['😬 Trouble on the deck: **{name}** leaves **{leave}**.','🪓 The rack tears apart — **{leave}** for **{name}**.'],
'split_convert':['🤯 **{name} CONVERTS THE {leave}!** The place erupts!','🎯 Impossible? Not tonight. **{name}** picks up the **{leave}**!'],
'gutter':['🕳️ Gutter ball. The pins remain completely unimpressed.','😱 That one finds the channel. Nothing doing for **{name}**.'],
'normal':['🎳 **{name}** knocks down **{pins}**.','Pins scatter — **{pins}** down for **{name}**.'],
'perfect':['🚨 **PERFECT GAME WATCH:** {name} is still flawless through {frame}!','🤫 The building knows. **{name}** remains perfect after {frame}.'],
'final_perfect':['🏆🎳 **300! PERFECT GAME!** {name} has done it!'],
'entrance':['🎤 The lights drop. **{name}** steps onto the approach.','📣 Make some noise — **{name}** has entered the lanes!'],}
def line(kind,**kw): return random.choice(LINES.get(kind,LINES['normal'])).format(**kw)
def event_text(session,event):
    if event.get('split_conversion'): kind='split_convert'
    elif event.get('pins',0)==0: kind='gutter'
    elif event.get('pins',0)==10: kind='strike'
    elif event.get('split'): kind='split'
    elif event.get('spare'): kind='spare'
    else: kind='normal'
    return event_line(session,kind,event)

def streak_call(event):
    n=event.get('strike_streak',0); name=event['bowler'];names={3:'🦃 TURKEY!',4:'🔥 FOUR-BAGGER!',5:'🔥 FIVE IN A ROW!',6:'🎒 SIX-PACK!',7:'🚂 SEVEN STRAIGHT!',8:'🚂 EIGHT STRAIGHT!',9:'🚨 FRONT NINE!',10:'🚨 TEN STRAIGHT!',11:'🚨 ELEVEN! ONE BALL FROM 300!',12:'🏆 PERFECT 300!'}
    return f"{names[n]} **{name}**" if n in names else None
def rivalry_call(event):
    if not event.get('rivalry'):return None
    a,b=event['rivalry'];return f"⚔️ **RIVALRY MOMENT:** {a} answers {b} under the lights!"
def perfect_watch(player):
    completed=min(player.frame-1,10)
    if not player.frames:return None
    for idx,f in enumerate(player.frames):
        if idx<9 and f and f[0]!=10:return None
        if idx==9 and any(x!=10 for x in f):return None
    if player.complete and len(player.frames)>=10 and player.frames[9]==[10,10,10]:return line('final_perfect',name=player.bowler.name)
    if completed>=5:return line('perfect',name=player.bowler.name,frame=completed)
    return None
PERSONAS={'saints':{'prefix':'🟣','strike':['That rack never stood a chance.','Neon shakes over the approach — all ten are gone.']},'classic':{'prefix':'🎙️','strike':['Textbook pocket strike.','Excellent execution and ten down.']},'hype':{'prefix':'📣','strike':['THE RACK EXPLODES!','ABSOLUTELY BURIED IT!']},'deadpan':{'prefix':'🥃','strike':['Ten pins were present. They are no longer present.','Efficient. Slightly rude to the pins.']}}
def personality_line(kind,name,pins=0,persona='saints',**kw):
    p=PERSONAS.get(persona,PERSONAS['saints'])
    if kind=='strike':return f"{p['prefix']} **{name}:** {random.choice(p['strike'])}"
    return event_text(None,{'bowler':name,'pins':pins,**kw})
def contact_call(event):
    if event['ball']!=1:return None
    q=event.get('quality',0);pins=event['pins'];after=set(event.get('after',[]))
    if pins==10:return random.choice(['🎯 **Pocket hit.** Flush and gone.','🪽 A **messenger** races across the deck to finish the rack.','🌉 **Brooklyn strike!** Crossed over — still counts.']) if q<.72 else '🎯 **Pocket hit** — pure execution.'
    if after=={10}:return '🔔 **Ringing 10-pin.** Everything moved except the corner.'
    if after=={8}:return '🪨 **Stone 8.** Robbed on a good-looking shot.'
    if after=={9}:return '🪨 **Stone 9.** The rack refuses to cooperate.'
    if 1 in after and len(after)>=3:return '⚠️ **Nose hit / washout territory.** Trouble on the deck.'
    if q>.75:return '💡 **Light pocket hit** — close, but not quite flush.'
    if q<.45:return '⬆️ **High hit.** The ball never found the ideal line.'
    return None


def lane_call(event):
 a=event.get('adaptation');condition=event.get('lane_condition');lane=event.get('lane_no','?')
 bits=[]
 if condition and condition!='still fairly stable':bits.append(f'🛢️ **Lane {lane} {condition}.**')
 if a:
  move=a['to_boards']-a['from_boards'];direction='left' if move>0 else 'right';shift=f' and moves **{abs(move)} boards {direction}**' if move else ''
  if a['from_ball']!=a['to_ball']:bits.append(f"🎳 **{event['bowler']} switches {a['from_ball'].title()} → {a['to_ball'].title()}**{shift} — {a['reason']}.")
  elif shift:bits.append(f"🎯 **{event['bowler']} moves {abs(move)} boards {direction}** — {a['reason']}.")
 return '\n'.join(bits) if bits else None
