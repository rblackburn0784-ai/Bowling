import contextlib,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from services import season_gazette
from services.gazette_artwork import render_issue

class GazetteTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=str(Path(self.tmp.name)/'gazette.db')
  with self.connection() as db:
   db.executescript("""
    CREATE TABLE seasons(id INTEGER PRIMARY KEY,name TEXT,status TEXT);
    CREATE TABLE bowlers(id INTEGER PRIMARY KEY,name TEXT);
    CREATE TABLE game_history(id INTEGER PRIMARY KEY,season_id INTEGER,bowler_id INTEGER,score INTEGER,created_at TEXT);
    CREATE TABLE competitions(id INTEGER PRIMARY KEY,season_id INTEGER,name TEXT);
    CREATE TABLE fixtures(id INTEGER PRIMARY KEY,competition_id INTEGER,status TEXT,played_at TEXT,round_no INTEGER,home_score INTEGER,away_score INTEGER);
    CREATE TABLE season_gazette_issues(id INTEGER PRIMARY KEY AUTOINCREMENT,season_id INTEGER NOT NULL,issue_no INTEGER NOT NULL,week_start TEXT NOT NULL,week_end TEXT NOT NULL,headline TEXT NOT NULL,body TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(season_id,week_start),UNIQUE(season_id,issue_no));
    INSERT INTO seasons VALUES(1,'Test Season','active');
    INSERT INTO bowlers VALUES(1,'TheDude');
    INSERT INTO game_history VALUES(1,1,1,225,'2026-10-05 18:00:00');
    INSERT INTO competitions VALUES(1,1,'League A');
    INSERT INTO fixtures VALUES(1,1,'complete','2026-10-06 18:00:00',1,1100,1050);
   """)
  self.patch=patch.object(season_gazette,'connect',self.connection);self.patch.start()
 def tearDown(self):self.patch.stop();self.tmp.cleanup()
 @contextlib.contextmanager
 def connection(self):
  db=sqlite3.connect(self.path);db.row_factory=sqlite3.Row
  try:
   yield db
   db.commit()
  finally:db.close()
 def test_duplicate_and_archive(self):
  first,created=season_gazette.publish(1,'2026-10-07')
  self.assertTrue(created);self.assertEqual(first['issue_no'],1)
  again,created=season_gazette.publish(1,'2026-10-08')
  self.assertFalse(created);self.assertEqual(first['id'],again['id'])
  self.assertEqual(len(season_gazette.archive(1)),1)
 def test_historical_issue_immutable(self):
  first,_=season_gazette.publish(1,'2026-10-07')
  with self.connection() as db:db.execute("UPDATE game_history SET score=300 WHERE id=1")
  again,_=season_gazette.publish(1,'2026-10-08')
  self.assertEqual(first['body'],again['body'])
  self.assertEqual(first,season_gazette.get_issue(1,1))
 def test_second_week_and_artwork(self):
  first,_=season_gazette.publish(1,'2026-10-07')
  second,created=season_gazette.publish(1,'2026-10-14')
  self.assertTrue(created);self.assertEqual(second['issue_no'],2)
  self.assertGreater(len(render_issue(first).getvalue()),1000)
 def test_missing_season(self):
  with self.assertRaises(ValueError):season_gazette.publish(999,'2026-10-07')
 def test_permission_guard_present(self):
  source=Path(__file__).resolve().parents[1].joinpath('cogs','season_ui.py').read_text()
  self.assertIn('guild_permissions.manage_guild',source)

if __name__=='__main__':unittest.main()
