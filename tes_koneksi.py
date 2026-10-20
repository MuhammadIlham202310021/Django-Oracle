import os
import cx_Oracle
from dotenv import load_dotenv

load_dotenv()
cx_Oracle.init_oracle_client(lib_dir=os.environ["ORA_CLIENT_DIR"])

conn = cx_Oracle.connect(
    os.environ["ORA_USER"],
    os.environ["ORA_PASSWORD"],
    os.environ["ORA_DSN"],
)
print("Versi server:", conn.version)

cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM EMPMASTEREPMS")
print("Jumlah baris:", cur.fetchone()[0])
conn.close()