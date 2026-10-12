"""Read-only tournament diagnostics and safe pause/resume controls.

Pausing suspends new/manual results; an already-started match may finish and be
recovered atomically. Never delete a bracket from this module.
"""
from storage.database import connect


def tournament_health(name):
    with connect() as db:
        t=db.execute('SELECT * FROM tournaments WHERE name=? COLLATE NOCASE',(name,)).fetchone()
        if not t:return None
        matches=db.execute('SELECT * FROM tournament_matches WHERE tournament_id=? ORDER BY round_no,match_no',(t['id'],)).fetchall()
        issues=[]
        for m in matches:
            if m['status']=='complete' and m['team_a_id'] and m['team_b_id'] and (m['score_a'] is None or m['score_b'] is None):
                issues.append(f"R{m['round_no']} M{m['match_no']}: completed without regulation scores")
            if m['status']=='complete' and m['team_a_id'] and m['team_b_id'] and m['winner_id'] is None:
                issues.append(f"R{m['round_no']} M{m['match_no']}: complete without a winner")
            if m['winner_id'] is not None and m['winner_id'] not in (m['team_a_id'],m['team_b_id']):
                issues.append(f"R{m['round_no']} M{m['match_no']}: winner not registered in match")
            for k in ('score_a','score_b'):
                if m[k] is not None and m[k]<0:issues.append(f"R{m['round_no']} M{m['match_no']}: negative score")
        if t['status']=='complete' and any(m['status']!='complete' and m['team_a_id'] and m['team_b_id'] for m in matches):
            issues.append('Tournament marked complete while a playable match is unfinished')
        if t['status']=='complete' and matches and matches[-1]['winner_id'] is None:
            issues.append('Tournament marked complete without a final winner')
        recover=[]
        for a in db.execute('SELECT channel_id,state_json FROM active_sessions'):
            import json
            try:d=json.loads(a['state_json'])
            except (ValueError,TypeError):continue
            if d.get('tournament_id')==t['id']:
                recover.append(a['channel_id'])
        return {'id':t['id'],'name':t['name'],'status':t['status'],
                'paused':bool(t['paused']),'total':len(matches),
                'complete':sum(m['status']=='complete' for m in matches),
                'recoverable_channels':recover,'issues':issues}


def set_tournament_paused(name, paused, actor_id=None):
    if type(paused) is not bool:return False,'Pause state must be true or false.'
    with connect() as db:
        t=db.execute('SELECT id,status,paused FROM tournaments WHERE name=? COLLATE NOCASE',(name,)).fetchone()
        if not t:return False,'Tournament not found.'
        if t['status']!='active':return False,'Only an active tournament can be paused or resumed.'
        if bool(t['paused'])==paused:return True,'Tournament was already '+('paused.' if paused else 'running.')
        db.execute('UPDATE tournaments SET paused=? WHERE id=?',(int(paused),t['id']))
        db.execute('INSERT INTO audit_log(actor_id,action,target_type,target_id,detail) VALUES(?,?,?,?,?)',
                   (actor_id or 0,'tournament_pause' if paused else 'tournament_resume','tournament',t['id'],name))
        return True,'Tournament '+('paused; new manual results are blocked.' if paused else 'resumed.')
