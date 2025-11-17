# LibraryIcons2 — Library Management Demo

Small Flask-based library management application. This repository includes a simple SQLite backend and
HTML templates for managing books, borrowers and loans.

This README contains quick setup instructions so you (or another developer) can run the project after
downloading from GitHub.

## Requirements

- Python 3.8 or newer (3.10+/3.11 recommended)
- pip

## Quick Start (Windows — PowerShell)

Open PowerShell in the project root (where `app.py` and `library.db` live) and run:

```powershell
# create & activate virtualenv
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1

# install requirements
pip install -r requirements.txt

# (optional) make a backup of existing DB
New-Item -ItemType Directory -Path backups -Force | Out-Null
Copy-Item -Path .\\library.db -Destination (Join-Path backups ("library_$(Get-Date -Format yyyyMMdd_HHmmss).db")) -ErrorAction SilentlyContinue

# (optional) seed demo data
python .\\scripts\\seed_demo.py

# start the dev server
python .\\app.py
```

The app will be available at `http://127.0.0.1:5000`.

## Convenience scripts

Two helper scripts are provided to simplify common tasks:

- `scripts\\run.ps1` — PowerShell helper with `start`, `seed`, `clear`, and `backup` actions.
- `run.bat` — Windows batch file that starts the dev server.

Examples:

PowerShell (from project root):
```powershell
# start the server
.\\scripts\\run.ps1 start

# seed demo data
.\\scripts\\run.ps1 seed

# clear all data (watch out — this deletes all rows)
.\\scripts\\run.ps1 clear

# backup DB
.\\scripts\\run.ps1 backup
```

Windows (cmd):
```
run.bat
```

## Useful scripts in `scripts/`

- `clear_db.py` — deletes rows from user tables (loans, books, borrowers, authors, publishers, categories), resets sequences and runs VACUUM.
- `check_db.py` — prints table row counts.
- `seed_demo.py` — seeds demo authors/publishers/books/borrowers/loans.

## Notes & Safety

- The project uses SQLite. Back up `library.db` before running any destructive script (for example, `clear_db.py`).
- The provided `scripts/run.ps1 clear` will remove data — use with caution.
- The dev server uses Flask's built-in server; it is not suitable for production.

## Troubleshooting

- If `import models` fails when running scripts from `scripts/`, ensure you run them from the project root (the `scripts/` helper sets the parent directory on `sys.path`).
- If you see `database is locked` errors while developing, avoid running multiple server processes and consider using the included retry logic in `models.py`.

If you'd like, I can also add a GitHub Actions workflow to run the test suite and linting automatically.
**Overview**
- **Project**: A small Flask-based library management app using SQLite.
- **Purpose**: Manage books, borrowers, loans, authors, publishers, and categories via a simple web UI.

**Prerequisites**
- **Python**: 3.10+ is recommended (project was developed with Python 3.13). Ensure `python` is on your PATH.
- **Packages**: Install from `requirements.txt`.

**Quick Start**
- **Install dependencies**:
```powershell
cd 'c:\Users\DIVYA\Downloads\LibraryIcons2 (1)\LibraryIcons2'
python -m venv .venv            # optional but recommended
.\.venv\Scripts\Activate.ps1 # PowerShell activate
pip install -r requirements.txt
```

- **Run the app**:
```powershell
cd 'c:\Users\DIVYA\Downloads\LibraryIcons2 (1)\LibraryIcons2'
python app.py
```
The server runs on `http://127.0.0.1:5000` by default.

**Stopping the app**
- Find the PID listening on port `5000` and kill it:
```powershell
netstat -ano | findstr ":5000"
taskkill /PID <pid> /F
```

**Important Files**
- `app.py` — Flask application and route handlers.
- `models.py` — Database access (SQLite) and helper functions.
- `library.db` — SQLite database file (created/used at runtime in the project root).
- `app.log` — Application log file that captures server logs and exceptions.
- `templates/` and `static/` — Jinja2 templates and CSS/JS assets.

**Notes & Troubleshooting**
- SQLite concurrency: the app enables WAL mode and sets timeouts, but avoid running multiple processes (Flask auto-reloader spawns a second process). When running locally, `app.py` disables the auto-reloader (`use_reloader=False`) to reduce "database is locked" errors.
- If you see `sqlite3.OperationalError: database is locked`, stop other Python processes that may be accessing `library.db`, then retry. Increasing the timeout or switching to a production DB (Postgres/MySQL) is recommended for multi-user setups.
- If a delete fails due to referential integrity, the app blocks deletes for records with dependent rows (e.g., books with loans). Check `models.get_loans_count_for_book` and related checks in `app.py`.
- To inspect errors, tail `app.log`:
```powershell
Get-Content .\app.log -Wait -Tail 200
```

**Testing / Next Steps**
- There are no automated tests included. Consider adding a small pytest suite exercising add/edit/delete flows.
- For production, run behind a WSGI server (Gunicorn/Waitress) and migrate to a server-grade RDBMS.

**Contributing**
- Create a branch, make changes, and open a PR. Keep database migrations in mind if you change schema.

**License**
- No license file included; add one if you plan to publish.

If you want, I can also:
- Add a minimal `README` badge and instructions for running in a venv.
- Add a quick integration script that exercises CRUD flows automatically.
- Commit these changes to a git branch and prepare a short changelog.
