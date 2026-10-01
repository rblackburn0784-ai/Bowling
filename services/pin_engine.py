import math
PINS={1:(0,0),2:(-1,1),3:(1,1),4:(-2,2),5:(0,2),6:(2,2),7:(-3,3),8:(-1,3),9:(1,3),10:(3,3)}
ALL=set(PINS)

def is_split(standing):
    s=set(standing)
    if 1 in s or len(s)<2:return False
    # Practical split approximation: separated survivors with a missing connector.
    xs=sorted(PINS[p][0] for p in s)
    return any(b-a>=2 for a,b in zip(xs,xs[1:]))

def roll_pins(rng,bowler,standing,lane='house',pressure=0.0,form=0.0,transition=0.0):
    standing=set(standing)
    lane_mod={'fresh':0.03,'house':0.0,'dry':-0.015,'oily':-0.025,'transition':-0.02}.get(lane,0)
    # Oil breaks down as traffic builds; spin can help read transition but can also overreact on dry boards.
    transition_penalty=transition*(0.055-max(0,bowler.spin-25)/25*0.025)
    lane_mod-=transition_penalty
    skill=(bowler.rank*.26+bowler.accuracy*.32+bowler.consistency*.16+bowler.spin*.14+bowler.nerves*.12)/50
    nerves=(bowler.nerves-25)/25*pressure*.10
    sigma=max(.18,1.15-(bowler.accuracy/50)*.62-(bowler.consistency/50)*.22)
    miss=rng.gauss(0,sigma)-((bowler.spin-25)/25)*.08
    quality=max(0,min(1,.38+.54*skill+lane_mod+nerves+form-abs(miss)*.16+rng.gauss(0,.07)))
    if standing==ALL:
        strike_p=.02+.73*(quality**2.25)
        if rng.random()<strike_p:return set(standing),quality
    target=1 if 1 in standing else min(standing,key=lambda p:abs(PINS[p][0]-miss))
    down=set()
    for p in standing:
        dx=abs(PINS[p][0]-(PINS[target][0]+miss)); depth=PINS[p][1]
        chance=max(.02,min(.97,quality*1.08-dx*.17+(3-depth)*.025))
        if rng.random()<chance:down.add(p)
    if not down and rng.random()<quality: down.add(target)
    return down,quality
