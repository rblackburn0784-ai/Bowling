"""v2.8.5s: SQL-level regression tests (run without a Discord connection)."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from models.bowler import Bowler
from services.game_engine import GameSession
from services.pin_engine import ALL,roll_pins
from services.postgame import commit_postgame,tournament_rolloff
from services.analytics import player_summary
from services.v25 import (save_snapshot,undo_snapshot,restore_session,
                          session_dict,session_from_dict,prepare_new_session)
from services.career import add_tendency
from storage import database


class V285sIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.patcher=patch.object(database,'DB_PATH',Path(self.tmp.name)/'test.db')
        self.patcher.start()
        database.init_db()
        with database.connect() as c:
            for ident,name in [(1,'Alpha'),(2,'Beta')]:
                c.execute('INSERT INTO bowlers(id,name,owner_id,rank,accuracy,consistency,spin,nerves,style,flair) VALUES(?,?,?,?,?,?,?,?,?,?)',
                          (ident,name,ident,1,20,20,20,20,20,20))
            c.execute('INSERT INTO teams(id,name,captain_id) VALUES(1,\'Left\',1),(2,\'Right\',2)')
        self.a=Bowler(id=1,name='Alpha',owner_id=1,sprite_key='none')
        self.b=Bowler(id=2,name='Beta',owner_id=2,sprite_key='none')

    def tearDown(self):
        self.patcher.stop()
        self.tmp.cleanup()

    def completed(self,tournament=False):
        if tournament:
            self.a.team_name='Left';self.b.team_name='Right'
        s=GameSession([self.a,self.b],seed=123)
        for p in s.players:
            p.frames=[[4,5] for _ in range(10)]
            p.frame=11;p.ball=1;p.standing=set()
        if tournament:
            with database.connect() as c:
                tid=c.execute("INSERT INTO tournaments(name,status) VALUES('Cup','active')").lastrowid
                mid=c.execute('INSERT INTO tournament_matches(tournament_id,round_no,match_no,team_a_id,team_b_id) VALUES(?,1,1,1,2)',(tid,)).lastrowid
            s.tournament_id=tid;s.match_id=mid
        return s

    def test_friendly_state_survives_snapshots_and_restoration(self):
        s=GameSession([self.a],seed=17)
        s.friendly_challenge=True
        s.last_attribute_changes=[('accuracy',1,21,'test')]
        s.last_attribute_bowler_id=1
        restored=session_from_dict(session_dict(s))
        self.assertTrue(restored.friendly_challenge)
        self.assertEqual(restored.session_uid,s.session_uid)
        self.assertEqual(restored.last_attribute_bowler_id,1)
        save_snapshot(31,s,'pre_ball')
        self.assertTrue(restore_session(31).friendly_challenge)
        self.assertEqual(restore_session(31).session_uid,s.session_uid)

    def test_undo_removes_one_delivery_each_time_and_reverts_career(self):
        s=GameSession([self.a],seed=19)
        prepare_new_session(91)
        for count in range(3):
            save_snapshot(91,s,'pre_ball')
            s.ball_count+=1
            add_tendency(1,'accuracy',2.0,'spare','delivery')
            save_snapshot(91,s,'post_ball')
        with database.connect() as c:
            self.assertEqual(c.execute('SELECT evidence FROM career_tendencies WHERE bowler_id=1 AND stat="accuracy"').fetchone()[0],3)
        for expected in (2,1,0):
            s=undo_snapshot(91)
            self.assertIsNotNone(s)
            self.assertEqual(s.ball_count,expected)
            with database.connect() as c:
                evidence=c.execute('SELECT evidence FROM career_tendencies WHERE bowler_id=1 AND stat="accuracy"').fetchone()
                self.assertEqual(evidence[0] if evidence else 0,expected)
        self.assertIsNone(undo_snapshot(91))
        with database.connect() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM match_snapshots WHERE channel_id=91').fetchone()[0],0)

    def test_undo_after_undo_then_new_ball_does_not_skip_previous(self):
        s=GameSession([self.a],seed=20)
        for _ in range(2):
            save_snapshot(99,s,'pre_ball');s.ball_count+=1;save_snapshot(99,s,'post_ball')
        restored=undo_snapshot(99)
        self.assertEqual(restored.ball_count,1)
        save_snapshot(99,restored,'pre_ball');restored.ball_count+=1;save_snapshot(99,restored,'post_ball')
        self.assertEqual(undo_snapshot(99).ball_count,1)
        self.assertEqual(undo_snapshot(99).ball_count,0)

    def test_tournament_tie_has_stable_sudden_death_winner(self):
        s=self.completed(True)
        summaries=[(p,player_summary(p)) for p in s.players]
        totals=s.team_totals()
        self.assertEqual(totals['Left'],totals['Right'])
        w,rounds=tournament_rolloff(s,summaries,totals)
        self.assertIn(w,totals)
        self.assertTrue(rounds)
        self.assertEqual(rounds[-1]['pins'][w],max(rounds[-1]['pins'].values()))
        self.assertEqual((w,rounds),tournament_rolloff(s,summaries,totals))
        gid=database.record_completed_session(s,155)
        cards,w2,rounds2,new=commit_postgame(s,gid,summaries,None,totals)
        self.assertTrue(new);self.assertEqual(w,w2);self.assertEqual(rounds,rounds2)
        with database.connect() as c:
            m=c.execute('SELECT * FROM tournament_matches WHERE id=?',(s.match_id,)).fetchone()
            self.assertEqual(m['status'],'complete')
            self.assertIn(m['winner_id'],[1,2])
            self.assertEqual(m['score_a'],m['score_b'])
            self.assertTrue(m['rolloff_json'])
            self.assertEqual(c.execute('SELECT COUNT(*) FROM head_to_head').fetchone()[0],1)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM team_history').fetchone()[0],2)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM game_finalizations').fetchone()[0],1)

    def test_postgame_retry_does_not_double_count_and_uses_uid(self):
        s=self.completed()
        summaries=[(p,player_summary(p)) for p in s.players]
        gid=database.record_completed_session(s,53)
        self.assertEqual(database.record_completed_session(s,53),gid)
        _,_,_,new=commit_postgame(s,gid,summaries,None,{})
        self.assertTrue(new)
        xp_before=[]
        with database.connect() as c:
            xp_before=[tuple(row) for row in c.execute('SELECT bowler_id,xp FROM bowler_progression ORDER BY bowler_id')]
        _,_,_,new=commit_postgame(s,gid,summaries,None,{})
        self.assertFalse(new)
        with database.connect() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM games').fetchone()[0],1)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM game_history').fetchone()[0],2)
            self.assertEqual([tuple(row) for row in c.execute('SELECT bowler_id,xp FROM bowler_progression ORDER BY bowler_id')],xp_before)
        # Simulate a restart from a session saved before finish.
        recovered=session_from_dict(session_dict(s))
        self.assertEqual(database.record_completed_session(recovered,53),gid)

    def test_postgame_failure_rolls_back_all_effects_and_retries(self):
        s=self.completed()
        from services import postgame
        summaries=[(p,player_summary(p)) for p in s.players]
        gid=database.record_completed_session(s,57)
        real=postgame.award_progression
        calls=[0]
        def fail_second(*a,**k):
            calls[0]+=1
            if calls[0]==2:raise RuntimeError('injected mid-commit failure')
            return real(*a,**k)
        with patch.object(postgame,'award_progression',side_effect=fail_second):
            with self.assertRaisesRegex(RuntimeError,'injected'):
                postgame.commit_postgame(s,gid,summaries,None,{})
        with database.connect() as c:
            for table in ('game_history','game_finalizations','bowler_progression','season_bowler_stats'):
                self.assertEqual(c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0],0,table)
        self.assertTrue(postgame.commit_postgame(s,gid,summaries,None,{})[3])

    def test_spare_with_full_rack_cannot_take_strike_branch(self):
        class ZeroRng:
            def gauss(self,mean,std):return mean
            def random(self):return 0.0
        down,q,info=roll_pins(ZeroRng(),self.a,set(ALL),target_mode='spare')
        self.assertEqual(info['target'],1) # not the strike-only 'pocket' shortcut
        down,q,info=roll_pins(ZeroRng(),self.a,set(ALL),target_mode='strike')
        self.assertEqual(info['target'],'pocket')

    def test_start_snapshot_survives_restart_without_a_first_ball(self):
        s=GameSession([self.a],seed=333)
        save_snapshot(700,s,'start')
        restored=restore_session(700)
        self.assertEqual(restored.session_uid,s.session_uid)
        self.assertEqual(restored.ball_count,0)
        self.assertEqual(restored.current().frame,1)
        self.assertIsNone(undo_snapshot(700))
        prepare_new_session(700)
        self.assertIsNone(restore_session(700))

    def test_existing_v285r_database_is_migrated_in_place(self):
        import sqlite3
        with database.connect() as c:
            # Mimic a pre-release DB where new columns are not present.
            c.execute('DROP TABLE game_finalizations')
            c.execute('DROP INDEX IF EXISTS ix_games_session_uid')
            c.execute('ALTER TABLE games RENAME TO legacy_games')
            c.execute('CREATE TABLE games(id INTEGER PRIMARY KEY,session_key TEXT,status TEXT,lane_condition TEXT,seed INTEGER)')
            c.execute('INSERT INTO games(id,session_key,status,lane_condition,seed) VALUES(90,"old","complete","house",55)')
            c.execute('DROP TABLE legacy_games')
        database.init_db()
        with database.connect() as c:
            cols={r['name'] for r in c.execute('PRAGMA table_info(games)')}
            self.assertIn('session_uid',cols)
            self.assertEqual(c.execute('SELECT seed FROM games WHERE id=90').fetchone()[0],55)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM game_finalizations').fetchone()[0],0)

    def test_undo_refuses_to_overwrite_concurrent_career_updates(self):
        s=GameSession([self.a],seed=55)
        save_snapshot(800,s,'pre_ball')
        s.ball_count+=1
        add_tendency(1,'accuracy',2.0,'delivery','delivery')
        save_snapshot(800,s,'post_ball')
        # An independent match changed this bowler AFTER the checkpoint.
        add_tendency(1,'accuracy',1.5,'other match','delivery')
        self.assertIsNone(undo_snapshot(800))
        with database.connect() as c:
            self.assertEqual(c.execute('SELECT evidence FROM career_tendencies WHERE bowler_id=1 AND stat="accuracy"').fetchone()[0],2)

    def test_undo_disallowed_once_base_game_committed(self):
        s=self.completed()
        s.players[0].frame=1
        s.players[0].frames=[]
        save_snapshot(543,s,'pre_ball')
        for p in s.players:
            p.frames=[[4,5] for _ in range(10)];p.frame=11
        save_snapshot(543,s,'post_ball')
        database.record_completed_session(s,543)
        self.assertIsNone(undo_snapshot(543))


if __name__=='__main__':unittest.main()
