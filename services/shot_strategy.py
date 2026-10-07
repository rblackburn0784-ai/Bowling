from dataclasses import dataclass

@dataclass(frozen=True,slots=True)
class ShotIntent:
 key:str;name:str;control:float=0.0;variance:float=1.0;carry:float=0.0;quality:float=0.0;hook:float=1.0

INTENTS={
 'normal':ShotIntent('normal','Normal'),
 'safe':ShotIntent('safe','Safe',control=.08,variance=.82,carry=-.055,quality=.015,hook=.92),
 'aggressive':ShotIntent('aggressive','Aggressive',control=-.04,variance=1.20,carry=.075,quality=.01,hook=1.12),
 'recovery':ShotIntent('recovery','Recovery',control=.11,variance=.76,carry=-.09,quality=.02,hook=.78),
 'spare':ShotIntent('spare','Spare',control=.14,variance=.68,carry=-.12,quality=.025,hook=.35),
}

def get_intent(key):
 return INTENTS.get((key or 'normal').lower(),INTENTS['normal'])

def auto_intent(bowler,standing,lane,pressure=0.0):
 if len(standing)<10:return 'spare'
 a=bowler.accuracy;c=bowler.consistency;sp=bowler.spin;n=bowler.nerves;sty=bowler.style
 # Protect control when the lane is burnt/volatile or the bowler is under pressure.
 if lane.transition>=.62 and (a+c)>=32:return 'safe'
 if pressure>=.65 and n<16:return 'safe'
 # Skilled shot-makers can chase carry when the lane is readable.
 if .30<=lane.oil<=.68 and lane.transition<.48 and sp+sty>=38 and a>=12:return 'aggressive'
 if lane.transition>=.78 or (lane.oil<=.25 and sp>=20):return 'recovery'
 return 'normal'
