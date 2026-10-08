from datetime import date, timedelta
from storage.database import connect

def week_bounds(day=None):
    day = date.fromisoformat(day) if isinstance(day, str) else (day or date.today())
    start = day - timedelta(days=day.weekday())
    return start.isoformat(), (start + timedelta(days=6)).isoformat()

def archive(season_id, offset=0):
    with connect() as db:
        return [dict(r) for r in db.execute('SELECT * FROM season_gazette_issues WHERE season_id=? ORDER BY issue_no DESC LIMIT 25 OFFSET ?', (season_id, max(0,offset)))]

def get_issue(season_id, issue_no):
    with connect() as db:
        row=db.execute('SELECT * FROM season_gazette_issues WHERE season_id=? AND issue_no=?',(season_id,issue_no)).fetchone()
        return dict(row) if row else None

def publish(season_id, day=None):
    start,end=week_bounds(day)
    with connect() as db:
        season=db.execute('SELECT name FROM seasons WHERE id=?',(season_id,)).fetchone()
        if not season: raise ValueError('Unknown season')
        old=db.execute('SELECT * FROM season_gazette_issues WHERE season_id=? AND week_start=?',(season_id,start)).fetchone()
        if old: return dict(old),False
        games=db.execute('SELECT b.name,g.score FROM game_history g JOIN bowlers b ON b.id=g.bowler_id WHERE g.season_id=? AND date(g.created_at) BETWEEN ? AND ? ORDER BY g.score DESC',(season_id,start,end)).fetchall()
        results=db.execute("SELECT co.name competition,f.round_no,f.home_score,f.away_score FROM fixtures f JOIN competitions co ON co.id=f.competition_id WHERE co.season_id=? AND f.status='complete' AND date(f.played_at) BETWEEN ? AND ? ORDER BY f.played_at",(season_id,start,end)).fetchall()
        headline=(games[0]['name']+' leads the week with '+str(games[0]['score'])) if games else season['name']+' weekly roundup'
        lines=[season['name']+' | '+start+' to '+end, str(len(results))+' completed fixtures | '+str(len(games))+' bowler games']
        for r in results[-8:]: lines.append(r['competition']+' Round '+str(r['round_no'])+': '+str(r['home_score'])+' - '+str(r['away_score']))
        if not results and not games: lines.append('No completed results this week.')
        number=db.execute('SELECT COALESCE(MAX(issue_no),0)+1 n FROM season_gazette_issues WHERE season_id=?',(season_id,)).fetchone()['n']
        db.execute('INSERT INTO season_gazette_issues(season_id,issue_no,week_start,week_end,headline,body) VALUES(?,?,?,?,?,?)',(season_id,number,start,end,headline,chr(10).join(lines)))
        return dict(db.execute('SELECT * FROM season_gazette_issues WHERE season_id=? AND issue_no=?',(season_id,number)).fetchone()),True


def publish_previous_week(season_id, today=None):
    current=date.fromisoformat(today) if isinstance(today,str) else (today or date.today())
    return publish(season_id,current-timedelta(days=7))
