from services.equipment import recommended_ball

def lane_adaptation(bowler,player,lane,spare=False):
 if spare:return {'ball':'plastic','boards':0,'reason':'spare targeting'}
 current=player.ball_key if player.ball_key!='auto' else recommended_ball(lane.oil)
 ball=current;move=0;reasons=[]
 outside=lane.outside;middle=lane.middle;inside=lane.inside
 # Right-handers normally chase transition left; mirror the move for left-handers.
 hand=-1 if str(bowler.handedness).upper().startswith('L') else 1
 read=(bowler.accuracy+bowler.consistency+bowler.style)/150
 if outside>=.34:
  move=hand*(1 if outside<.62 else 2);reasons.append('outside drying')
  if outside>=.48 and current in ('solid','hybrid'):ball='pearl'
 if middle>=.58:
  move=hand*2;reasons.append('track burning')
  if current=='solid':ball='hybrid'
 if lane.oil<=.30 or max(outside,middle)>=.78:
  ball='urethane';move=hand*2;reasons.append('lane severely transitioned')
 elif lane.oil>=.69 and max(outside,middle)<.25:
  ball='solid';reasons.append('fresh volume holding')
 # Poor lane readers adapt later; elite readers react earlier without receiving a scoring bonus.
 if read<.35 and max(outside,middle)<.55:return {'ball':current,'boards':0,'reason':'holding the current look'}
 return {'ball':ball,'boards':move,'reason':', '.join(dict.fromkeys(reasons)) or 'stable lane read'}
