import sqlite3
import json
import os

DB = os.path.join(os.path.dirname(__file__), '..', 'db.sqlite3')
DB = os.path.abspath(DB)
print(json.dumps({'db_path': DB}))
if not os.path.exists(DB):
    print(json.dumps({'error':'db not found', 'path': DB}))
    raise SystemExit(1)

conn = sqlite3.connect(DB)
cur = conn.cursor()
try:
    cur.execute('SELECT id, ip, server_reachable, last_seen, ssid, last_wifi_event FROM core_deviceinstance')
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    out = [dict(zip(cols, r)) for r in rows]
    if not out:
        print(json.dumps({'rows': [], 'note': 'no device rows found'}))
    else:
        print(json.dumps(out, default=str))
except Exception as e:
    print(json.dumps({'error': str(e)}))
finally:
    conn.close()