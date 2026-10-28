from __future__ import annotations

import streamlit as st

import config
from src import auth, theme, ui
from views import (admin_data, admin_users, beranda, detail, evaluasi, panduan, profil, sektor,
                   tentang)

st.set_page_config(
    page_title=f"{config.APP_NAME} · {config.APP_TAGLINE}",
    page_icon=str(config.LOGO_ICON),
    layout="wide",
    initial_sidebar_state="expanded",
)
ui.inject_css()
auth.init()
auth.restore_session()
auth.refresh_session()
auth.sync_cookie()
theme.apply_pending()
theme.ensure_default()


# --------------------------------------------------------------------------
# Halaman Login (Gambar 3.2)
# --------------------------------------------------------------------------
KEY_AUTH_MODE = "auth_mode"   # "masuk" | "daftar"
KEY_AUTH_ROLE = "auth_role"   # "Pengguna" | "Admin"
KEY_LANDING = "landing_login"  # True setelah tamu melihat halaman login
BARS = [26, 42, 36, 58, 50, 72, 96]

LOGIN_CSS = """<style>
section[data-testid='stSidebar'], header[data-testid='stHeader'],
[data-testid='stExpandSidebarButton'] { display: none !important; }
.block-container { padding: 0 !important; max-width: none !important; }
.stApp { background: var(--card); }
</style>"""


def _ganti_mode(mode: str) -> None:
    st.session_state[KEY_AUTH_MODE] = mode


def _form_masuk() -> None:
    peran = st.segmented_control("Masuk sebagai", ["Pengguna", "Admin"], default="Pengguna",
                                 key=KEY_AUTH_ROLE, label_visibility="collapsed",
                                 width="stretch") or "Pengguna"
    admin = peran == "Admin"
    with st.form("form_login", border=False):
        u = st.text_input("Nama Pengguna", placeholder="admin@123" if admin else "user@123")
        p = st.text_input("Kata Sandi", type="password", placeholder="Kata Sandi")
        ok = st.form_submit_button("Masuk sebagai Admin" if admin else "Masuk",
                                   type="primary", icon=":material/arrow_forward:",
                                   icon_position="right", width="stretch")
    if ok:
        try:
            auth.login(u, p, role=config.ROLE_ADMIN if admin else config.ROLE_USER)
            st.rerun()
        except auth.AuthError as e:
            st.error(str(e), icon=":material/error:")
    if config.ALLOW_SELF_REGISTER and not admin:
        st.button("Belum memiliki akun? **Daftar disini**", type="tertiary", width="stretch",
                  on_click=_ganti_mode, args=("daftar",), key="to_daftar")
    demo = " · ".join(f"{a['username']} / {a['password']}" for a in config.SEED_ACCOUNTS
                      if (a["role"] == config.ROLE_ADMIN) == admin)


def _form_daftar() -> None:
    with st.form("form_daftar", border=False):
        nama = st.text_input("Nama lengkap", placeholder="Nama Anda")
        un = st.text_input("Nama pengguna", placeholder="huruf kecil, angka, . atau _",
                           help="3–20 karakter: huruf kecil, angka, titik, garis bawah.")
        a, b = st.columns(2)
        pw = a.text_input("Kata sandi", type="password",
                          placeholder=f"Min. {config.PASSWORD_MIN_LENGTH} karakter")
        pw2 = b.text_input("Ulangi kata sandi", type="password", placeholder="Ulangi")
        daftar = st.form_submit_button("Buat akun", type="primary",
                                       icon=":material/arrow_forward:", icon_position="right",
                                       width="stretch")
    if daftar:
        try:
            auth.register(un, nama, pw, pw2)
            auth.login(un, pw)
            st.session_state.pop(KEY_AUTH_MODE, None)
            st.rerun()
        except auth.AuthError as e:
            st.error(str(e), icon=":material/error:")
    st.button("Sudah punya akun? **Masuk**", type="tertiary", width="stretch",
              on_click=_ganti_mode, args=("masuk",), key="to_masuk")


def _panel_kiri() -> str:
    bars = "".join(f"<i style='height:{h}%'></i>" for h in BARS)
    return (
        f"<div class='lp'><a class='brand' href='./?dari=masuk' target='_self'>{ui.logo_img(48)}"
        f"<b>{config.APP_NAME}</b></a>"
        "<div class='mid'><div class='eyebrow'>IDX Stock Screener</div>"
        "<div class='ttl'>Pengelompokan Valuasi Saham<br><span>Relatif terhadap Sektor</span></div>"
        "<div class='sub'>Clustering saham berdasarkan PER dan PBV, karakterisasi cluster "
        "menggunakan ROE dan DER.</div></div>"
        f"<div class='foot'><div class='bars'>{bars}</div><div class='checks'>"
        "<span>K-Means Clustering</span><span>Random Forest</span><span>IDX Stocks</span>"
        "</div></div></div>"
    )


def halaman_login(notice: str | None = None) -> None:
    st.session_state[KEY_LANDING] = True
    st.html(LOGIN_CSS)
    daftar = (config.ALLOW_SELF_REGISTER
              and st.session_state.get(KEY_AUTH_MODE) == "daftar")

    kiri, kanan = st.columns([1.1, 1], gap=None, vertical_alignment="center")
    kiri.html(_panel_kiri())
    with kanan, st.container(key="auth"):
        a, b = st.columns([1, 1], vertical_alignment="center")
        if "beranda" in ui.PAGES:
            a.page_link(ui.PAGES["beranda"], label="Beranda", icon=":material/arrow_back:")
        with b.container(horizontal=True, horizontal_alignment="right"):
            theme.toggle(key="theme_login", label=False)

        eyebrow, judul, sub = (
            ("Daftar", "Buat Akun Baru", "Akun baru berperan Pengguna.") if daftar else
            ("Selamat datang", "Masuk ke Akun Anda",
             "Akses detail saham, perbandingan sektor, dan evaluasi model.")
        )
        st.html(f"<div class='auth-eyebrow'>{eyebrow}</div>"
                f"<div class='auth-title'>{judul}</div><div class='auth-sub'>{sub}</div>")
        if msg := st.session_state.pop("auth_notice", None) or notice:
            st.info(msg, icon=":material/lock:")
        if daftar:
            _form_daftar()
        else:
            _form_masuk()


def _terkunci(title: str):
    """Halaman pengganti untuk tamu: membuka form login dengan pesan singkat."""
    def page() -> None:
        halaman_login(f"Masuk untuk membuka {title}.")
    page.__name__ = f"lock_{title}"
    return page


def _ke_beranda() -> None:
    st.switch_page(ui.PAGES["beranda"])


def _beranda_tamu() -> None:
    """Pengunjung baru diarahkan ke login lebih dulu; sesudahnya Beranda terbuka untuk tamu."""
    if not st.session_state.get(KEY_LANDING):
        st.session_state[KEY_LANDING] = True
        st.switch_page(ui.PAGES["masuk"])
    beranda.render()


# --------------------------------------------------------------------------
# Navigasi berdasarkan peran
# --------------------------------------------------------------------------
# url_path wajib diisi eksplisit: seluruh fungsi halaman bernama render(),
# sehingga Streamlit akan menyimpulkan URL yang identik bila dibiarkan.
PAGE_DEFS = {   # nama: (fungsi, judul, url, ikon)
    "detail": (detail.render, "Detail Saham", "detail", ":material/query_stats:"),
    "sektor": (sektor.render, "Perbandingan Sektor", "sektor", ":material/bar_chart:"),
    "evaluasi": (evaluasi.render, "Evaluasi Model", "evaluasi", ":material/fact_check:"),
    "panduan": (panduan.render, "Panduan", "panduan", ":material/menu_book:"),
    "admin_users": (admin_users.render, "Pengguna", "kelola-pengguna", ":material/group:"),
    "admin_data": (admin_data.render, "Data & Model", "kelola-data", ":material/database:"),
}


def _pages_for(role: str | None) -> dict[str, list[st.Page]]:
    P = ui.PAGES
    P.clear()
    tamu = role is None
    P["beranda"] = st.Page(_beranda_tamu if tamu else beranda.render, title="Beranda",
                           url_path="beranda", icon=":material/dashboard:", default=True)
    for name, (fn, title, url, icon) in PAGE_DEFS.items():
        if tamu:
            P[name] = st.Page(_terkunci(title), title=title, url_path=url, icon=":material/lock:")
        else:
            P[name] = st.Page(fn, title=title, url_path=url, icon=icon)
    # Tentang terbuka untuk semua, termasuk tamu.
    if not tamu:
        # Dibuka lewat kartu nama di sidebar, tidak tampil di menu.
        P["profil"] = st.Page(profil.render, title="Profil", url_path="profil",
                              icon=":material/manage_accounts:", visibility="hidden")
    P["tentang"] = st.Page(tentang.render, title="Tentang", url_path="tentang",
                           icon=":material/info:")
    # Tamu: form login. Sudah masuk: alamat /masuk diarahkan ke Screener.
    P["masuk"] = st.Page(halaman_login if tamu else _ke_beranda, title="Masuk",
                         url_path="masuk", visibility="hidden")

    sections = {"Pasar": [P["beranda"], P["detail"], P["sektor"], P["evaluasi"]]}
    if role == config.ROLE_ADMIN:
        # Admin berfokus mengelola akun pengguna, ditambah sumber data screener.
        sections["Admin"] = [P["admin_users"], P["admin_data"]]
    sections["Akun"] = [P["panduan"], P["tentang"], P["masuk"]] + \
        ([] if tamu else [P["profil"]])
    return sections


# ?dari=... dipasang tautan logo di halaman login dan tombol tema (memuat ulang
# halaman): pengunjung ini bukan pengunjung baru, jangan dialihkan ke login.
if st.query_params.get("dari"):
    st.session_state[KEY_LANDING] = True
    del st.query_params["dari"]

u = auth.current_user()
ui.brand_logo()
nav = st.navigation(_pages_for(u["role"] if u else None))
ui.sidebar()
nav.run()
