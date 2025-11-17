# Library Management System

## Overview
A web-based Library Management System built with Flask and SQLite3. This application allows librarians to manage books, borrowers, and lending operations efficiently.

## Project Architecture
- **Backend**: Flask (Python web framework)
- **Database**: SQLite3 with direct SQL queries
- **Frontend**: Bootstrap 5, HTML, CSS, JavaScript
- **Port**: Running on 0.0.0.0:5000

## Database Schema
- **Categories**: Book categories/genres (managed via dropdown)
- **Authors**: Stored as text in books table
- **Publishers**: Stored as text in books table
- **Books**: Book inventory with quantity tracking, author_name and publisher_name as TEXT fields
- **Borrowers**: Library members
- **Loans**: Book lending transactions with due dates (ISO 8601 format)

## Features
- Book management (CRUD operations) with category dropdown, text input for author/publisher
- Category management (CRUD)
- Author and Publisher management (CRUD - legacy tables remain)
- Borrower registration with active loan counts
- Book lending and return system with 14-day default loan period
- Dashboard with statistics
- Search and filter functionality
- Overdue loan detection

## Technical Implementation
- SQLite3 with `check_same_thread=False` for multi-threaded Flask
- Date storage in ISO 8601 format as TEXT
- Direct SQL queries with parameter binding
- Template date display using string slicing ([:10])
- Active loan counts via SQL aggregation

## Recent Changes
- Migrated from SQLAlchemy to SQLite3 (November 15, 2025)
- Fixed category field display in books listing
- Converted author and publisher from foreign keys to text fields
- Fixed strftime errors on date strings in templates
- Added database locked error fix
- Restored borrower active loan counts
- Fixed overdue loan detection logic
