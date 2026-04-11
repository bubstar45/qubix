import sqlite3

conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()

# Remove money emoji from all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

for table in tables:
    table_name = table[0]
    try:
        cursor.execute(f"UPDATE {table_name} SET description = REPLACE(description, '💰', '') WHERE description LIKE '%💰%'")
        cursor.execute(f"UPDATE {table_name} SET notes = REPLACE(notes, '💰', '') WHERE notes LIKE '%💰%'")
        cursor.execute(f"UPDATE {table_name} SET name = REPLACE(name, '💰', '') WHERE name LIKE '%💰%'")
        print(f"Cleaned {table_name}")
    except:
        pass

conn.commit()
print("Done! Emoji removed.")
conn.close()