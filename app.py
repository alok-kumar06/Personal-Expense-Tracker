"""
app.py
Personal Expense Tracker - Streamlit user interface.
Run with:  streamlit run app.py
"""

import calendar
from datetime import date, datetime, timedelta

import altair as alt
import pandas as pd
import streamlit as st

import database as db

st.set_page_config(page_title="Personal Expense Tracker", page_icon="💰", layout="wide")
db.init_db()

CURRENCY = "₹"


# ---------- small helper functions ----------

def money(value):
    sign = "-" if value < 0 else ""
    return f"{sign}{CURRENCY}{abs(value):,.2f}"


def month_label(month):
    """'2026-11' -> 'November 2026'"""
    return datetime.strptime(month, "%Y-%m").strftime("%B %Y")


def previous_month(month):
    first_day = datetime.strptime(month, "%Y-%m").date()
    return (first_day - timedelta(days=1)).strftime("%Y-%m")


def days_counted(month):
    """Days to divide by for 'average per day' (days passed so far if it is the current month)."""
    today = date.today()
    if month == today.strftime("%Y-%m"):
        return today.day
    year, mon = map(int, month.split("-"))
    return calendar.monthrange(year, mon)[1]


def flash(message):
    """Remember a message so it can be shown after the page reloads."""
    st.session_state["flash"] = message


def show_flash():
    if "flash" in st.session_state:
        st.success(st.session_state.pop("flash"))


def months_for_selector():
    months = db.get_months()
    this_month = date.today().strftime("%Y-%m")
    if this_month not in months:
        months.insert(0, this_month)
    return months


def donut_chart(cat_df):
    """Donut chart with a legend (no overlapping labels). Hover to see exact amounts."""
    return (
        alt.Chart(cat_df)
        .mark_arc(innerRadius=70)
        .encode(
            theta=alt.Theta("total:Q"),
            color=alt.Color("category:N", sort=list(cat_df["category"]), legend=alt.Legend(title="Category")),
            order=alt.Order("total:Q", sort="descending"),
            tooltip=[
                alt.Tooltip("category:N", title="Category"),
                alt.Tooltip("total:Q", title="Total (₹)", format=",.2f"),
            ],
        )
        .properties(height=320)
    )


def category_bar_chart(cat_df):
    """Horizontal bars sorted from highest to lowest, with the amount written on each bar."""
    base = alt.Chart(cat_df).encode(
        y=alt.Y("category:N", sort="-x", title=None),
        x=alt.X("total:Q", title="Total spent (₹)"),
        tooltip=[
            alt.Tooltip("category:N", title="Category"),
            alt.Tooltip("total:Q", title="Total (₹)", format=",.2f"),
        ],
    )
    labels = base.mark_text(align="left", dx=4).encode(text=alt.Text("total:Q", format=",.0f"))
    return (base.mark_bar() + labels).properties(height=max(200, 38 * len(cat_df)))


# ---------- pages ----------

def page_dashboard():
    st.title("📊 Dashboard")
    show_flash()

    months = months_for_selector()
    month = st.selectbox("Select month", months, format_func=month_label)

    df = db.get_month_expenses(month)
    if df.empty:
        st.info(f"No expenses recorded for {month_label(month)} yet. Add one from the sidebar.")
        return

    total = df["amount"].sum()
    income = db.get_income(month)
    cat_df = db.category_totals(month)

    # 1) The three main questions: received, spent, left
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💵 Money received", money(income) if income else "Not set")
    c1.caption("Your income this month")
    c2.metric("🧾 Money spent", money(total))
    c2.caption(f"Across {len(df)} transactions")
    if income:
        left_over = income - total
        c3.metric("💰 Money left", money(left_over))
        c3.caption("Income minus money spent")
        c4.metric("Savings rate", f"{left_over / income * 100:.1f}%")
        c4.caption("Share of income you kept")
        if left_over < 0:
            st.error(f"You spent {money(-left_over)} more than you received this month.")
    else:
        c3.metric("💰 Money left", "—")
        c3.caption("Income minus money spent")
        c4.metric("Savings rate", "—")
        st.info("Set your monthly income on the **Income & Budget** page to see how much money you have left.")

    # 2) Budget status
    budget = db.get_budget(month)
    st.subheader("Budget status")
    if budget is None:
        st.caption("No spending limit set for this month. You can set one on the Income & Budget page.")
    else:
        used = total / budget
        st.progress(min(used, 1.0), text=f"{money(total)} of {money(budget)} used ({used * 100:.1f}%)")
        if total > budget:
            st.error(f"You are over budget by {money(total - budget)}.")
        elif used >= 0.8:
            st.warning(f"Careful, you have used {used * 100:.0f}% of your budget. {money(budget - total)} left.")
        else:
            st.success(f"You are within budget. {money(budget - total)} left.")

    # 3) Spending habits
    st.subheader("Your spending habits")
    daily = df.groupby("date")["amount"].sum()
    top_day, top_day_amount = daily.idxmax(), daily.max()
    types = df["category"].map(db.spending_type)
    needs = df.loc[types == "Need", "amount"].sum()
    wants = df.loc[types == "Want", "amount"].sum()

    h1, h2, h3, h4 = st.columns(4)
    h1.metric("Average per day", money(total / days_counted(month)))
    h2.metric("Highest spending day", money(top_day_amount))
    h2.caption(f"on {pd.to_datetime(top_day).strftime('%d %b %Y')}")
    h3.metric("Needs", money(needs))
    h3.caption(f"{needs / total * 100:.1f}% of spending (food, rent, bills, travel, education, health)")
    h4.metric("Wants (can be reduced)", money(wants))
    h4.caption(f"{wants / total * 100:.1f}% of spending (shopping, entertainment, other)")

    prev = previous_month(month)
    prev_total = db.get_month_expenses(prev)["amount"].sum()
    if prev_total > 0:
        diff = total - prev_total
        word = "more" if diff > 0 else "less"
        note = " The month is still in progress." if month == date.today().strftime("%Y-%m") else ""
        st.info(f"You spent {money(abs(diff))} ({abs(diff) / prev_total * 100:.1f}%) {word} than in {month_label(prev)}.{note}")

    # 4) Category breakdown
    st.subheader("Where is my money going?")
    left, right = st.columns(2)
    with left:
        show_df = cat_df.copy()
        show_df["share"] = (show_df["total"] / total * 100).round(1).astype(str) + " %"
        show_df["total"] = show_df["total"].map(money)
        show_df.columns = ["Category", "Total", "Share"]
        st.dataframe(show_df, hide_index=True)
    with right:
        st.altair_chart(donut_chart(cat_df))

    st.subheader("Recent transactions")
    recent = df.head(5).copy()
    recent["amount"] = recent["amount"].map(money)
    recent = recent.drop(columns="id")
    recent.columns = ["Date", "Category", "Amount", "Note"]
    st.dataframe(recent, hide_index=True)


def page_add():
    st.title("➕ Add Expense")
    with st.form("add_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        exp_date = col1.date_input("Date", value=date.today(), max_value=date.today())
        category = col2.selectbox("Category", db.CATEGORIES)
        amount = st.number_input(f"Amount ({CURRENCY})", min_value=0.0, step=10.0, format="%.2f")
        note = st.text_input("Note (optional)", placeholder="e.g. Lunch with friends")
        submitted = st.form_submit_button("Save expense", type="primary")

    if submitted:
        if amount <= 0:
            st.error("Amount must be greater than 0.")
        else:
            db.add_expense(exp_date, category, amount, note)
            st.success(f"Saved: {money(amount)} on {category} ({exp_date}).")


def page_manage():
    st.title("📝 View, Edit and Delete")
    show_flash()

    df = db.get_all_expenses()
    if df.empty:
        st.info("No expenses yet. Add your first one from the sidebar.")
        return

    # Filters
    f1, f2 = st.columns(2)
    categories = f1.multiselect("Filter by category", db.CATEGORIES)
    search = f2.text_input("Search in notes")
    if categories:
        df = df[df["category"].isin(categories)]
    if search:
        df = df[df["note"].fillna("").str.contains(search, case=False)]

    if df.empty:
        st.warning("No expenses match your filters.")
        return

    st.caption(f"Showing {len(df)} expenses, total {money(df['amount'].sum())}")
    table = df.copy()
    table["amount"] = table["amount"].map(money)
    table.columns = ["ID", "Date", "Category", "Amount", "Note"]
    st.dataframe(table, hide_index=True)

    # Pick one expense to edit or delete
    st.subheader("Edit or delete an expense")
    labels = {
        row.id: f"#{row.id} | {row.date} | {row.category} | {money(row.amount)} | {row.note or ''}"
        for row in df.itertuples()
    }
    chosen_id = st.selectbox("Choose an expense", list(labels), format_func=labels.get)
    row = df[df["id"] == chosen_id].iloc[0]

    edit_col, delete_col = st.columns([2, 1])

    with edit_col:
        with st.form(f"edit_form_{chosen_id}"):
            e1, e2 = st.columns(2)
            new_date = e1.date_input("Date", value=pd.to_datetime(row["date"]).date(), max_value=date.today())
            cat_index = db.CATEGORIES.index(row["category"]) if row["category"] in db.CATEGORIES else 0
            new_cat = e2.selectbox("Category", db.CATEGORIES, index=cat_index)
            new_amount = st.number_input(f"Amount ({CURRENCY})", min_value=0.0, value=float(row["amount"]), step=10.0, format="%.2f")
            new_note = st.text_input("Note", value=row["note"] or "")
            if st.form_submit_button("Update expense", type="primary"):
                if new_amount <= 0:
                    st.error("Amount must be greater than 0.")
                else:
                    db.update_expense(chosen_id, new_date, new_cat, new_amount, new_note)
                    flash(f"Expense #{chosen_id} updated.")
                    st.rerun()

    with delete_col:
        st.write("**Delete this expense**")
        confirm = st.checkbox("Yes, I want to delete it", key=f"confirm_{chosen_id}")
        if st.button("Delete expense", disabled=not confirm):
            db.delete_expense(chosen_id)
            flash(f"Expense #{chosen_id} deleted.")
            st.rerun()


def page_reports():
    st.title("📈 Reports")
    df = db.get_all_expenses()
    if df.empty:
        st.info("No data yet. Add some expenses to see reports.")
        return

    st.subheader("Monthly spending trend")
    monthly = db.monthly_totals()
    st.bar_chart(monthly.set_index("month")["total"])

    # Month-wise income, spending and savings
    summary = monthly.merge(db.get_all_income(), on="month", how="left")
    summary["saved"] = summary["income"] - summary["total"]
    shown = pd.DataFrame({
        "Month": summary["month"].map(month_label),
        "Income": summary["income"].map(lambda v: money(v) if pd.notna(v) else "—"),
        "Spent": summary["total"].map(money),
        "Saved": summary["saved"].map(lambda v: money(v) if pd.notna(v) else "—"),
        "Transactions": summary["transactions"],
    })
    st.dataframe(shown, hide_index=True)
    st.caption("Income and savings appear only for months where you have set your income.")

    st.subheader("All-time spending by category")
    cat_df = db.category_totals()
    left, right = st.columns(2)
    with left:
        table = cat_df.copy()
        table["total"] = table["total"].map(money)
        table.columns = ["Category", "Total spent"]
        st.dataframe(table, hide_index=True)
    with right:
        st.altair_chart(category_bar_chart(cat_df))

    st.download_button(
        "⬇️ Download all expenses (CSV)",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="expenses.csv",
        mime="text/csv",
    )


def page_income_budget():
    st.title("🎯 Income & Budget")
    show_flash()

    months = months_for_selector()
    month = st.selectbox("Month", months, format_func=month_label)
    income = db.get_income(month)
    budget = db.get_budget(month)
    spent = db.get_month_expenses(month)["amount"].sum()

    st.caption(
        f"{month_label(month)}: income {money(income) if income else 'not set'} | "
        f"budget {money(budget) if budget else 'not set'} | spent so far {money(spent)}"
    )

    col_income, col_budget = st.columns(2)

    with col_income:
        st.subheader("Monthly income")
        st.caption("Needed to calculate your savings (income minus spending).")
        with st.form("income_form"):
            value = st.number_input(f"Income ({CURRENCY})", min_value=0.0, value=float(income or 0.0), step=500.0, format="%.2f")
            if st.form_submit_button("Save income", type="primary"):
                if value <= 0:
                    st.error("Income must be greater than 0.")
                else:
                    db.set_income(month, value)
                    flash(f"Income for {month_label(month)} set to {money(value)}.")
                    st.rerun()
        if income and st.button("Remove income"):
            db.remove_income(month)
            flash(f"Income for {month_label(month)} removed.")
            st.rerun()

    with col_budget:
        st.subheader("Spending limit (budget)")
        st.caption("You will get a warning when you reach 80% of it.")
        with st.form("budget_form"):
            value = st.number_input(f"Budget ({CURRENCY})", min_value=0.0, value=float(budget or 0.0), step=500.0, format="%.2f")
            if st.form_submit_button("Save budget", type="primary"):
                if value <= 0:
                    st.error("Budget must be greater than 0.")
                else:
                    db.set_budget(month, value)
                    flash(f"Budget for {month_label(month)} set to {money(value)}.")
                    st.rerun()
        if budget and st.button("Remove budget"):
            db.remove_budget(month)
            flash(f"Budget for {month_label(month)} removed.")
            st.rerun()


# ---------- navigation ----------

PAGES = {
    "📊 Dashboard": page_dashboard,
    "➕ Add Expense": page_add,
    "📝 View / Edit / Delete": page_manage,
    "📈 Reports": page_reports,
    "🎯 Income & Budget": page_income_budget,
}

st.sidebar.title("💰 Expense Tracker")
choice = st.sidebar.radio("Go to", list(PAGES))
st.sidebar.caption("Data is stored locally in expenses.db (SQLite).")
PAGES[choice]()
