"""Independent conventional-tenpin score oracle and second-ball stress gates.

USBC / IBF scoring:
- 10 frames; strikes + next two balls; spares + next one.
- Fresh rack only after a strike (including tenth) or tenth-frame spare fill.
- Second ball preserves the same player, lane and remaining pins.
- Exactly the same event must drive both GIF and graphical pin views.

Tests use a new oracle rather than calling score_game to compute expectations.
"""
import random
import unittest
from unittest.mock import patch
from models.bowler import Bowler
from services.scoring import score_game, frame_notation
from services.game_engine import GameSession
from services.pin_engine import ALL
from services.analytics import frame_flags
from services.shot_animation import ANIMATION_SEQUENCE
from services import scene_renderer as scene


def independent_oracle(frames):
    assert len(frames)==10
    scores=[]
    for n,frame in enumerate(frames):
        future=[pins for later in frames[n+1:] for pins in later]
        if frame[0]==10:
            bonus=(frame[1:] if n==9 else future)[:2]
            assert len(bonus)==2
            scores.append(10+bonus[0]+bonus[1])
        elif frame[0]+frame[1]==10:
            bonus=frame[2] if n==9 else future[0]
            scores.append(10+bonus)
        else:
            scores.append(sum(frame[:2]))
    return sum(scores)


def legal_random_card(rng):
    result=[]
    for _ in range(9):
        first=rng.randrange(11)
        result.append([10] if first==10 else [first,rng.randrange(11-first)])
    first=rng.randrange(11)
    if first==10:
        second=rng.randrange(11)
        third=rng.randrange(11) if second==10 else rng.randrange(11-second)
        result.append([first,second,third])
    else:
        second=rng.randrange(11-first)
        result.append([first,second,rng.randrange(11)] if first+second==10
                      else [first,second])
    return result


def bowler(number,hand='R'):
    return Bowler(id=number,name=f'Stress {number}',owner_id=number,
                  handedness=hand,accuracy=20,consistency=20,spin=15,
                  nerves=20,style=15,flair=10)


class IndependentScoringOracle(unittest.TestCase):
    def test_thirty_thousand_legal_cards_match_independent_oracle(self):
        rng=random.Random(20261015)
        for k in range(30000):
            frames=legal_random_card(rng)
            actual=score_game(frames)
            reference=independent_oracle(frames)
            self.assertEqual(actual,reference,('card',k,frames))
            self.assertTrue(0<=actual<=300)
            self.assertEqual(len(frames),10)

    def test_tenth_bonus_racks_and_symbols(self):
        examples=[
          ([10,10,10],30,'XXX'),([10,10,0],20,'XX-'),
          ([10,7,3],20,'X7/'),([10,0,10],20,'X-/'),
          ([9,1,10],20,'9/X'),([0,10,0],10,'-/ -'.replace(' ','')),
          ([0,0],0,'--'),([9,0],9,'9-'),
        ]
        for tenth,points,label in examples:
            with self.subTest(tenth=tenth):
                card=[[0,0] for _ in range(9)]+[tenth]
                self.assertEqual(score_game(card),points)
                self.assertEqual(frame_notation(tenth),label)

    def test_illegal_extra_tenth_delivery_is_rejected(self):
        illegal=[10,10,10,0]
        with self.assertRaises(ValueError):
            score_game([[0,0] for _ in range(9)]+[illegal])


class RealPhysicsSecondBallStress(unittest.TestCase):
    def test_two_player_first_and_second_shots_preserve_rack_and_lane(self):
        # Every delivery uses REAL current physics and RNG, never mocked pinfall.
        examined=0
        for seed in range(1,111):
            session=GameSession([bowler(1),bowler(2,'L')],seed=seed,lane='house')
            by_frame={}
            previous={}
            while not session.complete:
                player=session.current()
                prior_bowler=player.bowler.id
                prev_frame=player.frame
                prev_ball=player.ball
                current_standing=set(player.standing)
                result=session.bowl()
                examined+=1
                self.assertEqual((result['bowler_id'],result['frame'],result['ball']),
                                 (prior_bowler,prev_frame,prev_ball))
                self.assertEqual(set(result['before']),current_standing)
                self.assertEqual(set(result['down'])|set(result['after']),current_standing)
                self.assertFalse(set(result['down'])&set(result['after']))
                self.assertEqual(result['pins'],len(result['down']))
                self.assertEqual(len(set(result['physics']['contact_order'])),
                                 len(result['physics']['contact_order']))
                self.assertEqual(set(result['physics']['contact_order']),
                                 set(result['down']))
                ident=(prior_bowler,prev_frame)
                if ident not in by_frame:
                    by_frame[ident]=(result['lane_no'],result)
                else:
                    expected_lane,first=by_frame[ident]
                    self.assertEqual(result['lane_no'],expected_lane)
                    if prev_ball==2 and first['pins']!=10 and prev_frame<10:
                        self.assertEqual(result['before'],first['after'])
                        self.assertEqual(result['ball_key'],'plastic')
                        self.assertEqual(result['shot_intent'],'spare')
                if prev_ball>1:
                    self.assertTrue(result['before'])
                    # A fresh rack is legitimate on tenth bonus balls only.
                    if prev_frame<10:
                        self.assertEqual(result['ball_key'],'plastic')
                previous[(prior_bowler,prev_frame,prev_ball)]=result
            for player in session.players:
                self.assertEqual(score_game(player.frames),
                                 independent_oracle(player.frames))
                self.assertTrue(0<=score_game(player.frames)<=300)
                self.assertEqual(len(player.frames),10)
            self.assertEqual(len(session.scores()),2)
        self.assertGreater(examined,2500)

    def test_second_ball_event_carries_all_three_camera_pin_states(self):
        before={2,5,7,10}
        hit={5,10}
        event={'before':sorted(before),'down':sorted(hit),
               'after':sorted(before-hit),
               'physics':{'contact_order':[5,10]}}
        self.assertEqual(set(event['before'])-set(event['down']),
                         set(event['after']))
        self.assertEqual(scene.pin_impact_progress(event,5,1),0)
        self.assertEqual(scene.pin_impact_progress(event,10,1),0)
        self.assertEqual(scene.pin_impact_progress(event,5,5),1)
        self.assertEqual(scene.pin_impact_progress(event,10,5),1)
        self.assertEqual(len(ANIMATION_SEQUENCE),23)
        self.assertEqual([a[3] for a in ANIMATION_SEQUENCE if a[0]=='impact'],
                         [1,2,3,4,5])


if __name__=='__main__':
    unittest.main()
