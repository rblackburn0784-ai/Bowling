"""Season-level read models: no simulated results, all numbers from persisted games."""
from storage.database import connect
from services.league_engine import standings

def season_home(sid):
 with connect() as c:
  s=c.execute('SELECT * FROM seasons WHERE id=?',(sid,)).fetchone()
  if not s:return None
  comps=c.execute('SELECT * FROM competitions WHERE season_id=? ORDER BY id',(sid,)).fetchall()
  fixtures=c.execute("""SELECT f.*,co.name competition,co.entrant_type FROM fixtures f JOIN competitions co ON co.id=f.competition_id WHERE co.season_id=? ORDER BY f.stage_id,f.round_no,f.fixture_no""",(sid,)).fetchall()
  leaders=c.execute("""SELECT b.name,x.*,x.total_pins*1.0/NULLIF(x.games,0) average FROM season_bowler_stats x JOIN bowlers b ON b.id=x.bowler_id WHERE x.season_id=? AND x.games>0""",(sid,)).fetchall()
  return dict(s),[dict(x) for x in comps],[dict(x) for x in fixtures],[dict(x) for x in leaders]

def week_fixtures(cid,round_no=None):
 with connect() as c:
  if round_no is None:
   r=c.execute("SELECT MIN(round_no) n FROM fixtures WHERE competition_id=? AND status IN ('scheduled','playing')",(cid,)).fetchone()
   round_no=r['n'] if r and r['n'] is not None else 1
  return round_no,[dict(x) for x in c.execute('SELECT * FROM fixtures WHERE competition_id=? AND round_no=? ORDER BY fixture_no',(cid,round_no))]

def recent_form(cid,entrant_id,limit=5):
 with connect() as c:
  games=c.execute("SELECT winner_id,home_id,away_id,home_score,away_score FROM fixtures WHERE competition_id=? AND status='complete' AND (home_id=? OR away_id=?) AND home_id IS NOT NULL AND away_id IS NOT NULL ORDER BY played_at DESC,id DESC LIMIT ?",(cid,entrant_id,entrant_id,limit)).fetchall()
 return ''.join('D' if g['winner_id'] is None else 'W' if g['winner_id']==entrant_id else 'L' for g in reversed(games)) or '—'

def zones(cid):
 with connect() as c:co=c.execute('SELECT * FROM competitions WHERE id=?',(cid,)).fetchone()
 if not co:return []
 rs=standings(cid);out=[]
 for n,r in enumerate(rs,1):
  zone='playoff' if co['playoff_size'] and n<=co['playoff_size'] else 'promotion' if co['promotion_slots'] and n<=co['promotion_slots'] else 'relegation' if co['relegation_slots'] and n>len(rs)-co['relegation_slots'] else 'safe'
  out.append((n,dict(r),zone,recent_form(cid,r['entrant_id'])))
 return out

def season_award_races(sid):
 data=season_home(sid)
 if not data:return {}
 leaders=data[3]
 if not leaders:return {}
 eligible=[x for x in leaders if x['games']>=3]
 def top(key,rows=None):
  arr=rows if rows is not None else leaders
  return sorted(arr,key=lambda x:(x.get(key) or 0,x['games']),reverse=True)[:5]
 return {'Average (min 3 games)':sorted(eligible,key=lambda x:x['average'] or 0,reverse=True)[:5],
         'High Game':top('high_game'),'Strikes':top('strikes'),'Splits Converted':top('split_conversions'),
         'Games Played':top('games')}

def season_records(sid):
 with connect() as c:
  rows=c.execute('''SELECT b.name,g.score,g.strikes,g.spares,g.split_conversions,g.created_at
    FROM game_history g JOIN bowlers b ON b.id=g.bowler_id WHERE g.season_id=? ORDER BY g.score DESC,g.id DESC LIMIT 10''',(sid,)).fetchall()
 return [dict(x) for x in rows]

def season_gazette(sid):
 data=season_home(sid)
 if not data:return None
 s,comps,fixtures,leaders=data
 completed=[f for f in fixtures if f['status']=='complete']
 last=completed[-1] if completed else None
 high=max(leaders,key=lambda x:x['high_game']) if leaders else None
 avg=max((x for x in leaders if x['games']>=3),key=lambda x:x['average'] or 0,default=None)
 headline=f"{high['name']} sets the pace with {high['high_game']}" if high else 'Season preparations are underway'
 lines=[f"**{s['name']} — Season Bulletin**",f"Competitions: {len(comps)} • Completed fixtures: {len(completed)}"]
 if avg:lines.append(f"⭐ Average leader: {avg['name']} — {avg['average']:.1f}")
 if last:lines.append(f"🎳 Latest completed fixture: {last['competition']} • Round {last['round_no']}")
 return {'headline':headline,'body':'\n'.join(lines)}
