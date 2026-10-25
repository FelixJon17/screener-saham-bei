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

- Sesi login disimpan di st.session_state dan, agar tidak hilang saat halaman
  dimuat ulang (mis. ganti mode terang/gelap), juga sebagai cookie berisi
  token bertanda tangan HMAC-SHA256 yang berlaku SESSION_DAYS hari. Token ikut
  batal bila kata sandi diganti.

Batasan yang perlu dinyatakan jujur di skripsi: cookie diset lewat
JavaScript (bukan HttpOnly), tidak ada HTTPS bawaan, dan tidak ada
pemulihan kata sandi lewat surel. Ini cukup untuk pembatasan akses aplikasi
analisis, bukan sistem keamanan tingkat produksi.
"""
from __future__ import annotations

import base64
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
KEY_COOKIE_SET = "_auth_cookie_set"       # token yang menunggu ditulis ke cookie
KEY_COOKIE_CLEAR = "_auth_cookie_clear"   # cookie menunggu dihapus
KEY_NO_RESTORE = "_auth_no_restore"       # sudah keluar: abaikan cookie lama

COOKIE = "ssb_session"
SESSION_DAYS = 7

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
# Sesi lewat cookie
# --------------------------------------------------------------------------
def _secret() -> bytes:
    key = db.get_setting("session_secret")
    if not key:
        key = secrets.token_hex(32)
        db.set_setting("session_secret", key)
    return key.encode()


def _sign(username: str, exp: int, password_hash: str) -> str:
    msg = f"{username}|{exp}|{password_hash}".encode()
    return hmac.new(_secret(), msg, hashlib.sha256).hexdigest()


def _make_token(row: dict) -> str:
    exp = int(time.time()) + SESSION_DAYS * 86400
    u = base64.urlsafe_b64encode(row["username"].encode()).decode().rstrip("=")
    return f"{u}.{exp}.{_sign(row['username'], exp, row['password_hash'])}"


def _read_token(token: str) -> dict | None:
    try:
        u, exp, sig = token.split(".")
        username = base64.urlsafe_b64decode(u + "=" * (-len(u) % 4)).decode()
        exp = int(exp)
    except (ValueError, TypeError, UnicodeDecodeError):
        return None
    if exp < time.time():
        return None
    row = db.get_user(username)
    if not row or not row["is_active"]:
        return None
    if not hmac.compare_digest(sig, _sign(username, exp, row["password_hash"])):
        return None
    return row


def restore_session() -> None:
    """Memulihkan login dari cookie bila sesi Streamlit masih kosong."""
    if current_user() or st.session_state.get(KEY_NO_RESTORE):
        return
    token = st.context.cookies.get(COOKIE)
    row = _read_token(token) if token else None
    if row:
        st.session_state[KEY_USER] = _public(row)


def sync_cookie() -> None:
    """Menulis atau menghapus cookie sesi yang tertunda (dipanggil app.py)."""
    from src import theme
    if token := st.session_state.pop(KEY_COOKIE_SET, None):
        theme.run_js(f"document.cookie='{COOKIE}={token}; path=/; "
                     f"max-age={SESSION_DAYS * 86400}; SameSite=Strict';")
    if st.session_state.pop(KEY_COOKIE_CLEAR, None):
        theme.run_js(f"document.cookie='{COOKIE}=; path=/; max-age=0; SameSite=Strict';")


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
        st.session_state[KEY_COOKIE_CLEAR] = True
        st.session_state["auth_notice"] = "Akun Anda dinonaktifkan atau dihapus oleh admin."
        return
    st.session_state[KEY_USER] = _public(fresh)


def _public(row: dict) -> dict:
    return {"username": row["username"], "full_name": row["full_name"], "role": row["role"]}


def lock_remaining() -> int:
    return max(0, int(st.session_state.get(KEY_LOCK_UNTIL, 0) - time.time()))


def login(username: str, password: str, role: str | None = None) -> None:
    """
    Melempar AuthError bila gagal; mengisi sesi bila berhasil. Bila `role`
    diisi (dari pilihan Pengguna/Admin di halaman login), peran akun harus sama.
    """
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
    if role and row["role"] != role:
        raise AuthError("Akun ini bukan akun admin." if role == config.ROLE_ADMIN
                        else "Akun admin, silakan masuk lewat pilihan Admin.")

    st.session_state[KEY_FAILS] = 0
    st.session_state[KEY_USER] = _public(row)
    st.session_state[KEY_COOKIE_SET] = _make_token(row)
    st.session_state.pop(KEY_NO_RESTORE, None)
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
    st.session_state[KEY_COOKIE_CLEAR] = True
    st.session_state[KEY_NO_RESTORE] = True


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
    # Token lama ikut batal karena hash berubah; terbitkan token baru.
    st.session_state[KEY_COOKIE_SET] = _make_token(db.get_user(row["username"]))


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
