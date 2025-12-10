import sqlite3
from datetime import datetime
import os

DATABASE = 'maaser.db'

def init_db():
    # Create database + table if they don't exist
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,              -- ISO format YYYY-MM-DD
            amount REAL NOT NULL,            -- positive = income, negative = expense or maaser given
            description TEXT,
            category TEXT DEFAULT 'income',  -- income / expense / maaser_given
            source TEXT,                     -- ING, Amex, Beobank, Wise, Cash, Manual...
            note TEXT,                       -- your personal description
            imported_at TEXT                 -- when it was imported
        )
    ''')
    
    # Create index for speed
    c.execute('CREATE INDEX IF NOT EXISTS idx_date ON transactions(date)')
    
    conn.commit()
    conn.close()

# Call it once when app starts
if not os.path.exists(DATABASE):
    init_db()