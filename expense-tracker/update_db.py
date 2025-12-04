import sqlite3

try:
    with sqlite3.connect('expenses.db') as conn:
        conn.execute("ALTER TABLE expenses ADD COLUMN type TEXT DEFAULT 'expense'")
        print("✅ Column 'type' added successfully.")
except sqlite3.OperationalError as e:
    print("⚠️ Error:", e)