"""Atomic, duplicate-safe tournament career honours and team awards."""
from storage.database import connect


def _honour(db, bowler_id, tournament_id, code, title, detail, placing=None, icon='🏆'):
    cur=db.execute('''INSERT OR IGNORE INTO career_honours
          (bowler_id,tournament_id,code,title,detail,placing) VALUES(?,?,?,?,?,?)''',
          (bowler_id,tournament_id,code,title,detail,placing))
    if not cur.rowcount:return False
    db.execute('INSERT OR IGNORE INTO bowler_stats(bowler_id) VALUES(?)',(bowler_id,))
    db.execute('UPDATE bowler_stats SET awards=awards+1 WHERE bowler_id=?',(bowler_id,))
    db.execute('''INSERT INTO career_timeline(bowler_id,kind,icon,headline,detail,source)
          VALUES(?,?,?,?,?,?)''',(bowler_id,'honour',icon,title,detail,'tournament'))
    return True


def finalize_tournament_honours(tournament_id):
    with connect() as c:
        t=c.execute('SELECT * FROM tournaments WHERE id=?',(tournament_id,)).fetchone()
        if not t or t['status']!='complete':return None
        final=c.execute('''SELECT * FROM tournament_matches WHERE tournament_id=?
            ORDER BY round_no DESC,match_no LIMIT 1''',(tournament_id,)).fetchone()
        if not final or not final['winner_id']:return None
        champion=final['winner_id']
        runner=final['team_b_id'] if champion==final['team_a_id'] else final['team_a_id']
        champ=c.execute('SELECT name FROM teams WHERE id=?',(champion,)).fetchone()
        runner_row=c.execute('SELECT name FROM teams WHERE id=?',(runner,)).fetchone() if runner else None
        if champ is None:return None
        champ_name=champ['name'];runner_name=runner_row['name'] if runner_row else None
        champs=c.execute('''SELECT b.id,b.name FROM team_members tm JOIN bowlers b ON b.id=tm.bowler_id
                WHERE tm.team_id=?''',(champion,)).fetchall()
        runners=c.execute('''SELECT b.id,b.name FROM team_members tm JOIN bowlers b ON b.id=tm.bowler_id
                WHERE tm.team_id=?''',(runner,)).fetchall() if runner else []
        leaders=c.execute('''SELECT s.*,b.name FROM tournament_bowler_stats s JOIN bowlers b ON b.id=s.bowler_id
                         WHERE s.tournament_id=? AND s.games>0''',(tournament_id,)).fetchall()
        # This marker prevents duplicate team honours even if a winner has NO registered bowlers.
        # Existing tournaments are respected: older champion honours imply team counts already awarded.
        marker=c.execute('SELECT 1 FROM tournament_honour_runs WHERE tournament_id=?',(tournament_id,)).fetchone()
        legacy=c.execute('SELECT 1 FROM career_honours WHERE tournament_id=? AND code="champion" LIMIT 1',
                         (tournament_id,)).fetchone()
        if not marker:
            c.execute('INSERT OR IGNORE INTO tournament_honour_runs(tournament_id) VALUES(?)',(tournament_id,))
            if not legacy:
                c.execute('INSERT OR IGNORE INTO team_history(team_id) VALUES(?)',(champion,))
                c.execute('UPDATE team_history SET championships=championships+1,finals=finals+1 WHERE team_id=?',(champion,))
                if runner:
                    c.execute('INSERT OR IGNORE INTO team_history(team_id) VALUES(?)',(runner,))
                    c.execute('UPDATE team_history SET finals=finals+1 WHERE team_id=?',(runner,))
        name=t['name'];new=[]
        for b in champs:
            if _honour(c,b['id'],tournament_id,'champion',f'🏆 {name} Champion',f'Won {name} with {champ_name}.',1):new.append((b['name'],'Champion'))
        for b in runners:
            if _honour(c,b['id'],tournament_id,'runner_up',f'🥈 {name} Runner-up',f'Reached the final with {runner_name}.',2,'🥈'):new.append((b['name'],'Runner-up'))
        if leaders:
            top_avg=max(leaders,key=lambda x:(x['total_pins']/x['games'],x['total_pins'],-x['bowler_id']))
            avg=top_avg['total_pins']/top_avg['games']
            high=max(leaders,key=lambda x:(x['high_game'],-x['bowler_id']))
            strike=max(leaders,key=lambda x:(x['strikes'],-x['bowler_id']))
            split=max(leaders,key=lambda x:(x['split_conversions'],-x['bowler_id']))
            specs=[(top_avg,'high_average','🎯',f'{name} High Average',f'{avg:.1f} tournament average.'),
                   (high,'high_game','🔥',f'{name} High Game',f"High game of {high['high_game']}."),
                   (strike,'strike_leader','⚡',f'{name} Strike Leader',f"{strike['strikes']} strikes."),
                   (split,'split_slayer','🪓',f'{name} Split Slayer',f"{split['split_conversions']} split conversions.")]
            for row,code,icon,title,detail in specs:
                if _honour(c,row['bowler_id'],tournament_id,code,title,detail,None,icon):new.append((row['name'],title))
        return {'tournament':name,'champion':champ_name,'runner_up':runner_name,'new':new}


def honours_for_bowler(bowler_id):
    with connect() as c:
        return c.execute('SELECT * FROM career_honours WHERE bowler_id=? ORDER BY id DESC',(bowler_id,)).fetchall()
