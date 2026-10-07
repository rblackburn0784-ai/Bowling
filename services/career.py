import random
from storage.database import connect

ATTRS=('accuracy','consistency','spin','nerves','style','flair')
RANKS=[(1,'Rookie'),(5,'League Bowler'),(10,'Competitor'),(15,'Contender'),(20,'Ace'),(30,'Pro'),(40,'Elite'),(50,'Master'),(75,'Champion'),(100,'Hall of Famer')]

def rank_title(rank):
 title=RANKS[0][1]
 for level,name in RANKS:
  if rank>=level:title=name
 return title

def rank_from_xp(xp):
 # Slow prestige curve; rank has only a tiny simulation effect.
 return max(1,min(100,1+int((max(0,xp)/120)**0.72)))

def sync_rank(bowler_id):
 with connect() as c:
  p=c.execute('SELECT xp FROM bowler_progression WHERE bowler_id=?',(bowler_id,)).fetchone();xp=p['xp'] if p else 0
  rank=rank_from_xp(xp);c.execute('UPDATE bowlers SET rank=? WHERE id=?',(rank,bowler_id))
 return rank

def _change(bowler_id,stat,delta,reason):
 if stat not in ATTRS or not delta:return None
 with connect() as c:
  row=c.execute(f'SELECT {stat} FROM bowlers WHERE id=?',(bowler_id,)).fetchone()
  if not row:return None
  old=row[stat];new=max(1,min(50,old+delta))
  if new==old:return None
  c.execute(f'UPDATE bowlers SET {stat}=? WHERE id=?',(new,bowler_id))
  c.execute('INSERT INTO attribute_history(bowler_id,stat,delta,old_value,new_value,reason) VALUES(?,?,?,?,?,?)',(bowler_id,stat,new-old,old,new,reason))
 return stat,new-old,new,reason

def delivery_growth(event,rng=None):
 rng=rng or random
 bid=event.get('bowler_id')
 if not bid or bid<1:return []
 changes=[];pins=event.get('pins',0);ball=event.get('ball',1);before=len(event.get('before',[]));quality=event.get('quality',0)
 # Rare, event-driven movement. One bad roll should sting occasionally, not erase a career.
 if pins==0 and rng.random()<.16:
  stat=rng.choice(('accuracy','consistency'));x=_change(bid,stat,-1,'Gutter ball');changes += [x] if x else []
 elif ball>1 and before<=2 and pins==0 and rng.random()<.20:
  stat=rng.choice(('accuracy','nerves'));x=_change(bid,stat,-1,'Missed easy spare');changes += [x] if x else []
 if event.get('split_conversion') and rng.random()<.28:
  stat=rng.choice(('accuracy','style','nerves'));x=_change(bid,stat,1,'Difficult split conversion');changes += [x] if x else []
 elif pins==10 and quality<.58 and rng.random()<.08:
  stat=rng.choice(('style','flair'));x=_change(bid,stat,1,'Creative strike carry');changes += [x] if x else []
 elif event.get('strike_streak',0)>=3 and rng.random()<.06:
  stat=rng.choice(('consistency','spin','flair'));x=_change(bid,stat,1,'Strike streak');changes += [x] if x else []
 if event.get('frame',0)>=9 and (event.get('spare') or pins==10) and rng.random()<.08:
  x=_change(bid,'nerves',1,'Clutch late-frame shot');changes += [x] if x else []
 return changes


def rollback_delivery_changes(bowler_id,changes):
 if not bowler_id or not changes:return
 with connect() as c:
  for stat,delta,new,reason in changes:
   if stat not in ATTRS:continue
   row=c.execute('SELECT id,old_value,new_value FROM attribute_history WHERE bowler_id=? AND stat=? AND delta=? AND new_value=? AND reason=? ORDER BY id DESC LIMIT 1',(bowler_id,stat,delta,new,reason)).fetchone()
   if not row:continue
   cur=c.execute(f'SELECT {stat} FROM bowlers WHERE id=?',(bowler_id,)).fetchone()
   if cur and cur[stat]==row['new_value']:
    c.execute(f'UPDATE bowlers SET {stat}=? WHERE id=?',(row['old_value'],bowler_id));c.execute('DELETE FROM attribute_history WHERE id=?',(row['id'],))


def xp_for_rank(rank):
 if rank<=1:return 0
 return int(120*((rank-1)**(1/0.72)))

def rank_progress(xp, rank):
 if rank>=100:return 100.0,None
 prev=xp_for_rank(rank);nxt=xp_for_rank(rank+1)
 return max(0,min(100,(xp-prev)/max(1,nxt-prev)*100)),nxt


def rank_ladder():
 return tuple(RANKS)
