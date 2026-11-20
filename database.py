"""
database.py
All database (SQLite) work for the Personal Expense Tracker lives here,
so the Streamlit UI file (app.py) stays clean and simple.
"""

import sqlite3
from contextlib import closing

import pandas as pd

DB_NAME = "expenses.db"

CATEGORIES = [
    "Food", "Transport", "Rent", "Shopping", "Bills & Recharge",
    "Education", "Entertainment", "Health", "Other",
]


# Simple rule used to spot "unnecessary" spending:
# essential categories are Needs, everything else is a Want (can be reduced).
NEEDS = {"Food", "Transport", "Rent", "Bills & Recharge", "Education", "Health"}


def spending_type(category):
    return "Need" if category in NEEDS else "Want"


def get_connection():
    return sqlite3.connect(DB_NAME)


def init_db():
    """Create the tables if they do not exist yet."""
    with closing(get_connection()) as conn, conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                date     TEXT NOT NULL,            -- stored as YYYY-MM-DD
                category TEXT NOT NULL,
                amount   REAL NOT NULL CHECK (amount > 0),
                note     TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS income (
                month  TEXT PRIMARY KEY,           -- stored as YYYY-MM
                amount REAL NOT NULL CHECK (amount > 0)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS budget (
                month  TEXT PRIMARY KEY,           -- stored as YYYY-MM
                amount REAL NOT NULL CHECK (amount > 0)
            )
            """
        )


# ---------- CREATE / UPDATE / DELETE ----------

def add_expense(date, category, amount, note=""):
    with closing(get_connection()) as conn, conn:
        conn.execute(
            "INSERT INTO expenses (date, category, amount, note) VALUES (?, ?, ?, ?)",
            (str(date), category, float(amount), note.strip()),
        )


def update_expense(expense_id, date, category, amount, note=""):
    with closing(get_connection()) as conn, conn:
        conn.execute(
            "UPDATE expenses SET date = ?, category = ?, amount = ?, note = ? WHERE id = ?",
            (str(date), category, float(amount), note.strip(), expense_id),
        )


def delete_expense(expense_id):
    with closing(get_connection()) as conn, conn:
        conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))


# ---------- READ ----------

def get_all_expenses():
    """Return every expense as a DataFrame, newest first."""
    with closing(get_connection()) as conn:
        return pd.read_sql_query(
            "SELECT id, date, category, amount, note FROM expenses ORDER BY date DESC, id DESC",
            conn,
        )


def get_month_expenses(month):
    """month is 'YYYY-MM'."""
    with closing(get_connection()) as conn:
        return pd.read_sql_query(
            "SELECT id, date, category, amount, note FROM expenses "
            "WHERE substr(date, 1, 7) = ? ORDER BY date DESC, id DESC",
            conn,
            params=(month,),
        )


def get_months():
    """List of months (YYYY-MM) that have at least one expense, newest first."""
    with closing(get_connection()) as conn:
        rows = conn.execute(
            "SELECT DISTINCT substr(date, 1, 7) FROM expenses ORDER BY 1 DESC"
        ).fetchall()
    return [r[0] for r in rows]


def category_totals(month=None):
    """Total spent per category (for one month, or for all time if month is None)."""
    query = "SELECT category, SUM(amount) AS total FROM expenses"
    params = ()
    if month:
        query += " WHERE substr(date, 1, 7) = ?"
        params = (month,)
    query += " GROUP BY category ORDER BY total DESC"
    with closing(get_connection()) as conn:
        return pd.read_sql_query(query, conn, params=params)


def monthly_totals():
    """Total spent in every month, oldest first (good for a trend chart)."""
    with closing(get_connection()) as conn:
        return pd.read_sql_query(
            "SELECT substr(date, 1, 7) AS month, SUM(amount) AS total, COUNT(*) AS transactions "
            "FROM expenses GROUP BY month ORDER BY month",
            conn,
        )


# ---------- BUDGET ----------

def set_budget(month, amount):
    with closing(get_connection()) as conn, conn:
        conn.execute(
            "INSERT INTO budget (month, amount) VALUES (?, ?) "
            "ON CONFLICT(month) DO UPDATE SET amount = excluded.amount",
            (month, float(amount)),
        )


def get_budget(month):
    """Return the budget for a month, or None if not set."""
    with closing(get_connection()) as conn:
        row = conn.execute("SELECT amount FROM budget WHERE month = ?", (month,)).fetchone()
    return row[0] if row else None


def remove_budget(month):
    with closing(get_connection()) as conn, conn:
        conn.execute("DELETE FROM budget WHERE month = ?", (month,))


# ---------- INCOME (needed to calculate savings) ----------

def set_income(month, amount):
    with closing(get_connection()) as conn, conn:
        conn.execute(
            "INSERT INTO income (month, amount) VALUES (?, ?) "
            "ON CONFLICT(month) DO UPDATE SET amount = excluded.amount",
            (month, float(amount)),
        )


def get_income(month):
    """Return the income for a month, or None if not set."""
    with closing(get_connection()) as conn:
        row = conn.execute("SELECT amount FROM income WHERE month = ?", (month,)).fetchone()
    return row[0] if row else None


def remove_income(month):
    with closing(get_connection()) as conn, conn:
        conn.execute("DELETE FROM income WHERE month = ?", (month,))


def get_all_income():
    with closing(get_connection()) as conn:
        return pd.read_sql_query("SELECT month, amount AS income FROM income ORDER BY month", conn)
