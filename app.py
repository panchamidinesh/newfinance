from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response
import sqlite3
import os
from datetime import datetime
from io import StringIO, BytesIO
import pandas as pd
from xhtml2pdf import pisa

# Initialize app
app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Determine DB path
if os.environ.get("FLASK_ENV") == "testing":
    DB_PATH = 'test_database.db'
else:
    DB_PATH = os.path.join(os.getcwd(), 'instance', 'database.db')

# Connect to DB
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# DB setup
with get_db_connection() as conn:
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT NOT NULL UNIQUE,
                        password TEXT NOT NULL
                    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS transactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT NOT NULL,
                        type TEXT NOT NULL,
                        category TEXT NOT NULL,
                        amount REAL NOT NULL,
                        note TEXT,
                        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )''')
    conn.commit()

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
            conn.commit()
            flash('Registered successfully! Please login.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists.')
        finally:
            conn.close()

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
        conn.close()

        if user:
            session['username'] = username
            flash(f'Welcome, {username}!')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials!')

    return render_template('login.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'username' not in session:
        flash('You must be logged in to view the dashboard.')
        return redirect(url_for('login'))


    username = session['username']
    conn = get_db_connection()

    if request.method == 'POST':
        # Handle adding a new transaction
        t_type = request.form['type']
        category = request.form['category']
        amount = float(request.form['amount'])
        note = request.form['note']

        conn.execute('INSERT INTO transactions (username, type, category, amount, note) VALUES (?, ?, ?, ?, ?)',
                     (username, t_type, category, amount, note))
        conn.commit()
        flash('Transaction added successfully!')

    selected_category = request.args.get('category')
    selected_month = request.args.get('month')

    query = 'SELECT * FROM transactions WHERE username = ?'
    params = [username]

    if selected_category:
        query += ' AND category = ?'
        params.append(selected_category)

    if selected_month:
        query += " AND strftime('%Y-%m', date) = ?"
        params.append(selected_month)
    else:
        selected_month = datetime.now().strftime('%Y-%m')
        query += " AND strftime('%Y-%m', date) = ?"
        params.append(selected_month)

    query += ' ORDER BY date DESC'
    transactions = conn.execute(query, tuple(params)).fetchall()

    income = conn.execute(
        "SELECT SUM(amount) FROM transactions WHERE username=? AND type='income' AND strftime('%Y-%m', date)=?",
        (username, selected_month)).fetchone()[0] or 0

    expense = conn.execute(
        "SELECT SUM(amount) FROM transactions WHERE username=? AND type='expense' AND strftime('%Y-%m', date)=?",
        (username, selected_month)).fetchone()[0] or 0

    savings = income - expense

    categories = conn.execute("SELECT DISTINCT category FROM transactions WHERE username = ?", (username,)).fetchall()

    label_query = conn.execute("SELECT category, amount, type FROM transactions WHERE username=? ORDER BY date DESC LIMIT 10", (username,))
    labels, amounts, types = [], [], []
    for row in label_query:
        labels.append(row['category'])
        amounts.append(row['amount'])
        types.append(row['type'])

    conn.close()

    return render_template('dashboard.html',
                           username=username,
                           transactions=transactions,
                           total_income=income,
                           total_expenses=expense,
                           monthly_savings=savings,
                           selected_category=selected_category,
                           selected_month=selected_month,
                           categories=categories,
                           labels=labels,
                           amounts=amounts,
                           types=types)

@app.route('/download_report/<format>')
def download_report(format):
    if 'username' not in session:
        flash('You must be logged in to download a report.')
        return redirect(url_for('login'))

    username = session['username']
    conn = get_db_connection()
    transactions = conn.execute('SELECT * FROM transactions WHERE username = ?', (username,)).fetchall()
    conn.close()

    data = [{
        'Type': t['type'], 'Category': t['category'], 'Amount': t['amount'],
        'Note': t['note'], 'Date': t['date']}
        for t in transactions]

    df = pd.DataFrame(data)

    if format == 'csv':
        csv_data = df.to_csv(index=False)
        response = make_response(csv_data)
        response.headers["Content-Disposition"] = "attachment; filename=transactions.csv"
        response.headers["Content-Type"] = "text/csv"
        return response

    elif format == 'pdf':
        html = df.to_html(index=False)
        pdf = BytesIO()
        pisa.CreatePDF(StringIO(html), dest=pdf)
        response = make_response(pdf.getvalue())
        response.headers["Content-Disposition"] = "attachment; filename=transactions.pdf"
        response.headers["Content-Type"] = "application/pdf"
        return response

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_transaction(id):
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    transaction = conn.execute("SELECT * FROM transactions WHERE id = ?", (id,)).fetchone()

    if request.method == 'POST':
        t_type = request.form['type']
        category = request.form['category']
        amount = float(request.form['amount'])
        note = request.form['note']

        conn.execute('UPDATE transactions SET type=?, category=?, amount=?, note=? WHERE id=?',
                     (t_type, category, amount, note, id))
        conn.commit()
        conn.close()
        flash('Transaction added successfully!')
        return redirect(url_for('dashboard'))

    conn.close()
    return render_template('edit_transaction.html', transaction=transaction)

@app.route('/delete/<int:id>', methods=['POST'])
def delete_transaction(id):
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    conn.execute('DELETE FROM transactions WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash('Transaction deleted successfully!')
    return redirect(url_for('dashboard'))

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    flash('You have been logged out.')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
