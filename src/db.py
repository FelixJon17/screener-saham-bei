"""
src/db.py
Penyimpanan persisten aplikasi berbasis SQLite (pustaka standar Python).

Isi basis data:
  users      akun beserta peran (admin / user) dan hash kata sandi
  watchlist  daftar pantau saham milik setiap pengguna
  datasets   riwayat dataset yang diunggah admin
  settings   pengaturan global, misalnya dataset aktif dan nilai k
  activity   log aktivitas (masuk, kelola pengguna, ganti dataset)

Modul ini tidak mengimpor streamlit, sama seperti modul pipeline lainnya,
sehingga dapat diuji tanpa menjalankan aplikasi. Setiap fungsi membuka
koneksinya sendiri agar aman dipakai dari banyak sesi Streamlit sekaligus.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator

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
CREATE TABLE IF NOT EXISTS watchlist (
    username  TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE,
    kode      TEXT NOT NULL,
    added_at  TEXT NOT NULL,
    PRIMARY KEY (username, kode)
);
CREATE TABLE IF NOT EXISTS datasets (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
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
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        TEXT NOT NULL,
    username  TEXT,
    action    TEXT NOT NULL,
    detail    TEXT
);
"""


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init(hasher) -> None:
    """
    Membuat tabel bila belum ada dan mengisi akun awal bila tabel pengguna
    kosong. `hasher` adalah fungsi hash kata sandi dari src/auth.py, dioper
    sebagai argumen supaya modul ini tidak bergantung pada modul autentikasi.
    """
    with connect() as con:
        con.executescript(_SCHEMA)
        n = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if n == 0:
            for acc in config.SEED_ACCOUNTS:
                con.execute(
                    "INSERT INTO users (username, full_name, password_hash, role, created_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (acc["username"], acc["full_name"], hasher(acc["password"]),
                     acc["role"], now()),
                )


# --------------------------------------------------------------------------
# Pengguna
# --------------------------------------------------------------------------
def get_user(username: str) -> dict | None:
    with connect() as con:
        row = con.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return dict(row) if row else None


def list_users() -> pd.DataFrame:
    with connect() as con:
        rows = con.execute(
            "SELECT u.username, u.full_name, u.role, u.is_active, u.created_at,"
            "       u.last_login, COUNT(w.kode) AS n_watchlist"
            " FROM users u LEFT JOIN watchlist w ON w.username = u.username"
            " GROUP BY u.username ORDER BY u.role, u.username"
        ).fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def create_user(username: str, full_name: str, password_hash: str, role: str) -> None:
    with connect() as con:
        con.execute(
            "INSERT INTO users (username, full_name, password_hash, role, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (username, full_name, password_hash, role, now()),
        )


def update_user(username: str, **fields) -> None:
    allowed = {"full_name", "password_hash", "role", "is_active", "last_login"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return
    sets = ", ".join(f"{k} = ?" for k in fields)
    with connect() as con:
        con.execute(f"UPDATE users SET {sets} WHERE username = ?",
                    (*fields.values(), username))


def delete_user(username: str) -> None:
    with connect() as con:
        con.execute("DELETE FROM users WHERE username = ?", (username,))


def count_active_admins() -> int:
    with connect() as con:
        return con.execute(
            "SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1"
        ).fetchone()[0]


# --------------------------------------------------------------------------
# Watchlist
# --------------------------------------------------------------------------
def watchlist(username: str) -> list[str]:
    with connect() as con:
        rows = con.execute(
            "SELECT kode FROM watchlist WHERE username = ? ORDER BY added_at DESC",
            (username,),
        ).fetchall()
    return [r["kode"] for r in rows]


def watchlist_add(username: str, kode: str) -> None:
    with connect() as con:
        con.execute(
            "INSERT OR IGNORE INTO watchlist (username, kode, added_at) VALUES (?, ?, ?)",
            (username, kode, now()),
        )


def watchlist_remove(username: str, kode: str) -> None:
    with connect() as con:
        con.execute("DELETE FROM watchlist WHERE username = ? AND kode = ?", (username, kode))


# --------------------------------------------------------------------------
# Pengaturan global
# --------------------------------------------------------------------------
def get_setting(key: str, default: str | None = None) -> str | None:
    with connect() as con:
        row = con.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row and row["value"] is not None else default


def set_setting(key: str, value: str | None) -> None:
    with connect() as con:
        con.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


# --------------------------------------------------------------------------
# Riwayat dataset
# --------------------------------------------------------------------------
def add_dataset(filename: str, stored_path: str, n_rows: int, uploaded_by: str) -> int:
    with connect() as con:
        cur = con.execute(
            "INSERT INTO datasets (filename, stored_path, n_rows, uploaded_by, uploaded_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (filename, stored_path, n_rows, uploaded_by, now()),
        )
        return int(cur.lastrowid)


def get_dataset(dataset_id: int) -> dict | None:
    with connect() as con:
        row = con.execute("SELECT * FROM datasets WHERE id = ?", (dataset_id,)).fetchone()
    return dict(row) if row else None


def list_datasets() -> pd.DataFrame:
    with connect() as con:
        rows = con.execute("SELECT * FROM datasets ORDER BY id DESC").fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def delete_dataset(dataset_id: int) -> None:
    with connect() as con:
        con.execute("DELETE FROM datasets WHERE id = ?", (dataset_id,))


# --------------------------------------------------------------------------
# Log aktivitas
# --------------------------------------------------------------------------
def log(username: str | None, action: str, detail: str = "") -> None:
    with connect() as con:
        con.execute(
            "INSERT INTO activity (ts, username, action, detail) VALUES (?, ?, ?, ?)",
            (now(), username, action, detail),
        )


def recent_activity(limit: int = 50) -> pd.DataFrame:
    with connect() as con:
        rows = con.execute(
            "SELECT ts AS Waktu, username AS Pengguna, action AS Aktivitas,"
            "       detail AS Keterangan"
            " FROM activity ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return pd.DataFrame([dict(r) for r in rows],
                        columns=["Waktu", "Pengguna", "Aktivitas", "Keterangan"])


def activity_per_day(days: int = 14) -> pd.DataFrame:
    with connect() as con:
        rows = con.execute(
            "SELECT substr(ts, 1, 10) AS tanggal, COUNT(*) AS jumlah"
            " FROM activity WHERE action = 'Masuk'"
            " GROUP BY tanggal ORDER BY tanggal DESC LIMIT ?",
            (days,),
        ).fetchall()
    return pd.DataFrame([dict(r) for r in rows], columns=["tanggal", "jumlah"])
