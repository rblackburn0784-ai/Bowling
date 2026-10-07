from storage.database import connect

def _issue_no(c,tid):
 r=c.execute('SELECT COALESCE(MAX(issue_no),0)+1 n FROM gazette_issues WHERE tournament_id IS ?',(tid,)).fetchone();return r['n']

def build_gazette(tournament_id,force=False):
 with connect() as c:
  t=c.execute('SELECT * FROM tournaments WHERE id=?',(tournament_id,)).fetchone()
  if not t:return None
  stats=c.execute('SELECT s.*,b.name FROM tournament_bowler_stats s JOIN bowlers b ON b.id=s.bowler_id WHERE s.tournament_id=?',(tournament_id,)).fetchall()
  stories=c.execute('SELECT * FROM tournament_stories WHERE tournament_id=? ORDER BY id DESC',(tournament_id,)).fetchall()
  matches=c.execute('SELECT m.*,a.name team_a,b.name team_b,w.name winner FROM tournament_matches m LEFT JOIN teams a ON a.id=m.team_a_id LEFT JOIN teams b ON b.id=m.team_b_id LEFT JOIN teams w ON w.id=m.winner_id WHERE m.tournament_id=? AND m.status="complete" ORDER BY m.id DESC',(tournament_id,)).fetchall()
  if not stats and not stories:return None
  # Automatic publishing is idempotent for an unchanged tournament state.
  fingerprint=f"{len(matches)}:{len(stories)}:{sum(r['games'] for r in stats)}"
  last=c.execute('SELECT * FROM gazette_issues WHERE tournament_id=? ORDER BY issue_no DESC LIMIT 1',(tournament_id,)).fetchone()
  if last and not force and last['lead'].startswith(f'[{fingerprint}]'):return dict(last)
  high=max(stats,key=lambda r:r['high_game']) if stats else None
  avg=max(stats,key=lambda r:r['total_pins']/max(1,r['games'])) if stats else None
  streak=max(stats,key=lambda r:r['turkeys']) if stats else None
  split=max(stats,key=lambda r:r['split_conversions']) if stats else None
  comeback=next((x for x in stories if x['kind']=='comeback'),None)
  perfect=next((x for x in stories if x['kind']=='perfect_watch'),None)
  close=next((x for x in stories if x['kind']=='clutch'),None)
  headline=(perfect['headline'].upper() if perfect else comeback['headline'].upper() if comeback else high['name'].upper()+' LIGHTS UP THE LANES' if high else 'DRAMA AT THE GUTTER SAINTS')
  lead_text=(perfect['detail'] if perfect else comeback['detail'] if comeback else f"{high['name']} owns the current high game at {high['high_game']}." if high else stories[0]['detail'])
  lead=f'[{fingerprint}]'+lead_text
  lines=[]
  if avg:lines.append(f"⭐ **Player of the Issue:** {avg['name']} — {avg['total_pins']/max(1,avg['games']):.1f} average")
  if high:lines.append(f"🔥 **High Game:** {high['name']} — {high['high_game']}")
  if streak and streak['turkeys']:lines.append(f"⚡ **Strike Threat:** {streak['name']} — {streak['turkeys']} turkey+ runs")
  if split and split['split_conversions']:lines.append(f"🪓 **Split Slayer:** {split['name']} — {split['split_conversions']} conversions")
  if comeback:lines.append(f"📈 **Comeback:** {comeback['headline']} — {comeback['detail']}")
  if close:lines.append(f"🚨 **Match Drama:** {close['detail']}")
  # Attribute movement is factual and tournament-adjacent; use recent tournament-era timeline entries only when present.
  gains=c.execute("SELECT ct.*,b.name FROM career_timeline ct JOIN bowlers b ON b.id=ct.bowler_id WHERE ct.kind='attribute' AND ct.created_at>=? ORDER BY ct.id DESC LIMIT 3",(t['created_at'],)).fetchall()
  for g in gains:lines.append(f"{g['icon']} **Career Watch:** {g['name']} — {g['headline']} ({g['detail']})")
  if matches:
   m=matches[0];lines.append(f"🎳 **Latest Result:** {m['winner']} won {m['score_a']}–{m['score_b']} ({m['team_a']} vs {m['team_b']})")
  issue=_issue_no(c,tournament_id);body='\n'.join(lines)
  c.execute('INSERT INTO gazette_issues(tournament_id,issue_no,headline,lead,body) VALUES(?,?,?,?,?)',(tournament_id,issue,headline,lead,body))
  return {'issue_no':issue,'tournament':t['name'],'headline':headline,'lead':lead,'body':body}

def latest_gazette(tournament_id=None):
 with connect() as c:
  if tournament_id is None:return c.execute('SELECT g.*,t.name tournament FROM gazette_issues g LEFT JOIN tournaments t ON t.id=g.tournament_id ORDER BY g.id DESC LIMIT 1').fetchone()
  return c.execute('SELECT g.*,t.name tournament FROM gazette_issues g LEFT JOIN tournaments t ON t.id=g.tournament_id WHERE g.tournament_id=? ORDER BY g.issue_no DESC LIMIT 1',(tournament_id,)).fetchone()

def gazette_archive(limit=10):
 with connect() as c:return c.execute('SELECT g.*,t.name tournament FROM gazette_issues g LEFT JOIN tournaments t ON t.id=g.tournament_id ORDER BY g.id DESC LIMIT ?',(limit,)).fetchall()

def format_gazette(g):
 if not g:return '📰 **THE GUTTER GAZETTE**\nNo issue has been published yet.'
 lead=g['lead'];lead=lead.split(']',1)[1] if lead.startswith('[') and ']' in lead else lead
 return f"📰 **THE GUTTER GAZETTE** • Issue #{g['issue_no']}\n*{g['tournament']}*\n\n# {g['headline']}\n{lead}\n\n{g['body']}"
