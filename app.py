from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import csv
from flask import Response
from sklearn.linear_model import LinearRegression
import numpy as np
import pandas as pd

from datetime import datetime

app = Flask(__name__)

# Initialize DB
def init_db():
    with sqlite3.connect('expenses.db') as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                category TEXT,
                amount REAL,
                description TEXT
            )
        ''')
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
        # Add WHERE 1=1 to base_query so we can use AND safely
        base_query += " WHERE 1=1" + where_clause
        income_query += where_clause
        expense_query += where_clause

    # ✅ Append ORDER BY just once
    base_query += " ORDER BY date DESC"

    with sqlite3.connect('expenses.db') as conn:
        expenses = conn.execute(base_query, params).fetchall()
        income = conn.execute(income_query, params).fetchone()[0] or 0
        expense = conn.execute(expense_query, params).fetchone()[0] or 0
        total = income - expense

    return render_template("index.html", expenses=expenses, total=total, income=income, expense=expense)


@app.route('/add', methods=['POST'])
def add():
    date = request.form['date']
    category = request.form['category']
    amount = float(request.form['amount'])  # make sure it's float
    description = request.form['description']
    entry_type = request.form['type']

    with sqlite3.connect('expenses.db') as conn:
        conn.execute(
            "INSERT INTO expenses (date, category, amount, description, type) VALUES (?, ?, ?, ?, ?)",
            (date, category, amount, description, entry_type)
        )
    return redirect(url_for('index'))


@app.route('/delete/<int:expense_id>')
def delete(expense_id):
    with sqlite3.connect('expenses.db') as conn:
        conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    return redirect(url_for('index'))
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

@app.route('/charts')
def charts():
    with sqlite3.connect('expenses.db') as conn:
        # Get income and expense totals
        income = conn.execute("SELECT SUM(amount) FROM expenses WHERE type = 'income'").fetchone()[0] or 0
        expense = conn.execute("SELECT SUM(amount) FROM expenses WHERE type = 'expense'").fetchone()[0] or 0

        # Existing: get expenses grouped by category
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


@app.route('/export')
def export_csv():
    with sqlite3.connect('expenses.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM expenses ORDER BY date DESC")
        expenses = cursor.fetchall()

    def generate():
        data = [["ID", "Date", "Category", "Amount", "Description"]]  # CSV headers
        data += expenses  # add all expense rows
        for row in data:
            yield ','.join([str(item) for item in row]) + '\n'

    return Response(
        generate(),
        mimetype='text/csv',
        headers={"Content-Disposition": "attachment;filename=expenses.csv"}
    )

@app.route('/predict')
def predict():
    with sqlite3.connect('expenses.db') as conn:
        # Get only EXPENSE entries (not income)
        rows = conn.execute("""
            SELECT date, amount FROM expenses
            WHERE type = 'expense'
        """).fetchall()

    # Convert to pandas DataFrame
    df = pd.DataFrame(rows, columns=['date', 'amount'])

    # Convert "date" to "YYYY-MM"
    df['date'] = pd.to_datetime(df['date'])
    df['month'] = df['date'].dt.to_period('M')

    # Group by month
    monthly = df.groupby('month')['amount'].sum().reset_index()

    # Convert month to numeric index
    monthly['month_index'] = np.arange(len(monthly))

    # Prepare data
    X = monthly[['month_index']]
    y = monthly['amount']

    # Train model
    model = LinearRegression()
    model.fit(X, y)

    # Predict next month
    next_index = np.array([[len(monthly)]])
    predicted_amount = model.predict(next_index)[0]

    # Format month name
    next_month = (monthly['month'].iloc[-1] + 1).strftime("%B %Y")

    return render_template(
        "predict.html",
        next_month=next_month,
        predicted_amount=round(predicted_amount, 2),
        history=monthly.to_dict('records')
    )


if __name__ == '__main__':
    init_db()
    app.run(debug=True,port=5000,host='0.0.0.0')
