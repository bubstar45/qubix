# transfer_to_neon.py
import sqlite3
import psycopg2
from psycopg2.extras import execute_values

# !!! REPLACE WITH YOUR ACTUAL NEON CONNECTION STRING !!!
NEON_DATABASE_URL = 'postgresql://YOUR_USER:YOUR_PASSWORD@YOUR_HOST:5432/YOUR_DB?sslmode=require'

print("📦 Starting database transfer...")

# Connect to SQLite
sqlite_conn = sqlite3.connect('db.sqlite3')
sqlite_conn.text_factory = bytes  # Handle bytes properly
sqlite_cursor = sqlite_conn.cursor()
print("✅ Connected to SQLite")

# Connect to PostgreSQL
pg_conn = psycopg2.connect(NEON_DATABASE_URL)
pg_cursor = pg_conn.cursor()
print("✅ Connected to Neon PostgreSQL")

# First, clear existing data (but keep structure)
print("\n🗑️  Clearing existing data from Neon...")
pg_cursor.execute("""
    DO $$ DECLARE
        r RECORD;
    BEGIN
        FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
            EXECUTE 'TRUNCATE TABLE ' || quote_ident(r.tablename) || ' CASCADE';
        END LOOP;
    END $$;
""")
pg_conn.commit()
print("✅ Cleared existing data")

# Get all tables
sqlite_cursor.execute("""
    SELECT name FROM sqlite_master 
    WHERE type='table' 
    AND name NOT LIKE 'sqlite_%' 
    AND name NOT LIKE 'django_migrations'
    AND name NOT LIKE 'django_admin_log'
    AND name NOT LIKE 'auth_permission'
    AND name NOT LIKE 'django_content_type'
    AND name NOT LIKE 'auth_group'
    AND name NOT LIKE 'auth_group_permissions'
""")
tables = sqlite_cursor.fetchall()

print(f"\n📋 Found {len(tables)} tables to transfer\n")

for table in tables:
    table_name = table[0]
    print(f"Processing: {table_name}")
    
    # Get column names and types
    sqlite_cursor.execute(f"PRAGMA table_info({table_name})")
    columns_info = sqlite_cursor.fetchall()
    columns = [col[1] for col in columns_info]
    
    if not columns:
        continue
    
    # Get data from SQLite
    sqlite_cursor.execute(f"SELECT * FROM {table_name}")
    rows = sqlite_cursor.fetchall()
    
    if rows:
        # Convert rows to proper types
        converted_rows = []
        for row in rows:
            converted_row = []
            for i, value in enumerate(row):
                # Convert bytes to string if needed
                if isinstance(value, bytes):
                    value = value.decode('utf-8')
                # Convert integer 0/1 to boolean for boolean columns
                col_name = columns[i]
                if value in (0, 1) and col_name in ['is_featured', 'is_auto_approve', 'price_update_enabled', 'is_active', 'is_staff', 'is_superuser', 'is_verified']:
                    value = bool(value)
                converted_row.append(value)
            converted_rows.append(tuple(converted_row))
        
        # Create insert statement
        columns_str = ', '.join(columns)
        placeholders = ', '.join(['%s'] * len(columns))
        insert_sql = f'INSERT INTO {table_name} ({columns_str}) VALUES %s'
        
        try:
            # Insert into PostgreSQL
            execute_values(pg_cursor, insert_sql, converted_rows, page_size=100)
            pg_conn.commit()
            print(f"  ✅ Transferred {len(rows)} rows")
        except Exception as e:
            print(f"  ❌ Error: {e}")
            pg_conn.rollback()
    else:
        print(f"  ⏭️  No data")

# Close connections
sqlite_conn.close()
pg_conn.close()
print("\n🎉 Transfer complete!")