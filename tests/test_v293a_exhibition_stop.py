"""v2.9.3a: safe admin exhibitions, full rollback on Stop, and single-play GIFs."""
from contextlib import ExitStack
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest
from PIL import Image
from models.bowler import Bowler
from services import v25,shot_animation
from services.career import add_tendency
from services.game_engine import GameSession
from storage import database


def bowler(ident):
    return Bowler(id=ident,name=f'Practice {ident}',owner_id=ident,
                  accuracy=20,style=15,flair=15,consistency=20,spin=15,nerves=15)


class StopDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.folder=TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        path=Path(self.folder.name)/'stop.db'
        stack=ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(database,'DB_PATH',path))
        stack.enter_context(patch.object(v25,'DB_PATH',path))
        database.init_db()
        with database.connect() as db:
            for ident in (11,12):
                b=bowler(ident)
                db.execute('''INSERT INTO bowlers(id,name,owner_id,handedness,rank,accuracy,style,flair,consistency,spin,nerves)
                              VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                           (b.id,b.name,b.owner_id,b.handedness,b.rank,b.accuracy,b.style,
                            b.flair,b.consistency,b.spin,b.nerves))
        self.session=GameSession([bowler(11),bowler(12)],seed=991,lane='house')
        v25.save_snapshot(1909,self.session,'start')

    def _roll(self,deliveries=8,career=True):
        for _ in range(deliveries):
            v25.save_snapshot(1909,self.session,'pre_ball')
            ev=self.session.bowl()
            if career:
                add_tendency(ev['bowler_id'],'accuracy',2.8,'match test evidence')
            v25.save_snapshot(1909,self.session,'post_ball')

    def test_admin_exhibition_survives_recovery(self):
        self.session.friendly_challenge=True
        self.session.practice_no_rewards=True
        v25.save_snapshot(1909,self.session,'start')
        self._roll(4,career=False)
        restored=v25.restore_session(1909)
        self.assertTrue(restored.friendly_challenge)
        self.assertTrue(restored.practice_no_rewards)
        self.assertIsNone(restored.fixture_id)
        self.assertIsNone(restored.tournament_id)
        self.assertEqual(restored.ball_count,4)

    def test_stop_drops_unranked_game_without_stats(self):
        self.session.friendly_challenge=True
        self.session.practice_no_rewards=True
        v25.save_snapshot(1909,self.session,'start')
        self._roll(7,career=False)
        ok,_=v25.cancel_unfinished_session(1909,self.session.session_uid,actor_id=777)
        self.assertTrue(ok)
        with database.connect() as db:
            for table in ('games','game_results','achievements','attribute_history',
                          'career_tendencies','match_snapshots','active_sessions'):
                self.assertEqual(db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],0,table)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM audit_log WHERE action='cancel_game'").fetchone()[0],1)

    def test_stop_ranked_match_rolls_back_all_career_evidence(self):
        self._roll(10,career=True)
        with database.connect() as db:
            self.assertGreater(db.execute('SELECT COUNT(*) FROM career_tendencies').fetchone()[0],0)
        ok,_=v25.cancel_unfinished_session(1909,self.session.session_uid,actor_id=777)
        self.assertTrue(ok)
        with database.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM career_tendencies').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM attribute_history').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM career_timeline').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM active_sessions').fetchone()[0],0)
            self.assertEqual(tuple(db.execute('SELECT accuracy FROM bowlers WHERE id=?',(x,)).fetchone()[0]
                                   for x in (11,12)),(20,20))

    def test_refuses_to_erase_unrelated_career_change(self):
        self._roll(3,career=True)
        last=self.session.players[self.session.turn].bowler.id
        # This additional write was not recorded by our ball checkpoints.
        add_tendency(last,'accuracy',1.0,'other channel')
        with self.assertRaisesRegex(RuntimeError,'Career changed outside'):
            v25.cancel_unfinished_session(1909,self.session.session_uid,777)
        with database.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM active_sessions').fetchone()[0],1)
            self.assertGreater(db.execute('SELECT COUNT(*) FROM career_tendencies').fetchone()[0],0)

    def test_cannot_cancel_committed_game(self):
        self._roll(1,career=False)
        with database.connect() as db:
            db.execute('''INSERT INTO games(session_uid,session_key,status,lane_condition,seed)
                          VALUES(?,?,?,?,?)''',
                       (self.session.session_uid,'1909','complete','house',self.session.seed))
        ok,reason=v25.cancel_unfinished_session(1909,self.session.session_uid,777)
        self.assertFalse(ok)
        self.assertIn('already recorded',reason)
        with database.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM active_sessions').fetchone()[0],1)

    def test_stale_stop_does_not_touch_current_match(self):
        self._roll(1,career=False)
        ok,_=v25.cancel_unfinished_session(1909,'different-match-uid',777)
        self.assertFalse(ok)
        self.assertIsNotNone(v25.restore_session(1909))


class PresentationTests(unittest.TestCase):
    def test_gif_is_single_play_and_never_remains_for_multiple_loops(self):
        self.assertLessEqual(shot_animation.DISCORD_PLAYBACK_HEADROOM_SECONDS,.5)
        self.assertEqual(len(shot_animation.ANIMATION_SEQUENCE),23)
        self.assertAlmostEqual(shot_animation.DURATION_SECONDS,2.795,places=3)
        pictures=[Image.new('RGB',(120,100),(a*8,20,20)) for a in range(23)]
        data=shot_animation._encode(pictures)
        gif=Image.open(BytesIO(data))
        self.assertIsNone(gif.info.get('loop'))

    def test_admin_match_creation_paths_explicitly_choose_unranked(self):
        src=Path(__file__).resolve().parents[1]
        for name in ('cogs/games.py','cogs/dashboard_ui.py'):
            self.assertIn('s.friendly_challenge=True', (src/name).read_text(encoding="utf-8"))
            self.assertIn('s.practice_no_rewards=True', (src/name).read_text(encoding="utf-8"))


if __name__=='__main__':unittest.main()
