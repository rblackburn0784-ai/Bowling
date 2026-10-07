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

def _timeline(c,bowler_id,kind,icon,headline,detail='',source='career'):
 c.execute('INSERT INTO career_timeline(bowler_id,kind,icon,headline,detail,source) VALUES(?,?,?,?,?,?)',(bowler_id,kind,icon,headline,detail,source))

def add_tendency(bowler_id,stat,amount,reason,source='delivery'):
 if stat not in ATTRS or not amount:return None
 with connect() as c:
  c.execute('INSERT OR IGNORE INTO career_tendencies(bowler_id,stat) VALUES(?,?)',(bowler_id,stat))
  row=c.execute('SELECT score,evidence FROM career_tendencies WHERE bowler_id=? AND stat=?',(bowler_id,stat)).fetchone()
  score=max(-24.0,min(24.0,row['score']+amount));evidence=row['evidence']+1
  c.execute('UPDATE career_tendencies SET score=?,evidence=?,updated_at=CURRENT_TIMESTAMP WHERE bowler_id=? AND stat=?',(score,evidence,bowler_id,stat))
  threshold=10.0
  if evidence>=3 and abs(score)>=threshold:
   delta=1 if score>0 else -1
   br=c.execute(f'SELECT {stat} FROM bowlers WHERE id=?',(bowler_id,)).fetchone();old=br[stat];new=max(1,min(50,old+delta))
   if new!=old:
    c.execute(f'UPDATE bowlers SET {stat}=? WHERE id=?',(new,bowler_id))
    c.execute('INSERT INTO attribute_history(bowler_id,stat,delta,old_value,new_value,reason) VALUES(?,?,?,?,?,?)',(bowler_id,stat,new-old,old,new,reason))
    _timeline(c,bowler_id,'attribute','🟢' if delta>0 else '🔴',f"{stat.title()} {'+' if delta>0 else ''}{delta}",reason,source)
    score-=threshold*delta
   c.execute('UPDATE career_tendencies SET score=?,evidence=0 WHERE bowler_id=? AND stat=?',(score,bowler_id,stat))
   return (stat,new-old,new,reason) if new!=old else None
 return None

def delivery_growth(event,rng=None):
 bid=event.get('bowler_id')
 if not bid or bid<1:return []
 pins=event.get('pins',0);ball=event.get('ball',1);before=set(event.get('before',[]));frame=event.get('frame',0);quality=event.get('quality',0);changes=[]
 signals=[]
 # Persistent evidence: repeated behaviour shapes careers instead of independent random +/- rolls.
 if pins==0 and ball==1:signals += [('accuracy',-1.8,'Repeated gutter-ball control issues'),('consistency',-1.2,'Repeated gutter-ball control issues')]
 if ball>1 and len(before)==1 and pins==0:
  signals += [('accuracy',-2.0,'Repeated single-pin spare misses')]
  if frame>=9:signals += [('nerves',-2.4,'Late-frame single-pin misses')]
 if event.get('split_conversion'):
  leave=event.get('leave_name') or event.get('named_leave') or 'difficult split'
  signals += [('accuracy',2.4,f'Converted {leave}'),('style',1.5,f'Converted {leave}')]
 if pins==10:
  signals += [('consistency',.45,'Sustained strike production')]
  if quality<.58:signals += [('flair',1.25,'Messenger/creative strike carry')]
 if event.get('strike_streak',0)>=3:signals += [('consistency',1.0,'Built repeated strike streaks'),('spin',.55,'Strike-streak ball motion')]
 if frame>=9 and (event.get('spare') or pins==10):signals += [('nerves',1.1,'Clutch late-frame conversion')]
 for stat,amount,reason in signals:
  x=add_tendency(bid,stat,amount,reason)
  if x:changes.append(x)
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
