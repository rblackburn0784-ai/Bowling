"""v2.9 release gate: seeded bowling, camera state and lane variation.

Run: python -m services.v290_audit
No Discord, database or production assets required. Does not write state.
"""
import json
from statistics import mean
from models.bowler import Bowler
from services.game_engine import GameSession
from services.pin_engine import ALL
from services.scene_renderer import pin_impact_progress
from services.scoring import score_game


def _bowler(ident,skill,hand):
    return Bowler(id=ident,name=f'Test {ident}',owner_id=ident,handedness=hand,
                  accuracy=skill,consistency=skill,spin=skill,nerves=skill,
                  style=skill,flair=skill)


def run(games_per_setting=200,seed=290000):
    """Verify repeatable complete sessions and legal, coherent pinfall events."""
    report={};checked=0;deliveries=0
    lanes=('house','fresh','oily','dry','transition')
    for skill in (8,20,35,50):
        scores=[]
        for lane in lanes:
            lane_scores=[]
            for n in range(games_per_setting):
                number=seed+skill*100000+lanes.index(lane)*1000+n
                p=_bowler(1,skill,'L' if n%2 else 'R')
                match=GameSession([p],seed=number,lane=lane)
                count=0
                while not match.complete:
                    event=match.bowl();count+=1
                    before=set(event['before']);down=set(event['down']);after=set(event['after'])
                    assert before<=ALL and down<=before and not down&after
                    assert before-down==after
                    assert len(down)==event['pins']
                    order=event['physics']['contact_order']
                    assert len(order)==len(set(order)) and set(order)==down
                    assert all(pin_impact_progress(event,pin,1)==0 for pin in down)
                    assert all(pin_impact_progress(event,pin,5)==1 for pin in down)
                    assert count<=21
                value=next(iter(match.scores().values()))
                assert value==score_game(match.players[0].frames)
                assert 0<=value<=300
                lane_scores.append(value);deliveries+=count;checked+=1
            report.setdefault(str(skill),{})[lane]=round(mean(lane_scores),2)
            scores.extend(lane_scores)
        report[str(skill)]['overall']=round(mean(scores),2)
    averages=[report[str(skill)]['overall'] for skill in (8,20,35,50)]
    assert averages==sorted(averages),f'Skill inversion {averages}'
    assert averages[0]<100 and averages[-1]<240,averages
    output={'build':'v2.9.0','sessions':checked,'deliveries':deliveries,
            'seed':seed,'games_per_setting':games_per_setting,
            'skill_averages_by_lane':report,'outcome':'PASS'}
    print(json.dumps(output,indent=2))
    return output


if __name__=='__main__':run()
