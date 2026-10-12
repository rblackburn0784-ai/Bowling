"""v2.9.2 standalone career/competition acceptance tests."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from storage import database
from services.career_finale import (unlock_career_milestones,career_profile,
                                     leaderboard,competition_health)
from services.career import rank_from_xp,ATTRS
from services.tournament_admin import tournament_health,set_tournament_paused
from services.competition import report_match
from services.honours import finalize_tournament_honours
from services.roster import update_owned_bowler


class CareerCompetitionFinalisationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.patcher=patch.object(database,'DB_PATH',Path(self.temp.name)/'career.db')
        self.patcher.start();database.init_db()
        with database.connect() as c:
            for bid,name in ((1,'Alpha'),(2,'Beta'),(3,'Gamma')):
                c.execute('''INSERT INTO bowlers(id,name,owner_id,rank,accuracy,consistency,spin,nerves,style,flair)
                             VALUES(?,?,?,?,?,?,?,?,?,?)''',
                          (bid,name,bid,1,15,15,15,15,15,15))
                c.execute('INSERT INTO bowler_stats(bowler_id) VALUES(?)',(bid,))
            c.execute("INSERT INTO teams(id,name,captain_id) VALUES(1,'Blue',1),(2,'Red',2)")
            c.execute('INSERT INTO team_members(team_id,bowler_id,slot) VALUES(1,1,1),(2,2,1)')
    def tearDown(self):self.patcher.stop();self.temp.cleanup()

    def test_career_milestones_once(self):
        with database.connect() as c:
            c.execute('UPDATE bowler_stats SET games=10,strikes=51,spares=50,clean_games=5,split_conversions=5 WHERE bowler_id=1')
            first=unlock_career_milestones(1,db=c)
            second=unlock_career_milestones(1,db=c)
        self.assertTrue(any(a[0]=='Regular' for a in first))
        self.assertTrue(any(a[0]=='Spare Specialist' for a in first))
        self.assertEqual(second,[])
        with database.connect() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM achievements WHERE bowler_id=1').fetchone()[0],len(first))

    def test_atomic_milestone_rollback(self):
        with self.assertRaises(RuntimeError):
            with database.connect() as c:
                c.execute('UPDATE bowler_stats SET games=25 WHERE bowler_id=1')
                self.assertTrue(unlock_career_milestones(1,db=c))
                raise RuntimeError('simulate finalisation failure')
        with database.connect() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM achievements').fetchone()[0],0)
            self.assertEqual(c.execute('SELECT games FROM bowler_stats WHERE bowler_id=1').fetchone()[0],0)

    def test_career_profile_separates_cosmetic_xp(self):
        with database.connect() as c:
            c.execute('INSERT INTO bowler_progression(bowler_id,xp) VALUES(1,240)')
            c.execute('INSERT INTO exhibition_rewards(bowler_id,cosmetic_xp) VALUES(1,90000)')
        profile=career_profile(1)
        self.assertEqual(profile['rank_expected'],rank_from_xp(240))
        self.assertEqual(profile['cosmetic_xp'],90000)
        self.assertEqual(profile['attributes']['accuracy'],15)

    def test_average_qualification_and_record_ordering(self):
        with database.connect() as c:
            c.execute('UPDATE bowler_stats SET games=1,total_pins=300,high_game=300 WHERE bowler_id=1')
            c.execute('UPDATE bowler_stats SET games=5,total_pins=925,high_game=200 WHERE bowler_id=2')
            c.execute('UPDATE bowler_stats SET games=3,total_pins=360,high_game=140 WHERE bowler_id=3')
        title,rs=leaderboard('average')
        self.assertEqual([r['name'] for r in rs],['Beta','Gamma'])
        self.assertEqual(leaderboard('high_game')[1][0]['name'],'Alpha')
        with self.assertRaises(ValueError):leaderboard('nonexistent')
        with self.assertRaises(ValueError):leaderboard('average',limit=1000)

    def test_identity_edit_cannot_change_career_attributes(self):
        ok,err=update_owned_bowler(1,'AlphaRenamed','L',99,50,50,50,50,50,50)
        self.assertTrue(ok,err)
        with database.connect() as c:
            b=c.execute('SELECT * FROM bowlers WHERE id=1').fetchone()
        self.assertEqual(b['rank'],1)
        self.assertTrue(all(b[stat]==15 for stat in ATTRS))
        self.assertEqual(b['handedness'],'L')

    def _tourney(self,with_members=True):
        with database.connect() as c:
            tid=c.execute("INSERT INTO tournaments(name,status) VALUES('Saints Cup','complete')").lastrowid
            mid=c.execute('''INSERT INTO tournament_matches(tournament_id,round_no,match_no,team_a_id,team_b_id,winner_id,status,score_a,score_b)
                             VALUES(?,1,1,1,2,1,'complete',180,150)''',(tid,)).lastrowid
            if not with_members:c.execute('DELETE FROM team_members')
            c.execute('INSERT INTO tournament_bowler_stats(tournament_id,bowler_id,games,total_pins,high_game,strikes,split_conversions) VALUES(?,1,3,550,200,20,1)',(tid,))
        return tid,mid

    def test_tournament_honours_are_atomic_and_repeat_safe(self):
        tid,_=self._tourney()
        got=finalize_tournament_honours(tid)
        self.assertTrue(got['new'])
        self.assertEqual(finalize_tournament_honours(tid)['new'],[])
        with database.connect() as c:
            self.assertEqual(c.execute('SELECT championships FROM team_history WHERE team_id=1').fetchone()[0],1)
            self.assertEqual(c.execute('SELECT finals FROM team_history WHERE team_id=2').fetchone()[0],1)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM tournament_honour_runs WHERE tournament_id=?',(tid,)).fetchone()[0],1)
            self.assertEqual(c.execute('SELECT awards FROM bowler_stats WHERE bowler_id=1').fetchone()[0],5)

    def test_empty_team_honours_do_not_reaward_championship(self):
        tid,_=self._tourney(with_members=False)
        finalize_tournament_honours(tid);finalize_tournament_honours(tid)
        with database.connect() as c:
            self.assertEqual(c.execute('SELECT championships FROM team_history WHERE team_id=1').fetchone()[0],1)

    def test_ceremony_failure_rolls_back_entire_transaction(self):
        tid,_=self._tourney()
        from services import honours
        real=honours._honour; counter=[0]
        def fault(*args,**kwargs):
            counter[0]+=1
            if counter[0]==2:raise RuntimeError('award storage failed')
            return real(*args,**kwargs)
        with patch.object(honours,'_honour',side_effect=fault):
            with self.assertRaises(RuntimeError):finalize_tournament_honours(tid)
        with database.connect() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM career_honours').fetchone()[0],0)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM tournament_honour_runs').fetchone()[0],0)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM team_history').fetchone()[0],0)

    def test_pause_resume_is_logged_and_does_not_erase_bracket(self):
        with database.connect() as c:
            tid=c.execute("INSERT INTO tournaments(name,status) VALUES('Active Cup','active')").lastrowid
            c.execute("INSERT INTO tournament_matches(tournament_id,round_no,match_no,team_a_id,team_b_id) VALUES(?,1,1,1,2)",(tid,))
        self.assertTrue(set_tournament_paused('Active Cup',True,actor_id=123)[0])
        self.assertTrue(tournament_health('Active Cup')['paused'])
        self.assertFalse(report_match('Active Cup',1,1,200,160)[0])
        self.assertTrue(set_tournament_paused('Active Cup',False,actor_id=123)[0])
        self.assertTrue(report_match('Active Cup',1,1,200,160)[0])
        with database.connect() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM audit_log WHERE target_id=? AND action LIKE 'tournament_%'",(tid,)).fetchone()[0],2)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM tournament_matches WHERE tournament_id=?',(tid,)).fetchone()[0],1)

    def test_live_recoverable_match_blocks_manual_result(self):
        with database.connect() as c:
            tid=c.execute("INSERT INTO tournaments(name,status) VALUES('Active Cup','active')").lastrowid
            mid=c.execute('INSERT INTO tournament_matches(tournament_id,round_no,match_no,team_a_id,team_b_id) VALUES(?,1,1,1,2)',(tid,)).lastrowid
            c.execute('INSERT INTO active_sessions(channel_id,state_json) VALUES(?,?)',(55,json.dumps({'tournament_id':tid,'match_id':mid})))
        ok,msg=report_match('Active Cup',1,1,200,160)
        self.assertFalse(ok);self.assertIn('recover',msg)
        h=tournament_health('Active Cup')
        self.assertEqual(h['recoverable_channels'],[55])
        with database.connect() as c:c.execute('DELETE FROM active_sessions WHERE channel_id=55')
        self.assertTrue(report_match('Active Cup',1,1,200,160)[0])

    def test_competition_health_flags_corrupt_result_without_mutation(self):
        with database.connect() as c:
            cid=c.execute("INSERT INTO competitions(name,state) VALUES('League','active')").lastrowid
            c.execute("INSERT INTO fixtures(competition_id,round_no,fixture_no,home_id,away_id,status) VALUES(?,1,1,1,2,'complete')",(cid,))
        result=competition_health(cid)
        self.assertTrue(result['issues'])
        self.assertIn('completed without a score',result['issues'][0])
        with database.connect() as c:
            self.assertEqual(c.execute('SELECT status FROM fixtures WHERE competition_id=?',(cid,)).fetchone()[0],'complete')


class AwardAndPostgameTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.patcher=patch.object(database,'DB_PATH',Path(self.temp.name)/'postgame.db')
        self.patcher.start();database.init_db()
        with database.connect() as c:
            c.execute('''INSERT INTO bowlers(id,name,owner_id,rank,accuracy,consistency,spin,nerves,style,flair)
                         VALUES(1,'Dude',1,1,15,15,15,15,15,15)''')
            c.execute('INSERT INTO bowler_stats(bowler_id) VALUES(1)')
    def tearDown(self):self.patcher.stop();self.temp.cleanup()
    def test_manual_award_is_one_time_and_audited(self):
        from services.awards_admin import give_manual_award
        self.assertEqual(give_manual_award(1,'Best Bowler','Great game',99)[0],True)
        self.assertEqual(give_manual_award(1,'Best Bowler','Great game',99)[0],False)
        with database.connect() as c:
            self.assertEqual(c.execute('SELECT awards FROM bowler_stats WHERE bowler_id=1').fetchone()[0],1)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM audit_log WHERE action="award_give"').fetchone()[0],1)
    def test_bad_manual_award_is_rejected(self):
        from services.awards_admin import give_manual_award
        self.assertFalse(give_manual_award(1,'   ')[0])
        self.assertFalse(give_manual_award(1,'a'*61)[0])
        self.assertFalse(give_manual_award(1,'ok','b'*201)[0])
    def test_game_finalisation_awards_debut_only_once(self):
        from models.bowler import Bowler
        from services.game_engine import GameSession
        from services.analytics import player_summary
        from services.postgame import finalize_completed_session
        s=GameSession([Bowler(1,'Dude',1,'R',1,15,15,15,15,15,15)],seed=2902)
        p=s.players[0];p.frames=[[4,5] for _ in range(10)];p.frame=11;p.ball=1;p.standing=set()
        result=finalize_completed_session(s,'test',[(p,player_summary(p))],None,{})
        self.assertTrue(result[-1]);self.assertTrue(any('League Debut' in v for card in result[1] for v in card))
        again=finalize_completed_session(s,'test',[(p,player_summary(p))],None,{})
        self.assertFalse(again[-1])
        with database.connect() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM achievements WHERE bowler_id=1 AND code="debut"').fetchone()[0],1)
            self.assertEqual(c.execute('SELECT games FROM bowler_stats WHERE bowler_id=1').fetchone()[0],1)

if __name__=='__main__':unittest.main()
