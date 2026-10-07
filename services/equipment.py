from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class BallProfile:
    key: str
    name: str
    hook: float
    length: float
    control: float
    spare_bias: float = 0.0

BALLS = {
    "solid": BallProfile("solid","Solid Reactive",1.00,0.35,0.72),
    "pearl": BallProfile("pearl","Pearl Reactive",0.78,0.82,0.58),
    "hybrid": BallProfile("hybrid","Hybrid Reactive",0.88,0.62,0.72),
    "urethane": BallProfile("urethane","Urethane",0.58,0.42,0.92),
    "plastic": BallProfile("plastic","Plastic",0.10,0.95,0.98,1.0),
}

def get_ball(key: str | None):
    return BALLS.get((key or "hybrid").lower(), BALLS["hybrid"])

def recommended_ball(oil: float, spare: bool=False):
    if spare:
        return "plastic"
    if oil >= .68:
        return "solid"
    if oil <= .34:
        return "urethane"
    return "hybrid"
