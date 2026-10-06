"""
views/profil.py -- Profil & Keamanan

Setiap pengguna (admin maupun user) dapat melihat data akunnya, mengganti
nama tampilan, dan mengganti kata sandinya sendiri.
"""
from __future__ import annotations

import streamlit as st

import config
from src import auth, db, ui


def render() -> None:
    u = auth.current_user()
    row = db.get_user(u["username"])

    ui.page_header("Profil", "Akun dan kata sandi.")
    ui.stat_cards([
        {"label": "Nama pengguna", "value": row["username"]},
        {"label": "Peran", "value": config.ROLE_LABEL[row["role"]],
         "color": "#D97706" if row["role"] == config.ROLE_ADMIN else config.COLOR_PRIMARY},
        {"label": "Terdaftar sejak", "value": row["created_at"][:10], "color": "#7C3AED"},
        {"label": "Watchlist", "value": len(db.watchlist(row["username"])),
         "color": "#16A34A", "sub": "saham dipantau"},
    ])
    st.write("")

    a, b = st.columns(2, gap="large")
    with a.container(border=True):
        st.markdown("#### Informasi akun")
        with st.form("form_nama"):
            nama = st.text_input("Nama lengkap", value=row["full_name"])
            if st.form_submit_button("Simpan", type="primary", icon=":material/save:"):
                if not nama.strip():
                    st.error("Nama lengkap wajib diisi.")
                else:
                    db.update_user(row["username"], full_name=nama.strip())
                    db.log(row["username"], "Ubah nama", nama.strip())
                    st.toast("Nama berhasil diperbarui", icon=":material/check_circle:")
                    st.rerun()
        st.caption(f"Masuk terakhir: {row['last_login'] or '-'}")

    with b.container(border=True):
        st.markdown("#### Ganti kata sandi")
        with st.form("form_sandi", clear_on_submit=True):
            lama = st.text_input("Kata sandi lama", type="password")
            baru = st.text_input("Kata sandi baru", type="password",
                                 help=f"Minimal {config.PASSWORD_MIN_LENGTH} karakter.")
            ulang = st.text_input("Ulangi kata sandi baru", type="password")
            if st.form_submit_button("Ganti kata sandi", type="primary",
                                     icon=":material/key:"):
                try:
                    auth.change_own_password(lama, baru, ulang)
                    st.success("Kata sandi berhasil diganti.", icon=":material/check_circle:")
                except auth.AuthError as e:
                    st.error(str(e))
        seed = {a["username"]: a["password"] for a in config.SEED_ACCOUNTS}
        if row["username"] in seed and auth.verify_password(seed[row["username"]],
                                                            row["password_hash"]):
            st.warning("Akun ini masih memakai kata sandi demo bawaan. Segera ganti.",
                       icon=":material/warning:")
