"""Rule-book regression suite for conventional ten-pin scoring and live match turns.

Covers USBC/IBF ten-frame bonuses, second throws, tenth frame, lane pairs,
and the true event pin state used by the Discord GIF renderer.
"""
import unittest
from unittest.mock import patch
from models.bowler import Bowler
from services.game_engine import GameSession
from services.pin_engine import ALL
from services.scoring import score_game,frame_notation
from services.analytics import frame_flags
from services.v25 import session_dict,session_from_dict


def bowler(number):
    return Bowler(id=number,name=f'Player{number}',owner_id=number,
                  accuracy=20,consistency=20,spin=15,nerves=15,style=10,flair=10)


def controlled_rolls(counts):
    remaining=iter(counts)
    def fake(rng,bowler,standing,*args,**kwargs):
        number=next(remaining)
        if not 0<=number<=len(standing):
            raise AssertionError(f'Impossible controlled shot {number}/{len(standing)}')
        knocked=set(sorted(standing)[:number])
        physics={'miss':0.0,'ball':kwargs.get('ball_key','hybrid'),
                 'target':'pocket','metrics':{'revs':250,'entry_angle':3.0},'tags':[]}
        return knocked,0.8,physics
    return fake


class ConventionalScoreRules(unittest.TestCase):
    def test_standard_reference_games(self):
        vectors=[
            ([[0,0]]*10,0),
            ([[9,0]]*10,90),
            ([[5,5]]*9+[[5,5,5]],150),
            ([[9,1]]*9+[[9,1,9]],190),
            ([[10]]*9+[[10,10,10]],300),
            ([[10]]*9+[[9,1,9]],278),
            ([[10]]*9+[[10,7,3]],287),
            ([[10],[10],[10],[7,2],[8,2],[0,9],[10],[7,3],[9,0],[10,10,8]],180),
        ]
        for frames,total in vectors:
            with self.subTest(total=total,frames=frames):
                self.assertEqual(score_game(frames),total)
    def test_tenth_notation(self):
        for rolls,notation in [
            ([10,10,10],'XXX'),([10,7,3],'X7/'),([10,10,8],'XX8'),
            ([9,1,10],'9/X'),([9,0],'9-'),([0,10,8],'-/8'),
            ([10,0,10],'X-/'),([0,10],'-/'),
            ([7,2],'72'),([10],'X')
        ]:
            with self.subTest(rolls=rolls):
                self.assertEqual(frame_notation(rolls),notation)
    def test_incomplete_tenth_never_crashes_or_credits_bonus(self):
        for tenth in ([],[10],[10,10],[10,7],[9],[9,1],[9,0]):
            if tenth==[9,0]:
                self.assertEqual(score_game([[0,0]]*9+[tenth]),9)
            else:
                self.assertEqual(score_game([[0,0]]*9+[tenth]),0)
    def test_impossible_pinfall_and_extra_bonus_rejected(self):
        bad=[
            [[10,0]]+[[0,0]]*9,
            [[7,5]]+[[0,0]]*9,
            [[-1,0]]+[[0,0]]*9,
            [[4,0]]*9+[[10,7,7]],
            [[4,0]]*9+[[9,2]],
            [[4,0]]*9+[[9,0,3]],
            [[4,0]]*9+[[9,1,4,2]],
            [[4,0]]*9+[[10,10]],
        ]
        for frames in bad:
            with self.subTest(frames=frames):
                if frames[-1]==[10,10]:
                    self.assertEqual(score_game(frames),0)
                else:
                    with self.assertRaises(ValueError):
                        score_game(frames)
    def test_perfect_strike_and_turkey_streak_includes_bonus(self):
        summary=frame_flags([[10]]*9+[[10,10,10]])
        self.assertEqual(summary['strikes'],12)
        self.assertEqual(summary['longest_streak'],12)
        self.assertEqual(summary['turkeys'],10)
        self.assertEqual(summary['clean'],1)
        self.assertEqual(frame_flags([[9,1]]*9+[[9,1,10]])['strikes'],1)


class SecondDeliveryGameRules(unittest.TestCase):
    def test_two_balls_same_player_same_lane_and_true_remaining_pins(self):
        s=GameSession([bowler(1),bowler(2)],seed=101)
        with patch('services.game_engine.roll_pins',side_effect=controlled_rolls([7,3,10,10])):
            one=s.bowl()
            self.assertEqual((one['bowler_id'],one['frame'],one['ball']), (1,1,1))
            self.assertEqual(one['after'],[8,9,10])
            self.assertEqual(s.current().bowler.id,1)
            two=s.bowl()
            self.assertEqual((two['bowler_id'],two['frame'],two['ball']), (1,1,2))
            self.assertEqual(two['before'],one['after'])
            self.assertEqual(two['down'],one['after'])
            self.assertEqual(two['after'],[])
            self.assertEqual((one['lane_no'],two['lane_no']),(3,3))
            self.assertEqual(two['ball_key'],'plastic')
            self.assertEqual(two['shot_intent'],'spare')
            self.assertTrue(two['spare'])
            self.assertEqual(s.current().bowler.id,2)
            three=s.bowl()
            self.assertEqual((three['bowler_id'],three['frame'],three['ball']), (2,1,1))
            self.assertEqual(three['lane_no'],3)
            four=s.bowl()
            self.assertEqual(four['bowler_id'],1)
            self.assertEqual(four['frame'],2)
            self.assertEqual(four['lane_no'],4)
            self.assertEqual(four['before'],sorted(ALL))
    def test_first_nine_gutter_followed_by_ten_is_spare_not_strike(self):
        session=GameSession([bowler(1)],seed=42)
        with patch('services.game_engine.roll_pins',
                   side_effect=controlled_rolls([0,10])):
            first=session.bowl()
            second=session.bowl()
        self.assertEqual(first['after'],sorted(ALL))
        self.assertEqual(second['before'],sorted(ALL))
        self.assertEqual(second['ball'],2)
        self.assertEqual(second['ball_key'],'plastic')
        self.assertEqual(second['shot_intent'],'spare')
        self.assertTrue(second['spare'])
        self.assertFalse(second.get('strike_streak'))
        self.assertEqual(frame_notation(session.players[0].frames[0]),'-/')
        self.assertEqual((first['lane_no'],second['lane_no']),(3,3))

    def test_snapshot_restores_mid_frame_with_same_lane(self):
        session=GameSession([bowler(1),bowler(2)],seed=41)
        with patch('services.game_engine.roll_pins',side_effect=controlled_rolls([7])):
            first=session.bowl()
        restored=session_from_dict(session_dict(session))
        self.assertEqual(restored.current().bowler.id,1)
        self.assertEqual(restored.current().ball,2)
        self.assertEqual(restored.current().standing,set(first['after']))
        with patch('services.game_engine.roll_pins',side_effect=controlled_rolls([3])):
            second=restored.bowl()
        self.assertEqual(second['lane_no'],first['lane_no'])
        self.assertEqual(second['before'],first['after'])
        self.assertEqual(second['ball_key'],'plastic')
    def _prepare_tenth(self):
        s=GameSession([bowler(1)],seed=101)
        p=s.players[0]
        p.frames=[[0,0] for _ in range(9)]
        p.frame=10
        p.ball=1
        p.standing=set(ALL)
        return s
    def test_tenth_strike_three_balls_same_lane_correct_numbers(self):
        session=self._prepare_tenth()
        with patch('services.game_engine.roll_pins',side_effect=controlled_rolls([10,7,3])):
            events=[session.bowl() for _ in range(3)]
        self.assertEqual([e['ball'] for e in events],[1,2,3])
        self.assertEqual([e['lane_no'] for e in events],[3,3,3])
        self.assertEqual(events[1]['before'],sorted(ALL))
        self.assertEqual(len(events[2]['before']),3)
        self.assertEqual(events[2]['after'],[])
        self.assertTrue(session.complete)
        self.assertEqual(session.scores()['Player1'],20)
        self.assertEqual(frame_notation(session.players[0].frames[9]),'X7/')
    def test_tenth_spare_refills_new_rack_for_bonus(self):
        session=self._prepare_tenth()
        with patch('services.game_engine.roll_pins',side_effect=controlled_rolls([9,1,10])):
            events=[session.bowl() for _ in range(3)]
        self.assertEqual([e['ball'] for e in events],[1,2,3])
        self.assertEqual([e['lane_no'] for e in events],[3,3,3])
        self.assertEqual(events[1]['before'],[10])
        self.assertEqual(events[2]['before'],sorted(ALL))
        self.assertTrue(session.complete)
        self.assertEqual(session.scores()['Player1'],20)
        self.assertEqual(frame_notation(session.players[0].frames[9]),'9/X')
    def test_tenth_gutter_spare_and_bonus_strike_are_not_three_strikes(self):
        session=self._prepare_tenth()
        with patch('services.game_engine.roll_pins',
                   side_effect=controlled_rolls([0,10,10])):
            events=[session.bowl() for _ in range(3)]
        self.assertEqual(frame_notation(session.players[0].frames[9]),'-/X')
        self.assertFalse(events[1].get('strike_streak'))
        self.assertTrue(events[1]['spare'])
        self.assertEqual(events[2].get('strike_streak'),1)
        self.assertEqual(frame_flags(session.players[0].frames)['strikes'],1)
        self.assertEqual(session.scores()['Player1'],20)

    def test_tenth_strike_gutter_then_spare_uses_plastic_third(self):
        session=self._prepare_tenth()
        with patch('services.game_engine.roll_pins',
                   side_effect=controlled_rolls([10,0,10])):
            events=[session.bowl() for _ in range(3)]
        self.assertEqual(frame_notation(session.players[0].frames[9]),'X-/')
        self.assertEqual(events[2]['before'],sorted(ALL))
        self.assertEqual(events[2]['ball_key'],'plastic')
        self.assertEqual(events[2]['shot_intent'],'spare')
        self.assertTrue(events[2]['spare'])
        self.assertFalse(events[2].get('strike_streak'))
        self.assertEqual(session.scores()['Player1'],20)
        self.assertEqual(frame_flags(session.players[0].frames)['strikes'],1)

    def test_tenth_open_ends_after_two(self):
        session=self._prepare_tenth()
        with patch('services.game_engine.roll_pins',side_effect=controlled_rolls([7,2])):
            events=[session.bowl() for _ in range(2)]
        self.assertEqual([e['ball'] for e in events],[1,2])
        self.assertTrue(session.complete)
        self.assertEqual(session.scores()['Player1'],9)
    def test_seeded_reality_pin_constraints_and_score_range(self):
        # Real RNG/physics, not mocked. Run multiple complete games.
        for seed in range(1,31):
            with self.subTest(seed=seed):
                s=GameSession([bowler(1),bowler(2)],seed=seed)
                events=[]
                while not s.complete:
                    e=s.bowl()
                    events.append(e)
                    self.assertEqual(set(e['before']),set(e['down'])|set(e['after']))
                    self.assertTrue(set(e['down']).isdisjoint(e['after']))
                    self.assertLessEqual(e['pins'],len(e['before']))
                    if e['ball']>1:
                        self.assertEqual(e['lane_no'],next(
                            prev['lane_no'] for prev in reversed(events[:-1])
                            if prev['bowler_id']==e['bowler_id'] and prev['frame']==e['frame']))
                self.assertTrue(all(0<=v<=300 for v in s.scores().values()))
                self.assertEqual(len(s.card()),2)
                self.assertLessEqual(len(events),42)

if __name__=='__main__':
    unittest.main()
