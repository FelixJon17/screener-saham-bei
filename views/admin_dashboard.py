"""
views/admin_dashboard.py -- Dasbor Admin

Ringkasan kondisi aplikasi untuk admin: pengguna, dataset aktif, kualitas
model pada dataset tersebut, dan log aktivitas terbaru.
"""
from __future__ import annotations

import plotly.express as px
import streamlit as st

import config
from src import dataset_store, db, ui


def render() -> None:
    p = ui.get_pipeline()
    users = db.list_users()
    ds = dataset_store.active()
    n_admin = int((users["role"] == config.ROLE_ADMIN).sum())
    n_aktif = int(users["is_active"].sum())
    hari_ini = db.now()[:10]
    login_hari_ini = int(users["last_login"].fillna("").str.startswith(hari_ini).sum())

    ui.market_header(
        "Dasbor Admin",
        f"Data aktif: {ui.esc(ds.label)} · diimpor {ui.esc(ds.uploaded_at or 'bawaan')}",
        [("Pengguna", str(len(users)), None),
         ("Aktif", str(n_aktif), "#16A34A"),
         ("Admin", str(n_admin), None),
         ("Masuk hari ini", str(login_hari_ini), config.COLOR_PRIMARY)],
    )
    st.write("")

    a, b = st.columns([1.3, 1])
    with a.container(border=True, height="stretch"):
        st.markdown("**Status data & model**")
        m = p.cls.metrics
        c = st.columns(4)
        c[0].metric("Emiten", len(p.table), border=True)
        c[1].metric("Silhouette", f"{p.clu.silhouette:.4f}", border=True)
        c[2].metric("F1-macro RF", f"{m['f1_macro']:.4f}", border=True)
        c[3].metric("Verifikasi", "Lolos" if p.all_checks_ok else "Gagal", border=True,
                    help="Konsistensi data aplikasi dengan hasil notebook.")
        if not p.all_checks_ok:
            st.error("Data tidak konsisten dengan notebook. Lihat tab Verifikasi di "
                     "Evaluasi Model.", icon=":material/error:")
        if p.raw_summary["sektor_anomali_setelah_koreksi"]:
            st.info("Sektor di luar IDX-IC: "
                    + ", ".join(p.raw_summary["sektor_anomali_setelah_koreksi"]),
                    icon=":material/info:")
        b1, b2 = st.columns(2)
        b1.page_link(ui.PAGES["evaluasi"], label="Evaluasi Model", icon=":material/fact_check:")
        b2.page_link(ui.PAGES["admin_data"], label="Data & Model", icon=":material/database:")

    with b.container(border=True):
        st.markdown("**Distribusi kategori**")
        st.plotly_chart(ui.donut_categories(p.table, height=280), width="stretch")

    c1, c2 = st.columns([1, 1.4])
    with c1.container(border=True):
        st.markdown("**Aktivitas masuk** · 14 hari")
        per_hari = db.activity_per_day(14).sort_values("tanggal")
        if per_hari.empty:
            st.caption("Belum ada data.")
        else:
            fig = px.bar(per_hari, x="tanggal", y="jumlah")
            fig.update_traces(marker=dict(color=config.COLOR_PRIMARY, cornerradius=6),
                              hovertemplate="%{x}: %{y} kali masuk<extra></extra>")
            fig.update_layout(xaxis_title="", yaxis_title="Jumlah masuk")
            st.plotly_chart(ui.style_fig(fig, 280, legend=False), width="stretch")
        st.page_link(ui.PAGES["admin_users"], label="Pengguna", icon=":material/group:")

    with c2.container(border=True):
        st.markdown("**Log aktivitas**")
        st.dataframe(db.recent_activity(100), hide_index=True, width="stretch", height=330)
