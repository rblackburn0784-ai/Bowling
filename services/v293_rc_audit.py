"""Feature-frozen v2.9.3 release-candidate physics/replay stress gate.

Run: python -m services.v293_rc_audit [games_per_setting] [output_json_path]
No Discord, database, private artwork or network access required.
"""
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

from models.bowler import Bowler
from services.game_engine import GameSession
from services.pin_engine import ALL
from services.scoring import score_game
from services.v25 import session_dict,session_from_dict
from services.equipment import get_ball
from services.impact_model import impact_geometry
from services.lane_physics import LaneState

LANES=('house','fresh','oily','dry','transition')
SKILLS=(8,20,35,50)

def mk_bowler(ident, skill, hand):
    return Bowler(id=ident,name=f'Stress {ident}',owner_id=ident,
                  handedness=hand,accuracy=skill,consistency=skill,
                  spin=skill,nerves=skill,style=skill,flair=skill)

def run(games_per_setting=500,seed=293000,verbose=False):
    report={};n=0;deliveries=0;illegal=0;replays=0
    all_strikes=all_spares=all_splits=all_splits_converted=0
    for level in SKILLS:
        total_scores=[];by_lane={}
        for li,lane in enumerate(LANES):
            scores=[];strikes=spares=splits=converted=0
            for k in range(games_per_setting):
                serial=seed+level*1_000_000+li*100_000+k
                s=GameSession([mk_bowler(1,level,'R' if k%2==0 else 'L')],
                              seed=serial,lane=lane)
                restore=None
                count=0
                while not s.complete:
                    # Deterministic replay after a mid-game crash every 200th
                    # match: no changes to scores, state or future physics RNG.
                    if k%200==0 and count==4:
                        restore=session_from_dict(session_dict(s))
                        replays+=1
                    event=s.bowl();count+=1
                    before=set(event['before']);down=set(event['down'])
                    after=set(event['after']);order=event['physics']['contact_order']
                    assert before<=ALL and down<=before and before-down==after
                    assert len(down)==event['pins']
                    assert set(order)==down and len(order)==len(set(order))
                    assert count<=21
                    phys=event['physics']
                    assert 0<=phys['carry_factor']<=1.05
                    assert -4.2<=phys['impact_x']<=4.2
                    assert -1<=phys['deflection']<=1
                    if restore is not None:
                        other=restore.bowl()
                        assert event==other, ('Replay divergence',serial,event,other)
                    # Counting delivery strikes excludes tenth-frame spares.
                    if event['pins']==10 and event['ball']==1:
                        strikes+=1
                    if event['spare']:spares+=1
                    if event['split']:splits+=1
                    if event['split_conversion']:converted+=1
                score=score_game(s.players[0].frames)
                assert 0<=score<=300
                assert list(s.scores().values())==[score]
                if restore is not None:
                    assert s.scores()==restore.scores()
                    assert s.rng.getstate()==restore.rng.getstate()
                n+=1;deliveries+=count;scores.append(score)
            by_lane[lane]={'average':round(statistics.mean(scores),2),
                          'high':max(scores),'low':min(scores),
                          'strikes':strikes,'spares':spares,
                          'splits':splits,'split_conversions':converted}
            total_scores+=scores
            all_strikes+=strikes;all_spares+=spares;all_splits+=splits;all_splits_converted+=converted
        by_lane['overall_average']=round(statistics.mean(total_scores),2)
        report[str(level)]=by_lane
    avgs=[report[str(s)]['overall_average'] for s in SKILLS]
    assert avgs==sorted(avgs),('Skill ordering failure',avgs)
    assert 30<avgs[0]<90 and 140<avgs[-1]<230,('Bad balance envelope',avgs)
    # Oil effects are deterministic in the contact model, but estimates of
    # per-lane average score need enough samples to reject random noise.
    # The short CI gate must not be flaky when only 100 games are played.
    metrics={'entry_angle':4.7,'speed':16.2,'revs':350}
    ball=get_ball('hybrid')
    dry=impact_geometry(0,metrics,ball,LaneState(3,'dry'),1)
    wet=impact_geometry(0,metrics,ball,LaneState(3,'oily'),1)
    assert dry['impact_x']!=wet['impact_x'], 'Oil no longer changes impact'
    if games_per_setting>=500:
        assert any(abs(report[str(skill)]['house']['average']-
                       report[str(skill)]['oily']['average'])>2
                   for skill in SKILLS), 'No measurable lane contrast'
    result={'version':'2.9.3-rc','base':'2.9.2','status':'PASS',
            'sessions':n,'deliveries':deliveries,'snapshot_replays':replays,
            'seed':seed,'games_per_setting':games_per_setting,
            'lane_patterns':list(LANES),'stat_levels':list(SKILLS),
            'strike_deliveries':all_strikes,'spare_conversions':all_spares,
            'split_leaves':all_splits,'split_conversions':all_splits_converted,
            'mean_score_by_skill':dict(zip(map(str,SKILLS),avgs)),
            'detail':report}
    if verbose:print(json.dumps(result,indent=2))
    return result

if __name__=='__main__':
    count=int(sys.argv[1]) if len(sys.argv)>1 else 500
    result=run(count,verbose=True)
    if len(sys.argv)>2:Path(sys.argv[2]).write_text(json.dumps(result,indent=2)+'\n')
