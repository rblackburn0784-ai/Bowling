import math
from services.equipment import get_ball
from services.lane_physics import release_metrics
PINS={1:(0,0),2:(-1,1),3:(1,1),4:(-2,2),5:(0,2),6:(2,2),7:(-3,3),8:(-1,3),9:(1,3),10:(3,3)}
ALL=set(PINS)
def is_split(standing):
 s=set(standing)
 if 1 in s or len(s)<2:return False
 xs=sorted(PINS[p][0] for p in s);return any(b-a>=2 for a,b in zip(xs,xs[1:]))
def _special_carry(rng,standing,down,quality,miss,bowler):
 tags=[];style=max(1,min(50,bowler.style));flair=max(1,min(50,bowler.flair))
 if standing==ALL and len(down)==10:
  if abs(miss)>.72:tags.append('brooklyn')
  elif rng.random()<.055+style*.0011:tags.append('messenger')
  elif rng.random()<.04+flair*.0010:tags.append('trip_4')
  return down,tags
 if standing==ALL and quality>.50:
  left=standing-down
  if 10 in left and rng.random()<.20:tags.append('ringing_10')
  if 8 in left and rng.random()<.13:tags.append('stone_8')
  if 9 in left and rng.random()<.13:tags.append('stone_9')
  if {7,10}<=left:tags.append('pocket_7_10')
  if len(down)>=8 and abs(miss)>.55:tags.append('light_mixer')
 return down,tags
def roll_pins(rng,bowler,standing,lane='house',pressure=0.0,form=0.0,transition=0.0,lane_state=None,ball_key='hybrid',target_mode='strike'):
 standing=set(standing);ball=get_ball(ball_key)
 if lane_state is None:
  class Legacy:pass
  lane_state=Legacy();lane_state.pattern_key=lane;lane_state.oil={'fresh':.68,'house':.54,'dry':.30,'oily':.82,'transition':.46}.get(lane,.54);lane_state.transition=transition
 m=release_metrics(bowler,ball,lane_state,pressure);a=max(1,min(50,bowler.accuracy));c=max(1,min(50,bowler.consistency));sp=max(1,min(50,bowler.spin));n=max(1,min(50,bowler.nerves));sty=max(1,min(50,bowler.style));fl=max(1,min(50,bowler.flair))
 # Six player attributes all matter, but no one attribute owns the result.
 base=(a*.22+c*.20+sp*.17+n*.13+sty*.14+fl*.14)/50
 prestige=min(100,max(1,bowler.rank))/100*.025
 oil_fit=1-abs((.58+ball.hook*.16-ball.length*.12)-lane_state.oil)
 spare=standing!=ALL or target_mode=='spare'
 sigma=max(.18,1.02-(a/50)*.42-(c/50)*.25-ball.control*.10)
 if spare and ball.spare_bias:sigma*=.76
 handed=-1 if str(bowler.handedness).upper().startswith('L') else 1
 miss=rng.gauss(0,sigma)-handed*((sp-25)/25)*.06*ball.hook
 pressure_mod=(n-25)/25*pressure*.065
 style_recovery=max(0,sty-25)/25*.025 if abs(miss)>.45 else 0
 flair_form=form*(.75+fl/100)
 quality=max(0,min(1,.30+.48*base+.11*oil_fit+pressure_mod+style_recovery+flair_form+prestige-abs(miss)*.15+rng.gauss(0,.045+(50-c)/1200)))
 if standing==ALL:
  strike_p=.015+.69*(quality**2.38)
  if rng.random()<strike_p:
   down=set(standing);down,tags=_special_carry(rng,standing,down,quality,miss,bowler);return down,quality,{'miss':miss,'ball':ball.key,'target':'pocket','metrics':m,'tags':tags}
 target=min(standing,key=lambda p:(abs(PINS[p][0]),PINS[p][1])) if spare else 1;down=set()
 for p in standing:
  dx=abs(PINS[p][0]-(PINS[target][0]+miss));depth=PINS[p][1]
  chance=max(.015,min(.97,quality*1.08-dx*(.18 if spare else .16)+(3-depth)*.022))
  if rng.random()<chance:down.add(p)
 if not down and rng.random()<quality:down.add(target)
 down,tags=_special_carry(rng,standing,down,quality,miss,bowler);return down,quality,{'miss':miss,'ball':ball.key,'target':target,'metrics':m,'tags':tags}
