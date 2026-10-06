"""
views/sektor.py -- Halaman Perbandingan Sektor (Gambar 3.5)

Isi sesuai Spesifikasi Rancangan butir 3: rata-rata PER dan PBV setiap sektor
dalam grafik batang, dan diagram pencar PER terhadap PBV yang diwarnai
menurut kategori valuasi, sebagai representasi visual dari mekanisme tolok
ukur sektoral.
"""
from __future__ import annotations

import plotly.express as px
import streamlit as st

import config
from src import ui


def _sector_cards(sec, kat: list[str]) -> None:
    cards = []
    for nama, r in sec.sort_values("Jumlah", ascending=False).iterrows():
        total = max(sum(r[k] for k in kat), 1)
        stack = "".join(
            f"<span title='{ui.esc(ui.short(k))}: {int(r[k])}' style='width:{r[k] / total * 100:.1f}%;"
            f"background:{ui.color_of(k)}'></span>" for k in kat
        )
        cnt = " ".join(f"{ui.dot_html(k)}{int(r[k])}" for k in kat)
        cards.append(
            f"<div class='sector-card'><div class='nm'>{ui.esc(nama)}</div>"
            f"<div class='n'>{int(r['Jumlah'])} saham · {cnt}</div>"
            f"<div class='stack'>{stack}</div>"
            f"<div class='kv'><span>Median PER <b>{ui.fmt_num(r['PER_median'])}</b></span>"
            f"<span>Median PBV <b>{ui.fmt_num(r['PBV_median'])}</b></span></div></div>"
        )
    st.html(f"<div class='sector-grid'>{''.join(cards)}</div>")


def render() -> None:
    p = ui.get_pipeline()
    sec = p.sector_summary
    df = p.table
    kat = [c for c in config.LABEL_ORDER if c in sec.columns] + \
          [c for c in df["Kategori"].unique() if c in sec.columns and c not in config.LABEL_ORDER]

    ui.page_header("Perbandingan Sektor",
                   "Tolok ukur PER dan PBV tiap sektor, dasar perhitungan Z-score.")
    st.write("")
    _sector_cards(sec, kat)
    st.write("")

    fokus = st.selectbox("Sorot sektor", ["(tidak ada)"] + sorted(sec.index), index=0)
    fokus = None if fokus == "(tidak ada)" else fokus

    t1, t2, t3, t4 = st.tabs([":material/bar_chart: Rasio", ":material/stacked_bar_chart: Komposisi",
                              ":material/scatter_plot: Sebaran", ":material/table: Statistik"])

    with t1:
        ukuran = st.segmented_control("Ukuran pemusatan", ["Median", "Rata-rata"],
                                      default="Median") or "Median"
        suf = "rata" if ukuran == "Rata-rata" else "median"
        c1, c2 = st.columns(2)
        with c1.container(border=True):
            st.plotly_chart(ui.bar_sector(sec, f"PER_{suf}", f"{ukuran} PER per sektor",
                                          "PER", highlight=fokus), width="stretch")
        with c2.container(border=True):
            st.plotly_chart(ui.bar_sector(sec, f"PBV_{suf}", f"{ukuran} PBV per sektor",
                                          "PBV", color="#7C3AED", highlight=fokus),
                            width="stretch")
        if ukuran == "Rata-rata":
            st.caption("Selisih besar rata-rata vs median menandakan nilai ekstrem di sektor.")

    with t2:
        prop = sec[kat].div(sec[kat].sum(axis=1), axis=0).mul(100).round(2)
        prop = prop.reset_index().melt(id_vars=config.COL_SEKTOR, var_name="Kategori",
                                       value_name="Persentase")
        prop["Label"] = prop["Kategori"].map(ui.short)
        fig = px.bar(prop, y=config.COL_SEKTOR, x="Persentase", color="Kategori",
                     orientation="h", color_discrete_map={k: ui.color_of(k) for k in kat},
                     category_orders={"Kategori": config.LABEL_ORDER}, custom_data=["Label"],
                     text=prop["Persentase"].map(lambda v: f"{v:.0f}%" if v >= 6 else ""))
        fig.update_traces(hovertemplate="<b>%{y}</b><br>%{customdata[0]}: %{x:.1f}%"
                                        "<extra></extra>", textfont_color="white")
        fig.for_each_trace(lambda t: t.update(name=ui.short(t.name)))
        order = prop[prop["Kategori"] == kat[0]].sort_values("Persentase")[config.COL_SEKTOR]
        fig.update_layout(barmode="stack", xaxis_title="Persentase saham (%)", yaxis_title="",
                          yaxis=dict(categoryorder="array", categoryarray=list(order)))
        with st.container(border=True):
            st.plotly_chart(ui.style_fig(fig, 480), width="stretch")

    with t3:
        a, b = st.columns([3, 1], vertical_alignment="bottom")
        pilih = a.multiselect("Tampilkan sektor", sorted(df[config.COL_SEKTOR].unique()),
                              default=[fokus] if fokus else [],
                              placeholder="Semua sektor")
        skala = b.segmented_control("Skala sumbu", ["Log", "Linear"], default="Log") or "Log"
        sub = df[df[config.COL_SEKTOR].isin(pilih)] if pilih else df
        fig = ui.scatter_cluster(sub, config.COL_PER, config.COL_PBV, log=skala == "Log")
        fig.update_xaxes(title="PER" + (" (skala log)" if skala == "Log" else ""))
        fig.update_yaxes(title="PBV" + (" (skala log)" if skala == "Log" else ""))
        with st.container(border=True):
            st.plotly_chart(fig, width="stretch")

        box = px.box(sub, x=config.COL_SEKTOR, y=config.COL_PER, log_y=True, points=False,
                     color_discrete_sequence=[config.COLOR_PRIMARY],
                     title="Sebaran PER di setiap sektor (skala log)")
        box.update_layout(xaxis_title="", yaxis_title="PER", xaxis_tickangle=-25)
        with st.container(border=True):
            st.plotly_chart(ui.style_fig(box, 400, legend=False), width="stretch")
        st.caption("Kategori tampak tumpang tindih pada nilai asli karena pembandingnya "
                   "adalah sektor masing-masing, bukan seluruh pasar.")

    with t4:
        st.dataframe(sec.round(4), width="stretch",
                     column_config={
                         "PER_rata": "PER rata-rata", "PER_median": "PER median",
                         "PBV_rata": "PBV rata-rata", "PBV_median": "PBV median",
                         "ROE_median": "ROE median (%)", "DER_median": "DER median",
                     })
        st.download_button("Unduh CSV", sec.to_csv().encode("utf-8"),
                           file_name="ringkasan_sektor.csv", mime="text/csv",
                           icon=":material/download:")

    st.divider()
    ui.disclaimer()
