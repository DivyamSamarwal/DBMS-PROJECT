"""
Check and print row counts for all user tables in library.db
"""
import sqlite3
import os
DB='library.db'
if not os.path.exists(DB):
    print('NO_DB')
    raise SystemExit(1)
conn=sqlite3.connect(DB)
c=conn.cursor()
tables=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';").fetchall()]
print('tables:', tables)
for t in tables:
    try:
        cnt=c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    except Exception as e:
        cnt=f'ERR:{e}'
    print(f"{t}: {cnt}")
conn.close()
