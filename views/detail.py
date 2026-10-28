"""
views/detail.py -- Halaman Detail Saham (Gambar L6.3)

Spesifikasi Rancangan butir 2: nilai PER, PBV, ROE, dan DER suatu saham secara
individual, posisinya dalam cluster, perbandingannya terhadap rata-rata
sektor, serta hasil klasifikasi Random Forest untuk saham tersebut.

Tata letak mengikuti wireframe: pencarian kode saham, header emiten, kartu
PER/PBV/ROE/DER, diagram pencar PER-Z terhadap PBV-Z dengan posisi saham
ditandai dalam sebaran sektornya, dan panel interpretasi.

Rata-rata sektor untuk PER dan PBV adalah rata-rata hasil winsorizing (μ),
yaitu tolok ukur yang sama dengan penyebut Z-score.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

import config
from src import classification, ui

KEY_SELECT = "detail_kode"


def _bar_vs_sektor(row: pd.Series, rata: pd.Series) -> go.Figure:
    """Empat panel kecil: nilai saham vs rata-rata sektornya."""
    panel = [("PER", config.COL_PER, "PER"), ("PBV", config.COL_PBV, "PBV"),
             ("ROE (%)", config.COL_ROE, "ROE"), ("DER", config.COL_DER, "DER")]
    fig = make_subplots(rows=1, cols=4, subplot_titles=[p[0] for p in panel],
                        horizontal_spacing=0.07)
    warna = ui.color_of(row["Kategori"])
    for i, (nama, col, key) in enumerate(panel, start=1):
        xs, ys = [row[config.COL_KODE], "Rata-rata sektor"], [row[col], rata[key]]
        fig.add_bar(x=xs, y=ys, marker=dict(color=[warna, config.PERI], cornerradius=6),
                    text=[ui.fmt_num(v) for v in ys], textposition="outside",
                    cliponaxis=False, row=1, col=i, showlegend=False,
                    hovertemplate="%{x}: %{y:.2f}<extra>" + nama + "</extra>")
    fig.update_yaxes(showticklabels=False, rangemode="tozero")
    fig = ui.style_fig(fig, 340, legend=False)
    # style_fig mengatur margin atas kecil; judul subplot dan label nilai butuh ruang.
    fig.update_layout(margin=dict(t=56, b=30, l=10, r=10))
    fig.update_annotations(font=dict(size=13), yshift=6)
    for i in range(1, 5):
        fig.update_yaxes(range=[0, max(row_max(row, rata)[i - 1], 1e-9) * 1.22], row=1, col=i)
    return fig


def row_max(row: pd.Series, rata: pd.Series) -> list[float]:
    """Nilai tertinggi tiap panel (saham vs rata-rata sektor) untuk ruang label."""
    return [max(row[c], rata[k], 0) for c, k in ((config.COL_PER, "PER"), (config.COL_PBV, "PBV"),
                                                  (config.COL_ROE, "ROE"), (config.COL_DER, "DER"))]


def _proba_fig(proba: dict) -> go.Figure:
    s = pd.Series(proba).reindex([k for k in config.LABEL_ORDER if k in proba] +
                                 [k for k in proba if k not in config.LABEL_ORDER])
    fig = go.Figure(go.Bar(
        x=s.values * 100, y=[ui.tiny(k) for k in s.index], orientation="h",
        marker=dict(color=[ui.color_of(k) for k in s.index], cornerradius=6),
        text=[f"{v * 100:.1f}%" for v in s.values], textposition="outside",
        hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
    ))
    fig.update_layout(xaxis=dict(range=[0, 118], title="Probabilitas (%)"),
                      yaxis=dict(autorange="reversed"), margin=dict(t=6, b=30))
    return ui.horizontal(ui.style_fig(fig, 190, legend=False))


def _interpretasi(row: pd.Series, rata: pd.Series, hasil: dict, sektor: str) -> None:
    pred = hasil["prediksi"]
    sejalan = pred == row["Kategori"]
    with st.container(border=True, height="stretch"):
        st.markdown("**Random Forest** · ROE & DER")
        st.html(f"<div style='margin:2px 0 4px'>{ui.badge_html(pred)}</div>")
        st.plotly_chart(_proba_fig(hasil["probabilitas"]), width="stretch")
        if sejalan:
            st.success("Sejalan dengan kategori K-Means.", icon=":material/check_circle:")
        else:
            st.warning("Tidak sejalan dengan kategori K-Means.", icon=":material/info:")


def render() -> None:
    p = ui.get_pipeline()
    df = p.table
    codes = sorted(df[config.COL_KODE].unique())

    if (target := st.session_state.pop("kode_terpilih", None)) in codes:
        st.session_state[KEY_SELECT] = target
    if st.session_state.get(KEY_SELECT) not in codes:
        st.session_state[KEY_SELECT] = codes[0]

    # ------------------------------------------------- judul & pencarian
    kiri, kanan = st.columns([2.4, 1], vertical_alignment="bottom")
    with kiri:
        ui.page_header("Detail Saham", "Rasio, posisi cluster, dan karakterisasi "
                                       "Random Forest.")
    with kanan:
        sektor_of = dict(zip(df[config.COL_KODE], df[config.COL_SEKTOR]))
        kode = st.selectbox("Kode saham", codes, key=KEY_SELECT,
                            format_func=lambda k: f"{k} - {sektor_of.get(k, '')}")

    row = df[df[config.COL_KODE] == kode].iloc[0]
    sektor = row[config.COL_SEKTOR]
    rata = ui.sector_means(p).loc[sektor]
    c = ui.color_of(row["Kategori"])
    hasil = classification.predict_one(p.cls.model, row[config.COL_ROE], row[config.COL_DER])

    # ------------------------------------------------------ header emiten
    st.html(
        f"<div class='stock-head' style='--c:{c}'><div class='logo'>{ui.esc(kode[:4])}</div>"
        f"<div><div class='code'>{ui.esc(kode)}</div>"
        f"<div class='sector'>{ui.esc(sektor)} · {int(rata['Jumlah'])} emiten</div>"
        f"<div style='margin-top:8px'>{ui.badge_html(row['Kategori'])}</div></div>"
        f"<div class='right'><div class='conf-lbl'>Cluster</div>"
        f"<div class='conf-val'>{int(row['Cluster'])} · {ui.esc(ui.tiny(row['Kategori']))}</div>"
        f"<div class='conf-lbl' style='margin-top:8px'>Z-PER / Z-PBV sektor</div>"
        f"<div class='conf-val'>{row['Z-PER (sektor)']:+.2f} / {row['Z-PBV (sektor)']:+.2f}"
        f"</div></div></div>"
    )
    st.write("")

    # --------------------------------------------- PER, PBV, ROE, DER
    m = st.columns(4)
    for col, r, key, lbl, hlp in [
        (m[0], config.COL_PER, "PER", "PER", "Harga / laba per saham."),
        (m[1], config.COL_PBV, "PBV", "PBV", "Harga / nilai buku per saham."),
        (m[2], config.COL_ROE, "ROE", "ROE (%)", "Laba bersih / ekuitas."),
        (m[3], config.COL_DER, "DER", "DER", "Total utang / ekuitas."),
    ]:
        col.metric(lbl, ui.fmt_num(row[r]),
                   f"{row[r] - rata[key]:+.2f} vs rata-rata sektor",
                   delta_color="normal" if r == config.COL_ROE else "inverse",
                   help=f"{hlp} Rata-rata sektor: {ui.fmt_num(rata[key])}.", border=True)
    st.write("")

    # ------------------------------- posisi dalam cluster & interpretasi
    kiri, kanan = st.columns([1.8, 1], gap="medium")
    with kiri.container(border=True, height="stretch"):
        a, b = st.columns([1.6, 1.4], vertical_alignment="center")
        a.markdown("**Posisi dalam cluster**")
        lingkup = b.segmented_control(
            "Lingkup", [f"Sektor {sektor}", "Seluruh pasar"], default=f"Sektor {sektor}",
            label_visibility="collapsed", key="detail_lingkup") or f"Sektor {sektor}"
        sub = df if lingkup == "Seluruh pasar" else df[df[config.COL_SEKTOR] == sektor]
        fig = ui.scatter_cluster(sub, "Z-PER (sektor)", "Z-PBV (sektor)", highlight=kode,
                                 height=430)
        ui.zero_lines(fig)
        fig.update_xaxes(title="Z-PER relatif sektor")
        fig.update_yaxes(title="Z-PBV relatif sektor")
        st.plotly_chart(fig, width="stretch")
        st.caption(f"★ {kode} · titik (0, 0) = rata-rata sektor")
    with kanan:
        _interpretasi(row, rata, hasil, sektor)

    # ----------------------------------------- perbandingan rata-rata sektor
    with st.container(border=True):
        st.markdown(f"**Perbandingan terhadap rata-rata sektor {sektor}**")
        st.plotly_chart(_bar_vs_sektor(row, rata), width="stretch")
        st.caption(f"Rata-rata sektor dari nilai hasil {ui.winsor_text(p)} (tolok ukur Z-score).")
