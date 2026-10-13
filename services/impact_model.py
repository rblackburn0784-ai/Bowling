"""v2.9.0 Living Lanes: deterministic, physics-informed lane-to-pin contact.

This is intentionally a *reproducible game model*, not a rigid-body simulator.
The engine owns all random draws. Rendering only reads the resulting event.
Pin x coordinates use adjacent-pin spacing units; positive is camera-right.
"""
from math import exp


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def spare_target(standing, positions, handedness='R'):
    """Choose the first reachable pin, rather than arbitrarily aiming at 1.

    Frontmost pins have the smallest row index. On equally near pins the
    preferred side is mirrored for left- and right-handed players. This
    also gives deterministic targets for difficult split conversions.
    """
    hand = -1 if str(handedness).upper().startswith('L') else 1
    return min(standing, key=lambda pin:(positions[pin][1], abs(positions[pin][0]),
                                         -hand*positions[pin][0], pin))


def impact_geometry(miss, metrics, ball, lane, hand, line_boards=0, *,
                    spare=False, target_x=0.0):
    """Where the ball enters the rack given oil, line, hook and release.

    All returns are in normalized pin-spacing units. Board moves change
    the point of impact directly, not merely lane wear. Spare deliveries
    use a plastic ball and aim at the standing pin, not the strike pocket.
    """
    oil = clamp(float(getattr(lane,'oil',.54)),.0,1.0)
    transition = clamp(float(getattr(lane,'transition',0.0)),0.0,1.0)
    hook = clamp(float(ball.hook),0.,1.3)
    zone = getattr(lane,'outside',0.0) if abs(line_boards)>=2 else getattr(lane,'middle',0.0)
    oil_bias = hand * ((.54-oil)*.32 + transition*.10 + zone*.17)*hook
    # RH movement to the left compensates for premature hook on a burnt
    # track; LH movement is mirrored by lane_adaptation's signed boards.
    line_correction = -float(line_boards)*.105*(.4+.6*hook)
    release_error = float(miss)*(.72 if not spare else .87)
    pocket = 0.0 if spare else hand*.46
    impact_x = clamp(target_x + pocket + release_error + oil_bias + line_correction,-4.2,4.2)
    entry_angle = float(metrics.get('entry_angle',4.0))
    speed = float(metrics.get('speed',16.0))
    revs = float(metrics.get('revs',300.0))
    # Entry direction drives the lateral path *through* the pin deck;
    # rear pins see a different impact x after the ball deflects.
    deflection = hand * clamp((entry_angle-3.5)*.075 + (revs-250)*.00022,-.22,.40)
    # A good angle/speed combination carries through the back rack.
    angle_fit = clamp(1.-abs(entry_angle-4.7)/9.5,.35,1.)
    speed_fit = clamp(1.-abs(speed-16.3)/10.,.48,1.)
    rev_fit = clamp(.65 + revs/1250.,.60,1.05)
    carry = clamp((.56*angle_fit+.26*speed_fit+.18*rev_fit),.4,1.05)
    return {'impact_x':round(impact_x,5), 'pocket_x':round(target_x+pocket,5),
            'oil_bias':round(oil_bias,5), 'line_correction':round(line_correction,5),
            'angle_fit':round(angle_fit,5),'speed_fit':round(speed_fit,5),
            'carry_factor':round(carry,5),
            'deflection':round(deflection,5)}


def pinfall(rng, standing, positions, quality, geometry, *, spare=False, power_carry=False):
    """Contact-first pinfall with front-to-back energy transfer and deflection.

    A pin falls through ball contact or a nearby falling pin, not an
    unconnected global lottery. A very small residual chance represents a
    chaotic secondary rebound from pins outside the simplified 2D model.
    `power_carry` denotes an excellent pocket impact, not a forced strike;
    even these deliveries must knock down the head pin and propagate through
    the rack to clear ten pins. In particular this avoids unearned teleported
    corner pins and makes a 7–10 conversion appropriately difficult.
    """
    impact_x=float(geometry['impact_x'])
    carry=float(geometry['carry_factor'])
    deflection=float(geometry.get('deflection',0))
    knocked=set()
    order=sorted(standing,key=lambda p:(positions[p][1],
                                         abs(positions[p][0]-impact_x),p))
    for pin in order:
        x,depth=positions[pin]
        # Ball path bends and deflects laterally across the rack.
        path_x=impact_x+depth*deflection
        distance=abs(x-path_x)
        contact_radius=(1.08+depth*.11) if not spare else (1.02+depth*.06)
        direct=exp(-.5*(distance/contact_radius)**2)
        # Each actual predecessor can transfer impact energy one or two rows
        # backwards through neighbours; transfer does not cross isolated splits.
        predecessors=[other for other in knocked
                      if 0<depth-positions[other][1]<=2
                      and abs(x-positions[other][0])<=1.50]
        cascade=clamp(sum(.36 if depth-positions[q][1]==1 else .10
                          for q in predecessors)*carry,0.,.68)
        ball_touch=distance<=contact_radius*1.32
        connected=ball_touch or bool(predecessors)
        if not connected:
            chance=.003  # rare secondary ricochet, never a blanket strike
        else:
            ball_energy=(.18+.89*quality)*carry*direct
            chance=.025+ball_energy+(.28+.26*quality)*cascade
            if power_carry and not spare:
                # Pocket carry energises *reachable* pins only. Far pin
                # survival still depends on the actual advancing cascade.
                chance=max(chance,.965 if predecessors else .958*direct)
        chance=clamp(chance,.003,.985)
        if rng.random()<chance:knocked.add(pin)
    return knocked,sorted(knocked,key=lambda p:(positions[p][1],
                        abs(positions[p][0]-impact_x),p))
