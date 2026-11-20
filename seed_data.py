"""
seed_data.py
Adds about 60 sample expenses (last 3 months) plus sample income and budget so you can test the app quickly.
Run once:  python seed_data.py
"""

import random
from datetime import date, timedelta

import database as db

db.init_db()
if not db.get_all_expenses().empty:
    print("Database already has data. Delete expenses.db first if you want fresh sample data.")
    raise SystemExit

random.seed(42)

SAMPLES = {
    "Food": ("Lunch", "Dinner", "Snacks", "Tea and samosa", "Groceries", (40, 400)),
    "Transport": ("Auto fare", "Bus ticket", "Train ticket", "Petrol", (20, 500)),
    "Rent": ("Hostel/room rent", (3500, 3500)),
    "Shopping": ("T-shirt", "Shoes", "Backpack", "Stationery", (150, 1800)),
    "Bills & Recharge": ("Mobile recharge", "Wi-Fi bill", "Electricity bill", (199, 700)),
    "Education": ("Online course", "Books", "Printout and xerox", (50, 900)),
    "Entertainment": ("Movie", "OTT subscription", "Outing with friends", (100, 600)),
    "Health": ("Medicine", "Doctor visit", (80, 500)),
    "Other": ("Gift", "Miscellaneous", (50, 300)),
}
WEIGHTS = {"Food": 20, "Transport": 10, "Shopping": 5, "Bills & Recharge": 4,
           "Education": 4, "Entertainment": 4, "Health": 2, "Other": 3}

today = date.today()

# one rent entry per month
for months_back in range(3):
    first_of_month = (today.replace(day=1) - timedelta(days=30 * months_back)).replace(day=3)
    if first_of_month <= today:
        db.add_expense(first_of_month, "Rent", 3500, "Hostel/room rent")

# random expenses over the last 90 days
cats = list(WEIGHTS)
for _ in range(57):
    cat = random.choices(cats, weights=[WEIGHTS[c] for c in cats])[0]
    *notes, (low, high) = SAMPLES[cat]
    when = today - timedelta(days=random.randint(0, 89))
    db.add_expense(when, cat, round(random.uniform(low, high), 2), random.choice(notes))

# sample income and budget for every month that has expenses
for month in db.get_months():
    db.set_income(month, 15000)
    db.set_budget(month, 11000)

print("Sample data added.")
