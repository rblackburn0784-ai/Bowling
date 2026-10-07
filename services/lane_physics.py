from dataclasses import dataclass, field

PATTERNS = {
    "house": {"name":"House 40'","length":40,"volume":.54,"ratio":8.0},
    "fresh": {"name":"Fresh House 41'","length":41,"volume":.68,"ratio":7.0},
    "oily": {"name":"Neon Flood 44'","length":44,"volume":.82,"ratio":4.0},
    "dry": {"name":"Burnt Saints 37'","length":37,"volume":.30,"ratio":6.0},
    "transition": {"name":"Transition 40'","length":40,"volume":.46,"ratio":5.0},
}

@dataclass
class LaneState:
    number: int
    pattern_key: str = "house"
    traffic: int = 0
    oil: float = .54
    track: float = 0.0
    def __post_init__(self):
        self.oil = PATTERNS.get(self.pattern_key,PATTERNS["house"])["volume"]
    @property
    def transition(self):
        return min(1.0, self.track)
    def apply_shot(self, hook: float, boards: float):
        self.traffic += 1
        burn=(.0042 + hook*.0022) * (1.0 + min(1.0,abs(boards)/10)*.18)
        self.track=min(1.0,self.track+burn)
        self.oil=max(.12,self.oil-burn*.52)

@dataclass
class LanePair:
    left: LaneState
    right: LaneState
    next_side: dict = field(default_factory=dict)
    @classmethod
    def create(cls, start_lane=3, pattern="house"):
        return cls(LaneState(start_lane,pattern),LaneState(start_lane+1,pattern))
    def lane_for(self,bowler_id):
        side=self.next_side.get(bowler_id,0)
        lane=self.left if side==0 else self.right
        self.next_side[bowler_id]=1-side
        return lane

def release_metrics(bowler, ball, lane, pressure=0.0,intent=None):
    from services.shot_strategy import get_intent
    intent=get_intent(intent);accuracy=max(0,min(50,bowler.accuracy)); spin=max(0,min(50,bowler.spin))
    consistency=max(0,min(50,bowler.consistency)); nerves=max(0,min(50,bowler.nerves))
    speed=15.0 + (bowler.accuracy/50)*1.1 + (bowler.consistency/50)*.7 - (spin/50)*.55
    speed+= {'safe':-.25,'aggressive':.45,'recovery':-.55,'spare':.15}.get(intent.key,0)
    revs=(205 + spin*7.2 + bowler.style*1.25)*intent.hook
    breakpoint=PATTERNS.get(lane.pattern_key,PATTERNS["house"])["length"] + (ball.length-.5)*3.8
    breakpoint-= lane.transition*2.1
    entry=3.0 + (spin/50)*3.1*ball.hook - lane.oil*.65 + lane.transition*.75
    control=.50 + accuracy/100 + consistency/180 + (nerves-25)/250*pressure + intent.control
    return {"speed":round(speed,1),"revs":int(revs),"entry_angle":round(entry,1),
            "breakpoint":round(breakpoint,1),"control":max(.15,min(.98,control))}
