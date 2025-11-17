import sqlite3
import time
import functools
from datetime import datetime, timedelta

DB = "library.db"

def get_conn():
    """Get database connection with foreign keys enabled"""
    # Increase timeout and allow cross-thread usage. Use a longer timeout so
    # short locks (from concurrent access or the reloader) will be waited on
    # rather than immediately raising "database is locked".
    conn = sqlite3.connect(DB, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys and use WAL journal mode to reduce write locking.
    # Also set a busy timeout for good measure.
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 30000;")
    except sqlite3.OperationalError:
        # If any PRAGMA fails, continue — the DB will still work with defaults.
        pass
    return conn

def init_db():
    """Initialize database tables"""
    conn = get_conn()
    c = conn.cursor()
    
    # Create categories table
    c.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    """)
    
    # Create authors table
    c.execute("""
        CREATE TABLE IF NOT EXISTS authors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    """)
    
    # Create publishers table
    c.execute("""
        CREATE TABLE IF NOT EXISTS publishers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    """)
    
    # Create books table
    c.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            isbn TEXT UNIQUE,
            category_id INTEGER,
            author_name TEXT,
            publisher_name TEXT,
            quantity INTEGER DEFAULT 1,
            available INTEGER DEFAULT 1,
            added_date TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
    """)
    
    # Create borrowers table
    c.execute("""
        CREATE TABLE IF NOT EXISTS borrowers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE,
            phone TEXT,
            joined_date TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create loans table
    c.execute("""
        CREATE TABLE IF NOT EXISTS loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            borrower_id INTEGER NOT NULL,
            loan_date TEXT DEFAULT CURRENT_TIMESTAMP,
            due_date TEXT,
            return_date TEXT,
            status TEXT DEFAULT 'active',
            FOREIGN KEY (book_id) REFERENCES books(id),
            FOREIGN KEY (borrower_id) REFERENCES borrowers(id)
        )
    """)
    
    conn.commit()
    conn.close()


# Retry decorator for write operations to reduce chance of transient
# sqlite "database is locked" OperationalError bubbling up to the app.
def retry_db(max_attempts=5, initial_delay=0.05, backoff=2.0):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    # Retry on database locked or busy errors
                    msg = str(e).lower()
                    if 'locked' in msg or 'database is locked' in msg or 'busy' in msg:
                        if attempt == max_attempts:
                            raise
                        time.sleep(delay)
                        delay *= backoff
                        continue
                    raise
        return wrapper
    return decorator

@retry_db()
def seed_default_categories():
    """Insert default categories if table is empty"""
    conn = get_conn()
    c = conn.cursor()
    
    count = c.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
    
    if count == 0:
        default_categories = ['Fiction', 'Non-Fiction', 'Science', 'History', 'Biography']
        for cat_name in default_categories:
            c.execute("INSERT INTO categories (name) VALUES (?)", (cat_name,))
        conn.commit()
    
    conn.close()

# Simple in-memory TTL cache to reduce frequent identical reads
_CACHE = {}
_CACHE_TTL = 5  # seconds

def _cache_get(key):
    entry = _CACHE.get(key)
    if not entry:
        return None
    value, ts = entry
    if time.time() - ts > _CACHE_TTL:
        _CACHE.pop(key, None)
        return None
    return value

def _cache_set(key, value):
    _CACHE[key] = (value, time.time())

def _cache_clear(prefix=None):
    if prefix is None:
        _CACHE.clear()
    else:
        for k in list(_CACHE.keys()):
            if k.startswith(prefix):
                _CACHE.pop(k, None)

def ensure_db_indexes():
    """Create commonly-used indexes to speed up queries (idempotent)."""
    conn = get_conn()
    c = conn.cursor()
    # Indexes to speed up joins and lookups for loans and books
    c.execute("CREATE INDEX IF NOT EXISTS idx_loans_book_id ON loans (book_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_loans_borrower_id ON loans (borrower_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_books_category_id ON books (category_id)")
    # The schema stores author and publisher names on the books table
    # (author_name / publisher_name). Attempt to create indexes on those
    # columns and ignore failures if the column is missing for older DBs.
    try:
        c.execute("CREATE INDEX IF NOT EXISTS idx_books_author_name ON books (author_name)")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("CREATE INDEX IF NOT EXISTS idx_books_publisher_name ON books (publisher_name)")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

# ------------- CATEGORIES -------------
def get_all_categories():
    """Get all categories with book count"""
    conn = get_conn()
    rows = conn.execute("""
        SELECT c.id, c.name, COUNT(b.id) as book_count
        FROM categories c
        LEFT JOIN books b ON c.id = b.category_id
        GROUP BY c.id, c.name
        ORDER BY c.name
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_category_by_id(category_id):
    """Get category by ID"""
    conn = get_conn()
    row = conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

@retry_db()
def add_category(name):
    """Add new category"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO categories (name) VALUES (?)", (name,))
    conn.commit()
    category_id = c.lastrowid
    conn.close()
    return category_id

@retry_db()
def update_category(category_id, name):
    """Update category"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE categories SET name = ? WHERE id = ?", (name, category_id))
    conn.commit()
    conn.close()

@retry_db()
def delete_category(category_id):
    """Delete category"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    conn.commit()
    conn.close()

# ------------- AUTHORS -------------
def get_all_authors():
    """Get all authors with book count"""
    conn = get_conn()
    rows = conn.execute("""
        SELECT a.id, a.name, COUNT(b.id) as book_count
        FROM authors a
        LEFT JOIN books b ON a.name = b.author_name
        GROUP BY a.id, a.name
        ORDER BY a.name
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_author_by_id(author_id):
    """Get author by ID"""
    conn = get_conn()
    row = conn.execute("SELECT * FROM authors WHERE id = ?", (author_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

@retry_db()
def add_author(name):
    """Add new author"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO authors (name) VALUES (?)", (name,))
    conn.commit()
    author_id = c.lastrowid
    conn.close()
    return author_id

@retry_db()
def update_author(author_id, name):
    """Update author"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE authors SET name = ? WHERE id = ?", (name, author_id))
    conn.commit()
    conn.close()

@retry_db()
def delete_author(author_id):
    """Delete author"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM authors WHERE id = ?", (author_id,))
    conn.commit()
    conn.close()

# ------------- PUBLISHERS -------------
def get_all_publishers():
    """Get all publishers with book count"""
    conn = get_conn()
    rows = conn.execute("""
        SELECT p.id, p.name, COUNT(b.id) as book_count
        FROM publishers p
        LEFT JOIN books b ON p.name = b.publisher_name
        GROUP BY p.id, p.name
        ORDER BY p.name
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_publisher_by_id(publisher_id):
    """Get publisher by ID"""
    conn = get_conn()
    row = conn.execute("SELECT * FROM publishers WHERE id = ?", (publisher_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

@retry_db()
def add_publisher(name):
    """Add new publisher"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO publishers (name) VALUES (?)", (name,))
    conn.commit()
    publisher_id = c.lastrowid
    conn.close()
    return publisher_id

@retry_db()
def update_publisher(publisher_id, name):
    """Update publisher"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE publishers SET name = ? WHERE id = ?", (name, publisher_id))
    conn.commit()
    conn.close()

@retry_db()
def delete_publisher(publisher_id):
    """Delete publisher"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM publishers WHERE id = ?", (publisher_id,))
    conn.commit()
    conn.close()

# ------------- BOOKS -------------
def get_all_books(search='', category_filter=''):
    """Get all books with optional filters"""
    # Use a small cache to reduce frequent identical queries
    cache_key = f"books:{search}:{category_filter}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    conn = get_conn()
    
    query = """
        SELECT b.*, c.name as category_name
        FROM books b
        LEFT JOIN categories c ON b.category_id = c.id
        WHERE 1=1
    """
    params = []
    
    if search:
        query += " AND b.title LIKE ?"
        params.append(f'%{search}%')
    
    if category_filter:
        query += " AND b.category_id = ?"
        params.append(category_filter)
    
    query += " ORDER BY b.title"
    
    rows = conn.execute(query, params).fetchall()
    conn.close()
    result = [dict(r) for r in rows]
    _cache_set(cache_key, result)
    return result

def get_book_by_id(book_id):
    """Get book by ID"""
    conn = get_conn()
    row = conn.execute("""
        SELECT b.*, c.name as category_name
        FROM books b
        LEFT JOIN categories c ON b.category_id = c.id
        WHERE b.id = ?
    """, (book_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_total_books():
    """Get total number of books"""
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    conn.close()
    return count

def get_total_available_books():
    """Get total available books"""
    conn = get_conn()
    total = conn.execute("SELECT COALESCE(SUM(available), 0) FROM books").fetchone()[0]
    conn.close()
    return total

@retry_db()
def add_book(title, isbn, category_id, author_name, publisher_name, quantity):
    """Add new book"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO books (title, isbn, category_id, author_name, publisher_name, quantity, available)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (title, isbn, category_id, author_name, publisher_name, quantity, quantity))
    conn.commit()
    book_id = c.lastrowid
    conn.close()
    # Invalidate books cache
    _cache_clear('books')
    return book_id

@retry_db()
def update_book(book_id, title, isbn, category_id, author_name, publisher_name, quantity):
    """Update book"""
    conn = get_conn()
    c = conn.cursor()
    
    # Get active loans count
    active_loans = c.execute(
        "SELECT COUNT(*) FROM loans WHERE book_id = ? AND status = 'active'",
        (book_id,)
    ).fetchone()[0]
    
    # Calculate available
    available = quantity - active_loans
    
    c.execute("""
        UPDATE books 
        SET title = ?, isbn = ?, category_id = ?, author_name = ?, publisher_name = ?, 
            quantity = ?, available = ?
        WHERE id = ?
    """, (title, isbn, category_id, author_name, publisher_name, quantity, available, book_id))
    conn.commit()
    conn.close()
    # Invalidate books cache
    _cache_clear('books')
    return active_loans

@retry_db()
def delete_book(book_id):
    """Delete book"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM books WHERE id = ?", (book_id,))
    conn.commit()
    conn.close()
    # Invalidate books cache
    _cache_clear('books')

# ------------- BORROWERS -------------
def get_all_borrowers():
    """Get all borrowers with active and total loan counts"""
    cache_key = 'borrowers:all'
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    conn = get_conn()
    rows = conn.execute("""
        SELECT b.*, 
               COUNT(CASE WHEN l.status = 'active' THEN 1 END) AS active_loans,
               COUNT(l.id) AS total_loans
        FROM borrowers b
        LEFT JOIN loans l ON b.id = l.borrower_id
        GROUP BY b.id, b.name, b.email, b.phone, b.joined_date
        ORDER BY b.name
    """).fetchall()
    conn.close()
    # Ensure numeric fields exist even when NULL
    result = []
    for r in rows:
        row = dict(r)
        row.setdefault('active_loans', 0)
        row.setdefault('total_loans', 0)
        result.append(row)
    _cache_set(cache_key, result)
    return result

def get_borrower_by_id(borrower_id):
    """Get borrower by ID"""
    conn = get_conn()
    row = conn.execute("SELECT * FROM borrowers WHERE id = ?", (borrower_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_total_borrowers():
    """Get total number of borrowers"""
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM borrowers").fetchone()[0]
    conn.close()
    return count

@retry_db()
def add_borrower(name, email, phone):
    """Add new borrower"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO borrowers (name, email, phone) VALUES (?, ?, ?)", (name, email, phone))
    conn.commit()
    borrower_id = c.lastrowid
    conn.close()
    # Invalidate borrowers cache
    _cache_clear('borrowers')
    return borrower_id

@retry_db()
def update_borrower(borrower_id, name, email, phone):
    """Update borrower"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        UPDATE borrowers SET name = ?, email = ?, phone = ? WHERE id = ?
    """, (name, email, phone, borrower_id))
    conn.commit()
    conn.close()
    # Invalidate borrowers cache
    _cache_clear('borrowers')

@retry_db()
def delete_borrower(borrower_id):
    """Delete borrower"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM borrowers WHERE id = ?", (borrower_id,))
    conn.commit()
    conn.close()
    # Invalidate borrowers cache
    _cache_clear('borrowers')

# ------------- LOANS -------------
def get_all_loans():
    """Get all loans with book and borrower details"""
    conn = get_conn()
    rows = conn.execute("""
        SELECT l.*, b.title as book_title, br.name as borrower_name
        FROM loans l
        JOIN books b ON l.book_id = b.id
        JOIN borrowers br ON l.borrower_id = br.id
        ORDER BY l.loan_date DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_active_loans():
    """Get recent active loans"""
    conn = get_conn()
    rows = conn.execute("""
        SELECT l.*, b.title as book_title, br.name as borrower_name
        FROM loans l
        JOIN books b ON l.book_id = b.id
        JOIN borrowers br ON l.borrower_id = br.id
        WHERE l.status = 'active'
        ORDER BY l.loan_date DESC
        LIMIT 5
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_total_active_loans():
    """Get total number of active loans"""
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM loans WHERE status = 'active'").fetchone()[0]
    conn.close()
    return count

def get_loans_count_for_book(book_id):
    """Return the total number of loans (any status) for a specific book."""
    conn = get_conn()
    try:
        count = conn.execute("SELECT COUNT(*) FROM loans WHERE book_id = ?", (book_id,)).fetchone()[0]
    finally:
        conn.close()
    return count


def get_loans_count_for_borrower(borrower_id):
    """Return the total number of loans (any status) for a specific borrower."""
    conn = get_conn()
    try:
        count = conn.execute("SELECT COUNT(*) FROM loans WHERE borrower_id = ?", (borrower_id,)).fetchone()[0]
    finally:
        conn.close()
    return count

def get_active_loans_count_for_borrower(borrower_id):
    """Return the count of active loans for a specific borrower."""
    conn = get_conn()
    try:
        count = conn.execute("SELECT COUNT(*) FROM loans WHERE borrower_id = ? AND status = 'active'", (borrower_id,)).fetchone()[0]
    finally:
        conn.close()
    return count

@retry_db()
def add_loan(book_id, borrower_id):
    """Create new loan"""
    conn = get_conn()
    c = conn.cursor()
    
    loan_date = datetime.utcnow().isoformat()
    due_date = (datetime.utcnow() + timedelta(days=14)).isoformat()
    
    c.execute("""
        INSERT INTO loans (book_id, borrower_id, loan_date, due_date, status)
        VALUES (?, ?, ?, ?, 'active')
    """, (book_id, borrower_id, loan_date, due_date))
    
    # Update book availability
    c.execute("UPDATE books SET available = available - 1 WHERE id = ?", (book_id,))
    
    conn.commit()
    loan_id = c.lastrowid
    conn.close()
    # Invalidate affected caches: books availability and borrower loan counts
    _cache_clear('books')
    _cache_clear('borrowers')
    return loan_id

@retry_db()
def return_loan(loan_id):
    """Return a loaned book"""
    conn = get_conn()
    c = conn.cursor()
    
    # Get book_id before updating
    book_id = c.execute("SELECT book_id FROM loans WHERE id = ?", (loan_id,)).fetchone()[0]
    
    return_date = datetime.utcnow().isoformat()
    c.execute("""
        UPDATE loans SET status = 'returned', return_date = ? WHERE id = ?
    """, (return_date, loan_id))
    
    # Update book availability
    c.execute("UPDATE books SET available = available + 1 WHERE id = ?", (book_id,))
    
    conn.commit()
    conn.close()
    # Invalidate affected caches
    _cache_clear('books')
    _cache_clear('borrowers')

def is_loan_overdue(loan, now):
    """
    Check if a loan is overdue.
    Handles both full ISO timestamps and date-only strings.
    Date-only strings (YYYY-MM-DD) are treated as end-of-day.
    """
    if loan.get('status') != 'active' or not loan.get('due_date'):
        return False
    
    try:
        due_date_str = loan['due_date']
        
        # Check if date-only format (length 10, no 'T')
        if len(due_date_str) == 10 and 'T' not in due_date_str:
            # Treat as end of day: append 23:59:59
            due_date_str += 'T23:59:59'
        
        due_date_obj = datetime.fromisoformat(due_date_str)
        return due_date_obj < now
    except (ValueError, TypeError, AttributeError):
        # If parsing fails, assume not overdue to avoid false positives
        return False
