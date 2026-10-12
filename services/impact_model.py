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
    # A good angle/speed combination carries through the back rack.
    angle_fit = clamp(1.-abs(entry_angle-4.7)/9.5,.35,1.)
    speed_fit = clamp(1.-abs(speed-16.3)/10.,.48,1.)
    rev_fit = clamp(.65 + revs/1250.,.60,1.05)
    carry = clamp((.56*angle_fit+.26*speed_fit+.18*rev_fit),.4,1.05)
    return {'impact_x':round(impact_x,5), 'pocket_x':round(target_x+pocket,5),
            'oil_bias':round(oil_bias,5), 'line_correction':round(line_correction,5),
            'angle_fit':round(angle_fit,5),'speed_fit':round(speed_fit,5),
            'carry_factor':round(carry,5)}


def pinfall(rng, standing, positions, quality, geometry, *, spare=False):
    """Front-to-back contact and transfer: every pin is a legal standing pin.

    The impact point influences direct contact. Pins that fall can transfer
    energy to neighbours one rack row behind, which makes entry/carry
    meaningful and produces believable spare leaves without teleporting pins.
    """
    impact_x=geometry['impact_x'];carry=geometry['carry_factor']
    knocked=set()
    # The chronological pin order is also the authoritative animation order.
    order=sorted(standing,key=lambda p:(positions[p][1],abs(positions[p][0]-impact_x),p))
    for pin in order:
        x,depth=positions[pin]
        distance=abs(x-impact_x)
        # Width grows slightly downlane due to deflection and mixing.
        width=(1.25+depth*.55) if not spare else (.96+depth*.44)
        direct=exp(-.5*(distance/width)**2)
        nearby=sum(1 for fallen in knocked if
                   0 < depth-positions[fallen][1]<=2 and
                   abs(x-positions[fallen][0])<=1.65)
        transfer=min(.25,nearby*.082*carry)
        base=(.045+quality*(.46+.34*direct)*carry+transfer
              -max(0,distance-width)*.028)
        chance=clamp(base,.006,.968)
        if rng.random()<chance:
            knocked.add(pin)
    # Weak direct contact can still clip a pin instead of magically leaving
    # a perfect gutter-to-zero-pin shot every time.
    if not knocked and standing and rng.random()<quality*.30:
        nearest=min(standing,key=lambda pin:abs(positions[pin][0]-impact_x)
                    + .12*positions[pin][1])
        knocked.add(nearest)
    return knocked, sorted(knocked,key=lambda p:(positions[p][1],
                                                  abs(positions[p][0]-impact_x),p))
