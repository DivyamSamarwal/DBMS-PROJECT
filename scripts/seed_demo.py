"""
Seed the database with sample/demo data using the `models` API.
Run from project root: `python .\scripts\seed_demo.py`
"""
import random
import sys
import os
# Ensure project root is on sys.path so `import models` finds the module when running
# this script from the `scripts/` folder.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import models
import sqlite3

# Ensure DB/tables exist
models.init_db()
# Do not reseed default categories automatically if already present; call anyway ensures defaults
models.seed_default_categories()

print('Seeding demo data...')

# Clear caches if available
try:
    models._cache_clear()
except Exception:
    pass

# Sample data lists
authors = [
    'Jane Austen', 'Mark Twain', 'Isaac Asimov', 'Agatha Christie', 'George Orwell',
    'J.K. Rowling', 'J.R.R. Tolkien', 'Haruki Murakami', 'Toni Morrison', 'Yuval Noah Harari'
]
publishers = [
    'Penguin Random House', 'HarperCollins', 'Simon & Schuster', 'Hachette', 'Macmillan'
]
books = [
    ('Pride and Prejudice', '1111111111'),
    ('Adventures of Huckleberry Finn', '2222222222'),
    ('Foundation', '3333333333'),
    ('Murder on the Orient Express', '4444444444'),
    ('1984', '5555555555'),
    ('Harry Potter and the Sorcerer\'s Stone', '6666666666'),
    ('The Hobbit', '7777777777'),
    ('Norwegian Wood', '8888888888'),
    ('Beloved', '9999999999'),
    ('Sapiens', '1010101010'),
    ('Sample Science', '1112223334'),
    ('Sample Fiction A', '1112223335'),
    ('Sample Fiction B', '1112223336'),
    ('Sample Non-Fiction', '1112223337'),
    ('Sample Children', '1112223338'),
    ('Sample Mystery', '1112223339'),
    ('Sample History', '1112223340'),
    ('Sample Biography', '1112223341'),
    ('Sample Tech', '1112223342'),
    ('Sample Travel', '1112223343')
]
borrowers = [
    ('Alice Johnson', 'alice@example.com', '555-0100'),
    ('Bob Smith', 'bob@example.com', '555-0101'),
    ('Carol Lee', 'carol@example.com', '555-0102'),
    ('David Kim', 'david@example.com', '555-0103'),
    ('Eve Chen', 'eve@example.com', '555-0104'),
    ('Frank Wright', 'frank@example.com', '555-0105'),
    ('Grace Park', 'grace@example.com', '555-0106'),
    ('Hank Rivera', 'hank@example.com', '555-0107'),
    ('Ivy Gomez', 'ivy@example.com', '555-0108'),
    ('Jack Black', 'jack@example.com', '555-0109')
]

# Add authors
author_ids = []
for a in authors:
    try:
        aid = models.add_author(a)
    except Exception:
        # maybe duplicate or DB empty, try to find existing
        row = models.get_all_authors()
        aid = next((r['id'] for r in row if r['name'] == a), None)
    if aid:
        author_ids.append(aid)

# Add publishers
publisher_ids = []
for p in publishers:
    try:
        pid = models.add_publisher(p)
    except Exception:
        row = models.get_all_publishers()
        pid = next((r['id'] for r in row if r['name'] == p), None)
    if pid:
        publisher_ids.append(pid)

# Ensure categories list
cats = models.get_all_categories()
if not cats:
    models.seed_default_categories()
    cats = models.get_all_categories()
category_ids = [c['id'] for c in cats]

# Add books
book_ids = []
for i, (title, isbn) in enumerate(books):
    cat = random.choice(category_ids) if category_ids else None
    author = random.choice(authors)
    publisher = random.choice(publishers)
    qty = random.randint(1, 5)
    try:
        bid = models.add_book(title, isbn, cat, author, publisher, qty)
    except Exception:
        # fallback: insert directly
        conn = sqlite3.connect(models.DB)
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO books (title,isbn,category_id,author_name,publisher_name,quantity,available) VALUES (?,?,?,?,?,?,?)", (title, isbn, cat, author, publisher, qty, qty))
        conn.commit()
        bid = c.lastrowid
        conn.close()
    book_ids.append(bid)

# Add borrowers
borrower_ids = []
for name, email, phone in borrowers:
    try:
        br = models.add_borrower(name, email, phone)
    except Exception:
        # try to find existing
        allb = models.get_all_borrowers()
        br = next((b['id'] for b in allb if b['email'] == email), None)
    borrower_ids.append(br)

# Create some loans (only when books available)
loan_ids = []
for _ in range(8):
    b = random.choice(book_ids)
    br = random.choice(borrower_ids)
    # Check availability
    book = models.get_book_by_id(b)
    if book and book.get('available', 0) > 0:
        try:
            lid = models.add_loan(b, br)
            loan_ids.append(lid)
        except Exception:
            pass

# Return a couple of loans to create history
if loan_ids:
    for lid in loan_ids[:3]:
        try:
            models.return_loan(lid)
        except Exception:
            pass

# Print summary counts
import subprocess, sys
print('\nSeed summary:')
subprocess.check_call([sys.executable, '-c', "import sqlite3; conn=sqlite3.connect('library.db'); c=conn.cursor(); print('categories:', c.execute(\"SELECT COUNT(*) FROM categories\").fetchone()[0]); print('authors:', c.execute(\"SELECT COUNT(*) FROM authors\").fetchone()[0]); print('publishers:', c.execute(\"SELECT COUNT(*) FROM publishers\").fetchone()[0]); print('books:', c.execute(\"SELECT COUNT(*) FROM books\").fetchone()[0]); print('borrowers:', c.execute(\"SELECT COUNT(*) FROM borrowers\").fetchone()[0]); print('loans:', c.execute(\"SELECT COUNT(*) FROM loans\").fetchone()[0]); conn.close()"])

# Print sample rows
print('\nSample books:')
import sqlite3
conn=sqlite3.connect('library.db')
c=conn.cursor()
for row in c.execute('SELECT id,title,isbn,author_name,publisher_name,quantity,available FROM books ORDER BY id LIMIT 5'):
    print(row)
print('\nSample borrowers:')
for row in c.execute('SELECT id,name,email,phone FROM borrowers ORDER BY id LIMIT 5'):
    print(row)
print('\nSample loans:')
for row in c.execute("SELECT l.id,l.book_id,l.borrower_id,l.status,l.loan_date,l.return_date,b.title,br.name FROM loans l JOIN books b ON l.book_id=b.id JOIN borrowers br ON l.borrower_id=br.id LIMIT 8"):
    print(row)
conn.close()
print('\nDone')
