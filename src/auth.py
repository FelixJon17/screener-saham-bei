"""
src/auth.py
Autentikasi dan otorisasi berbasis peran (admin / user).

- Kata sandi disimpan sebagai hash PBKDF2-SHA256 dengan garam acak per akun
  (hashlib bawaan Python), bukan teks biasa.
- Peran menentukan halaman yang didaftarkan ke st.navigation di app.py.
  Halaman yang tidak didaftarkan tidak dapat dibuka, termasuk lewat URL.
- Status akun dibaca ulang dari basis data setiap kali halaman dimuat,
  sehingga akun yang dinonaktifkan atau diubah perannya oleh admin langsung
  berlaku tanpa menunggu pengguna keluar.

Batasan yang perlu dinyatakan jujur di skripsi: sesi disimpan di memori
Streamlit (st.session_state), tidak ada HTTPS bawaan, dan tidak ada
pemulihan kata sandi lewat surel. Ini cukup untuk pembatasan akses aplikasi
analisis, bukan sistem keamanan tingkat produksi.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time

import streamlit as st

import config
from src import db

KEY_USER = "auth_user"
KEY_FAILS = "auth_fail_count"
KEY_LOCK_UNTIL = "auth_lock_until"

USERNAME_RE = re.compile(r"^[a-z0-9_.]{3,20}$")


class AuthError(ValueError):
    """Pesan kesalahan yang aman ditampilkan langsung ke pengguna."""


# --------------------------------------------------------------------------
# Hash kata sandi
# --------------------------------------------------------------------------
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), config.PBKDF2_ITERATIONS
    ).hex()
    return f"pbkdf2_sha256${config.PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt, digest = stored.split("$")
        calc = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), int(iters)
        ).hex()
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(calc, digest)


@st.cache_resource
def init() -> bool:
    """Menyiapkan basis data sekali per proses server."""
    db.init(hash_password)
    return True


# --------------------------------------------------------------------------
# Validasi masukan
# --------------------------------------------------------------------------
def validate_username(username: str) -> str:
    username = (username or "").strip().lower()
    if not USERNAME_RE.match(username):
        raise AuthError(
            "Nama pengguna harus 3–20 karakter dan hanya berisi huruf kecil, "
            "angka, titik, atau garis bawah."
        )
    return username


def validate_password(password: str, confirm: str | None = None) -> None:
    if len(password or "") < config.PASSWORD_MIN_LENGTH:
        raise AuthError(f"Kata sandi minimal {config.PASSWORD_MIN_LENGTH} karakter.")
    if confirm is not None and password != confirm:
        raise AuthError("Konfirmasi kata sandi tidak sama.")


# --------------------------------------------------------------------------
# Sesi
# --------------------------------------------------------------------------
def current_user() -> dict | None:
    return st.session_state.get(KEY_USER)


def is_authenticated() -> bool:
    return current_user() is not None


def is_admin() -> bool:
    u = current_user()
    return bool(u and u["role"] == config.ROLE_ADMIN)


def refresh_session() -> None:
    """Menyinkronkan sesi dengan basis data (nama, peran, status aktif)."""
    u = current_user()
    if not u:
        return
    fresh = db.get_user(u["username"])
    if not fresh or not fresh["is_active"]:
        st.session_state.pop(KEY_USER, None)
        st.session_state["auth_notice"] = "Akun Anda dinonaktifkan atau dihapus oleh admin."
        return
    st.session_state[KEY_USER] = _public(fresh)


def _public(row: dict) -> dict:
    return {"username": row["username"], "full_name": row["full_name"], "role": row["role"]}


def lock_remaining() -> int:
    return max(0, int(st.session_state.get(KEY_LOCK_UNTIL, 0) - time.time()))


def login(username: str, password: str) -> None:
    """Melempar AuthError bila gagal; mengisi sesi bila berhasil."""
    if lock_remaining():
        raise AuthError(f"Terlalu banyak percobaan. Coba lagi dalam {lock_remaining()} detik.")

    username = (username or "").strip().lower()
    row = db.get_user(username) if username else None
    if not row or not verify_password(password or "", row["password_hash"]):
        fails = st.session_state.get(KEY_FAILS, 0) + 1
        st.session_state[KEY_FAILS] = fails
        if fails >= config.MAX_LOGIN_ATTEMPTS:
            st.session_state[KEY_LOCK_UNTIL] = time.time() + config.LOGIN_LOCK_SECONDS
            st.session_state[KEY_FAILS] = 0
        db.log(username or None, "Gagal masuk", "Nama pengguna atau kata sandi salah")
        raise AuthError("Nama pengguna atau kata sandi salah.")
    if not row["is_active"]:
        raise AuthError("Akun ini sedang dinonaktifkan. Hubungi admin.")

    st.session_state[KEY_FAILS] = 0
    st.session_state[KEY_USER] = _public(row)
    db.update_user(username, last_login=db.now())
    db.log(username, "Masuk", config.ROLE_LABEL[row["role"]])


def register(username: str, full_name: str, password: str, confirm: str) -> None:
    if not config.ALLOW_SELF_REGISTER:
        raise AuthError("Pendaftaran mandiri dinonaktifkan. Hubungi admin.")
    create_account(username, full_name, password, config.ROLE_USER, confirm=confirm,
                   actor=None)


def logout() -> None:
    u = current_user()
    if u:
        db.log(u["username"], "Keluar")
    for key in list(st.session_state.keys()):
        del st.session_state[key]


# --------------------------------------------------------------------------
# Pengelolaan akun (dipakai halaman Profil dan Kelola Pengguna)
# --------------------------------------------------------------------------
def create_account(username: str, full_name: str, password: str, role: str,
                   confirm: str | None = None, actor: str | None = None) -> str:
    username = validate_username(username)
    full_name = (full_name or "").strip()
    if not full_name:
        raise AuthError("Nama lengkap wajib diisi.")
    validate_password(password, confirm)
    if role not in (config.ROLE_ADMIN, config.ROLE_USER):
        raise AuthError("Peran tidak dikenal.")
    if db.get_user(username):
        raise AuthError(f"Nama pengguna '{username}' sudah dipakai.")
    db.create_user(username, full_name, hash_password(password), role)
    if actor:
        db.log(actor, "Tambah pengguna", f"{username} ({config.ROLE_LABEL[role]})")
    else:
        db.log(username, "Daftar akun", "Pendaftaran mandiri")
    return username


def change_own_password(old: str, new: str, confirm: str) -> None:
    u = current_user()
    row = db.get_user(u["username"]) if u else None
    if not row or not verify_password(old, row["password_hash"]):
        raise AuthError("Kata sandi lama salah.")
    validate_password(new, confirm)
    db.update_user(row["username"], password_hash=hash_password(new))
    db.log(row["username"], "Ganti kata sandi")


def admin_reset_password(target: str, new: str) -> None:
    validate_password(new)
    db.update_user(target, password_hash=hash_password(new))
    db.log(current_user()["username"], "Reset kata sandi", target)


def _guard_last_admin(target: str) -> None:
    row = db.get_user(target)
    if row and row["role"] == config.ROLE_ADMIN and row["is_active"] \
            and db.count_active_admins() <= 1:
        raise AuthError("Harus tersisa minimal satu admin aktif.")


def admin_set_role(target: str, role: str) -> None:
    if role != config.ROLE_ADMIN:
        _guard_last_admin(target)
    db.update_user(target, role=role)
    db.log(current_user()["username"], "Ubah peran", f"{target} → {config.ROLE_LABEL[role]}")


def admin_set_active(target: str, active: bool) -> None:
    if target == current_user()["username"]:
        raise AuthError("Anda tidak dapat menonaktifkan akun sendiri.")
    if not active:
        _guard_last_admin(target)
    db.update_user(target, is_active=int(active))
    db.log(current_user()["username"], "Aktifkan akun" if active else "Nonaktifkan akun", target)


def admin_delete(target: str) -> None:
    if target == current_user()["username"]:
        raise AuthError("Anda tidak dapat menghapus akun sendiri.")
    _guard_last_admin(target)
    db.delete_user(target)
    db.log(current_user()["username"], "Hapus pengguna", target)
