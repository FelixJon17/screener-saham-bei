"""
src/theme.py -- Mode terang / gelap

Warna widget Streamlit diatur oleh [theme.light] dan [theme.dark] di
.streamlit/config.toml. Mode yang aktif dibaca dari st.context.theme, lalu
dipakai untuk warna komponen HTML (variabel CSS) dan grafik Plotly.

Streamlit menyimpan pilihan mode pengguna di localStorage peramban dengan
kunci "stActiveTheme-<path>-v2" (path = alamat saat halaman pertama dimuat).
Tombol tema menulis kunci itu untuk seluruh alamat halaman lalu memuat ulang
halaman; sesi login dipulihkan dari cookie (lihat src/auth.py). Alamat dasar
dibaca dari peramban, karena saat di-hosting aplikasi berada di bawah awalan
(mis. "/~/+/" di Streamlit Community Cloud).
"""
from __future__ import annotations

import json

import streamlit as st

# url_path seluruh halaman di app.py; "" = halaman utama.
PAGES = ["", "beranda", "detail", "sektor", "evaluasi", "panduan", "tentang", "profil",
         "masuk", "kelola-data", "kelola-pengguna"]

# Menulis mode ke kunci tema setiap halaman di bawah alamat dasar yang sama, lalu
# memuat ulang dengan ?dari=tema agar tamu tidak dialihkan ke halaman login.
_JS_SET = r"""
const pages = %s, mode = %s;
let base = window.location.pathname.replace(/\/+$/, "");
const last = base.split("/").pop();
if (pages.includes(last)) base = base.slice(0, base.length - last.length).replace(/\/+$/, "");
for (const pg of pages) window.localStorage.setItem(`stActiveTheme-${base}/${pg}-v2`, mode);
const url = new URL(window.location.href);
url.searchParams.set("dari", "tema");
window.location.replace(url.toString());
"""

LIGHT = dict(strong="#091540", text="#0E1A45", muted="#5B6B92", grid="#E9F0FC",
             line="#D5E1F5", plot_bg="#FFFFFF", hover_bg="#091540", scale_lo="#EEF4FE",
             scale_hi="#1B2CC1", ok_bg="rgba(22,163,74,.16)")
DARK = dict(strong="#E3EBFC", text="#D6E3FB", muted="#93A3CC", grid="#1A2756",
            line="#24346E", plot_bg="#0B1538", hover_bg="#1B2CC1", scale_lo="#111C45",
            scale_hi="#7692FF", ok_bg="rgba(43,196,109,.22)")

# Variabel CSS untuk komponen HTML buatan sendiri (assets/style.css).
_CSS_DARK = """
:root {
  --title: #FFFFFF; --ink: #E3EBFC; --muted: #93A3CC; --line: #1F2C63; --card: #0B1538;
  --sky-50: #16224F; --trk-lo: #123B2A; --trk-mid: #3B3216; --trk-hi: #3D1A22;
}
.auth-eyebrow { color: var(--peri); }
.stock-head .logo { background: var(--royal); }
.tb-head .cnt, .pf-head .ic, .ds-bar .ic, .req-cols span { color: var(--sky); }
.ds-bar .ic.pri { color: #FFFFFF; }
.kpi-card .lbl { color: #B9C6E8; }
"""

KEY_PENDING = "_theme_pending"


def is_dark() -> bool:
    return getattr(st.context.theme, "type", None) == "dark"


def colors() -> dict:
    return DARK if is_dark() else LIGHT


def css_overrides() -> str:
    return _CSS_DARK if is_dark() else ""


def run_js(code: str) -> None:
    """Menjalankan potongan JavaScript di halaman (tanpa ruang tampilan)."""
    st.html(f"<script>{code}</script>", unsafe_allow_javascript=True)


def _request(mode: str) -> None:
    st.session_state[KEY_PENDING] = mode


def apply_pending() -> None:
    """Dipanggil sekali per eksekusi; menerapkan pergantian mode bila diminta."""
    mode = st.session_state.pop(KEY_PENDING, None)
    if not mode:
        return
    run_js(_JS_SET % (json.dumps(PAGES), json.dumps(json.dumps(mode))))


def toggle(key: str = "theme_toggle", label: bool = True) -> None:
    """Tombol pengganti mode terang/gelap."""
    dark = is_dark()
    st.button("Mode terang" if dark and label else "Mode gelap" if label else "",
              icon=":material/light_mode:" if dark else ":material/dark_mode:",
              key=key, width="stretch" if label else "content",
              help="Ganti ke mode terang" if dark else "Ganti ke mode gelap",
              on_click=_request, args=("Light" if dark else "Dark",))
