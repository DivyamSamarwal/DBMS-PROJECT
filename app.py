import os
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from datetime import datetime
import models
import logging
from logging.handlers import RotatingFileHandler
import sqlite3

# Basic logging to file and console for easier debugging of server errors
# Use a rotating file handler to avoid unbounded log growth
handler = RotatingFileHandler('app.log', maxBytes=5 * 1024 * 1024, backupCount=5)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')
handler.setFormatter(formatter)
root = logging.getLogger()
root.setLevel(logging.INFO)
root.addHandler(handler)
root.addHandler(logging.StreamHandler())

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SESSION_SECRET', 'dev-secret-key')

# Initialize database and seed default data
models.init_db()
models.seed_default_categories()
def app_startup_maintenance():
    """Run lightweight DB maintenance tasks once at startup."""
    try:
        models.ensure_db_indexes()
        # Clear any in-memory caches in models
        try:
            models._cache_clear()
        except Exception:
            pass
    except Exception:
        logging.exception('Startup maintenance failed')

# Run startup maintenance now (avoid relying on Flask decorator compatibility)
app_startup_maintenance()

@app.route('/')
def index():
    total_books = models.get_total_books()
    total_borrowers = models.get_total_borrowers()
    active_loans = models.get_total_active_loans()
    available_books = models.get_total_available_books()
    
    recent_loans = models.get_active_loans()
    # Add is_overdue flag to each loan
    now = datetime.utcnow()
    for loan in recent_loans:
        loan['is_overdue'] = models.is_loan_overdue(loan, now)
    
    return render_template('index.html', 
                         total_books=total_books,
                         total_borrowers=total_borrowers,
                         active_loans=active_loans,
                         available_books=available_books,
                         recent_loans=recent_loans)

@app.route('/books')
def books():
    search = request.args.get('search', '')
    category_filter = request.args.get('category', '')
    
    books = models.get_all_books(search, category_filter)
    categories = models.get_all_categories()
    
    return render_template('books.html', books=books, categories=categories)

@app.route('/books/add', methods=['GET', 'POST'])
def add_book():
    if request.method == 'POST':
        title = request.form.get('title')
        if not title or not title.strip():
            flash('Title is required.', 'danger')
            return redirect(url_for('add_book'))

        isbn = request.form.get('isbn') or None

        category_id_str = request.form.get('category_id')
        try:
            category_id = int(category_id_str) if category_id_str else None
        except (TypeError, ValueError):
            flash('Invalid category selected.', 'danger')
            return redirect(url_for('add_book'))
        # Validate category exists if provided
        if category_id is not None and not models.get_category_by_id(category_id):
            flash('Selected category does not exist.', 'danger')
            return redirect(url_for('add_book'))

        author_name = request.form.get('author_name') or None
        publisher_name = request.form.get('publisher_name') or None

        try:
            quantity_raw = request.form.get('quantity', '1')
            quantity = int(quantity_raw)
            if quantity < 0:
                raise ValueError('quantity')
        except (TypeError, ValueError):
            flash('Quantity must be a non-negative integer.', 'danger')
            return redirect(url_for('add_book'))

        try:
            models.add_book(title.strip(), isbn, category_id, author_name, publisher_name, quantity)
        except Exception:
            logging.exception('Failed to add book')
            flash('Failed to add book. See server logs for details.', 'danger')
            return redirect(url_for('add_book'))

        flash('Book added successfully!', 'success')
        return redirect(url_for('books'))
    
    categories = models.get_all_categories()
    
    return render_template('add_book.html', categories=categories)

@app.route('/books/edit/<int:id>', methods=['GET', 'POST'])
def edit_book(id):
    book = models.get_book_by_id(id)
    if not book:
        abort(404)
    
    if request.method == 'POST':
        title = request.form.get('title')
        isbn = request.form.get('isbn') or None
        
        category_id_str = request.form.get('category_id')
        try:
            category_id = int(category_id_str) if category_id_str else None
        except (TypeError, ValueError):
            flash('Invalid category selected.', 'danger')
            return redirect(url_for('edit_book', id=id))
        # Validate category exists if provided
        if category_id is not None and not models.get_category_by_id(category_id):
            flash('Selected category does not exist.', 'danger')
            return redirect(url_for('edit_book', id=id))
        
        author_name = request.form.get('author_name') or None
        publisher_name = request.form.get('publisher_name') or None
        # Validate quantity
        try:
            new_quantity_raw = request.form.get('quantity')
            if new_quantity_raw is None or new_quantity_raw == '':
                flash('Quantity is required.', 'danger')
                return redirect(url_for('edit_book', id=id))
            new_quantity = int(new_quantity_raw)
            if new_quantity < 0:
                flash('Quantity must be non-negative.', 'danger')
                return redirect(url_for('edit_book', id=id))
        except ValueError:
            flash('Quantity must be a number.', 'danger')
            return redirect(url_for('edit_book', id=id))

        # Get active loans count from the update function
        try:
            active_loans = models.update_book(id, title, isbn, category_id, author_name, publisher_name, new_quantity)
        except Exception as e:
            logging.exception('Error updating book %s', id)
            flash('An error occurred while updating the book. See server logs for details.', 'danger')
            return redirect(url_for('edit_book', id=id))

        if new_quantity < active_loans:
            flash(f'Cannot set quantity to {new_quantity}. There are {active_loans} active loans for this book.', 'danger')
            return redirect(url_for('edit_book', id=id))

        flash('Book updated successfully!', 'success')
        return redirect(url_for('books'))
    
    categories = models.get_all_categories()
    
    return render_template('edit_book.html', book=book, categories=categories)

@app.route('/books/delete/<int:id>')
def delete_book(id):
    # Prevent deleting a book that has any loans (active or returned)
    try:
        loans_count = models.get_loans_count_for_book(id)
        if loans_count and loans_count > 0:
            flash('Cannot delete book while loans reference it. Return or delete loans first.', 'danger')
            return redirect(url_for('books'))

        try:
            models.delete_book(id)
        except sqlite3.IntegrityError:
            logging.exception('IntegrityError deleting book %s', id)
            flash('Cannot delete book due to database constraints.', 'danger')
            return redirect(url_for('books'))
        except Exception:
            logging.exception('Failed to delete book %s', id)
            flash('Failed to delete book.', 'danger')
            return redirect(url_for('books'))

        flash('Book deleted successfully!', 'success')
        return redirect(url_for('books'))
    except Exception:
        logging.exception('Error checking loans for book %s', id)
        flash('Failed to delete book. See server logs for details.', 'danger')
        return redirect(url_for('books'))

@app.route('/categories')
def categories():
    categories = models.get_all_categories()
    return render_template('categories.html', categories=categories)

@app.route('/categories/add', methods=['POST'])
def add_category_route():
    name = request.form.get('name')
    if not name or not name.strip():
        flash('Category name is required.', 'danger')
        return redirect(url_for('categories'))

    try:
        models.add_category(name.strip())
    except Exception:
        logging.exception('Failed to add category')
        flash('Failed to add category. It may already exist or there was a server error.', 'danger')
        return redirect(url_for('categories'))

    flash('Category added successfully!', 'success')
    return redirect(url_for('categories'))

@app.route('/categories/edit/<int:id>', methods=['GET', 'POST'])
def edit_category(id):
    category = models.get_category_by_id(id)
    if not category:
        abort(404)
    
    if request.method == 'POST':
        name = request.form.get('name')
        if not name or not name.strip():
            flash('Category name is required.', 'danger')
            return redirect(url_for('edit_category', id=id))

        try:
            models.update_category(id, name.strip())
        except Exception:
            logging.exception('Failed to update category %s', id)
            flash('Failed to update category.', 'danger')
            return redirect(url_for('edit_category', id=id))

        flash('Category updated successfully!', 'success')
        return redirect(url_for('categories'))
    
    return render_template('edit_category.html', category=category)

@app.route('/categories/delete/<int:id>')
def delete_category(id):
    # Prevent deleting a category that has books
    try:
        books_in_cat = models.get_all_books('', id)
        if books_in_cat and len(books_in_cat) > 0:
            flash('Cannot delete category while books reference it. Remove or reassign books first.', 'danger')
            return redirect(url_for('categories'))

        models.delete_category(id)
    except Exception:
        logging.exception('Failed to delete category %s', id)
        flash('Failed to delete category.', 'danger')
        return redirect(url_for('categories'))

    flash('Category deleted successfully!', 'success')
    return redirect(url_for('categories'))

@app.route('/authors')
def authors():
    authors = models.get_all_authors()
    return render_template('authors.html', authors=authors)

@app.route('/authors/add', methods=['POST'])
def add_author_route():
    name = request.form.get('name')
    if not name or not name.strip():
        flash('Author name is required.', 'danger')
        return redirect(url_for('authors'))
    try:
        models.add_author(name.strip())
    except Exception:
        logging.exception('Failed to add author')
        flash('Failed to add author.', 'danger')
        return redirect(url_for('authors'))

    flash('Author added successfully!', 'success')
    return redirect(url_for('authors'))

@app.route('/authors/edit/<int:id>', methods=['GET', 'POST'])
def edit_author(id):
    author = models.get_author_by_id(id)
    if not author:
        abort(404)
    
    if request.method == 'POST':
        name = request.form.get('name')
        if not name or not name.strip():
            flash('Author name is required.', 'danger')
            return redirect(url_for('edit_author', id=id))
        try:
            models.update_author(id, name.strip())
        except Exception:
            logging.exception('Failed to update author %s', id)
            flash('Failed to update author.', 'danger')
            return redirect(url_for('edit_author', id=id))

        flash('Author updated successfully!', 'success')
        return redirect(url_for('authors'))
    
    return render_template('edit_author.html', author=author)

@app.route('/authors/delete/<int:id>')
def delete_author(id):
    # Prevent deleting author if books reference the author by name
    try:
        author = models.get_author_by_id(id)
        if not author:
            abort(404)
        author_name = author.get('name')
        all_books = models.get_all_books()
        referencing = [b for b in all_books if b.get('author_name') == author_name]
        if referencing:
            flash('Cannot delete author while books reference them. Reassign or remove those books first.', 'danger')
            return redirect(url_for('authors'))

        models.delete_author(id)
    except Exception:
        logging.exception('Failed to delete author %s', id)
        flash('Failed to delete author.', 'danger')
        return redirect(url_for('authors'))

    flash('Author deleted successfully!', 'success')
    return redirect(url_for('authors'))

@app.route('/publishers')
def publishers():
    publishers = models.get_all_publishers()
    return render_template('publishers.html', publishers=publishers)

@app.route('/publishers/add', methods=['POST'])
def add_publisher_route():
    name = request.form.get('name')
    if not name or not name.strip():
        flash('Publisher name is required.', 'danger')
        return redirect(url_for('publishers'))
    try:
        models.add_publisher(name.strip())
    except Exception:
        logging.exception('Failed to add publisher')
        flash('Failed to add publisher.', 'danger')
        return redirect(url_for('publishers'))

    flash('Publisher added successfully!', 'success')
    return redirect(url_for('publishers'))

@app.route('/publishers/edit/<int:id>', methods=['GET', 'POST'])
def edit_publisher(id):
    publisher = models.get_publisher_by_id(id)
    if not publisher:
        abort(404)
    
    if request.method == 'POST':
        name = request.form.get('name')
        if not name or not name.strip():
            flash('Publisher name is required.', 'danger')
            return redirect(url_for('edit_publisher', id=id))
        try:
            models.update_publisher(id, name.strip())
        except Exception:
            logging.exception('Failed to update publisher %s', id)
            flash('Failed to update publisher.', 'danger')
            return redirect(url_for('edit_publisher', id=id))

        flash('Publisher updated successfully!', 'success')
        return redirect(url_for('publishers'))
    
    return render_template('edit_publisher.html', publisher=publisher)

@app.route('/publishers/delete/<int:id>')
def delete_publisher(id):
    # Prevent deleting publisher if books reference the publisher by name
    try:
        publisher = models.get_publisher_by_id(id)
        if not publisher:
            abort(404)
        publisher_name = publisher.get('name')
        all_books = models.get_all_books()
        referencing = [b for b in all_books if b.get('publisher_name') == publisher_name]
        if referencing:
            flash('Cannot delete publisher while books reference it. Reassign or remove those books first.', 'danger')
            return redirect(url_for('publishers'))

        models.delete_publisher(id)
    except Exception:
        logging.exception('Failed to delete publisher %s', id)
        flash('Failed to delete publisher.', 'danger')
        return redirect(url_for('publishers'))

    flash('Publisher deleted successfully!', 'success')
    return redirect(url_for('publishers'))

@app.route('/borrowers')
def borrowers():
    borrowers = models.get_all_borrowers()
    return render_template('borrowers.html', borrowers=borrowers)

@app.route('/borrowers/add', methods=['GET', 'POST'])
def add_borrower_route():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        if not name or not name.strip():
            flash('Borrower name is required.', 'danger')
            return redirect(url_for('add_borrower_route'))
        try:
            models.add_borrower(name.strip(), email.strip() if email else None, phone.strip() if phone else None)
        except Exception:
            logging.exception('Failed to add borrower')
            flash('Failed to add borrower.', 'danger')
            return redirect(url_for('add_borrower_route'))

        flash('Borrower added successfully!', 'success')
        return redirect(url_for('borrowers'))
    
    return render_template('add_borrower.html')

@app.route('/borrowers/edit/<int:id>', methods=['GET', 'POST'])
def edit_borrower(id):
    borrower = models.get_borrower_by_id(id)
    if not borrower:
        abort(404)
    
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        if not name or not name.strip():
            flash('Borrower name is required.', 'danger')
            return redirect(url_for('edit_borrower', id=id))
        try:
            models.update_borrower(id, name.strip(), email.strip() if email else None, phone.strip() if phone else None)
        except Exception:
            logging.exception('Failed to update borrower %s', id)
            flash('Failed to update borrower.', 'danger')
            return redirect(url_for('edit_borrower', id=id))

        flash('Borrower updated successfully!', 'success')
        return redirect(url_for('borrowers'))
    
    return render_template('edit_borrower.html', borrower=borrower)

@app.route('/borrowers/delete/<int:id>')
def delete_borrower(id):
    # Prevent deleting a borrower that has active loans
    try:
        active_loans = models.get_active_loans_count_for_borrower(id)
        if active_loans and active_loans > 0:
            flash('Cannot delete borrower while active loans exist. Return those books first.', 'danger')
            return redirect(url_for('borrowers'))

        # Also prevent deleting if the borrower has any loan history (FK prevents deletion)
        total_loans = models.get_loans_count_for_borrower(id)
        if total_loans and total_loans > 0:
            flash('Cannot delete borrower: loan history exists. Remove loans first or anonymize the record.', 'danger')
            return redirect(url_for('borrowers'))

        try:
            models.delete_borrower(id)
        except sqlite3.IntegrityError:
            logging.exception('IntegrityError deleting borrower %s', id)
            flash('Cannot delete borrower due to database constraints.', 'danger')
            return redirect(url_for('borrowers'))
        except Exception:
            logging.exception('Failed to delete borrower %s', id)
            flash('Failed to delete borrower.', 'danger')
            return redirect(url_for('borrowers'))

        flash('Borrower deleted successfully!', 'success')
        return redirect(url_for('borrowers'))
    except Exception:
        logging.exception('Error checking loans for borrower %s', id)
        flash('Failed to delete borrower. See server logs for details.', 'danger')
        return redirect(url_for('borrowers'))

@app.route('/loans')
def loans():
    loans = models.get_all_loans()
    # Add is_overdue flag to each loan
    now = datetime.utcnow()
    for loan in loans:
        loan['is_overdue'] = models.is_loan_overdue(loan, now)
    return render_template('loans.html', loans=loans)

@app.route('/loans/add', methods=['GET', 'POST'])
def add_loan_route():
    if request.method == 'POST':
        # Validate and convert IDs
        try:
            book_id = int(request.form.get('book_id'))
            borrower_id = int(request.form.get('borrower_id'))
        except (TypeError, ValueError):
            flash('Invalid book or borrower selection.', 'danger')
            return redirect(url_for('add_loan_route'))

        try:
            book = models.get_book_by_id(book_id)
        except Exception:
            logging.exception('Error fetching book %s', book_id)
            flash('An internal error occurred.', 'danger')
            return redirect(url_for('add_loan_route'))

        if book and book.get('available', 0) > 0:
            try:
                models.add_loan(book_id, borrower_id)
            except Exception:
                logging.exception('Error creating loan for book %s borrower %s', book_id, borrower_id)
                flash('Failed to create loan; try again.', 'danger')
                return redirect(url_for('add_loan_route'))

            flash('Book loaned successfully!', 'success')
            return redirect(url_for('loans'))
        else:
            flash('Book is not available!', 'danger')
    
    # Get available books only
    all_books = models.get_all_books()
    books = [b for b in all_books if b['available'] > 0]
    borrowers = models.get_all_borrowers()
    
    return render_template('add_loan.html', books=books, borrowers=borrowers)

@app.route('/loans/return/<int:id>')
def return_loan_route(id):
    models.return_loan(id)
    flash('Book returned successfully!', 'success')
    return redirect(url_for('loans'))

# Generic error handler to log unexpected exceptions and present a friendly message
@app.errorhandler(Exception)
def handle_exception(e):
    # If it's an HTTPException, let Flask handle the response
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e

    logging.exception('Unhandled exception:')
    # Return a simple message and 500 status
    return render_template('500.html'), 500


if __name__ == '__main__':
    # Disable the auto-reloader when running directly to avoid spawning a
    # second process that may concurrently access the SQLite file and cause
    # "database is locked" errors during development.
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
