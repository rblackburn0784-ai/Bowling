"""v2.9.6 — Bowling Physics & Intelligence.

Fresh sessions use this physics model; earlier saved sessions retain their
frozen versions. Rendering and replays never call this module.
"""
import math
from services.equipment import get_ball
from services.impact_model import clamp, impact_geometry, pinfall, spare_target
from services.lane_physics import PATTERNS, release_metrics
from services.pin_engine import ALL, PINS, _special_carry
from services.shot_strategy import get_intent

def _stats(bowler):
    return {k: clamp(float(getattr(bowler,k,15)),1.,50.) / 50. for k in
            ('accuracy','consistency','spin','nerves','style','flair')}

def lane_read(lane, ball, handedness='R', line_boards=0):
    """Deterministic lane read; no randomness or game-state changes."""
    pat=PATTERNS.get(getattr(lane,'pattern_key','house'),PATTERNS['house'])
    oil=clamp(float(getattr(lane,'oil',pat['volume'])),.12,1.)
    transition=clamp(float(getattr(lane,'transition',0)),0.,1.)
    carrydown=clamp(float(getattr(lane,'carrydown',0)),0.,1.)
    zone='outside' if abs(line_boards)>=2 else 'inside' if abs(line_boards)<.5 else 'middle'
    zone_burn=clamp(float(getattr(lane,zone,0)),0.,1.)
    forgiveness=clamp((float(pat['ratio'])-2.)/7.,.1,1.)
    target_oil=clamp(.47+ball.hook*.18-ball.length*.10,.30,.70)
    oil_fit=clamp(1.0-abs(oil-target_oil)*.74,.56,1.)
    transition_penalty=clamp(transition*.11+zone_burn*.12+carrydown*.065,0,.24)
    return {'oil':oil,'transition':transition,'carrydown':carrydown,
            'zone':zone,'zone_burn':zone_burn,'pattern':pat['name'],
            'forgiveness':forgiveness,'oil_fit':oil_fit,
            'transition_penalty':transition_penalty}

def choose_spare_target(standing, handedness='R'):
    pins=set(standing)
    if not pins:
        return 1,0.,False
    target=spare_target(pins,PINS,handedness)
    if len(pins)==2:
        first,second=sorted(pins)
        x1,y1=PINS[first];x2,y2=PINS[second]
        if y1==y2 and abs(x1-x2)<=2:
            return target,(x1+x2)/2.,True
    return target,float(PINS[target][0]),False

def roll_pins(rng,bowler,standing,lane='house',pressure=0.0,form=0.0,
              transition=0.0,lane_state=None,ball_key='hybrid',
              target_mode='strike',shot_intent='normal',line_boards=0):
    """Return down, quality, metadata; matches the legacy pinfall API."""
    standing=set(standing)
    if not standing:
        return set(),0.,{'contact_order':[],'tags':[],'miss':0.,'intent':'spare'}
    if lane_state is None:
        from services.lane_physics import LaneState
        lane_state=LaneState(3,lane)
        lane_state.track=clamp(float(transition),0.,1.)
    ball=get_ball(ball_key)
    spare=(standing!=ALL or target_mode=='spare')
    intent=get_intent('spare' if spare else shot_intent)
    skills=_stats(bowler)
    hand=-1 if str(bowler.handedness).upper().startswith('L') else 1
    read=lane_read(lane_state,ball,bowler.handedness,line_boards)
    metrics=release_metrics(bowler,ball,lane_state,pressure,intent.key,line_boards)
    breakpoint=metrics['breakpoint']+read['carrydown']*.9-read['zone_burn']*.85
    metrics['breakpoint']=round(clamp(breakpoint,31.,48.),2)
    entry=metrics['entry_angle']+(read['zone_burn']-read['carrydown'])*.35*ball.hook
    metrics['entry_angle']=round(clamp(entry,1.0,8.5),2)
    spread=(.87-.31*skills['accuracy']-.20*skills['consistency']
            -.065*ball.control)*intent.variance
    spread*=1.+read['transition_penalty']*.6+(1.-read['forgiveness'])*.16
    spread=clamp(spread,.20,1.0)
    miss=hand*rng.gauss(0.,spread)
    miss-=hand*(skills['spin']-.5)*.075*ball.hook
    pressure_mod=(skills['nerves']-.5)*pressure*.095
    weighted=(skills['accuracy']*.23+skills['consistency']*.22+
              skills['spin']*.16+skills['nerves']*.16+
              skills['style']*.13+skills['flair']*.10)
    rank_bonus=clamp(float(getattr(bowler,'rank',1)),1,100)*.00024
    quality=clamp(.30+.46*weighted+.13*read['oil_fit']
                  -read['transition_penalty']*.43
                  +pressure_mod+rank_bonus+intent.quality
                  +clamp(float(form),-.03,.03)*(.7+skills['flair']*.3)
                  -abs(miss)*.14+rng.gauss(0,.044+(1-skills['consistency'])*.018),0.,1.)
    aim,target_x,gap=choose_spare_target(standing,bowler.handedness) if spare else (1,0.,False)
    geometry=impact_geometry(miss,metrics,ball,lane_state,hand,line_boards,
                             spare=spare,target_x=target_x)
    travel=(40.-metrics['breakpoint'])/40.
    shape=hand*clamp(travel*skills['spin']*ball.hook*.13,-.08,.08)
    geometry['impact_x']=round(clamp(geometry['impact_x']+shape,-4.2,4.2),5)
    geometry['deflection']=round(clamp(geometry['deflection']+shape*.12,-.28,.46),5)
    pocket_error=abs(geometry['impact_x']-geometry['pocket_x'])
    pocket=math.exp(-.5*(pocket_error/(.78+.16*read['forgiveness']))**2)
    strike_chance=clamp((.014+1.07*quality**2.1+
                         intent.carry*(.55+skills['style']*.21+skills['flair']*.20))
                        *pocket*geometry['carry_factor']
                        *(.89+.11*read['forgiveness']),.001,.78)
    power=bool(standing==ALL and not spare and rng.random()<strike_chance)
    down,contact=pinfall(rng,standing,PINS,quality,geometry,spare=spare,
                         power_carry=power)
    down,tags=_special_carry(rng,standing,down,quality,miss,bowler,spare)
    detail=dict(geometry,miss=miss,ball=ball.key,
                target=aim if spare else 'pocket',metrics=metrics,tags=tags,
                intent=intent.key,contact_order=contact,
                strike_chance=round(strike_chance,5) if not spare else 0.,
                power_carry=power,aim_pin=aim,aim_gap=gap,
                lane_read=read,physics_version='2.9.6')
    return down,quality,detail
