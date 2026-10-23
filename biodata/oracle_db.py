# Koneksi dan query ke Oracle (SQL langsung, tanpa ORM Django).
import os
import re
from contextlib import contextmanager

import cx_Oracle
from dotenv import load_dotenv

load_dotenv()

_initialized = False

# memuat Instant Client sekali saja. Oracle mengharuskan pemanggilan ini tidak boleh dua kali.
def _init_client():
    global _initialized
    if not _initialized:
        cx_Oracle.init_oracle_client(lib_dir=os.environ["ORA_CLIENT_DIR"])
        _initialized = True

# membaca nama tabel dari .env. Regex memastikan isinya hanya huruf, angka, dan karakter yang sah. Nama tabel disisipkan langsung ke SQL (tidak bisa memakai bind variable), jadi ini perlu dijaga.
def _table_name():
    name = os.getenv("ORA_TABLE", "EMPMASTEREPMS")
    schema = os.getenv("ORA_SCHEMA", "")
    full = f"{schema}.{name}" if schema else name
    if not re.fullmatch(r"[A-Za-z0-9_$#.]+", full):
        raise ValueError("Nama tabel/schema di .env tidak valid")
    return full

TABLE = _table_name()

def _view_name():
    name = (os.getenv("ORA_VIEW_COMPSITE") or "VW_REF_COMPSITE").strip()
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_$#]*(\.[A-Za-z][A-Za-z0-9_$#])?", name):
        raise ValueError(f"Nama View di .env tidak valdi: {name!r}")
    return name

VIEW_COMPSITE = _view_name()
    

# membuka koneksi lalu menutupnya otomatis (finally), walaupun terjadi error. Setiap permintaan halaman membuka koneksi baru. Ini sederhana dan cukup untuk pemakaian internal. Kalau nanti pengguna banyak, bisa diganti connection pool.
@contextmanager
def get_connection():
    _init_client()
    conn = cx_Oracle.connect(
        os.environ["ORA_USER"],
        os.environ["ORA_PASSWORD"],
        os.environ["ORA_DSN"],
    )
    try:
        yield conn
    finally:
        conn.close()


def _rows_as_dicts(cur):
    names = [d[0] for d in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def fetch_all(sql, binds=None):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, binds or {})
        return _rows_as_dicts(cur)


def fetch_one(sql, binds=None):
    rows = fetch_all(sql, binds)
    return rows[0] if rows else None


def scalar(sql, binds=None):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, binds or {})
        return cur.fetchone()[0]


def execute(sql, binds=None):
    """Jalankan INSERT/UPDATE, commit bila berhasil."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, binds or {})
        conn.commit()
