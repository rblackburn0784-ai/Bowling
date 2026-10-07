import sqlite3
from contextlib import contextmanager
from config import DB_PATH

SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS bowlers(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL COLLATE NOCASE UNIQUE,owner_id INTEGER NOT NULL,handedness TEXT NOT NULL DEFAULT 'R',rank INTEGER NOT NULL,accuracy INTEGER NOT NULL,style INTEGER NOT NULL,flair INTEGER NOT NULL,consistency INTEGER NOT NULL,spin INTEGER NOT NULL,nerves INTEGER NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS teams(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL COLLATE NOCASE UNIQUE,captain_id INTEGER NOT NULL,flair INTEGER NOT NULL DEFAULT 0,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS team_members(team_id INTEGER NOT NULL,bowler_id INTEGER NOT NULL,slot INTEGER NOT NULL,PRIMARY KEY(team_id,bowler_id),FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE,FOREIGN KEY(bowler_id) REFERENCES bowlers(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS games(id INTEGER PRIMARY KEY AUTOINCREMENT,session_key TEXT NOT NULL,team_a_id INTEGER,team_b_id INTEGER,status TEXT NOT NULL,lane_condition TEXT NOT NULL,seed INTEGER NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP,finished_at TEXT);
CREATE TABLE IF NOT EXISTS game_bowlers(game_id INTEGER NOT NULL,bowler_id INTEGER NOT NULL,team_id INTEGER,position INTEGER NOT NULL,score INTEGER DEFAULT 0,PRIMARY KEY(game_id,bowler_id));
CREATE TABLE IF NOT EXISTS deliveries(id INTEGER PRIMARY KEY AUTOINCREMENT,game_id INTEGER NOT NULL,bowler_id INTEGER NOT NULL,frame INTEGER NOT NULL,ball INTEGER NOT NULL,standing_before TEXT NOT NULL,pins_down TEXT NOT NULL,standing_after TEXT NOT NULL,notation TEXT,quality REAL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS bowler_stats(bowler_id INTEGER PRIMARY KEY,games INTEGER DEFAULT 0,total_pins INTEGER DEFAULT 0,high_game INTEGER DEFAULT 0,strikes INTEGER DEFAULT 0,spares INTEGER DEFAULT 0,splits INTEGER DEFAULT 0,split_conversions INTEGER DEFAULT 0,turkeys INTEGER DEFAULT 0,clean_games INTEGER DEFAULT 0,games_200 INTEGER DEFAULT 0,games_250 INTEGER DEFAULT 0,perfect_games INTEGER DEFAULT 0,awards INTEGER DEFAULT 0,FOREIGN KEY(bowler_id) REFERENCES bowlers(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS series(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,team_a_id INTEGER,team_b_id INTEGER,best_of INTEGER NOT NULL DEFAULT 3,status TEXT NOT NULL DEFAULT 'active',team_a_wins INTEGER DEFAULT 0,team_b_wins INTEGER DEFAULT 0,created_at TEXT DEFAULT CURRENT_TIMESTAMP,finished_at TEXT);
CREATE TABLE IF NOT EXISTS tournaments(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL COLLATE NOCASE UNIQUE,format TEXT NOT NULL DEFAULT 'single_elimination',status TEXT NOT NULL DEFAULT 'registration',lane_condition TEXT NOT NULL DEFAULT 'house',created_at TEXT DEFAULT CURRENT_TIMESTAMP,finished_at TEXT);
CREATE TABLE IF NOT EXISTS tournament_entries(tournament_id INTEGER NOT NULL,team_id INTEGER NOT NULL,seed INTEGER,PRIMARY KEY(tournament_id,team_id));
CREATE TABLE IF NOT EXISTS tournament_matches(id INTEGER PRIMARY KEY AUTOINCREMENT,tournament_id INTEGER NOT NULL,round_no INTEGER NOT NULL,match_no INTEGER NOT NULL,team_a_id INTEGER,team_b_id INTEGER,winner_id INTEGER,status TEXT NOT NULL DEFAULT 'pending',score_a INTEGER,score_b INTEGER,UNIQUE(tournament_id,round_no,match_no));
CREATE TABLE IF NOT EXISTS awards(id INTEGER PRIMARY KEY AUTOINCREMENT,tournament_id INTEGER,bowler_id INTEGER,team_id INTEGER,title TEXT NOT NULL,detail TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS achievements(id INTEGER PRIMARY KEY AUTOINCREMENT,bowler_id INTEGER NOT NULL,code TEXT NOT NULL,title TEXT NOT NULL,detail TEXT,earned_at TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(bowler_id,code));
'''

@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(DB_PATH); con.row_factory=sqlite3.Row; con.execute('PRAGMA foreign_keys=ON')
    try: yield con; con.commit()
    finally: con.close()

def init_db():
    with connect() as con:
        con.executescript(SCHEMA)
        cols={r['name'] for r in con.execute('PRAGMA table_info(bowler_stats)')}
        if 'awards' not in cols: con.execute('ALTER TABLE bowler_stats ADD COLUMN awards INTEGER DEFAULT 0')
    ensure_v25_schema()

def ensure_v22_schema():
    with connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS game_results(id INTEGER PRIMARY KEY AUTOINCREMENT,game_id INTEGER,bowler_id INTEGER NOT NULL,team_id INTEGER,score INTEGER NOT NULL,strikes INTEGER DEFAULT 0,spares INTEGER DEFAULT 0,splits INTEGER DEFAULT 0,split_conversions INTEGER DEFAULT 0,turkeys INTEGER DEFAULT 0,longest_streak INTEGER DEFAULT 0,clean INTEGER DEFAULT 0,pocket_pct REAL DEFAULT 0,tournament_id INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS tournament_bowler_stats(tournament_id INTEGER NOT NULL,bowler_id INTEGER NOT NULL,games INTEGER DEFAULT 0,total_pins INTEGER DEFAULT 0,high_game INTEGER DEFAULT 0,strikes INTEGER DEFAULT 0,spares INTEGER DEFAULT 0,splits INTEGER DEFAULT 0,split_conversions INTEGER DEFAULT 0,turkeys INTEGER DEFAULT 0,clean_games INTEGER DEFAULT 0,PRIMARY KEY(tournament_id,bowler_id));
        ''')

def record_completed_session(session,session_key='discord'):
    from services.analytics import player_summary
    if session.persisted:return None
    ensure_v22_schema()
    with connect() as c:
        gid=c.execute("INSERT INTO games(session_key,status,lane_condition,seed,finished_at) VALUES(?,?,?,?,CURRENT_TIMESTAMP)",(str(session_key),'complete',session.lane,session.seed)).lastrowid
        for pos,p in enumerate(session.players,1):
            s=player_summary(p); team_name=getattr(p.bowler,'team_name',None)
            team_id=None
            if team_name:
                tr=c.execute('SELECT id FROM teams WHERE name=? COLLATE NOCASE',(team_name,)).fetchone();team_id=tr['id'] if tr else None
            c.execute('INSERT INTO game_bowlers(game_id,bowler_id,team_id,position,score) VALUES(?,?,?,?,?)',(gid,p.bowler.id,team_id,pos,s['score']))
            c.execute('''INSERT INTO game_results(game_id,bowler_id,team_id,score,strikes,spares,splits,split_conversions,turkeys,longest_streak,clean,pocket_pct,tournament_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(gid,p.bowler.id,team_id,s['score'],s['strikes'],s['spares'],s['splits'],s['split_conversions'],s['turkeys'],s['longest_streak'],s['clean'],s['pocket_pct'],session.tournament_id))
            c.execute('INSERT OR IGNORE INTO bowler_stats(bowler_id) VALUES(?)',(p.bowler.id,))
            c.execute('''UPDATE bowler_stats SET games=games+1,total_pins=total_pins+?,high_game=MAX(high_game,?),strikes=strikes+?,spares=spares+?,splits=splits+?,split_conversions=split_conversions+?,turkeys=turkeys+?,clean_games=clean_games+?,games_200=games_200+?,games_250=games_250+?,perfect_games=perfect_games+? WHERE bowler_id=?''',(s['score'],s['score'],s['strikes'],s['spares'],s['splits'],s['split_conversions'],s['turkeys'],s['clean'],int(s['score']>=200),int(s['score']>=250),int(s['score']==300),p.bowler.id))
            if session.tournament_id:
                c.execute('INSERT OR IGNORE INTO tournament_bowler_stats(tournament_id,bowler_id) VALUES(?,?)',(session.tournament_id,p.bowler.id))
                c.execute('''UPDATE tournament_bowler_stats SET games=games+1,total_pins=total_pins+?,high_game=MAX(high_game,?),strikes=strikes+?,spares=spares+?,splits=splits+?,split_conversions=split_conversions+?,turkeys=turkeys+?,clean_games=clean_games+? WHERE tournament_id=? AND bowler_id=?''',(s['score'],s['score'],s['strikes'],s['spares'],s['splits'],s['split_conversions'],s['turkeys'],s['clean'],session.tournament_id,p.bowler.id))
        session.persisted=True
        return gid

def career_row(name):
    ensure_v22_schema()
    with connect() as c:return c.execute('''SELECT b.name,s.*,CASE WHEN s.games=0 THEN 0 ELSE s.total_pins*1.0/s.games END avg FROM bowlers b LEFT JOIN bowler_stats s ON s.bowler_id=b.id WHERE b.name=? COLLATE NOCASE''',(name,)).fetchone()

def tournament_leaders(name):
    ensure_v22_schema()
    with connect() as c:
        t=c.execute('SELECT id,name FROM tournaments WHERE name=? COLLATE NOCASE',(name,)).fetchone()
        if not t:return None,[]
        rows=c.execute('''SELECT b.name,s.*,s.total_pins*1.0/NULLIF(s.games,0) avg FROM tournament_bowler_stats s JOIN bowlers b ON b.id=s.bowler_id WHERE s.tournament_id=? ORDER BY avg DESC,total_pins DESC''',(t['id'],)).fetchall();return t,rows

V25_SCHEMA='''
CREATE TABLE IF NOT EXISTS seasons(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL UNIQUE,status TEXT NOT NULL DEFAULT 'draft',started_at TEXT,ended_at TEXT,archived_at TEXT);
CREATE TABLE IF NOT EXISTS bowler_progression(bowler_id INTEGER PRIMARY KEY,xp INTEGER DEFAULT 0,credits INTEGER DEFAULT 0,spent INTEGER DEFAULT 0,FOREIGN KEY(bowler_id) REFERENCES bowlers(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS game_history(id INTEGER PRIMARY KEY AUTOINCREMENT,game_id INTEGER,bowler_id INTEGER,season_id INTEGER,tournament_id INTEGER,team_id INTEGER,score INTEGER,strikes INTEGER,spares INTEGER,splits INTEGER,split_conversions INTEGER,longest_streak INTEGER,clean INTEGER,form REAL DEFAULT 0,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS team_history(team_id INTEGER PRIMARY KEY,wins INTEGER DEFAULT 0,losses INTEGER DEFAULT 0,championships INTEGER DEFAULT 0,finals INTEGER DEFAULT 0,high_game INTEGER DEFAULT 0,high_series INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS roster_history(id INTEGER PRIMARY KEY AUTOINCREMENT,team_id INTEGER,bowler_id INTEGER,action TEXT,slot INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS head_to_head(id INTEGER PRIMARY KEY AUTOINCREMENT,team_a_id INTEGER,team_b_id INTEGER,winner_id INTEGER,score_a INTEGER,score_b INTEGER,tournament_id INTEGER,match_id INTEGER,played_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY AUTOINCREMENT,actor_id INTEGER NOT NULL,action TEXT NOT NULL,target_type TEXT,target_id INTEGER,detail TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS match_snapshots(id INTEGER PRIMARY KEY AUTOINCREMENT,channel_id INTEGER NOT NULL,match_id INTEGER,label TEXT,state_json TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS active_sessions(channel_id INTEGER PRIMARY KEY,state_json TEXT NOT NULL,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS predictions(id INTEGER PRIMARY KEY AUTOINCREMENT,tournament_id INTEGER,match_id INTEGER,user_id INTEGER NOT NULL,team_id INTEGER NOT NULL,points INTEGER DEFAULT 0,created_at TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(match_id,user_id));
CREATE TABLE IF NOT EXISTS tournament_stories(id INTEGER PRIMARY KEY AUTOINCREMENT,tournament_id INTEGER,match_id INTEGER,kind TEXT,headline TEXT,detail TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS gazette_issues(id INTEGER PRIMARY KEY AUTOINCREMENT,tournament_id INTEGER,issue_no INTEGER NOT NULL,headline TEXT NOT NULL,lead TEXT NOT NULL,body TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(tournament_id,issue_no));
CREATE TABLE IF NOT EXISTS bot_settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS bowler_presentation(bowler_id INTEGER PRIMARY KEY,primary_ball TEXT NOT NULL DEFAULT 'hybrid',avatar_url TEXT,FOREIGN KEY(bowler_id) REFERENCES bowlers(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS team_presentation(team_id INTEGER PRIMARY KEY,logo_url TEXT,FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS tournament_presentation(tournament_id INTEGER PRIMARY KEY,layout TEXT NOT NULL DEFAULT 'broadcast',lane_start INTEGER NOT NULL DEFAULT 3,brand_title TEXT,background_url TEXT,FOREIGN KEY(tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS bowler_origins(bowler_id INTEGER PRIMARY KEY,accuracy INTEGER NOT NULL,consistency INTEGER NOT NULL,spin INTEGER NOT NULL,nerves INTEGER NOT NULL,style INTEGER NOT NULL,flair INTEGER NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);\nCREATE TABLE IF NOT EXISTS career_tendencies(bowler_id INTEGER NOT NULL,stat TEXT NOT NULL,score REAL NOT NULL DEFAULT 0,evidence INTEGER NOT NULL DEFAULT 0,updated_at TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(bowler_id,stat),FOREIGN KEY(bowler_id) REFERENCES bowlers(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS career_honours(id INTEGER PRIMARY KEY AUTOINCREMENT,bowler_id INTEGER NOT NULL,tournament_id INTEGER,code TEXT NOT NULL,title TEXT NOT NULL,detail TEXT,placing INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP,UNIQUE(bowler_id,tournament_id,code),FOREIGN KEY(bowler_id) REFERENCES bowlers(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS career_timeline(id INTEGER PRIMARY KEY AUTOINCREMENT,bowler_id INTEGER NOT NULL,kind TEXT NOT NULL,icon TEXT NOT NULL,headline TEXT NOT NULL,detail TEXT,source TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(bowler_id) REFERENCES bowlers(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS attribute_history(id INTEGER PRIMARY KEY AUTOINCREMENT,bowler_id INTEGER NOT NULL,stat TEXT NOT NULL,delta INTEGER NOT NULL,old_value INTEGER NOT NULL,new_value INTEGER NOT NULL,reason TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(bowler_id) REFERENCES bowlers(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS competitions(id INTEGER PRIMARY KEY AUTOINCREMENT,season_id INTEGER,name TEXT NOT NULL,kind TEXT NOT NULL DEFAULT 'league',format TEXT NOT NULL DEFAULT 'round_robin',entrant_type TEXT NOT NULL DEFAULT 'team',state TEXT NOT NULL DEFAULT 'draft',lane_condition TEXT NOT NULL DEFAULT 'house',points_win INTEGER NOT NULL DEFAULT 3,points_draw INTEGER NOT NULL DEFAULT 1,points_loss INTEGER NOT NULL DEFAULT 0,playoff_size INTEGER DEFAULT 0,promotion_slots INTEGER DEFAULT 0,relegation_slots INTEGER DEFAULT 0,template_id INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP,started_at TEXT,completed_at TEXT,archived_at TEXT,UNIQUE(season_id,name));
CREATE TABLE IF NOT EXISTS competition_entries(competition_id INTEGER NOT NULL,entrant_id INTEGER NOT NULL,seed INTEGER,group_name TEXT,registered_at TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(competition_id,entrant_id),FOREIGN KEY(competition_id) REFERENCES competitions(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS competition_rosters(competition_id INTEGER NOT NULL,team_id INTEGER NOT NULL,bowler_id INTEGER NOT NULL,slot INTEGER NOT NULL,is_substitute INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(competition_id,team_id,bowler_id),FOREIGN KEY(competition_id) REFERENCES competitions(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS competition_stages(id INTEGER PRIMARY KEY AUTOINCREMENT,competition_id INTEGER NOT NULL,stage_no INTEGER NOT NULL,name TEXT NOT NULL,format TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',qualify_count INTEGER DEFAULT 0,best_of INTEGER NOT NULL DEFAULT 1,UNIQUE(competition_id,stage_no),FOREIGN KEY(competition_id) REFERENCES competitions(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS fixtures(id INTEGER PRIMARY KEY AUTOINCREMENT,competition_id INTEGER NOT NULL,stage_id INTEGER,round_no INTEGER NOT NULL DEFAULT 1,fixture_no INTEGER NOT NULL,home_id INTEGER,away_id INTEGER,status TEXT NOT NULL DEFAULT 'scheduled',home_score INTEGER,away_score INTEGER,winner_id INTEGER,series_best_of INTEGER NOT NULL DEFAULT 1,scheduled_for TEXT,played_at TEXT,UNIQUE(competition_id,stage_id,round_no,fixture_no),FOREIGN KEY(competition_id) REFERENCES competitions(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS competition_standings(competition_id INTEGER NOT NULL,entrant_id INTEGER NOT NULL,played INTEGER NOT NULL DEFAULT 0,wins INTEGER NOT NULL DEFAULT 0,draws INTEGER NOT NULL DEFAULT 0,losses INTEGER NOT NULL DEFAULT 0,pins_for INTEGER NOT NULL DEFAULT 0,pins_against INTEGER NOT NULL DEFAULT 0,points INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(competition_id,entrant_id),FOREIGN KEY(competition_id) REFERENCES competitions(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS season_bowler_stats(season_id INTEGER NOT NULL,bowler_id INTEGER NOT NULL,games INTEGER NOT NULL DEFAULT 0,total_pins INTEGER NOT NULL DEFAULT 0,high_game INTEGER NOT NULL DEFAULT 0,strikes INTEGER NOT NULL DEFAULT 0,spares INTEGER NOT NULL DEFAULT 0,split_conversions INTEGER NOT NULL DEFAULT 0,championships INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(season_id,bowler_id));
CREATE TABLE IF NOT EXISTS league_templates(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL UNIQUE,format TEXT NOT NULL DEFAULT 'round_robin',entrant_type TEXT NOT NULL DEFAULT 'team',lane_condition TEXT NOT NULL DEFAULT 'house',points_win INTEGER NOT NULL DEFAULT 3,points_draw INTEGER NOT NULL DEFAULT 1,points_loss INTEGER NOT NULL DEFAULT 0,playoff_size INTEGER DEFAULT 0,promotion_slots INTEGER DEFAULT 0,relegation_slots INTEGER DEFAULT 0,recurrence TEXT);
'''

def ensure_v25_schema():
    ensure_v22_schema()
    with connect() as c:
        c.executescript(V25_SCHEMA)
        cols={r['name'] for r in c.execute('PRAGMA table_info(tournaments)')}
        if 'season_id' not in cols:c.execute('ALTER TABLE tournaments ADD COLUMN season_id INTEGER')
        if 'announcer' not in cols:c.execute("ALTER TABLE tournaments ADD COLUMN announcer TEXT DEFAULT 'saints'")
        if 'paused' not in cols:c.execute('ALTER TABLE tournaments ADD COLUMN paused INTEGER DEFAULT 0')
        c.execute('INSERT OR IGNORE INTO bowler_origins(bowler_id,accuracy,consistency,spin,nerves,style,flair) SELECT id,accuracy,consistency,spin,nerves,style,flair FROM bowlers')
