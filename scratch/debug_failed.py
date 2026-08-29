import sqlite3
conn = sqlite3.connect('webguard.db')
cur = conn.cursor()
cur.execute('SELECT tool_name, status, raw_output FROM tool_scores WHERE status="FAILED"')
for row in cur.fetchall():
    print(f"Tool: {row[0]}")
    print(f"Status: {row[1]}")
    print(f"Output: {row[2]}")
    print("-" * 50)
conn.close()
