"""
Small maintenance script to backup and clear the SQLite database used by the app.
Run from the project root (where `library.db` lives).
"""
import sqlite3
import os
import sys

DB = 'library.db'
if not os.path.exists(DB):
    print('No database file found at', DB)
    sys.exit(1)

conn = sqlite3.connect(DB)
cursor = conn.cursor()

# Discover user tables (exclude sqlite internal tables)
tables = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';").fetchall()]
print('Found tables:', tables)

# Order deletion so foreign keys don't block (delete children first)
prefer_order = ['loans', 'books', 'borrowers', 'authors', 'publishers', 'categories']
# Build final order: prefer_order first if present, then any others
order = [t for t in prefer_order if t in tables] + [t for t in tables if t not in prefer_order]

for t in order:
    try:
        cursor.execute(f'DELETE FROM {t};')
        print('Cleared table', t)
    except Exception as e:
        print('Failed clearing', t, '=>', e)

# Reset sqlite_sequence (autoincrement counters)
try:
    cursor.execute("DELETE FROM sqlite_sequence;")
    print('Reset sqlite_sequence')
except Exception as e:
    print('Failed to reset sqlite_sequence:', e)

conn.commit()
conn.close()

# Vacuum to rebuild database file and reclaim space
try:
    import subprocess
    subprocess.check_call([sys.executable, '-c', "import sqlite3; conn=sqlite3.connect('library.db'); conn.execute('VACUUM;'); conn.close()"])
    print('VACUUM completed')
except Exception as e:
    print('VACUUM failed:', e)

print('Database cleared successfully')
