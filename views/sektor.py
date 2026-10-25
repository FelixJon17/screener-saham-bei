"""
views/sektor.py -- Halaman Perbandingan Sektor (Gambar L6.4)

Spesifikasi Rancangan butir 3: rata-rata PER dan PBV setiap sektor dalam
grafik batang, serta sebaran seluruh saham pada diagram pencar PER terhadap
PBV yang diwarnai berdasarkan kategori valuasi, sebagai representasi visual
mekanisme tolok ukur sektoral.

Tata letak mengikuti wireframe: panel pilihan (sektor multi-pilih dan metrik
pembanding), grafik batang, komposisi cluster per sektor, diagram pencar,
dan tabel statistik sektor. Rata-rata PER dan PBV adalah rata-rata hasil
winsorizing (μ), yaitu tolok ukur Z-score setiap sektor.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

import config
from src import ui


def render() -> None:
    p = ui.get_pipeline()
    df = p.table
    stat = ui.sector_means(p)
    semua = sorted(stat.index)

    # ------------------------------------------------ judul & panel pilihan
    kiri, kanan = st.columns([2, 1], gap="medium")
    with kiri:
        ui.page_header("Perbandingan Sektor",
                       f"Rata-rata PER dan PBV per sektor sebagai tolok ukur Z-score · "
                       f"{ui.data_badge(p)}")
    with kanan.container(border=True):
        st.markdown("**Panel Pilihan**")
        pilih = st.multiselect("Sektor (multi-pilih)", semua, key="sek_pilih",
                               placeholder="Semua sektor")
        metrik = st.selectbox("Metrik pembanding", ["PER", "PBV"], key="sek_metrik")
    pilih = pilih or semua
    sub_stat = stat.loc[pilih]
    sub = df[df[config.COL_SEKTOR].isin(pilih)]

    # ------------------------------------------------- grafik batang rata-rata
    a, b = st.columns(2, gap="medium")
    with a.container(border=True):
        fig = ui.bar_sector(sub_stat.rename(columns={metrik: f"{metrik}_rata"}),
                            f"{metrik}_rata", f"Rata-rata {metrik} per sektor", metrik,
                            color=ui.accent(config.ROYAL) if metrik == "PER" else config.PERI)
        st.plotly_chart(fig, width="stretch")
    with b.container(border=True):
        st.markdown("**Komposisi cluster per sektor**")
        komp = (sub.groupby([config.COL_SEKTOR, "Kategori"]).size()
                .rename("Jumlah saham").reset_index())
        fig = px.bar(komp, x=config.COL_SEKTOR, y="Jumlah saham", color="Kategori",
                     color_discrete_map=ui.color_map_for(sub),
                     category_orders={"Kategori": config.LABEL_ORDER})
        fig.for_each_trace(lambda t: t.update(name=ui.short(t.name)))
        fig.update_traces(marker_cornerradius=4)
        fig.update_layout(barmode="stack", xaxis_title="", xaxis_tickangle=-30,
                          xaxis=dict(categoryorder="total descending"), legend_title_text="")
        st.plotly_chart(ui.style_fig(fig, 400), width="stretch")

    # ------------------------------------------------------- diagram pencar
    with st.container(border=True):
        a, b = st.columns([3, 1], vertical_alignment="center")
        a.markdown(f"**Sebaran PER terhadap PBV** · {len(sub)} saham")
        skala = b.segmented_control("Skala sumbu", ["Log", "Linear"], default="Log",
                                    key="sek_skala", label_visibility="collapsed") or "Log"
        fig = ui.scatter_cluster(sub, config.COL_PER, config.COL_PBV, log=skala == "Log")
        fig.update_xaxes(title="PER" + (" (skala log)" if skala == "Log" else ""))
        fig.update_yaxes(title="PBV" + (" (skala log)" if skala == "Log" else ""))
        st.plotly_chart(fig, width="stretch")
        st.caption("Kategori dapat tumpang tindih pada nilai asli karena pembandingnya "
                   "rata-rata sektor masing-masing.")

    # ------------------------------------------------------ tabel statistik
    with st.container(border=True):
        st.markdown("**Tabel Statistik Sektor**")
        tabel = sub_stat[["Jumlah"]].rename(columns={"Jumlah": "Jumlah saham"})
        for m, nama in (("PER", "PER"), ("PBV", "PBV"), ("ROE", "ROE %"), ("DER", "DER")):
            tabel[f"{nama} (avg ± std)"] = [f"{a:.2f}" + ("" if pd.isna(s) else f" ± {s:.2f}")
                                            for a, s in zip(sub_stat[m], sub_stat[f"Std {m}"])]
        ui.table(tabel.rename_axis("Sektor"), width="stretch")
        st.caption(f"avg ± std dari nilai hasil {ui.winsor_text(p)}. Untuk PER dan PBV, "
                   "keduanya adalah μ dan σ pada rumus Z-score.")
        st.download_button("Unduh CSV", sub_stat.to_csv().encode("utf-8"),
                           file_name="statistik_sektor.csv", mime="text/csv",
                           icon=":material/download:")
