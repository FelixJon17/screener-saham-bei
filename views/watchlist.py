"""
views/watchlist.py -- Watchlist Saya

Daftar pantau pribadi setiap pengguna, disimpan di basis data sehingga tetap
ada setelah keluar-masuk. Kategori yang ditampilkan selalu mengikuti set
hasil notebook yang aktif, sehingga bila admin mengimpor hasil baru,
perubahan kategori saham yang dipantau langsung terlihat.
"""
from __future__ import annotations

import streamlit as st

import config
from src import auth, db, ui


def render() -> None:
    p = ui.get_pipeline()
    df = p.table
    user = auth.current_user()["username"]
    codes = db.watchlist(user)

    ui.page_header("Watchlist", "Emiten yang Anda pantau.")

    with st.container(border=True):
        a, b = st.columns([4, 1], vertical_alignment="bottom")
        tambah = a.multiselect(
            "Tambah saham ke watchlist",
            [k for k in sorted(df[config.COL_KODE]) if k not in codes],
            placeholder="Ketik kode saham, bisa lebih dari satu",
        )
        if b.button("Tambahkan", icon=":material/add:", type="primary", width="stretch",
                    disabled=not tambah):
            for k in tambah:
                db.watchlist_add(user, k)
            st.toast(f"{len(tambah)} saham ditambahkan", icon=":material/bookmark_added:")
            st.rerun()

    if not codes:
        st.write("")
        ui.callout("Tambahkan emiten lewat kotak di atas, atau tombol <b>Pantau</b> di "
                   "Screener dan Detail Saham.", title="Watchlist kosong", kind="neutral")
        return

    wl = df[df[config.COL_KODE].isin(codes)]
    hilang = sorted(set(codes) - set(wl[config.COL_KODE]))

    st.write("")
    ui.stat_cards(
        [{"label": "Dipantau", "value": len(codes), "sub": "saham"}] + [
            {"label": ui.short(k), "value": int((wl["Kategori"] == k).sum()),
             "color": ui.color_of(k), "sub": "di watchlist"}
            for k in config.LABEL_ORDER if k in df["Kategori"].unique()
        ]
    )
    st.write("")

    if hilang:
        st.warning("Tidak ada di data terbaru: " + ", ".join(hilang),
                   icon=":material/warning:")

    t = ui.with_label(wl).drop(columns=["Kategori", "Cluster"])
    t.insert(0, "Hapus", False)
    edited = st.data_editor(
        t, hide_index=True, width="stretch", key="wl_editor",
        disabled=[c for c in t.columns if c != "Hapus"],
        column_config={
            "Hapus": st.column_config.CheckboxColumn(width="small"),
            config.COL_ROE: st.column_config.NumberColumn("ROE (%)", format="%.2f"),
            config.COL_PER: st.column_config.NumberColumn(format="%.2f"),
            config.COL_PBV: st.column_config.NumberColumn(format="%.2f"),
            config.COL_DER: st.column_config.NumberColumn(format="%.2f"),
            "Z-PER (sektor)": st.column_config.NumberColumn(format="%+.3f"),
            "Z-PBV (sektor)": st.column_config.NumberColumn(format="%+.3f"),
            "Silhouette Sampel": st.column_config.ProgressColumn(
                "Kekuatan cluster", min_value=-1.0, max_value=1.0, format="%.2f"),
        },
    )
    hapus = edited.loc[edited["Hapus"], config.COL_KODE].tolist()
    c1, c2, c3 = st.columns([1.2, 1.2, 3])
    if c1.button(f"Hapus {len(hapus)} terpilih", icon=":material/delete:",
                 disabled=not hapus, width="stretch"):
        for k in hapus:
            db.watchlist_remove(user, k)
        st.toast(f"{len(hapus)} saham dihapus dari watchlist")
        st.rerun()
    c2.download_button("Unduh CSV", wl.to_csv(index=False).encode("utf-8"),
                       file_name="watchlist.csv", mime="text/csv",
                       icon=":material/download:", width="stretch")

    st.markdown("#### Peta watchlist")
    fig = ui.scatter_cluster(df, "Z-PER (sektor)", "Z-PBV (sektor)", height=460)
    fig.update_traces(marker=dict(opacity=0.18))
    fig.add_scatter(
        x=wl["Z-PER (sektor)"], y=wl["Z-PBV (sektor)"], mode="markers+text",
        text=wl[config.COL_KODE], textposition="top center",
        marker=dict(size=14, color=[ui.color_of(k) for k in wl["Kategori"]],
                    line=dict(width=2, color="#0F172A")),
        name="Watchlist", hovertemplate="<b>%{text}</b><extra></extra>",
    )
    fig.add_hline(y=0, line_dash="dot", line_color="#94A3B8")
    fig.add_vline(x=0, line_dash="dot", line_color="#94A3B8")
    fig.update_xaxes(title="Z-PER relatif sektor")
    fig.update_yaxes(title="Z-PBV relatif sektor")
    with st.container(border=True):
        st.plotly_chart(fig, width="stretch")

    st.markdown("#### Buka detail")
    cols = st.columns(min(len(wl), 6) or 1)
    for i, (_, r) in enumerate(wl.iterrows()):
        if cols[i % len(cols)].button(
                r[config.COL_KODE], icon=":material/open_in_new:",
                key=f"open_{r[config.COL_KODE]}", width="stretch"):
            ui.goto("detail", kode_terpilih=r[config.COL_KODE])

    st.divider()
    ui.disclaimer()
