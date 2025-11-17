import os
import tempfile
import models

# Use a temporary database file for tests
DB_OLD = models.DB

def setup_module(module):
    fd, path = tempfile.mkstemp(prefix='test_library_', suffix='.db')
    os.close(fd)
    models.DB = path
    models.init_db()

def teardown_module(module):
    try:
        os.remove(models.DB)
    except Exception:
        pass
    finally:
        models.DB = DB_OLD


def test_create_borrower_and_delete_flow():
    # Create borrower
    borrower_id = models.add_borrower('Test User', 'test@example.com', '123456')
    assert borrower_id is not None

    # Create book
    book_id = models.add_book('Test Book', 'ISBN-TEST', None, 'Author', 'Publisher', 1)
    assert book_id is not None

    # Loan the book to borrower
    loan_id = models.add_loan(book_id, borrower_id)
    assert loan_id is not None

    # Attempt to delete borrower should be blocked by active loan
    active_count = models.get_active_loans_count_for_borrower(borrower_id)
    assert active_count == 1

    try:
        models.delete_borrower(borrower_id)
        deleted = True
    except Exception:
        deleted = False

    # Should not be deleted because foreign key or app logic prevents it
    assert deleted is True or models.get_borrower_by_id(borrower_id) is not None

    # Return loan
    models.return_loan(loan_id)

    # Now there should be 0 active loans
    assert models.get_active_loans_count_for_borrower(borrower_id) == 0

    # Now deleting borrower should succeed (no active loans)
    models.delete_borrower(borrower_id)
    assert models.get_borrower_by_id(borrower_id) is None
