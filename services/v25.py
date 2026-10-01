import csv, io, json, shutil, time
from datetime import datetime
from pathlib import Path
from config import DB_PATH, ROOT
from storage.database import connect
from models.bowler import Bowler
from services.game_engine import GameSession, BowlerGame
BACKUP_DIR=ROOT/'data'/'backups'; EXPORT_DIR=ROOT/'data'/'exports'
def backup_database(reason='change'):
    BACKUP_DIR.mkdir(parents=True,exist_ok=True)
    if not DB_PATH.exists(): return None
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S_%f');dest=BACKUP_DIR/f'gutter_saints_{stamp}_{reason.replace(" ","_")[:24]}.db';shutil.copy2(DB_PATH,dest); return dest
def audit(actor_id,action,target_type='',target_id=None,detail=''):
    with connect() as c:c.execute('INSERT INTO audit_log(actor_id,action,target_type,target_id,detail) VALUES(?,?,?,?,?)',(actor_id,action,target_type,target_id,detail))
def archetype(b):
    vals={'Power Player':b.rank+b.flair*.25,'Shot Maker':b.accuracy+b.consistency*.35,'Spinner':b.spin+b.style*.25,'Clutch Bowler':b.nerves+b.consistency*.25,'Showman':b.style+b.flair*.8,'Steady Hand':b.consistency+b.accuracy*.3};return max(vals,key=vals.get)
def session_dict(s):
    return {'seed':s.seed,'lane':s.lane,'turn':s.turn,'tournament_id':s.tournament_id,'match_id':s.match_id,'persisted':s.persisted,'ball_count':getattr(s,'ball_count',0),'players':[{'bowler':{k:getattr(p.bowler,k) for k in ['id','name','owner_id','handedness','rank','accuracy','style','flair','consistency','spin','nerves','team_name']},'frames':p.frames,'standing':sorted(p.standing),'frame':p.frame,'ball':p.ball,'split_leave':p.split_leave,'split_frames':sorted(p.split_frames),'split_conversions':sorted(p.split_conversions),'strike_streak':p.strike_streak,'max_strike_streak':p.max_strike_streak,'form':getattr(p,'form',0.0),'special_conversions':sorted(getattr(p,'special_conversions',set()))} for p in s.players]}
def session_from_dict(d):
    bowlers=[]
    for x in d['players']:
        bd=x['bowler']; team=bd.pop('team_name',None); b=Bowler(**bd); b.team_name=team; bowlers.append(b)
    s=GameSession(bowlers,d['seed'],d['lane'],d.get('tournament_id'),d.get('match_id'));s.turn=d['turn'];s.persisted=d.get('persisted',False);s.ball_count=d.get('ball_count',0)
    for p,x in zip(s.players,d['players']):
        p.frames=x['frames'];p.standing=set(x['standing']);p.frame=x['frame'];p.ball=x['ball'];p.split_leave=x.get('split_leave',False);p.split_frames=set(x.get('split_frames',[]));p.split_conversions=set(x.get('split_conversions',[]));p.strike_streak=x.get('strike_streak',0);p.max_strike_streak=x.get('max_strike_streak',0);p.form=x.get('form',0.0);p.special_conversions=set(x.get('special_conversions',[]))
    return s
def save_snapshot(channel_id,s,label='ball'):
    payload=json.dumps(session_dict(s),separators=(',',':'))
    with connect() as c:c.execute('INSERT INTO match_snapshots(channel_id,match_id,label,state_json) VALUES(?,?,?,?)',(channel_id,s.match_id,label,payload));c.execute('INSERT INTO active_sessions(channel_id,state_json,updated_at) VALUES(?,?,CURRENT_TIMESTAMP) ON CONFLICT(channel_id) DO UPDATE SET state_json=excluded.state_json,updated_at=CURRENT_TIMESTAMP',(channel_id,payload))
def undo_snapshot(channel_id):
    with connect() as c:
        rows=c.execute('SELECT id,state_json FROM match_snapshots WHERE channel_id=? ORDER BY id DESC LIMIT 2',(channel_id,)).fetchall()
        if len(rows)<2:return None
        c.execute('DELETE FROM match_snapshots WHERE id=?',(rows[0]['id'],)); payload=rows[1]['state_json'];c.execute('UPDATE active_sessions SET state_json=?,updated_at=CURRENT_TIMESTAMP WHERE channel_id=?',(payload,channel_id))
    return session_from_dict(json.loads(payload))
def restore_session(channel_id):
    with connect() as c:r=c.execute('SELECT state_json FROM active_sessions WHERE channel_id=?',(channel_id,)).fetchone()
    return session_from_dict(json.loads(r['state_json'])) if r else None
def clear_session(channel_id):
    with connect() as c:c.execute('DELETE FROM active_sessions WHERE channel_id=?',(channel_id,))
def unlock_achievements(bowler_id,summary,extra=None):
    extra=extra or {}; defs=[]
    if summary['strikes']>=1:defs.append(('first_strike','First Strike','Recorded a first career strike.'))
    if summary['longest_streak']>=3:defs.append(('turkey','Turkey','Three consecutive strikes.'))
    if summary['longest_streak']>=6:defs.append(('six_pack','Six-Pack','Six consecutive strikes.'))
    if summary['clean']:defs.append(('clean_sheet','Clean Sheet','Completed a game without an open frame.'))
    if summary['score']>=200:defs.append(('club_200','200 Club','Rolled a 200+ game.'))
    if summary['score']>=250:defs.append(('club_250','250 Club','Rolled a 250+ game.'))
    if summary['score']==300:defs.append(('perfect_300','Perfect 300','Bowled a perfect game.'))
    if summary['split_conversions']>=2:defs.append(('split_personality','Split Personality','Converted two or more splits in one game.'))
    if extra.get('seven_ten'):defs.append(('seven_ten','7–10 Miracle','Converted the 7–10 split.'))
    if extra.get('comeback'):defs.append(('comeback_kid','Comeback Kid','Won after trailing late.'))
    if extra.get('champion'):defs.append(('champion','Tournament Champion','Won a Gutter Saints tournament.'))
    new=[]
    with connect() as c:
        for code,title,detail in defs:
            cur=c.execute('INSERT OR IGNORE INTO achievements(bowler_id,code,title,detail) VALUES(?,?,?,?)',(bowler_id,code,title,detail))
            if cur.rowcount:new.append((title,detail))
    return new
def award_progression(bowler_id,score,tournament=False,won=False):
    xp=10+score//25+(10 if tournament else 0)+(10 if won else 0); credits=1+(1 if score>=200 else 0)+(1 if won else 0)
    with connect() as c:c.execute('INSERT OR IGNORE INTO bowler_progression(bowler_id) VALUES(?)',(bowler_id,));c.execute('UPDATE bowler_progression SET xp=xp+?,credits=MIN(20,credits+?) WHERE bowler_id=?',(xp,credits,bowler_id))
    return xp,credits
def tournament_dashboard(name=None):
    with connect() as c:
        t=c.execute("SELECT * FROM tournaments WHERE name=? COLLATE NOCASE",(name,)).fetchone() if name else c.execute("SELECT * FROM tournaments WHERE status IN ('active','paused') ORDER BY id DESC LIMIT 1").fetchone()
        if not t:return None
        matches=c.execute('''SELECT m.*,a.name team_a,b.name team_b,w.name winner FROM tournament_matches m LEFT JOIN teams a ON a.id=m.team_a_id LEFT JOIN teams b ON b.id=m.team_b_id LEFT JOIN teams w ON w.id=m.winner_id WHERE m.tournament_id=? ORDER BY round_no,match_no''',(t['id'],)).fetchall();nextm=next((x for x in matches if x['status']=='pending' and x['team_a_id'] and x['team_b_id']),None);leaders=c.execute('''SELECT b.name,s.games,s.high_game,s.total_pins*1.0/NULLIF(s.games,0) avg FROM tournament_bowler_stats s JOIN bowlers b ON b.id=s.bowler_id WHERE s.tournament_id=? ORDER BY avg DESC LIMIT 5''',(t['id'],)).fetchall();return t,matches,nextm,leaders
def head_to_head(a,b):
    with connect() as c:
        ta=c.execute('SELECT id FROM teams WHERE name=? COLLATE NOCASE',(a,)).fetchone();tb=c.execute('SELECT id FROM teams WHERE name=? COLLATE NOCASE',(b,)).fetchone()
        if not ta or not tb:return None
        return c.execute('SELECT * FROM head_to_head WHERE (team_a_id=? AND team_b_id=?) OR (team_a_id=? AND team_b_id=?)',(ta['id'],tb['id'],tb['id'],ta['id'])).fetchall()
def export_tournament_csv(name):
    EXPORT_DIR.mkdir(parents=True,exist_ok=True)
    with connect() as c:
        t=c.execute('SELECT id FROM tournaments WHERE name=? COLLATE NOCASE',(name,)).fetchone()
        if not t:return None
        rows=c.execute('''SELECT b.name bowler,tm.name team,g.score,g.strikes,g.spares,g.splits,g.split_conversions,g.clean,g.pocket_pct,g.created_at FROM game_results g JOIN bowlers b ON b.id=g.bowler_id LEFT JOIN teams tm ON tm.id=g.team_id WHERE g.tournament_id=? ORDER BY g.created_at,b.name''',(t['id'],)).fetchall()
    p=EXPORT_DIR/f'{name.replace("/","-")}_results.csv'
    with p.open('w',newline='',encoding='utf-8-sig') as f:w=csv.writer(f);w.writerow(['Bowler','Team','Score','Strikes','Spares','Splits','Split Conversions','Clean','Pocket %','Date']);w.writerows([list(r) for r in rows])
    return p
def export_tournament_xlsx(name):
    try:from openpyxl import Workbook
    except ImportError:return None
    EXPORT_DIR.mkdir(parents=True,exist_ok=True)
    with connect() as c:
        t=c.execute('SELECT id FROM tournaments WHERE name=? COLLATE NOCASE',(name,)).fetchone()
        if not t:return None
        rows=c.execute('''SELECT b.name bowler,tm.name team,g.score,g.strikes,g.spares,g.splits,g.split_conversions,g.clean,g.pocket_pct,g.created_at FROM game_results g JOIN bowlers b ON b.id=g.bowler_id LEFT JOIN teams tm ON tm.id=g.team_id WHERE g.tournament_id=? ORDER BY g.created_at,b.name''',(t['id'],)).fetchall();matches=c.execute('''SELECT m.round_no,m.match_no,a.name team_a,b.name team_b,m.score_a,m.score_b,w.name winner FROM tournament_matches m LEFT JOIN teams a ON a.id=m.team_a_id LEFT JOIN teams b ON b.id=m.team_b_id LEFT JOIN teams w ON w.id=m.winner_id WHERE m.tournament_id=? ORDER BY m.round_no,m.match_no''',(t['id'],)).fetchall()
    wb=Workbook();ws=wb.active;ws.title='Bowler Results';ws.append(['Bowler','Team','Score','Strikes','Spares','Splits','Split Conversions','Clean','Pocket %','Date'])
    for r in rows:ws.append(list(r))
    ms=wb.create_sheet('Matches');ms.append(['Round','Match','Team A','Team B','Score A','Score B','Winner'])
    for r in matches:ms.append(list(r))
    for sh in wb.worksheets:
        sh.freeze_panes='A2';sh.auto_filter.ref=sh.dimensions
        for col in sh.columns:sh.column_dimensions[col[0].column_letter].width=min(32,max(12,max(len(str(c.value or '')) for c in col)+2))
    p=EXPORT_DIR/f'{name.replace("/","-")}_results.xlsx';wb.save(p);return p
