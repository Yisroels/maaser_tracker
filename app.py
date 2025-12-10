from flask import Flask, render_template, request, redirect, url_for, flash
from database import init_db
from datetime import datetime
import sqlite3
import os
import PyPDF2
from werkzeug.utils import secure_filename

# Hebrew calendar + AI parser
from hebrew_dates import get_current_hebrew_year, get_hebrew_year_start_end
from ai_parser import parse_with_ai

app = Flask(__name__)
app.secret_key = 'change-this-to-something-random-123456789'
app.config['UPLOAD_FOLDER'] = os.path.join('instance', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

init_db()

ALLOWED_EXTENSIONS = {'csv', 'pdf', 'xlsx', 'xls'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    conn = sqlite3.connect('maaser.db')
    conn.row_factory = sqlite3.Row
    return conn

# ─── DASHBOARD WITH HEBREW / GREGORIAN TOGGLE ───
@app.route('/')
def index():
    conn = get_db_connection()

    period = request.args.get('period', 'gregorian')
    today = datetime.now()
    hebrew_year = get_current_hebrew_year()

    if period == 'hebrew':
        start_date, _ = get_hebrew_year_start_end(hebrew_year)
        title = f"Hebrew Year {hebrew_year} (תשפ״ו{hebrew_year - 5000})"
    else:
        start_date = today.strftime('%Y-01-01')
        title = f"Gregorian Year {today.year}"

    income = conn.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM transactions
        WHERE amount > 0 AND category = 'income' AND date >= ?
    """, (start_date,)).fetchone()[0]

    maaser_given = abs(conn.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM transactions WHERE category = 'maaser_given'
    """).fetchone()[0] or 0)

    owed = income * 0.1 - maaser_given

    conn.close()

    return render_template('index.html',
                           income=f"€ {income:,.2f}",
                           maaser_given=f"€ {maaser_given:,.2f}",
                           owed=f"€ {owed:,.2f}",
                           owed_class="text-success" if owed <= 0 else "text-danger",
                           title=title,
                           period=period,
                           hebrew_year=hebrew_year,
                           now_year=today.year)

# ─── MANUAL ENTRY ───
@app.route('/manual_entry', methods=['GET', 'POST'])
def manual_entry():
    if request.method == 'POST':
        date = request.form['date']
        amount = float(request.form['amount'])
        category = request.form['category']
        source = request.form.get('source', 'Manual')
        note = request.form.get('note', '')

        conn = get_db_connection()
        conn.execute('''
            INSERT INTO transactions (date, amount, description, category, source, note, imported_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (date, amount, '', category, source, note, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        flash('Transaction saved successfully!', 'success')
        return redirect(url_for('index'))

    today = datetime.now().strftime('%Y-%m-%d')
    return render_template('manual_entry.html', today=today)

# ─── UPLOAD WITH AI PARSER ───
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'danger')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            try:
                if filename.lower().endswith('.pdf'):
                    with open(filepath, 'rb') as f:
                        reader = PyPDF2.PdfReader(f)
                        raw_text = "\n".join(page.extract_text() or "" for page in reader.pages)
                else:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        raw_text = f.read()

                transactions = parse_with_ai(raw_text)

                if not transactions:
                    flash('AI found no transactions – wrong file?', 'warning')
                else:
                    conn = get_db_connection()
                    imported = 0
                    for t in transactions:
                        try:
                            amount = float(t['amount'])
                            conn.execute('''
                                INSERT INTO transactions
                                (date, amount, description, category, source, note, imported_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            ''', (t['date'], amount, t['description'], t['category'],
                                  'AI Parsed', '', datetime.now().isoformat()))
                            imported += 1
                        except Exception as e:
                            print(f"Skipped bad row: {e}")
                    conn.commit()
                    conn.close()
                    flash(f'AI successfully imported {imported} transactions', 'success')
                os.remove(filepath)
                return redirect(url_for('index'))

            except Exception as e:
                flash(f'AI parser error: {str(e)}', 'danger')
                if os.path.exists(filepath):
                    os.remove(filepath)
                return redirect(request.url)
        else:
            flash('Allowed files: csv, pdf, xlsx, xls', 'danger')
    return render_template('upload.html')

# ─── ALL TRANSACTIONS LIST ───
@app.route('/transactions')
def transactions():
    conn = get_db_connection()
    trans = conn.execute("""
        SELECT id, date, amount, description, category, source, note
        FROM transactions
        ORDER BY date DESC, id DESC
    """).fetchall()
    conn.close()
    return render_template('transactions.html', transactions=trans)

# ─── EDIT TRANSACTION ───
@app.route('/transaction/<int:id>/edit', methods=['GET', 'POST'])
def edit_transaction(id):
    conn = get_db_connection()
    if request.method == 'POST':
        category = request.form['category']
        note = request.form.get('note', '').strip()
        conn.execute('UPDATE transactions SET category = ?, note = ? WHERE id = ?', (category, note, id))
        conn.commit()
        conn.close()
        flash('Transaction updated successfully!', 'success')
        return redirect(url_for('transactions'))

    transaction = conn.execute('SELECT * FROM transactions WHERE id = ?', (id,)).fetchone()
    conn.close()
    if not transaction:
        flash('Transaction not found', 'danger')
        return redirect(url_for('transactions'))
    return render_template('edit_transaction.html', transaction=transaction)

# ─── DELETE TRANSACTION ───
@app.route('/transaction/<int:id>/delete')
def delete_transaction(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM transactions WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash('Transaction deleted successfully!', 'info')
    return redirect(url_for('transactions'))

# ─── BULK DELETE TRANSACTIONS ───
@app.route('/transactions/bulk_delete', methods=['POST'])
def bulk_delete_transactions():
    selected_ids = request.form.getlist('selected_ids')
    if not selected_ids:
        flash('No transactions selected', 'warning')
        return redirect(url_for('transactions'))

    conn = get_db_connection()
    conn.execute('DELETE FROM transactions WHERE id IN ({})'.format(','.join('?' for _ in selected_ids)), selected_ids)
    conn.commit()
    conn.close()
    flash(f'{len(selected_ids)} transactions deleted successfully!', 'info')
    return redirect(url_for('transactions'))
    
if __name__ == '__main__':
    app.run(debug=True)