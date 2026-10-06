"""
views/detail.py -- Halaman Detail Saham (Gambar 3.4)

Isi sesuai Spesifikasi Rancangan butir 2: nilai PER, PBV, ROE, DER satu saham,
posisinya dalam cluster, perbandingan terhadap rata-rata sektor, dan hasil
klasifikasi Random Forest untuk saham tersebut.

Tambahan agar mudah dipahami: ringkasan otomatis dalam bahasa sehari-hari,
posisi persentil di dalam sektor, dan daftar saham sejenis terdekat.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

import config
from src import auth, classification, db, ui

KEY_SELECT = "detail_kode"


def _strength(sil: float) -> tuple[str, str]:
    if sil >= 0.5:
        return "Kuat", "posisinya sangat khas untuk kelompok ini"
    if sil >= 0.25:
        return "Sedang", "cukup khas untuk kelompok ini"
    return "Lemah", "berada di dekat perbatasan dengan kelompok lain"


def _percentile(series: pd.Series, value: float) -> float:
    s = series.dropna()
    return float(((s < value).sum() + 0.5 * (s == value).sum()) / max(len(s), 1) * 100)


def _pct_bar(label: str, value: float, pct: float, median: float, unit: str,
             higher_is_better: bool) -> str:
    return (
        f"<div class='pctl'><div class='row'><b>{label}</b>"
        f"<span>{ui.fmt_num(value)}{unit} · median {ui.fmt_num(median)}{unit} · "
        f"persentil {pct:.0f}</span></div>"
        f"<div class='track{' inv' if higher_is_better else ''}'><div class='med'></div>"
        f"<div class='mark' style='left:{min(max(pct, 2), 98):.1f}%'></div></div></div>"
    )


def _diff_text(val: float, med: float) -> str:
    if med == 0:
        return "di atas median" if val > med else "di bawah median"
    pct = (val - med) / abs(med) * 100
    return f"{pct:+.0f}% vs median"


def _insights(row: pd.Series, sec: pd.Series, hasil: dict, kode: str) -> list[str]:
    per, pbv = row[config.COL_PER], row[config.COL_PBV]
    roe, der = row[config.COL_ROE], row[config.COL_DER]
    kuat, _ = _strength(row["Silhouette Sampel"])
    pred = hasil["prediksi"]
    prob = hasil["probabilitas"][pred] * 100
    sejalan = "sejalan" if pred == row["Kategori"] else "tidak sejalan"
    return [
        f"<b>Valuasi</b> · PER {ui.fmt_num(per)} ({_diff_text(per, sec['PER_median'])}), "
        f"PBV {ui.fmt_num(pbv)} ({_diff_text(pbv, sec['PBV_median'])})",
        f"<b>Profitabilitas</b> · ROE {ui.fmt_num(roe)}% "
        f"({'di atas' if roe >= sec['ROE_median'] else 'di bawah'} median sektor)",
        f"<b>Leverage</b> · DER {ui.fmt_num(der)} "
        f"({'di bawah' if der <= sec['DER_median'] else 'di atas'} median sektor)",
        f"<b>Keanggotaan cluster</b> · {kuat} (silhouette {row['Silhouette Sampel']:.2f})",
        f"<b>Random Forest</b> · {ui.esc(ui.short(pred))} {prob:.0f}%, {sejalan} "
        f"dengan kategori",
    ]


def _peers(df: pd.DataFrame, row: pd.Series, n: int = 8) -> pd.DataFrame:
    same = df[(df[config.COL_SEKTOR] == row[config.COL_SEKTOR])
              & (df[config.COL_KODE] != row[config.COL_KODE])].copy()
    z = same[["Z-PER (sektor)", "Z-PBV (sektor)"]].to_numpy()
    me = row[["Z-PER (sektor)", "Z-PBV (sektor)"]].to_numpy(dtype=float)
    same["Jarak"] = np.linalg.norm(z - me, axis=1)
    return ui.with_label(same.nsmallest(n, "Jarak"))


def _bar_vs_sektor(row: pd.Series, sec: pd.Series) -> go.Figure:
    """Empat panel kecil, masing-masing dengan skala sendiri."""
    panel = [
        ("PER", row[config.COL_PER], sec["PER_median"], sec["PER_rata"]),
        ("PBV", row[config.COL_PBV], sec["PBV_median"], sec["PBV_rata"]),
        ("ROE (%)", row[config.COL_ROE], sec["ROE_median"], None),
        ("DER", row[config.COL_DER], sec["DER_median"], None),
    ]
    fig = make_subplots(rows=1, cols=4, subplot_titles=[p[0] for p in panel],
                        horizontal_spacing=0.07)
    warna = ui.color_of(row["Kategori"])
    for i, (nama, saham, med, rata) in enumerate(panel, start=1):
        xs, ys, cs = [row[config.COL_KODE], "Median"], [saham, med], [warna, "#94A3B8"]
        if rata is not None:
            xs.append("Rata-rata")
            ys.append(rata)
            cs.append("#CBD5E1")
        fig.add_bar(x=xs, y=ys, marker=dict(color=cs, cornerradius=6),
                    text=[ui.fmt_num(v) for v in ys], textposition="outside",
                    cliponaxis=False, row=1, col=i, showlegend=False,
                    hovertemplate="%{x}: %{y:.2f}<extra>" + nama + "</extra>")
    fig.update_yaxes(showticklabels=False, rangemode="tozero")
    fig.update_layout(margin=dict(t=40))
    return ui.style_fig(fig, 380, legend=False)


def _proba_fig(proba: dict) -> go.Figure:
    s = pd.Series(proba).reindex([k for k in config.LABEL_ORDER if k in proba] +
                                 [k for k in proba if k not in config.LABEL_ORDER])
    fig = go.Figure(go.Bar(
        x=s.values * 100, y=[ui.short(k) for k in s.index], orientation="h",
        marker=dict(color=[ui.color_of(k) for k in s.index], cornerradius=6),
        text=[f"{v * 100:.1f}%" for v in s.values], textposition="outside",
        hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
    ))
    fig.update_layout(xaxis=dict(range=[0, 115], title="Probabilitas (%)"),
                      yaxis=dict(autorange="reversed"))
    return ui.style_fig(fig, 230, legend=False)


def _pick_peer(codes: list[str]):
    def cb() -> None:
        rows = st.session_state["peer_table"].selection.rows
        if rows:
            st.session_state[KEY_SELECT] = codes[rows[0]]
    return cb


def render() -> None:
    p = ui.get_pipeline()
    df = p.table
    codes = sorted(df[config.COL_KODE].unique())
    user = auth.current_user()["username"]

    if (target := st.session_state.pop("kode_terpilih", None)) in codes:
        st.session_state[KEY_SELECT] = target
    if st.session_state.get(KEY_SELECT) not in codes:
        st.session_state[KEY_SELECT] = codes[0]

    ui.page_header("Detail Saham", "Valuasi, fundamental, dan posisi relatif sektor.")

    a, b = st.columns([3, 1], vertical_alignment="bottom")
    labels = dict(zip(df[config.COL_KODE], df[config.COL_SEKTOR]))
    kode = a.selectbox("Pilih atau ketik kode saham", codes, key=KEY_SELECT,
                       format_func=lambda k: f"{k} — {labels.get(k, '')}")
    in_wl = kode in db.watchlist(user)
    if b.button("Hapus dari watchlist" if in_wl else "Tambah ke watchlist",
                icon=":material/bookmark_remove:" if in_wl else ":material/bookmark_add:",
                width="stretch", type="secondary" if in_wl else "primary"):
        (db.watchlist_remove if in_wl else db.watchlist_add)(user, kode)
        st.toast(f"{kode} {'dihapus dari' if in_wl else 'ditambahkan ke'} watchlist",
                 icon=":material/bookmark:")
        st.rerun()

    row = df[df[config.COL_KODE] == kode].iloc[0]
    sektor = row[config.COL_SEKTOR]
    sec = p.sector_summary.loc[sektor]
    sec_df = df[df[config.COL_SEKTOR] == sektor]
    c = ui.color_of(row["Kategori"])
    kuat, _ = _strength(row["Silhouette Sampel"])
    hasil = classification.predict_one(p.cls.model, row[config.COL_ROE], row[config.COL_DER])

    # ------------------------------------------------------------- kepala
    st.html(
        f"<div class='stock-head' style='--c:{c}'><div class='logo'>{ui.esc(kode[:4])}</div>"
        f"<div><div class='code'>{ui.esc(kode)}</div>"
        f"<div class='sector'>{ui.esc(sektor)} · {int(sec['Jumlah'])} emiten</div>"
        f"<div style='margin-top:8px'>{ui.badge_html(row['Kategori'])}</div></div>"
        f"<div class='right'><div class='conf-lbl'>Kekuatan cluster</div>"
        f"<div class='conf-val'>{kuat} ({row['Silhouette Sampel']:.2f})</div>"
        f"<div class='conf-lbl' style='margin-top:8px'>Z-PER / Z-PBV sektor</div>"
        f"<div class='conf-val'>{row['Z-PER (sektor)']:+.2f} / {row['Z-PBV (sektor)']:+.2f}"
        f"</div></div></div>"
    )
    st.write("")

    # ---------------------------------------------------- ringkasan & persentil
    kiri, kanan = st.columns([1.25, 1])
    with kiri:
        items = "".join(f"<li>{t}</li>" for t in _insights(row, sec, hasil, kode))
        st.html(f"<div class='insight'><div class='ttl'>Ringkasan</div>"
                f"<ul>{items}</ul></div>")
    with kanan:
        with st.container(border=True):
            st.markdown(f"**Persentil di sektor** · {sektor}")
            bars = "".join([
                _pct_bar("PER", row[config.COL_PER],
                         _percentile(sec_df[config.COL_PER], row[config.COL_PER]),
                         sec["PER_median"], "", higher_is_better=False),
                _pct_bar("PBV", row[config.COL_PBV],
                         _percentile(sec_df[config.COL_PBV], row[config.COL_PBV]),
                         sec["PBV_median"], "", higher_is_better=False),
                _pct_bar("ROE", row[config.COL_ROE],
                         _percentile(sec_df[config.COL_ROE], row[config.COL_ROE]),
                         sec["ROE_median"], "%", higher_is_better=True),
                _pct_bar("DER", row[config.COL_DER],
                         _percentile(sec_df[config.COL_DER], row[config.COL_DER]),
                         sec["DER_median"], "", higher_is_better=False),
            ])
            st.html(bars)

    # ------------------------------------------------------------- metrik
    m = st.columns(4)
    for col, r, med, lbl, hlp in [
        (m[0], config.COL_PER, "PER_median", "PER", "Harga / laba per saham."),
        (m[1], config.COL_PBV, "PBV_median", "PBV", "Harga / nilai buku per saham."),
        (m[2], config.COL_ROE, "ROE_median", "ROE (%)", "Laba bersih / ekuitas."),
        (m[3], config.COL_DER, "DER_median", "DER", "Total utang / ekuitas."),
    ]:
        col.metric(lbl, ui.fmt_num(row[r]), f"{row[r] - sec[med]:+.2f} vs median",
                   delta_color="normal" if r == config.COL_ROE else "inverse",
                   help=hlp, border=True)

    # ----------------------------------------------------------------- tab
    t1, t2, t3 = st.tabs([":material/scatter_plot: Posisi cluster",
                          ":material/bar_chart: vs Sektor", ":material/group: Emiten sejenis"])
    with t1:
        lingkup = st.segmented_control(
            "Lingkup", ["Seluruh pasar", f"Sektor {sektor}"], default="Seluruh pasar",
            label_visibility="collapsed") or "Seluruh pasar"
        sub = df if lingkup == "Seluruh pasar" else sec_df
        fig = ui.scatter_cluster(sub, "Z-PER (sektor)", "Z-PBV (sektor)", highlight=kode)
        fig.add_hline(y=0, line_dash="dot", line_color="#94A3B8")
        fig.add_vline(x=0, line_dash="dot", line_color="#94A3B8")
        fig.update_xaxes(title="Z-PER relatif sektor")
        fig.update_yaxes(title="Z-PBV relatif sektor")
        st.plotly_chart(fig, width="stretch")
        st.caption(f"★ {kode} · Z-score relatif terhadap rata-rata sektor {sektor}.")
    with t2:
        st.plotly_chart(_bar_vs_sektor(row, sec), width="stretch")
    with t3:
        peers = _peers(df, row)
        st.caption(f"8 emiten {sektor} terdekat di ruang Z-score · klik baris untuk detail")
        st.dataframe(
            peers[[config.COL_KODE, "Valuasi", config.COL_PER, config.COL_PBV,
                   config.COL_ROE, config.COL_DER, "Jarak"]],
            hide_index=True, width="stretch", key="peer_table", selection_mode="single-row",
            on_select=_pick_peer(peers[config.COL_KODE].tolist()),
            column_config={
                config.COL_PER: st.column_config.NumberColumn(format="%.2f"),
                config.COL_PBV: st.column_config.NumberColumn(format="%.2f"),
                config.COL_ROE: st.column_config.NumberColumn("ROE (%)", format="%.2f"),
                config.COL_DER: st.column_config.NumberColumn(format="%.2f"),
                "Jarak": st.column_config.ProgressColumn(
                    "Jarak Z", format="%.2f", min_value=0.0,
                    max_value=float(max(peers["Jarak"].max(), 0.01))),
            },
        )

    # -------------------------------------------------- karakterisasi RF
    st.markdown("#### Karakterisasi fundamental")
    cocok = hasil["prediksi"] == row["Kategori"]
    x, y, z = st.columns([1, 1, 1.6])
    with x.container(border=True, height="stretch"):
        st.caption("K-Means · PER & PBV")
        st.html(f"<div style='font-size:1.3rem;margin:6px 0'>{ui.badge_html(row['Kategori'])}</div>")
    with y.container(border=True, height="stretch"):
        st.caption("Random Forest · ROE & DER")
        st.html(f"<div style='font-size:1.3rem;margin:6px 0'>"
                f"{ui.badge_html(hasil['prediksi'])}</div>")
        if cocok:
            st.success("Sejalan", icon=":material/check_circle:")
        else:
            st.warning("Tidak sejalan", icon=":material/info:")
    with z.container(border=True):
        st.caption("Probabilitas Random Forest")
        st.plotly_chart(_proba_fig(hasil["probabilitas"]), width="stretch")

    st.caption("Tidak sejalan = profil ROE dan DER tidak khas untuk kelompok valuasinya.")
    st.write("")
    ui.disclaimer()
