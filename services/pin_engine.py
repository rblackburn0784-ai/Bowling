import math
from services.equipment import get_ball
from services.lane_physics import release_metrics
PINS={1:(0,0),2:(-1,1),3:(1,1),4:(-2,2),5:(0,2),6:(2,2),7:(-3,3),8:(-1,3),9:(1,3),10:(3,3)}
ALL=set(PINS)

def is_split(standing):
    s=set(standing)
    if 1 in s or len(s)<2:return False
    xs=sorted(PINS[p][0] for p in s)
    return any(b-a>=2 for a,b in zip(xs,xs[1:]))

def _special_carry(rng, standing, down, quality, miss, handedness):
    tags=[]
    if standing==ALL and len(down)==10:
        if abs(miss)>.72: tags.append("brooklyn")
        elif rng.random()<.10: tags.append("messenger")
        elif rng.random()<.08: tags.append("trip_4")
        return down,tags
    if standing==ALL and quality>.55:
        # Common pocket leaves are deliberately rare and descriptive, not forced every shot.
        if 10 in standing-down and rng.random()<.20: tags.append("ringing_10")
        if 8 in standing-down and rng.random()<.13: tags.append("stone_8")
        if 9 in standing-down and rng.random()<.13: tags.append("stone_9")
        if len(standing-down)==2 and {7,10} <= (standing-down): tags.append("pocket_7_10")
        if len(down)>=8 and abs(miss)>.55: tags.append("light_mixer")
    return down,tags

def roll_pins(rng,bowler,standing,lane='house',pressure=0.0,form=0.0,transition=0.0,
              lane_state=None,ball_key='hybrid',target_mode='strike'):
    standing=set(standing); ball=get_ball(ball_key)
    if lane_state is None:
        class Legacy: pass
        lane_state=Legacy();lane_state.pattern_key=lane;lane_state.oil={'fresh':.68,'house':.54,'dry':.30,'oily':.82,'transition':.46}.get(lane,.54);lane_state.transition=transition
    metrics=release_metrics(bowler,ball,lane_state,pressure)
    skill=(bowler.rank*.25+bowler.accuracy*.31+bowler.consistency*.17+bowler.spin*.14+bowler.nerves*.13)/50
    oil_fit=1-abs((.58+ball.hook*.16-ball.length*.12)-lane_state.oil)
    spare=standing!=ALL or target_mode=='spare'
    sigma=max(.13,1.08-(bowler.accuracy/50)*.58-(bowler.consistency/50)*.24-ball.control*.12)
    if spare and ball.spare_bias:sigma*=.72
    handed=-1 if str(bowler.handedness).upper().startswith('L') else 1
    miss=rng.gauss(0,sigma) - handed*((bowler.spin-25)/25)*.07*ball.hook
    pressure_mod=(bowler.nerves-25)/25*pressure*.09
    quality=max(0,min(1,.34+.48*skill+.12*oil_fit+pressure_mod+form-abs(miss)*.17+rng.gauss(0,.055)))
    if standing==ALL:
        strike_p=.018+.72*(quality**2.32)
        if rng.random()<strike_p:
            down=set(standing);down,tags=_special_carry(rng,standing,down,quality,miss,bowler.handedness)
            return down,quality,{"miss":miss,"ball":ball.key,"target":"pocket","metrics":metrics,"tags":tags}
    # Spares target a surviving pin/cluster, not the head-pin pocket.
    if spare:
        target=min(standing,key=lambda p:(abs(PINS[p][0]),PINS[p][1]))
    else: target=1
    down=set()
    for p in standing:
        dx=abs(PINS[p][0]-(PINS[target][0]+miss));depth=PINS[p][1]
        chance=max(.015,min(.98,quality*1.10-dx*(.18 if spare else .16)+(3-depth)*.022))
        if rng.random()<chance:down.add(p)
    if not down and rng.random()<quality:down.add(target)
    down,tags=_special_carry(rng,standing,down,quality,miss,bowler.handedness)
    return down,quality,{"miss":miss,"ball":ball.key,"target":target,"metrics":metrics,"tags":tags}
