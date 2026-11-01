"""v2.8.5t: end-to-end SQL and renderer hardening regressions (no Discord required)."""
import copy
import tempfile
from contextlib import closing
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from PIL import Image, ImageDraw

from models.bowler import Bowler
from services.analytics import player_summary
from services.game_engine import GameSession
from services.postgame import finalize_completed_session
from services.competition import start_tournament, report_match
from services.career import sync_rank
from services import scene_renderer, lane_visual
from services.v25 import session_dict,session_from_dict,backup_database
from storage import database
from services import league_engine as lg


class ReleaseIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.patcher=patch.object(database,'DB_PATH',Path(self.tmp.name)/'release.db')
        self.patcher.start()
        database.init_db()
        with database.connect() as c:
            for ident,name,team in [(1,'Alpha','Left'),(2,'Beta','Right')]:
                c.execute('INSERT INTO bowlers(id,name,owner_id,rank,accuracy,consistency,spin,nerves,style,flair) VALUES(?,?,?,?,?,?,?,?,?,?)',
                          (ident,name,ident,1,20,20,20,20,20,20))
                c.execute('INSERT INTO teams(id,name,captain_id) VALUES(?,?,?)',(ident,team,ident))
                c.execute('INSERT INTO team_members(team_id,bowler_id,slot) VALUES(?,?,1)',(ident,ident))

    def tearDown(self):
        self.patcher.stop()
        self.tmp.cleanup()

    def fixture(self,fmt='round_robin'):
        cid=lg.create_competition('Release Cup',format=fmt)
        self.assertTrue(lg.transition(cid,'registration')[0])
        self.assertTrue(lg.register(cid,1))
        self.assertTrue(lg.register(cid,2))
        self.assertTrue(lg.transition(cid,'locked')[0])
        self.assertTrue(lg.generate_schedule(cid)[0])
        self.assertTrue(lg.transition(cid,'active')[0])
        with database.connect() as c:
            f=c.execute('SELECT id FROM fixtures WHERE competition_id=?',(cid,)).fetchone()
        return cid,f['id']

    def session(self,score_a=90,score_b=90,cid=None,fid=None,tid=None,mid=None):
        a=Bowler(id=1,name='Alpha',owner_id=1,team_name='Left',sprite_key='none')
        b=Bowler(id=2,name='Beta',owner_id=2,team_name='Right',sprite_key='none')
        s=GameSession([a,b],seed=45,competition_id=cid,fixture_id=fid,tournament_id=tid,match_id=mid)
        # Any multiple of 10 in 0..180 can be encoded in legal open 9+0 frames.
        for p,score in zip(s.players,(score_a,score_b)):
            self.assertIn(score,(0,90))
            p.frames=[[score//10,0] for _ in range(10)]
            p.frame=11;p.ball=1;p.standing=set()
        return s

    def publish(self,s):
        totals=s.team_totals()
        summaries=[(p,player_summary(p)) for p in s.players]
        return finalize_completed_session(s,23,summaries,None,totals)

    def test_round_robin_draw_is_committed_once_and_retry_does_not_reaward(self):
        cid,fid=self.fixture()
        s=self.session(cid=cid,fid=fid)
        _,_,_,_,fresh=self.publish(s)
        self.assertTrue(fresh)
        _,_,_,_,fresh=self.publish(s)
        self.assertFalse(fresh)
        with database.connect() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM fixture_games').fetchone()[0],1)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM game_results').fetchone()[0],2)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM game_history').fetchone()[0],2)
            rows=c.execute('SELECT played,draws,points FROM competition_standings ORDER BY entrant_id').fetchall()
            self.assertEqual([tuple(x) for x in rows],[(1,1,1),(1,1,1)])

    def test_invalid_fixture_mapping_rolls_back_base_game_career_stats(self):
        cid,fid=self.fixture()
        s=self.session(cid=cid,fid=fid)
        s.players[0].bowler.team_name='Unregistered Club'
        with self.assertRaises(ValueError):self.publish(s)
        with database.connect() as c:
            for table in ('games','game_results','bowler_stats','game_history','game_finalizations','fixture_games'):
                self.assertEqual(c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0],0,table)
        self.assertFalse(s.persisted)

    def test_non_fixture_tournament_failure_is_atomic(self):
        with database.connect() as c:
            tid=c.execute("INSERT INTO tournaments(name,status) VALUES('Legacy','active')").lastrowid
            mid=c.execute('INSERT INTO tournament_matches(tournament_id,round_no,match_no,team_a_id,team_b_id) VALUES(?,1,1,1,99)',(tid,)).lastrowid
        s=self.session(tid=tid,mid=mid)
        with self.assertRaises(ValueError):self.publish(s)
        with database.connect() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM games').fetchone()[0],0)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM bowler_stats').fetchone()[0],0)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM game_finalizations').fetchone()[0],0)

    def test_best_of_three_records_games_only_finalises_after_two_wins(self):
        cid,fid=self.fixture('best_of')
        s1=self.session(90,0,cid,fid)
        self.publish(s1)
        with database.connect() as c:
            self.assertEqual(c.execute('SELECT status FROM fixtures WHERE id=?',(fid,)).fetchone()['status'],'scheduled')
            self.assertEqual(c.execute('SELECT COUNT(*) FROM fixture_games').fetchone()[0],1)
            self.assertEqual(c.execute('SELECT SUM(played) FROM competition_standings').fetchone()[0],0)
        s2=self.session(90,0,cid,fid)
        self.publish(s2)
        with database.connect() as c:
            fx=c.execute('SELECT status,winner_id,home_score,away_score FROM fixtures WHERE id=?',(fid,)).fetchone()
            self.assertEqual((fx['status'],fx['winner_id'],fx['home_score'],fx['away_score']),('complete',1,180,0))
            self.assertEqual(c.execute('SELECT COUNT(*) FROM fixture_games').fetchone()[0],2)
            self.assertEqual(c.execute('SELECT SUM(played) FROM competition_standings').fetchone()[0],2)

    def test_knockout_tie_uses_regulation_scores_plus_rolloff(self):
        cid,fid=self.fixture('single_elimination')
        s=self.session(cid=cid,fid=fid)
        _,_,winner,rolloff,_=self.publish(s)
        self.assertIn(winner,('Left','Right'))
        self.assertTrue(rolloff)
        with database.connect() as c:
            fx=c.execute('SELECT home_score,away_score,winner_id,status FROM fixtures WHERE id=?',(fid,)).fetchone()
            self.assertEqual((fx['home_score'],fx['away_score'],fx['status']),(90,90,'complete'))
            self.assertIn(fx['winner_id'],(1,2))
            result=c.execute('SELECT rolloff_json FROM fixture_games WHERE fixture_id=?',(fid,)).fetchone()
            self.assertTrue(result['rolloff_json'])
        _,_,again,rounds,fresh=self.publish(s)
        self.assertFalse(fresh)
        self.assertEqual((again,rounds),(winner,rolloff))

    def test_tournament_restart_does_not_clear_results(self):
        with database.connect() as c:
            tid=c.execute("INSERT INTO tournaments(name,status) VALUES('Legacy','active')").lastrowid
            c.execute("INSERT INTO tournament_matches(tournament_id,round_no,match_no,team_a_id,team_b_id,score_a,score_b,winner_id,status) VALUES(?,1,1,1,2,180,90,1,'complete')",(tid,))
        new,err=start_tournament('Legacy')
        self.assertIsNone(new)
        self.assertIn('already started',err)
        with database.connect() as c:
            row=c.execute('SELECT score_a,score_b,status FROM tournament_matches WHERE tournament_id=?',(tid,)).fetchone()
        self.assertEqual(tuple(row),(180,90,'complete'))

    def test_manual_tournament_invalid_scores_are_rejected(self):
        with database.connect() as c:
            tid=c.execute("INSERT INTO tournaments(name,status) VALUES('Legacy','active')").lastrowid
            c.execute('INSERT INTO tournament_matches(tournament_id,round_no,match_no,team_a_id,team_b_id) VALUES(?,1,1,1,2)',(tid,))
        for a,b in ((-30,90),(300,400),(20,20),(2.5,90)):
            self.assertFalse(report_match('Legacy',1,1,a,b)[0])
        self.assertTrue(report_match('Legacy',1,1,180,90)[0])
        self.assertFalse(report_match('Legacy',1,1,90,180)[0])

    def test_restoring_twice_keeps_immutable_team_ids(self):
        s=self.session()
        state=session_dict(s)
        first=session_from_dict(state)
        second=session_from_dict(state)
        self.assertEqual([p.bowler.team_name for p in first.players],['Left','Right'])
        self.assertEqual([p.bowler.team_name for p in second.players],['Left','Right'])
        self.assertEqual(state['players'][0]['bowler']['team_name'],'Left')

    def test_ranked_xp_does_not_depend_on_cosmetic_reward(self):
        with database.connect() as c:
            c.execute('INSERT INTO bowler_progression(bowler_id,xp) VALUES(1,119)')
            c.execute('INSERT INTO exhibition_rewards(bowler_id,cosmetic_xp) VALUES(1,10)')
        self.assertEqual(sync_rank(1),1)

    def test_all_elimination_and_multi_stage_formats_progress(self):
        for fmt in ('single_elimination','double_elimination','stepladder','qualifying','groups_knockout'):
            with self.subTest(fmt=fmt):
                # Isolate fixtures while sharing the current in-memory DB.
                cid=lg.create_competition('Format '+fmt,format=fmt)
                self.assertTrue(lg.transition(cid,'registration')[0])
                for eid in (1,2):self.assertTrue(lg.register(cid,eid))
                self.assertTrue(lg.transition(cid,'locked')[0])
                self.assertTrue(lg.generate_schedule(cid)[0])
                self.assertTrue(lg.transition(cid,'active')[0])
                for i in range(6):
                    fx=lg.next_fixture(cid)
                    if fx is None:break
                    with database.connect() as c:
                        c.execute("UPDATE fixtures SET status='playing' WHERE id=?",(fx['id'],))
                    session=self.session(90,0,cid,fx['id'])
                    self.publish(session)
                with database.connect() as c:
                    co=c.execute('SELECT state FROM competitions WHERE id=?',(cid,)).fetchone()
                    self.assertEqual(co['state'],'completed',fmt)
                    self.assertFalse(c.execute("SELECT 1 FROM fixtures WHERE competition_id=? AND status!='complete'",(cid,)).fetchone())

    def test_online_sqlite_backup_keeps_committed_rows(self):
        from services import v25
        with patch.object(v25,'DB_PATH',database.DB_PATH),\
             patch.object(v25,'BACKUP_DIR',Path(self.tmp.name)/'backups'):
            created=backup_database('before result')
        self.assertTrue(created.is_file())
        import sqlite3
        with closing(sqlite3.connect(created)) as db:
            self.assertEqual(db.execute('PRAGMA quick_check').fetchone()[0],'ok')
            self.assertEqual(db.execute('SELECT COUNT(*) FROM bowlers').fetchone()[0],2)

    def test_asset_manifest_reports_missing_art_without_crashing(self):
        from services.asset_validation import validate_broadcast_assets
        missing=validate_broadcast_assets(root=Path(self.tmp.name))
        self.assertFalse(missing['ok'])
        self.assertIn('assets/cameras/overhead_empty.png',missing['missing'])
        with self.assertRaises(RuntimeError):
            validate_broadcast_assets(root=Path(self.tmp.name),strict=True)

    def test_overhead_regulation_rack_and_legacy_markers(self):
        spots=scene_renderer.CAMERA_OVERHEAD
        grouped={}
        for pin,(u,v) in spots.items():grouped.setdefault(v,[]).append(pin)
        self.assertEqual([sorted(p) for _,p in sorted(grouped.items())],[[7,8,9,10],[4,5,6],[2,3],[1]])
        base=Image.new('RGBA',(1254,1254),(150,110,74,255))
        d=ImageDraw.Draw(base)
        for x,y in scene_renderer.LEGACY_OVERHEAD_CIRCLES:
            d.ellipse((x-13,y-13,x+13,y+13),fill=(12,11,10,255))
        fixed=scene_renderer._regulation_overhead_plate(base)
        self.assertLess(fixed.getpixel((round(spots[1][0]*1254),round(spots[1][1]*1254)))[0],75)
        self.assertGreater(fixed.getpixel((281,386))[0],50)
        clean=Image.new('RGBA',(1254,1254),(150,110,74,255))
        self.assertEqual(scene_renderer._regulation_overhead_plate(clean).tobytes(),clean.tobytes())

    def test_fallback_first_impact_keeps_original_pins(self):
        s=GameSession([Bowler(id=1,name='Alpha',owner_id=1)],seed=11)
        ev={'before':[1,2,3,4,5,6,7,8,9,10],'down':[1,2,3,7],'after':[4,5,6,8,9,10]}
        first,_=lane_visual._base(s,ev,'impact',1)
        pre,_=lane_visual._base(s,ev,'approach')
        later,_=lane_visual._base(s,ev,'impact',5)
        region=(185,120,495,310)
        self.assertEqual(first.crop(region).tobytes(),pre.crop(region).tobytes())
        self.assertNotEqual(first.crop(region).tobytes(),later.crop(region).tobytes())


if __name__=='__main__':unittest.main()
