"""
views/admin_users.py -- Kelola Pengguna (khusus admin)

Menambah akun, mengubah peran, mengaktifkan/menonaktifkan, mereset kata
sandi, dan menghapus akun. Aturan pengaman di src/auth.py mencegah admin
menghapus/menonaktifkan dirinya sendiri dan menjaga minimal satu admin aktif.
"""
from __future__ import annotations

import secrets

import streamlit as st

import config
from src import auth, db, ui


@st.dialog("Hapus pengguna?", icon=":material/person_remove:")
def _confirm_delete(username: str) -> None:
    st.write(f"Akun **{username}** beserta watchlist-nya akan dihapus permanen.")
    a, b = st.columns(2)
    if a.button("Batal", width="stretch"):
        st.rerun()
    if b.button("Ya, hapus", type="primary", width="stretch"):
        try:
            auth.admin_delete(username)
            st.session_state["users_flash"] = f"Akun {username} dihapus."
            st.rerun()
        except auth.AuthError as e:
            st.error(str(e))


def _toggle_active(target: str) -> None:
    key = f"active_{target}"
    aktif = st.session_state[key]
    try:
        auth.admin_set_active(target, aktif)
        st.session_state["users_flash"] = (
            f"Akun {target} {'diaktifkan' if aktif else 'dinonaktifkan'}.")
    except auth.AuthError as e:
        st.session_state[key] = not aktif
        st.session_state["users_error"] = str(e)


def render() -> None:
    me = auth.current_user()["username"]
    users = db.list_users()

    ui.page_header("Pengguna", "Akun, peran, dan akses.")
    if msg := st.session_state.pop("users_flash", None):
        st.success(msg, icon=":material/check_circle:")

    n_admin = int((users["role"] == config.ROLE_ADMIN).sum())
    ui.stat_cards([
        {"label": "Total akun", "value": len(users)},
        {"label": "Admin", "value": n_admin, "color": "#D97706"},
        {"label": "Pengguna", "value": len(users) - n_admin, "color": "#16A34A"},
        {"label": "Nonaktif", "value": int((users["is_active"] == 0).sum()),
         "color": "#DC2626"},
    ])
    st.write("")

    kiri, kanan = st.columns([1.7, 1], gap="large")

    # ------------------------------------------------------------ daftar
    with kiri:
        a, b = st.columns([2, 1], vertical_alignment="bottom")
        cari = a.text_input("Cari pengguna", placeholder="nama atau username",
                            icon=":material/search:").lower()
        peran = b.segmented_control("Peran", ["Semua", "Admin", "Pengguna"],
                                    default="Semua") or "Semua"
        view = users.copy()
        if cari:
            view = view[view["username"].str.contains(cari, regex=False)
                        | view["full_name"].str.lower().str.contains(cari, regex=False)]
        if peran != "Semua":
            view = view[view["role"] == (config.ROLE_ADMIN if peran == "Admin"
                                         else config.ROLE_USER)]
        view = view.assign(
            role=view["role"].map(config.ROLE_LABEL),
            is_active=view["is_active"].map(lambda v: "Aktif" if v else "Nonaktif"),
        )
        st.dataframe(
            view, hide_index=True, width="stretch", height=420,
            column_config={
                "username": "Username", "full_name": "Nama lengkap", "role": "Peran",
                "is_active": "Status", "created_at": "Terdaftar", "last_login": "Masuk terakhir",
                "n_watchlist": st.column_config.NumberColumn("Watchlist", format="%d"),
            },
        )

    # ------------------------------------------------------- tambah akun
    with kanan:
        with st.container(border=True):
            st.markdown("#### Tambah pengguna")
            with st.form("form_tambah", clear_on_submit=True):
                nama = st.text_input("Nama lengkap")
                un = st.text_input("Username", help="3–20 karakter: huruf kecil, angka, . atau _")
                role = st.radio("Peran", [config.ROLE_USER, config.ROLE_ADMIN], horizontal=True,
                                format_func=config.ROLE_LABEL.get)
                pw = st.text_input("Kata sandi awal", type="password",
                                   help="Kosongkan untuk membuat kata sandi acak.")
                if st.form_submit_button("Buat akun", type="primary",
                                         icon=":material/person_add:", width="stretch"):
                    pw_final = pw or secrets.token_urlsafe(8)
                    try:
                        auth.create_account(un, nama, pw_final, role, actor=me)
                        st.session_state["users_flash"] = (
                            f"Akun {un.strip().lower()} dibuat."
                            + ("" if pw else f" Kata sandi acak: {pw_final}")
                        )
                        st.rerun()
                    except auth.AuthError as e:
                        st.error(str(e))

    # ------------------------------------------------------ kelola akun
    st.markdown("#### Kelola akun")
    with st.container(border=True):
        opsi = users["username"].tolist()
        info = users.set_index("username")
        target = st.selectbox(
            "Pilih akun", opsi,
            format_func=lambda u: f"{u} — {info.loc[u, 'full_name']} "
                                  f"({config.ROLE_LABEL[info.loc[u, 'role']]})"
                                  + (" · Anda" if u == me else ""),
        )
        row = info.loc[target]
        c1, c2, c3 = st.columns(3, gap="medium")

        with c1:
            st.markdown("**Peran**")
            new_role = st.segmented_control(
                "Peran", [config.ROLE_USER, config.ROLE_ADMIN], default=row["role"],
                format_func=config.ROLE_LABEL.get, key=f"role_{target}",
                label_visibility="collapsed")
            if st.button("Simpan peran", disabled=not new_role or new_role == row["role"],
                         icon=":material/shield_person:", width="stretch"):
                try:
                    auth.admin_set_role(target, new_role)
                    st.session_state["users_flash"] = (
                        f"Peran {target} diubah menjadi {config.ROLE_LABEL[new_role]}.")
                    st.rerun()
                except auth.AuthError as e:
                    st.error(str(e))

            st.markdown("**Status akun**")
            st.toggle("Akun aktif", value=bool(row["is_active"]), key=f"active_{target}",
                      disabled=target == me, on_change=_toggle_active, args=(target,))
            if err := st.session_state.pop("users_error", None):
                st.error(err)

        with c2:
            st.markdown("**Reset kata sandi**")
            with st.form(f"reset_{target}", clear_on_submit=True, border=False):
                pw = st.text_input("Kata sandi baru", type="password",
                                   help="Kosongkan untuk membuat kata sandi acak.")
                if st.form_submit_button("Reset kata sandi", icon=":material/lock_reset:",
                                         width="stretch"):
                    pw_final = pw or secrets.token_urlsafe(8)
                    try:
                        auth.admin_reset_password(target, pw_final)
                        st.session_state["users_flash"] = (
                            f"Kata sandi {target} direset."
                            + ("" if pw else f" Kata sandi baru: {pw_final}"))
                        st.rerun()
                    except auth.AuthError as e:
                        st.error(str(e))

        with c3:
            st.markdown("**Ringkasan**")
            st.caption(f"Terdaftar: {row['created_at']}")
            st.caption(f"Masuk terakhir: {row['last_login'] or '-'}")
            st.caption(f"Watchlist: {int(row['n_watchlist'])} saham")
            if st.button("Hapus akun", icon=":material/delete:", type="secondary",
                         disabled=target == me, width="stretch"):
                _confirm_delete(target)

    st.caption("Kata sandi disimpan sebagai hash PBKDF2-SHA256 bergaram. Admin tidak dapat "
               "melihat kata sandi pengguna, hanya meresetnya.")
