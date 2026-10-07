import math,random,time,csv
from dataclasses import dataclass
from config import ROOT
from models.bowler import Bowler
from services.game_engine import GameSession
from services.analytics import player_summary
EXPORT_DIR=ROOT/'data'/'simulations'
@dataclass(slots=True)
class SimProfile:
 name:str;rank:int=20;accuracy:int=20;style:int=10;flair:int=10;consistency:int=20;spin:int=10;nerves:int=10;handedness:str='R';ball:str='hybrid'
 def bowler(self,idx=1):return Bowler(-idx,self.name,0,self.handedness,self.rank,self.accuracy,self.style,self.flair,self.consistency,self.spin,self.nerves)
def run_profile(p,games=1000,lane='house',burn=0.0,seed=7275):
 games=max(1,min(100000,int(games)));rng=random.Random(seed);scores=[];strikes=spares=chances=firsts=0
 for n in range(games):
  s=GameSession([p.bowler(n+1)],rng.randrange(1,2**31),lane,lane_start=3,layout='standard');pg=s.players[0];pg.ball_key=p.ball
  for ls in (s.lane_pair.left,s.lane_pair.right):ls.track=max(0,min(1,burn));ls.oil=max(.12,ls.oil-burn*.20)
  while not s.complete:
   ev=s.bowl()
   if ev['ball']==1:firsts+=1;strikes+=int(ev['pins']==10)
   else:chances+=1;spares+=int(bool(ev.get('spare')))
  scores.append(player_summary(pg)['score'])
 avg=sum(scores)/games;sd=math.sqrt(sum((x-avg)**2 for x in scores)/max(1,games-1));ci=1.96*sd/math.sqrt(games)
 return {'name':p.name,'games':games,'avg':avg,'ci95':ci,'strike_pct':strikes/max(1,firsts)*100,'spare_pct':spares/max(1,chances)*100,'p200':sum(x>=200 for x in scores)/games*100,'p250':sum(x>=250 for x in scores)/games*100,'p300':sum(x==300 for x in scores)/games*100,'sd':sd,'min':min(scores),'max':max(scores)}
def compare(profiles,games=1000,lane='house',burn=0.0,seed=7275):return [run_profile(p,games,lane,burn,seed+i*100003) for i,p in enumerate(profiles)]
def dominance_flags(rows):
 if len(rows)<2:return []
 out=[];q=sorted(rows,key=lambda r:r['avg'],reverse=True);gap=q[0]['avg']-q[1]['avg']
 if gap>12:out.append(f"Dominance warning: {q[0]['name']} leads by {gap:.1f} pins.")
 for r in rows:
  if r['p300']>1:out.append(f"Perfect-game warning: {r['name']} = {r['p300']:.2f}%.")
  if r['strike_pct']>60:out.append(f"Strike-rate warning: {r['name']} = {r['strike_pct']:.1f}%.")
 return out
def export_csv(rows,label='simulation'):
 EXPORT_DIR.mkdir(parents=True,exist_ok=True);p=EXPORT_DIR/f"{label}_{int(time.time())}.csv"
 with p.open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 return p
