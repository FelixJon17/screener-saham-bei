"""
src/db.py
Penyimpanan persisten aplikasi.

Dua backend dengan isi yang sama:
  - PostgreSQL bila DATABASE_URL diisi (Streamlit Secrets atau variabel
    lingkungan). Dipakai saat di-hosting, karena berkas di Streamlit Community
    Cloud ikut terhapus setiap kali aplikasi di-reboot atau tertidur.
  - SQLite (data/app.db) bila DATABASE_URL kosong, mis. saat dijalankan lokal.

Isi basis data:
  users      akun beserta peran (admin / user) dan hash kata sandi
  datasets   riwayat dataset yang diunggah admin
  settings   pengaturan global, misalnya dataset aktif dan data perhitungan
  activity   log aktivitas (masuk, kelola pengguna, ganti dataset)
  blobs      isi CSV dataset unggahan, agar tidak hilang bersama berkasnya

Modul ini tidak bergantung pada streamlit kecuali untuk membaca Secrets,
sehingga dapat diuji tanpa menjalankan aplikasi. Kueri ditulis dengan
placeholder "?" dan diubah ke "%s" untuk PostgreSQL.
"""
from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime

import pandas as pd

import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    username      TEXT PRIMARY KEY,
    full_name     TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('admin', 'user')),
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL,
    last_login    TEXT
);
CREATE TABLE IF NOT EXISTS datasets (
    id           {pk},
    filename     TEXT NOT NULL,
    stored_path  TEXT NOT NULL,
    n_rows       INTEGER NOT NULL,
    uploaded_by  TEXT,
    uploaded_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS activity (
    id        {pk},
    ts        TEXT NOT NULL,
    username  TEXT,
    action    TEXT NOT NULL,
    detail    TEXT
);
CREATE TABLE IF NOT EXISTS blobs (
    key         TEXT PRIMARY KEY,
    content     TEXT NOT NULL,
    updated_at  TEXT NOT NULL
)
"""
_PK = {"sqlite": "INTEGER PRIMARY KEY AUTOINCREMENT", "postgres": "BIGSERIAL PRIMARY KEY"}


def now() -> str:
    """Waktu sekarang dalam WIB (config.TIMEZONE), bukan zona waktu server."""
    return datetime.now(config.TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")


# --------------------------------------------------------------------------
# Koneksi
# --------------------------------------------------------------------------
_url_cache: list[str | None] = []


def _database_url() -> str | None:
    """DATABASE_URL dari Streamlit Secrets, lalu variabel lingkungan."""
    if not _url_cache:
        url = None
        try:
            import streamlit as st
            url = st.secrets.get("DATABASE_URL")
        except Exception:   # tidak ada secrets.toml
            pass
        url = url or os.environ.get("DATABASE_URL")
        _url_cache.append(str(url).strip() if url else None)
    return _url_cache[0]


def backend() -> str:
    return "postgres" if _database_url() else "sqlite"


# Satu koneksi PostgreSQL per proses, dipakai bergantian (dikunci) oleh semua
# sesi. Koneksi dibuka ulang otomatis bila diputus server (mis. Neon tertidur).
_pg_lock = threading.RLock()
_pg_con = None


def _pg_connection():
    global _pg_con
    if _pg_con is None or _pg_con.closed:
        import psycopg
        from psycopg.rows import dict_row
        # prepare_threshold=None: tanpa prepared statement di server, agar
        # aman dipakai lewat connection pooler (Neon/Supabase, PgBouncer).
        _pg_con = psycopg.connect(_database_url(), autocommit=True, row_factory=dict_row,
                                  connect_timeout=15, prepare_threshold=None)
    return _pg_con


def _run(sql: str, params: tuple = (), fetch: str | None = None):
    """Menjalankan satu kueri. fetch: None, "one" (dict/None), atau "all" (list[dict])."""
    global _pg_con
    if backend() == "postgres":
        import psycopg
        sql = sql.replace("?", "%s")
        with _pg_lock:
            for percobaan in (1, 2):
                try:
                    with _pg_connection().cursor() as cur:
                        cur.execute(sql, params)
                        if fetch == "one":
                            return cur.fetchone()
                        if fetch == "all":
                            return cur.fetchall()
                        return None
                except psycopg.OperationalError:
                    _pg_con = None          # koneksi putus: buka ulang sekali
                    if percobaan == 2:
                        raise

    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        cur = con.execute(sql, params)
        if fetch == "one":
            row = cur.fetchone()
            out = dict(row) if row else None
        elif fetch == "all":
            out = [dict(r) for r in cur.fetchall()]
        else:
            out = None
        con.commit()
        return out
    finally:
        con.close()


def init(hasher) -> None:
    """
    Membuat tabel bila belum ada dan mengisi akun awal bila tabel pengguna
    kosong. `hasher` adalah fungsi hash kata sandi dari src/auth.py, dioper
    sebagai argumen supaya modul ini tidak bergantung pada modul autentikasi.
    """
    for stmt in _SCHEMA.format(pk=_PK[backend()]).split(";"):
        if stmt.strip():
            _run(stmt)
    if _run("SELECT COUNT(*) AS n FROM users", fetch="one")["n"] == 0:
        for acc in config.SEED_ACCOUNTS:
            create_user(acc["username"], acc["full_name"],
                        hasher(_secret_password(acc) or acc["password"]), acc["role"])
    _sync_secret_passwords(hasher)


def _secret_password(acc: dict) -> str | None:
    """
    Kata sandi akun awal dari Streamlit Secrets (ADMIN_PASSWORD /
    INVESTOR_PASSWORD) saat di-hosting, agar kata sandi demo di README tidak
    berlaku. None bila tidak diisi (mis. dijalankan lokal).
    """
    try:
        import streamlit as st
        key = f"{acc['username']}_password"
        pw = st.secrets.get(key.upper()) or st.secrets.get(key)
    except Exception:   # tidak ada secrets.toml
        return None
    return (str(pw).strip() or None) if pw else None


def _sync_secret_passwords(hasher) -> None:
    """
    Menerapkan kata sandi dari Secrets ke akun awal yang sudah ada, setiap kali
    nilai Secrets diisi atau diganti (dicatat sebagai hash SHA-256 di tabel
    settings). Kata sandi yang diganti lewat Profil tetap berlaku sampai nilai
    Secrets berubah lagi.
    """
    import hashlib
    for acc in config.SEED_ACCOUNTS:
        pw = _secret_password(acc)
        if not pw:
            continue
        tanda, key = hashlib.sha256(pw.encode()).hexdigest(), f"secret_pw_{acc['username']}"
        if get_setting(key) == tanda:
            continue
        if get_user(acc["username"]):
            update_user(acc["username"], password_hash=hasher(pw))
            log(None, "Kata sandi dari Secrets diterapkan", acc["username"])
        set_setting(key, tanda)


# --------------------------------------------------------------------------
# Pengguna
# --------------------------------------------------------------------------
def get_user(username: str) -> dict | None:
    return _run("SELECT * FROM users WHERE username = ?", (username,), "one")


def list_users() -> pd.DataFrame:
    return pd.DataFrame(_run(
        "SELECT username, full_name, role, is_active, created_at, last_login"
        " FROM users ORDER BY role, username", fetch="all"))


def create_user(username: str, full_name: str, password_hash: str, role: str) -> None:
    _run("INSERT INTO users (username, full_name, password_hash, role, created_at)"
         " VALUES (?, ?, ?, ?, ?)", (username, full_name, password_hash, role, now()))


def update_user(username: str, **fields) -> None:
    allowed = {"full_name", "password_hash", "role", "is_active", "last_login"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return
    sets = ", ".join(f"{k} = ?" for k in fields)
    _run(f"UPDATE users SET {sets} WHERE username = ?", (*fields.values(), username))


def delete_user(username: str) -> None:
    _run("DELETE FROM users WHERE username = ?", (username,))


def count_active_admins() -> int:
    return _run("SELECT COUNT(*) AS n FROM users WHERE role = 'admin' AND is_active = 1",
                fetch="one")["n"]


# --------------------------------------------------------------------------
# Pengaturan global
# --------------------------------------------------------------------------
def get_setting(key: str, default: str | None = None) -> str | None:
    row = _run("SELECT value FROM settings WHERE key = ?", (key,), "one")
    return row["value"] if row and row["value"] is not None else default


def set_setting(key: str, value: str | None) -> None:
    _run("INSERT INTO settings (key, value) VALUES (?, ?)"
         " ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))


# --------------------------------------------------------------------------
# Isi berkas dataset (agar dataset unggahan tidak hilang saat server di-reset)
# --------------------------------------------------------------------------
def put_blob(key: str, content: str) -> None:
    _run("INSERT INTO blobs (key, content, updated_at) VALUES (?, ?, ?)"
         " ON CONFLICT(key) DO UPDATE SET content = excluded.content,"
         " updated_at = excluded.updated_at", (key, content, now()))


def get_blob(key: str) -> str | None:
    row = _run("SELECT content FROM blobs WHERE key = ?", (key,), "one")
    return row["content"] if row else None


def delete_blob(key: str) -> None:
    _run("DELETE FROM blobs WHERE key = ?", (key,))


# --------------------------------------------------------------------------
# Riwayat dataset
# --------------------------------------------------------------------------
def add_dataset(filename: str, stored_path: str, n_rows: int, uploaded_by: str) -> int:
    row = _run("INSERT INTO datasets (filename, stored_path, n_rows, uploaded_by, uploaded_at)"
               " VALUES (?, ?, ?, ?, ?) RETURNING id",
               (filename, stored_path, n_rows, uploaded_by, now()), "one")
    return int(row["id"])


def get_dataset(dataset_id: int) -> dict | None:
    return _run("SELECT * FROM datasets WHERE id = ?", (dataset_id,), "one")


def list_datasets() -> pd.DataFrame:
    return pd.DataFrame(_run("SELECT * FROM datasets ORDER BY id DESC", fetch="all"))


def delete_dataset(dataset_id: int) -> None:
    _run("DELETE FROM datasets WHERE id = ?", (dataset_id,))


# --------------------------------------------------------------------------
# Log aktivitas
# --------------------------------------------------------------------------
KOLOM_LOG = ["Waktu", "Pengguna", "Aktivitas", "Keterangan"]
_SELECT_LOG = ('SELECT ts AS "Waktu", username AS "Pengguna", action AS "Aktivitas",'
               ' detail AS "Keterangan" FROM activity')


def log(username: str | None, action: str, detail: str = "") -> None:
    _run("INSERT INTO activity (ts, username, action, detail) VALUES (?, ?, ?, ?)",
         (now(), username, action, detail))


def recent_activity(limit: int = 50) -> pd.DataFrame:
    rows = _run(f"{_SELECT_LOG} ORDER BY id DESC LIMIT ?", (limit,), "all")
    return pd.DataFrame(rows, columns=KOLOM_LOG)


AKTIVITAS_DATASET = ("Unggah dataset global", "Aktifkan dataset", "Hapus dataset",
                     "Ganti data perhitungan")


def dataset_activity(limit: int = 50) -> pd.DataFrame:
    """Log perubahan dataset global dan data perhitungan (halaman Data & Model)."""
    tanda = ",".join("?" * len(AKTIVITAS_DATASET))
    rows = _run(f"{_SELECT_LOG} WHERE action IN ({tanda}) ORDER BY id DESC LIMIT ?",
                (*AKTIVITAS_DATASET, limit), "all")
    return pd.DataFrame(rows, columns=KOLOM_LOG)


def activity_per_day(days: int = 14) -> pd.DataFrame:
    rows = _run("SELECT substr(ts, 1, 10) AS tanggal, COUNT(*) AS jumlah"
                " FROM activity WHERE action = 'Masuk'"
                " GROUP BY tanggal ORDER BY tanggal DESC LIMIT ?", (days,), "all")
    return pd.DataFrame(rows, columns=["tanggal", "jumlah"])
