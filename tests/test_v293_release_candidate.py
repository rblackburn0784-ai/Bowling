"""v2.9.3 release-candidate gates: physics causality, visual and save recovery."""
import io
import math
import random
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from services.analytics import player_summary
from storage import database
from services import v25

from PIL import Image
from models.bowler import Bowler
from services import scene_renderer as scene
from services import impact_model, postgame
from services.ball_sprites import path_points
from services.equipment import get_ball
from services.game_engine import GameSession
from services.impact_model import impact_geometry, pinfall
from services.lane_physics import LaneState
from services.pin_engine import ALL, PINS, roll_pins
from services.scoring import score_game
from services.shot_animation import DURATION_SECONDS,ANIMATION_SEQUENCE
from services.v25 import session_dict, session_from_dict


def mk_bowler(ident=1,stats=30,hand='R'):
    return Bowler(id=ident,name=f'RC Bowler {ident}',owner_id=ident,
                  accuracy=stats,consistency=stats,spin=stats,
                  nerves=stats,style=stats,flair=stats,
                  handedness=hand)


class PhysicsReleaseGates(unittest.TestCase):
    def test_new_matches_use_explicit_version_and_saved_290_keeps_exact_old_model(self):
        from services.legacy_v290_pin_engine import roll_pins as frozen
        from services.legacy_v290_impact_model import impact_geometry as old_geometry
        src=Path(__file__).resolve().parents[1]
        self.assertEqual(GameSession([mk_bowler()],seed=3).physics_version,'2.9.6')
        self.assertNotEqual(impact_geometry.__code__.co_code,old_geometry.__code__.co_code)
        a=GameSession([mk_bowler()],seed=431,lane='dry');a.physics_version='2.9.0'
        for _ in range(6):a.bowl()
        raw=session_dict(a)
        b=session_from_dict(deepcopy(raw))
        self.assertEqual(b.physics_version,'2.9.0')
        while not a.complete:
            x,y=a.bowl(),b.bowl()
            for field in ('down','after','physics','lane_no','pins'):
                self.assertEqual(x[field],y[field],field)
        self.assertEqual(a.scores(),b.scores())
        self.assertEqual(a.rng.getstate(),b.rng.getstate())
        # Old model is copied, not a delegating wrapper to the revised engine.
        self.assertIn('def roll_pins(', (src/'services/legacy_v290_pin_engine.py').read_text(encoding='utf-8'))
        self.assertIsNot(frozen,roll_pins)

    def test_geometry_physically_uses_hook_oil_entry_speed_revs_line_and_hand(self):
        ball=get_ball('hybrid');lane=LaneState(3,'house')
        m={'entry_angle':4.7,'speed':16,'revs':320}
        original=impact_geometry(0,m,ball,lane,1)
        lane.oil=.20;lane.middle=.8
        burnt=impact_geometry(0,m,ball,lane,1)
        self.assertNotEqual(original['impact_x'],burnt['impact_x'])
        self.assertNotEqual(burnt['impact_x'],impact_geometry(0,m,ball,lane,1,2)['impact_x'])
        self.assertNotEqual(burnt['impact_x'],impact_geometry(0,m,get_ball('plastic'),lane,1)['impact_x'])
        change=dict(m,entry_angle=7.5,revs=490)
        rotated=impact_geometry(0,change,ball,lane,1)
        self.assertNotEqual(burnt['deflection'],rotated['deflection'])
        self.assertNotEqual(burnt['carry_factor'],rotated['carry_factor'])
        self.assertLess(impact_geometry(0,dict(m,speed=30),ball,lane,1)['carry_factor'],
                        original['carry_factor'])
        mirrored=impact_geometry(0,m,ball,lane,-1)
        self.assertAlmostEqual(burnt['impact_x'],-mirrored['impact_x'],places=3)
        self.assertAlmostEqual(original['deflection'],-mirrored['deflection'],places=3)

    def test_old_tournament_rolloff_never_switches_to_new_physics(self):
        a=mk_bowler(1,25);b=mk_bowler(2,25,'L')
        a.team_name='Blue';b.team_name='Red'
        match=GameSession([a,b],seed=1975)
        match.physics_version='2.9.0'
        totals={'Blue':150,'Red':150}
        summaries=[(p,{}) for p in match.players]
        with patch.object(postgame,'roll_pins',side_effect=AssertionError('Wrong physics version')):
            winner,rounds=postgame.tournament_rolloff(match,summaries,totals)
        self.assertIn(winner,totals)
        self.assertTrue(rounds)
        self.assertEqual((winner,rounds),postgame.tournament_rolloff(
            session_from_dict(session_dict(match)),summaries,totals))

    def test_energetic_carry_is_not_automatic_ten_pin_strike(self):
        geometry={'impact_x':.46,'carry_factor':1,'deflection':.12}
        counts=[]
        for seed in range(250):
            down,order=pinfall(random.Random(seed),ALL,PINS,.78,geometry,power_carry=True)
            self.assertEqual(set(order),down)
            counts.append(len(down))
        self.assertLess(sum(x==10 for x in counts),len(counts))
        self.assertGreater(sum(x==10 for x in counts),0)
        self.assertGreater(sum(counts)/len(counts),6)

    def test_separated_spare_pins_rarely_fall_together(self):
        geometry={'impact_x':-3,'carry_factor':.85,'deflection':.03}
        leaves={7,10}
        clears=0
        for seed in range(1000):
            knocked,_=pinfall(random.Random(seed),leaves,PINS,.82,geometry,spare=True)
            self.assertTrue(knocked<=leaves)
            clears+=knocked==leaves
        self.assertLess(clears,25,'Unconnected 7–10 split too easy')

    def test_pin_location_changes_results_even_with_same_random_stream(self):
        geometry={'impact_x':0,'carry_factor':.96,'deflection':0}
        far={'impact_x':3.7,'carry_factor':.96,'deflection':0}
        total_near=total_far=0
        for seed in range(150):
            d,_=pinfall(random.Random(seed),ALL,PINS,.76,geometry)
            e,_=pinfall(random.Random(seed),ALL,PINS,.76,far)
            total_near+=len(d);total_far+=len(e)
        self.assertGreater(total_near,total_far)

    def test_entire_run_stays_scoring_legal_and_replay_deterministic(self):
        a=GameSession([mk_bowler(1,26),mk_bowler(2,37,'L')],seed=90293,lane='oily')
        for _ in range(8):a.bowl()
        b=session_from_dict(session_dict(a))
        self.assertEqual(b.session_uid,a.session_uid)
        while not a.complete:
            x=a.bowl();y=b.bowl()
            self.assertEqual(x,y)
            self.assertEqual(set(x['before'])-set(x['down']),set(x['after']))
            self.assertEqual(set(x['physics']['contact_order']),set(x['down']))
        self.assertEqual(a.scores(),b.scores())
        self.assertTrue(all(0<=score<=300 for score in a.scores().values()))

    def test_two_pin_baby_split_aims_at_gap_but_wide_7_10_does_not(self):
        hits=0;total=240
        for seed in range(total):
            down,_,info=roll_pins(random.Random(seed),mk_bowler(stats=50),
                                  {2,3},ball_key='plastic',target_mode='spare')
            self.assertTrue(info['aim_gap'])
            self.assertAlmostEqual(info['pocket_x'],0.0)
            if down=={2,3}:hits+=1
        self.assertGreater(hits,20)
        _,_,far=roll_pins(random.Random(43),mk_bowler(stats=50),
                          {7,10},ball_key='plastic',target_mode='spare')
        self.assertFalse(far['aim_gap'])
        self.assertNotEqual(far['pocket_x'],0.0)

    def test_spare_after_zero_is_not_strike_with_full_rack(self):
        class FixedRng:
            def gauss(self,mu,sigma):return mu
            def random(self):return .5
        down,quality,physics=roll_pins(FixedRng(),mk_bowler(),ALL,target_mode='spare')
        self.assertEqual(physics['aim_pin'],1)
        self.assertEqual(physics['target'],1)
        self.assertFalse(physics['power_carry'])


class BroadcastReleaseGates(unittest.TestCase):
    def setUp(self):
        self.event={'before':list(ALL),'down':[1,2,4,7,10],
                    'after':[3,5,6,8,9],
                    'physics':{'contact_order':[1,2,4,7,10]},
                    'bowler_id':1,'frame':1,'ball':1,'bowler':'RC Bowler'}

    def test_regulation_formation_and_camera_regions_unchanged(self):
        from services.hybrid_broadcast import HERO_BOX,OVERHEAD_BOX,PIT_BOX
        self.assertEqual(HERO_BOX,(0,0,422,750))
        self.assertEqual(OVERHEAD_BOX,(432,0,850,365))
        self.assertEqual(PIT_BOX,(432,377,850,750))
        self.assertEqual(len(scene.CAMERA_OVERHEAD),10)
        for row,ids in ((.300,(7,8,9,10)),(.423,(4,5,6)),(.546,(2,3)),(.669,(1,))):
            self.assertTrue(all(scene.CAMERA_OVERHEAD[p][1]==row for p in ids))
        self.assertEqual(len(scene.CAMERA_PIT),10)

    def test_all_three_camera_pins_use_same_fall_progress(self):
        import unittest.mock as mock
        hero={};overhead={};pit={}
        for frame in range(1,6):
            seen={};seen_right=[]
            with patch.object(scene,'_fall',side_effect=lambda base,view,p,progress,pos=None:seen.__setitem__(p,progress)),\
                 patch.object(scene,'_upright'),\
                 patch.object(scene,'_camera_pin',side_effect=lambda img,view,p,progress=None:seen_right.append((view,p,progress))),\
                 patch.object(scene,'_camera_background',side_effect=lambda name:Image.new('RGBA',(1254,1254))),\
                 patch.object(scene,'_pin',return_value=None):
                scene.pin_layers(Image.new('RGBA',(941,1672)),self.event,'impact',frame,
                                 views=('vertical',),front_positions=scene.HERO_FRONT)
                scene.right_cameras(self.event,'impact',frame)
            for p in self.event['down']:
                expected=scene.pin_impact_progress(self.event,p,frame)
                self.assertEqual(seen[p],expected)
                self.assertEqual(next(progress for cam,pin,progress in seen_right if cam=='overhead' and pin==p),expected)
                self.assertEqual(next(progress for cam,pin,progress in seen_right if cam=='pit' and pin==p),expected)

    def test_image_render_cannot_consume_physics_rng(self):
        s=GameSession([mk_bowler()],seed=933)
        event=s.bowl()
        with tempfile.TemporaryDirectory() as d,\
             patch.object(scene,'BG',Path(d)/'test.png'):
            Image.new('RGBA',(941,1672),(82,52,36)).save(scene.BG)
            scene._background.cache_clear()
            before=s.rng.getstate()
            picture=scene.render_scene_image(s,event,'impact',ball_frame=5)
            self.assertIsNotNone(picture)
            self.assertEqual(picture.size,(850,750))
            self.assertEqual(s.rng.getstate(),before)
            scene._background.cache_clear()

    def test_animation_time_and_frame_count_are_frozen(self):
        self.assertEqual(len(ANIMATION_SEQUENCE),23)
        self.assertAlmostEqual(DURATION_SECONDS,2.795)


class DatabaseRecoveryGates(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        root=Path(self.temp.name)
        self.dbpath=root/'production-like.db'
        self.patchers=(patch.object(database,'DB_PATH',self.dbpath),
                       patch.object(v25,'DB_PATH',self.dbpath),
                       patch.object(v25,'BACKUP_DIR',root/'backup'))
        for p in self.patchers:p.start()
        database.init_db()
        with database.connect() as c:
            for ident in (1,2):
                c.execute("""INSERT INTO bowlers(id,name,owner_id,handedness,rank,accuracy,consistency,spin,nerves,style,flair)
                             VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                          (ident,f'RC Bowler {ident}',ident,'R',1,30,30,30,30,30,30))

    def tearDown(self):
        for p in reversed(self.patchers):p.stop()
        self.temp.cleanup()

    def _finished(self,seed=55):
        session=GameSession([mk_bowler(1,30),mk_bowler(2,30)],seed=seed)
        while not session.complete:session.bowl()
        summaries=[(p,player_summary(p)) for p in session.players]
        return session,summaries

    def test_restart_and_repeated_finalisation_never_double_counts(self):
        s,summaries=self._finished()
        from services.postgame import finalize_completed_session
        first=finalize_completed_session(s,891,summaries,None,{})
        self.assertTrue(first[-1])
        again=finalize_completed_session(session_from_dict(session_dict(s)),891,summaries,None,{})
        self.assertFalse(again[-1])
        self.assertEqual(first[0],again[0])
        with database.connect() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM games').fetchone()[0],1)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM game_finalizations').fetchone()[0],1)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM game_history').fetchone()[0],2)
            self.assertEqual([r['games'] for r in c.execute('SELECT games FROM bowler_stats ORDER BY bowler_id')],[1,1])

    def test_injected_postgame_exception_rolls_back_base_game_and_career(self):
        s,summaries=self._finished(seed=97)
        from services.postgame import finalize_completed_session
        with patch.object(postgame,'unlock_career_milestones',side_effect=RuntimeError('injected failure')):
            with self.assertRaisesRegex(RuntimeError,'injected failure'):
                finalize_completed_session(s,892,summaries,None,{})
        with database.connect() as c:
            for table in ('games','game_results','game_history','game_finalizations','bowler_progression'):
                self.assertEqual(c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0],0,table)
        self.assertFalse(s.persisted)
        self.assertTrue(finalize_completed_session(s,892,summaries,None,{})[-1])

    def test_wal_backup_and_restore_preserve_rows(self):
        import sqlite3
        with database.connect() as c:
            c.execute('PRAGMA journal_mode=WAL')
            c.execute('UPDATE bowlers SET rank=17 WHERE id=1')
        backup=v25.backup_database('rc_wal')
        self.assertTrue(backup.is_file())
        from contextlib import closing
        with closing(sqlite3.connect(backup)) as c:
            self.assertEqual(c.execute('PRAGMA quick_check').fetchone()[0],'ok')
            self.assertEqual(c.execute('SELECT rank FROM bowlers WHERE id=1').fetchone()[0],17)
        self.assertNotEqual(str(backup),str(self.dbpath))

    def test_in_progress_undo_and_restore_keep_version_and_pin_state(self):
        from services.v25 import prepare_new_session,save_snapshot,undo_snapshot,restore_session
        s=GameSession([mk_bowler(1,30)],seed=29345)
        prepare_new_session(3991)
        save_snapshot(3991,s,'start')
        save_snapshot(3991,s,'pre_ball')
        x=s.bowl()
        save_snapshot(3991,s,'post_ball')
        restored=restore_session(3991)
        self.assertEqual(restored.physics_version,'2.9.6')
        self.assertEqual(restored.ball_count,1)
        previous=undo_snapshot(3991)
        self.assertEqual(previous.ball_count,0)
        self.assertEqual(previous.physics_version,'2.9.6')
        self.assertEqual(previous.bowl(),x)


if __name__=='__main__':unittest.main()
