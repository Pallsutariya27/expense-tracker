from flask import Flask, render_template, request, redirect, url_for, Response
import sqlite3
import csv
import numpy as np
import pandas as pd
from datetime import datetime

app = Flask(__name__)

# ---------------------- INIT DB ----------------------
def init_db():
    with sqlite3.connect('expenses.db') as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                category TEXT,
                amount REAL,
                description TEXT,
                type TEXT
            )
        ''')

# ---------------------- HOME PAGE ----------------------
@app.route('/')
def index():
    filter_type = request.args.get('filter', '')
    base_query = "SELECT * FROM expenses"
    income_query = "SELECT SUM(amount) FROM expenses WHERE type = 'income'"
    expense_query = "SELECT SUM(amount) FROM expenses WHERE type = 'expense'"
    params = []

    today = datetime.now().date()
    this_month = today.strftime("%Y-%m")
    this_year = today.strftime("%Y")

    where_clause = ""
    if filter_type == 'today':
        where_clause = " AND date = ?"
        params.append(str(today))
    elif filter_type == 'month':
        where_clause = " AND strftime('%Y-%m', date) = ?"
        params.append(this_month)
    elif filter_type == 'year':
        where_clause = " AND strftime('%Y', date) = ?"
        params.append(this_year)

    if where_clause:
        base_query += " WHERE 1=1" + where_clause
        income_query += where_clause
        expense_query += where_clause

    base_query += " ORDER BY date DESC"

    with sqlite3.connect('expenses.db') as conn:
        expenses = conn.execute(base_query, params).fetchall()
        income = conn.execute(income_query, params).fetchone()[0] or 0
        expense = conn.execute(expense_query, params).fetchone()[0] or 0
        total = income - expense

    return render_template("index.html", expenses=expenses, total=total, income=income, expense=expense)

# ---------------------- ADD EXPENSE ----------------------
@app.route('/add', methods=['POST'])
def add():
    date = request.form['date']
    category = request.form['category']
    amount = float(request.form['amount'])
    description = request.form['description']
    entry_type = request.form['type']

    with sqlite3.connect('expenses.db') as conn:
        conn.execute(
            "INSERT INTO expenses (date, category, amount, description, type) VALUES (?, ?, ?, ?, ?)",
            (date, category, amount, description, entry_type)
        )
    return redirect(url_for('index'))

# ---------------------- DELETE ----------------------
@app.route('/delete/<int:expense_id>')
def delete(expense_id):
    with sqlite3.connect('expenses.db') as conn:
        conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    return redirect(url_for('index'))

# ---------------------- EDIT ----------------------
@app.route('/edit/<int:expense_id>', methods=['GET', 'POST'])
def edit(expense_id):
    if request.method == 'POST':
        date = request.form['date']
        category = request.form['category']
        amount = request.form['amount']
        description = request.form['description']

        with sqlite3.connect('expenses.db') as conn:
            conn.execute('''
                UPDATE expenses
                SET date = ?, category = ?, amount = ?, description = ?
                WHERE id = ?
            ''', (date, category, amount, description, expense_id))
        return redirect(url_for('index'))

    else:
        with sqlite3.connect('expenses.db') as conn:
            expense = conn.execute('SELECT * FROM expenses WHERE id = ?', (expense_id,)).fetchone()
        return render_template('edit.html', expense=expense)

# ---------------------- CHARTS ----------------------
@app.route('/charts')
def charts():
    with sqlite3.connect('expenses.db') as conn:
        income = conn.execute("SELECT SUM(amount) FROM expenses WHERE type = 'income'").fetchone()[0] or 0
        expense = conn.execute("SELECT SUM(amount) FROM expenses WHERE type = 'expense'").fetchone()[0] or 0
        category_data = conn.execute('''
            SELECT category, SUM(amount)
            FROM expenses
            WHERE type = 'expense'
            GROUP BY category
        ''').fetchall()

    labels = [row[0] for row in category_data]
    amounts = [row[1] for row in category_data]

    return render_template(
        'charts.html',
        labels=labels,
        amounts=amounts,
        income=income,
        expense=expense
    )

# ---------------------- EXPORT CSV ----------------------
@app.route('/export')
def export_csv():
    with sqlite3.connect('expenses.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM expenses ORDER BY date DESC")
        expenses = cursor.fetchall()

    def generate():
        data = [["ID", "Date", "Category", "Amount", "Description", "Type"]]
        data += expenses
        for row in data:
            yield ','.join([str(item) for item in row]) + '\n'

    return Response(
        generate(),
        mimetype='text/csv',
        headers={"Content-Disposition": "attachment;filename=expenses.csv"}
    )

# ---------------------- PREDICTION (NumPy instead of sklearn) ----------------------
@app.route("/predict")
def predict():
    conn = sqlite3.connect("expenses.db")
    df = pd.read_sql_query("SELECT amount, date FROM expenses WHERE type='expense'", conn)
    conn.close()

    if df.empty:
        return render_template("predict.html",
                               predicted_amount=0,
                               next_month=datetime.now().strftime("%b %Y"),
                               history=[])

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna()

    if df.empty:
        return render_template("predict.html",
                               predicted_amount=0,
                               next_month=datetime.now().strftime("%b %Y"),
                               history=[])

    # Aggregate monthly totals
    df["month"] = df["date"].dt.to_period("M")
    monthly_data = df.groupby("month")["amount"].sum().reset_index()
    monthly_data["month_str"] = monthly_data["month"].dt.strftime("%b %Y")
    history = list(zip(monthly_data["month_str"], monthly_data["amount"]))

    # Linear regression for prediction
    monthly_data["timestamp"] = monthly_data["month"].dt.to_timestamp().astype(np.int64) // 10**9
    X = monthly_data["timestamp"].values
    y = monthly_data["amount"].values

    if len(X) < 2:
        predicted_amount = round(y[-1], 2)
    else:
        slope, intercept = np.polyfit(X, y, 1)
        next_timestamp = X.max() + 30 * 86400  # approximate next month in seconds
        predicted_amount = round(slope * next_timestamp + intercept, 2)

    # Next month label
    last_month = monthly_data["month"].max().to_timestamp()
    next_month = (last_month + pd.DateOffset(months=1)).strftime("%b %Y")

    return render_template("predict.html",
                           predicted_amount=predicted_amount,
                           next_month=next_month,
                           history=history)


# ---------------------- RUN APP ----------------------
if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000, host='0.0.0.0')
