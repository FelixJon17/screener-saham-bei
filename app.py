"""
app.py -- Titik masuk aplikasi.

Menjalankan: streamlit run app.py

Navigasi memakai st.navigation, sehingga halaman hanya didaftarkan setelah
pengguna masuk, dan halaman admin hanya didaftarkan untuk akun berperan
admin. Halaman yang tidak terdaftar tidak dapat dibuka, termasuk lewat URL
langsung.

  Peran "user"  : Screener, Detail Saham, Sektor, Watchlist, Panduan, Profil
  Peran "admin" : seluruh halaman user + Dasbor, Evaluasi Model, Data & Model,
                  Pengguna
"""
from __future__ import annotations

import streamlit as st

import config
from src import auth, ui
from views import (admin_dashboard, admin_data, admin_users, beranda, detail,
                   evaluasi, panduan, profil, sektor, watchlist)

st.set_page_config(
    page_title="Saham Screener · Valuasi Relatif BEI",
    page_icon=":material/query_stats:",
    layout="wide",
    initial_sidebar_state="expanded",
)
ui.inject_css()
auth.init()
auth.refresh_session()


# --------------------------------------------------------------------------
# Halaman Login (Gambar 3.2)
# --------------------------------------------------------------------------
KEY_AUTH_MODE = "auth_mode"   # "masuk" | "daftar"


def _ganti_mode(mode: str) -> None:
    st.session_state[KEY_AUTH_MODE] = mode


def _form_masuk() -> None:
    with st.form("form_login", border=False):
        u = st.text_input("Nama pengguna", icon=":material/person:")
        p = st.text_input("Kata sandi", type="password", icon=":material/lock:")
        ok = st.form_submit_button("Masuk", type="primary", width="stretch")
    if ok:
        try:
            auth.login(u, p)
            st.rerun()
        except auth.AuthError as e:
            st.error(str(e), icon=":material/error:")
    if config.ALLOW_SELF_REGISTER:
        a, b = st.columns([1.5, 1], vertical_alignment="center")
        a.html("<div class='auth-switch'>Belum punya akun?</div>")
        b.button("Buat akun", type="tertiary", on_click=_ganti_mode, args=("daftar",),
                 width="stretch")


def _form_daftar() -> None:
    with st.form("form_daftar", border=False):
        nama = st.text_input("Nama lengkap", icon=":material/badge:")
        un = st.text_input("Nama pengguna", icon=":material/person:",
                           help="3–20 karakter: huruf kecil, angka, titik, garis bawah.")
        pw = st.text_input("Kata sandi", type="password", icon=":material/lock:",
                           help=f"Minimal {config.PASSWORD_MIN_LENGTH} karakter.")
        pw2 = st.text_input("Ulangi kata sandi", type="password", icon=":material/lock:")
        daftar = st.form_submit_button("Buat akun", type="primary", width="stretch")
    if daftar:
        try:
            auth.register(un, nama, pw, pw2)
            auth.login(un, pw)
            st.session_state.pop(KEY_AUTH_MODE, None)
            st.rerun()
        except auth.AuthError as e:
            st.error(str(e), icon=":material/error:")
    a, b = st.columns([1.5, 1], vertical_alignment="center")
    a.html("<div class='auth-switch'>Sudah punya akun?</div>")
    b.button("Masuk", type="tertiary", on_click=_ganti_mode, args=("masuk",),
             width="stretch")


def halaman_login() -> None:
    st.html("<style>section[data-testid='stSidebar']{display:none}</style>")
    daftar = (config.ALLOW_SELF_REGISTER
              and st.session_state.get(KEY_AUTH_MODE) == "daftar")
    _, tengah, _ = st.columns([1, 1.05, 1])
    with tengah:
        st.html(
            "<div class='auth-head'><div class='logo'><i></i><i></i><i></i></div>"
            f"<div class='ttl'>{'Buat akun' if daftar else 'Masuk'}</div>"
            f"<div class='sub'>Saham Screener · Valuasi Relatif BEI</div></div>"
        )
        if msg := st.session_state.pop("auth_notice", None):
            st.warning(msg)
        with st.container(border=True):
            if daftar:
                _form_daftar()
            else:
                _form_masuk()
        if not daftar:
            with st.expander("Akun demo"):
                for acc in config.SEED_ACCOUNTS:
                    st.markdown(f"**{config.ROLE_LABEL[acc['role']]}** — "
                                f"`{acc['username']}` / `{acc['password']}`")


# --------------------------------------------------------------------------
# Navigasi berdasarkan peran
# --------------------------------------------------------------------------
# url_path wajib diisi eksplisit: seluruh fungsi halaman bernama render(),
# sehingga Streamlit akan menyimpulkan URL yang identik bila dibiarkan.
def _pages_for(role: str) -> dict[str, list[st.Page]]:
    P = ui.PAGES
    P.clear()
    P["beranda"] = st.Page(beranda.render, title="Screener", url_path="beranda",
                           icon=":material/dashboard:", default=True)
    P["detail"] = st.Page(detail.render, title="Detail Saham", url_path="detail",
                          icon=":material/query_stats:")
    P["sektor"] = st.Page(sektor.render, title="Sektor", url_path="sektor",
                          icon=":material/bar_chart:")
    P["watchlist"] = st.Page(watchlist.render, title="Watchlist", url_path="watchlist",
                             icon=":material/bookmark:")
    P["panduan"] = st.Page(panduan.render, title="Panduan", url_path="panduan",
                           icon=":material/menu_book:")
    P["profil"] = st.Page(profil.render, title="Profil", url_path="profil",
                          icon=":material/manage_accounts:")

    sections = {
        "Pasar": [P["beranda"], P["detail"], P["sektor"], P["watchlist"]],
    }
    if role == config.ROLE_ADMIN:
        P["admin_dashboard"] = st.Page(admin_dashboard.render, title="Dasbor",
                                       url_path="admin", icon=":material/admin_panel_settings:")
        P["evaluasi"] = st.Page(evaluasi.render, title="Evaluasi Model", url_path="evaluasi",
                                icon=":material/fact_check:")
        P["admin_data"] = st.Page(admin_data.render, title="Data & Model",
                                  url_path="kelola-data", icon=":material/database:")
        P["admin_users"] = st.Page(admin_users.render, title="Pengguna",
                                   url_path="kelola-pengguna", icon=":material/group:")
        sections["Admin"] = [P["admin_dashboard"], P["evaluasi"], P["admin_data"],
                             P["admin_users"]]
    sections["Akun"] = [P["panduan"], P["profil"]]
    return sections


if auth.is_authenticated():
    ui.brand_logo()
    nav = st.navigation(_pages_for(auth.current_user()["role"]))
    ui.sidebar()
    nav.run()
else:
    st.navigation([st.Page(halaman_login, title="Masuk", url_path="masuk")],
                  position="hidden").run()
