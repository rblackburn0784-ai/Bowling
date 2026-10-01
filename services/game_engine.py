import random
from dataclasses import dataclass,field
from services.pin_engine import ALL,roll_pins,is_split
from services.scoring import score_game,frame_notation
from services.analytics import named_leave

@dataclass
class BowlerGame:
    bowler: object
    frames:list=field(default_factory=list)
    standing:set=field(default_factory=lambda:set(ALL))
    frame:int=1; ball:int=1; split_leave:bool=False
    split_frames:set=field(default_factory=set); split_conversions:set=field(default_factory=set)
    strike_streak:int=0; max_strike_streak:int=0; form:float=0.0; special_conversions:set=field(default_factory=set)
    @property
    def complete(self):return self.frame>10

class GameSession:
    def __init__(self,bowlers,seed=None,lane='house',tournament_id=None,match_id=None):
        self.seed=seed if seed is not None else random.SystemRandom().randrange(1,2**31)
        self.rng=random.Random(self.seed);self.lane=lane;self.players=[BowlerGame(b) for b in bowlers];self.turn=0
        self.tournament_id=tournament_id;self.match_id=match_id;self.persisted=False;self.ball_count=0
    def current(self):return self.players[self.turn]
    def bowl(self):
        p=self.current();before=set(p.standing);frame_no=p.frame;ball_no=p.ball
        pressure=max(0,(p.frame-7)/3) if p.frame<=10 else 1
        transition=min(1.0,self.ball_count/90.0); down,q=roll_pins(self.rng,p.bowler,before,self.lane,pressure,p.form,transition); self.ball_count+=1;p.standing-=down;pins=len(down)
        delta=0.006 if pins==10 else (-0.004 if pins<=6 else 0.001)
        p.form=max(-0.025,min(0.025,p.form*0.82+delta))
        if len(p.frames)<p.frame:p.frames.append([])
        f=p.frames[p.frame-1];f.append(pins)
        ev={'bowler':p.bowler.name,'bowler_id':p.bowler.id,'frame':frame_no,'ball':ball_no,'pins':pins,'before':sorted(before),'down':sorted(down),'after':sorted(p.standing),'quality':q,'split':False,'spare':False,'split_conversion':False}
        if frame_no<10:
            if ball_no==1 and pins==10:
                p.strike_streak+=1;p.max_strike_streak=max(p.max_strike_streak,p.strike_streak);ev['strike_streak']=p.strike_streak;self._advance(p)
            elif ball_no==1:
                p.strike_streak=0;p.split_leave=is_split(p.standing);ev['split']=p.split_leave
                if p.split_leave:p.split_frames.add(frame_no);ev['leave_name']=named_leave(p.standing) or 'Split'
                p.ball=2
            else:
                ev['spare']=sum(f[:2])==10
                if ev['spare'] and frame_no in p.split_frames:p.split_conversions.add(frame_no);ev['split_conversion']=True;ev['split_name']=named_leave(before) or 'Split';p.special_conversions.add(ev['split_name'])
                self._advance(p)
        else:self._tenth(p,f,pins,ev,before)
        self._rivalry(ev,p);self._next_active();return ev
    def _advance(self,p):p.frame+=1;p.ball=1;p.standing=set(ALL);p.split_leave=False
    def _tenth(self,p,f,pins,ev,before):
        if pins==10:
            p.strike_streak+=1;p.max_strike_streak=max(p.max_strike_streak,p.strike_streak);ev['strike_streak']=p.strike_streak
        elif len(f)==1:p.strike_streak=0
        if len(f)==1:
            if pins==10:p.standing=set(ALL)
            else:
                p.split_leave=is_split(p.standing);ev['split']=p.split_leave
                if p.split_leave:p.split_frames.add(10);ev['leave_name']=named_leave(p.standing) or 'Split'
                p.ball=2
        elif len(f)==2:
            if f[0]==10:
                if pins==10:p.standing=set(ALL)
                p.ball=3
            elif sum(f[:2])==10:
                ev['spare']=True
                if 10 in p.split_frames:p.split_conversions.add(10);ev['split_conversion']=True;ev['split_name']=named_leave(before) or 'Split';p.special_conversions.add(ev['split_name'])
                p.standing=set(ALL);p.ball=3
            else:self._advance(p)
        else:self._advance(p)
    def _rivalry(self,ev,p):
        team=getattr(p.bowler,'team_name',None)
        if not team or not (ev.get('strike_streak') or ev.get('split_conversion')):return
        rivals=[x for x in self.players if getattr(x.bowler,'team_name',None) not in (None,team)]
        if rivals:
            r=max(rivals,key=lambda x:x.max_strike_streak)
            if r.max_strike_streak>=2:ev['rivalry']=(p.bowler.name,r.bowler.name)
    def _next_active(self):
        if all(x.complete for x in self.players):return
        for _ in self.players:
            self.turn=(self.turn+1)%len(self.players)
            if not self.players[self.turn].complete:return
    @property
    def complete(self):return all(p.complete for p in self.players)
    def scores(self):return {p.bowler.name:score_game(p.frames) for p in self.players if p.complete}
    def card(self):return {p.bowler.name:[frame_notation(f) for f in p.frames] for p in self.players}
    def team_totals(self):
        out={}
        for p in self.players:
            t=getattr(p.bowler,'team_name',None)
            if t and p.complete:out[t]=out.get(t,0)+score_game(p.frames)
        return out
