"""Staff-only manual award writer, separate from auto-generated honours.

Permission checks belong at Discord entry points; this module enforces data
validation and duplicate-safe accounting inside one transaction.
"""
from contextlib import nullcontext
from storage.database import connect


def give_manual_award(bowler_id, title, detail='', actor_id=None, db=None):
    title=(title or '').strip();detail=(detail or '').strip()
    if not 1<=len(title)<=60 or len(detail)>200:
        return False,'Title must contain 1–60 characters; detail at most 200.'
    with (nullcontext(db) if db is not None else connect()) as c:
        row=c.execute('SELECT name FROM bowlers WHERE id=?',(bowler_id,)).fetchone()
        if not row:return False,'Bowler not found.'
        prior=c.execute('''SELECT id FROM awards WHERE bowler_id=? AND tournament_id IS NULL
                  AND title=? AND COALESCE(detail,'')=? LIMIT 1''',(bowler_id,title,detail)).fetchone()
        if prior:return False,'This award has already been issued to the bowler.'
        c.execute('INSERT INTO awards(bowler_id,title,detail) VALUES(?,?,?)',(bowler_id,title,detail))
        c.execute('INSERT OR IGNORE INTO bowler_stats(bowler_id) VALUES(?)',(bowler_id,))
        c.execute('UPDATE bowler_stats SET awards=awards+1 WHERE bowler_id=?',(bowler_id,))
        c.execute('''INSERT INTO audit_log(actor_id,action,target_type,target_id,detail)
                     VALUES(?,?,?,?,?)''',(actor_id or 0,'award_give','bowler',bowler_id,title))
        return True,row['name']
