"""
views/beranda.py -- Halaman Beranda/Screener (Gambar 3.3)

Isi sesuai Spesifikasi Rancangan butir 1: tabel seluruh saham, tampilan visual
clustering, label klasifikasi, filter sektor dan kategori valuasi.

Interaksi: klik titik pada peta valuasi atau baris pada tabel untuk membuka
pratinjau saham, lalu lompat ke Detail Saham atau tambahkan ke watchlist.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

import config
from src import auth, db, ui

KEY_PICK = "beranda_pick"


def _pick_point(key: str) -> None:
    """Callback klik titik: hanya dipanggil saat pilihan berubah."""
    if kode := ui.selected_code(st.session_state.get(key)):
        st.session_state[KEY_PICK] = kode


def _pick_row(key: str, codes: list[str]):
    def cb() -> None:
        rows = st.session_state[key].selection.rows
        if rows:
            st.session_state[KEY_PICK] = codes[rows[0]]
    return cb


def _filters(df: pd.DataFrame) -> pd.DataFrame:
    with st.container(border=True):
        a, b, c = st.columns([1.2, 1.6, 2.2], vertical_alignment="bottom")
        cari = a.text_input("Cari kode saham", placeholder="mis. BBCA",
                            icon=":material/search:").strip().upper()
        sektor = b.multiselect("Sektor", sorted(df[config.COL_SEKTOR].unique()),
                               placeholder="Semua sektor")
        kat_opsi = [k for k in config.LABEL_ORDER if k in df["Kategori"].unique()]
        kat_opsi += [k for k in df["Kategori"].unique() if k not in kat_opsi]
        kategori = c.pills(
            "Kategori valuasi", kat_opsi, selection_mode="multi",
            format_func=ui.short,
        )

        with st.expander("Filter lanjutan (rentang rasio)", icon=":material/tune:"):
            g1, g2, g3, g4 = st.columns(4)
            per = g1.slider("PER", 0.0, float(df[config.COL_PER].max()),
                            (0.0, float(df[config.COL_PER].max())),
                            help="Price to Earnings Ratio: harga saham dibagi laba per saham.")
            pbv = g2.slider("PBV", 0.0, float(df[config.COL_PBV].max()),
                            (0.0, float(df[config.COL_PBV].max())),
                            help="Price to Book Value: harga saham dibagi nilai buku per saham.")
            roe_lo, roe_hi = float(df[config.COL_ROE].min()), float(df[config.COL_ROE].max())
            roe = g3.slider("ROE (%)", roe_lo, roe_hi, (roe_lo, roe_hi),
                            help="Return on Equity: laba bersih dibagi ekuitas.")
            der_hi = float(df[config.COL_DER].max())
            der = g4.slider("DER", 0.0, der_hi, (0.0, der_hi),
                            help="Debt to Equity Ratio: total utang dibagi ekuitas.")

    view = df
    if cari:
        view = view[view[config.COL_KODE].str.contains(cari, regex=False)]
    if sektor:
        view = view[view[config.COL_SEKTOR].isin(sektor)]
    if kategori:
        view = view[view["Kategori"].isin(kategori)]
    return view[
        view[config.COL_PER].between(*per)
        & view[config.COL_PBV].between(*pbv)
        & view[config.COL_ROE].between(*roe)
        & view[config.COL_DER].between(*der)
    ]


def _quick_view(p, kode: str) -> None:
    """Kartu pratinjau untuk saham yang diklik di peta atau tabel."""
    row = p.table[p.table[config.COL_KODE] == kode]
    if row.empty:
        return
    row = row.iloc[0]
    sec = p.sector_summary.loc[row[config.COL_SEKTOR]]
    user = auth.current_user()["username"]
    in_wl = kode in db.watchlist(user)

    with st.container(border=True):
        a, b = st.columns([3, 2], vertical_alignment="center")
        a.html(
            f"<div style='display:flex;gap:12px;align-items:center;flex-wrap:wrap'>"
            f"<span style='font-size:1.5rem;font-weight:800'>{ui.esc(kode)}</span>"
            f"{ui.badge_html(row['Kategori'])}"
            f"<span style='color:#64748B'>{ui.esc(row[config.COL_SEKTOR])}</span></div>"
        )
        with b:
            bb = st.columns(3)
            if bb[0].button("Lihat detail", icon=":material/open_in_new:", type="primary",
                            width="stretch"):
                ui.goto("detail", kode_terpilih=kode)
            if in_wl:
                if bb[1].button("Hapus", icon=":material/bookmark_remove:", width="stretch"):
                    db.watchlist_remove(user, kode)
                    st.toast(f"{kode} dihapus dari watchlist")
                    st.rerun()
            elif bb[1].button("Pantau", icon=":material/bookmark_add:", width="stretch"):
                db.watchlist_add(user, kode)
                st.toast(f"{kode} ditambahkan ke watchlist", icon=":material/bookmark_added:")
                st.rerun()
            if bb[2].button("Tutup", icon=":material/close:", width="stretch"):
                st.session_state.pop(KEY_PICK, None)
                st.rerun()

        m = st.columns(4)
        for col, r, med, inv in [
            (m[0], config.COL_PER, "PER_median", False), (m[1], config.COL_PBV, "PBV_median", False),
            (m[2], config.COL_ROE, "ROE_median", False), (m[3], config.COL_DER, "DER_median", True),
        ]:
            col.metric(r + (" (%)" if r == config.COL_ROE else ""), ui.fmt_num(row[r]),
                       f"{row[r] - sec[med]:+.2f} vs median sektor",
                       delta_color="inverse" if inv or r in (config.COL_PER, config.COL_PBV)
                       else "normal", border=True)


def _highlights(df: pd.DataFrame, sec: pd.DataFrame) -> None:
    d = df.copy()
    d["Skor relatif"] = d["Z-PER (sektor)"] + d["Z-PBV (sektor)"]
    d = d.join(sec[["ROE_median", "DER_median"]], on=config.COL_SEKTOR)
    cols = [config.COL_KODE, config.COL_SEKTOR, config.COL_PER, config.COL_PBV,
            config.COL_ROE, config.COL_DER, "Skor relatif"]
    cfg = {
        "Skor relatif": st.column_config.NumberColumn(
            "Z-PER + Z-PBV", format="%.2f",
            help="Makin negatif, makin murah dibanding sektornya."),
        config.COL_ROE: st.column_config.NumberColumn("ROE (%)", format="%.2f"),
        config.COL_PER: st.column_config.NumberColumn(format="%.2f"),
        config.COL_PBV: st.column_config.NumberColumn(format="%.2f"),
        config.COL_DER: st.column_config.NumberColumn(format="%.2f"),
    }

    lists = [
        ("Termurah vs sektor", "Z-PER + Z-PBV terendah",
         d.nsmallest(10, "Skor relatif")),
        ("Murah, fundamental kuat",
         "Relatif Rendah · ROE ≥ median · DER ≤ median sektor",
         d[(d["Kategori"] == config.LABEL_LOW)
           & (d[config.COL_ROE] >= d["ROE_median"])
           & (d[config.COL_DER] <= d["DER_median"])].nlargest(10, config.COL_ROE)),
        ("Termahal vs sektor", "Z-PER + Z-PBV tertinggi",
         d.nlargest(10, "Skor relatif")),
    ]
    c = st.columns(3)
    for i, (ttl, desc, sub) in enumerate(lists):
        with c[i].container(border=True):
            st.markdown(f"**{ttl}**")
            st.caption(desc)
            st.dataframe(sub[cols], hide_index=True, width="stretch", height=390,
                         column_config=cfg, selection_mode="single-row", key=f"hl_{i}",
                         on_select=_pick_row(f"hl_{i}", sub[config.COL_KODE].tolist()))


def render() -> None:
    p = ui.get_pipeline()
    df = p.table
    u = auth.current_user()

    sumber = p.raw_summary.get("berkas")
    ui.market_header(
        "Screener Valuasi Saham BEI",
        "PER &amp; PBV relatif sektor · K-Means" + (f" · {ui.esc(sumber.rsplit('.', 1)[0])}"
                                                   if sumber else ""),
        [("Emiten", str(len(df)), None),
         ("Sektor", str(df[config.COL_SEKTOR].nunique()), None),
         ("Median PER", ui.fmt_num(df[config.COL_PER].median()), None),
         ("Median PBV", ui.fmt_num(df[config.COL_PBV].median()), None),
         ("Watchlist", str(len(db.watchlist(u["username"]))), config.COLOR_PRIMARY)],
    )
    st.write("")
    ui.category_cards(df)
    st.write("")

    view = _filters(df)
    if view.empty:
        st.warning("Tidak ada saham yang cocok. Longgarkan filter.",
                   icon=":material/filter_alt_off:")
        return

    preview = st.container()

    tab_peta, tab_tabel, tab_sorot, tab_ringkas = st.tabs(
        [":material/scatter_plot: Peta Valuasi", ":material/table_rows: Tabel",
         ":material/star: Sorotan", ":material/donut_large: Ringkasan"]
    )

    with tab_peta:
        a, b = st.columns([2, 1.3], vertical_alignment="bottom")
        a.caption(f"**{len(view)}** / {len(df)} saham · klik titik untuk detail")
        sumbu = b.segmented_control(
            "Sumbu", ["Z-score sektor", "PER & PBV asli"], default="Z-score sektor",
            label_visibility="collapsed",
        ) or "Z-score sektor"
        if sumbu == "Z-score sektor":
            fig = ui.scatter_cluster(view, "Z-PER (sektor)", "Z-PBV (sektor)",
                                     highlight=st.session_state.get(KEY_PICK))
            fig.add_hline(y=0, line_dash="dot", line_color="#94A3B8")
            fig.add_vline(x=0, line_dash="dot", line_color="#94A3B8")
            for x, y, t in [(-1, -1, "← lebih murah dari sektor"),
                            (1, 1, "lebih mahal dari sektor →")]:
                fig.add_annotation(xref="paper", yref="paper", x=0.02 if x < 0 else 0.98,
                                   y=0.02 if y < 0 else 0.98, text=t, showarrow=False,
                                   font=dict(color="#94A3B8", size=11),
                                   xanchor="left" if x < 0 else "right")
            fig.update_xaxes(title="Z-PER relatif sektor")
            fig.update_yaxes(title="Z-PBV relatif sektor")
        else:
            fig = ui.scatter_cluster(view, config.COL_PER, config.COL_PBV, log=True,
                                     highlight=st.session_state.get(KEY_PICK))
            fig.update_xaxes(title="PER (skala log)")
            fig.update_yaxes(title="PBV (skala log)")
        st.plotly_chart(fig, width="stretch", selection_mode="points", key="peta_valuasi",
                        on_select=lambda: _pick_point("peta_valuasi"))

        st.caption("Z = 0 berarti setara rata-rata sektor; ±1 = satu simpangan baku.")

    with tab_tabel:
        t = ui.with_label(view)
        c1, c2 = st.columns([3, 1], vertical_alignment="center")
        c1.caption(f"**{len(view)}** / {len(df)} saham · klik baris untuk detail")
        c2.download_button("Unduh CSV", view.to_csv(index=False).encode("utf-8"),
                           file_name="hasil_screener.csv", mime="text/csv",
                           icon=":material/download:", width="stretch")
        st.dataframe(
            t.drop(columns=["Kategori"]),
            width="stretch", hide_index=True, height=520, selection_mode="single-row",
            key="tabel_saham",
            on_select=_pick_row("tabel_saham", view[config.COL_KODE].tolist()),
            column_config={
                config.COL_KODE: st.column_config.TextColumn("Kode", pinned=True),
                "Valuasi": st.column_config.TextColumn(width="small"),
                config.COL_PER: st.column_config.NumberColumn(format="%.2f"),
                config.COL_PBV: st.column_config.NumberColumn(format="%.2f"),
                config.COL_ROE: st.column_config.NumberColumn("ROE (%)", format="%.2f"),
                config.COL_DER: st.column_config.NumberColumn(format="%.2f"),
                "Z-PER (sektor)": st.column_config.NumberColumn(format="%+.3f"),
                "Z-PBV (sektor)": st.column_config.NumberColumn(format="%+.3f"),
                "Silhouette Sampel": st.column_config.ProgressColumn(
                    "Kekuatan cluster", min_value=-1.0, max_value=1.0, format="%.2f",
                    help="Silhouette: 1 = sangat khas, 0 = di perbatasan cluster."),
            },
        )

    with tab_sorot:
        _highlights(view, p.sector_summary)

    with tab_ringkas:
        a, b = st.columns([1, 2])
        with a.container(border=True):
            st.markdown("**Proporsi kategori**")
            st.plotly_chart(ui.donut_categories(view), width="stretch")
        with b.container(border=True):
            st.markdown("**Komposisi kategori per sektor**")
            comp = (view.groupby([config.COL_SEKTOR, "Kategori"]).size()
                    .rename("Jumlah").reset_index())
            comp["Label"] = comp["Kategori"].map(ui.short)
            fig = px.bar(comp, y=config.COL_SEKTOR, x="Jumlah", color="Kategori",
                         orientation="h", color_discrete_map=ui.color_map_for(view),
                         category_orders={"Kategori": config.LABEL_ORDER},
                         custom_data=["Label"])
            fig.update_traces(hovertemplate="<b>%{y}</b><br>%{customdata[0]}: %{x} saham"
                                            "<extra></extra>")
            fig.for_each_trace(lambda t: t.update(name=ui.short(t.name)))
            fig.update_layout(barmode="stack", yaxis=dict(categoryorder="total ascending"),
                              yaxis_title="", xaxis_title="Jumlah saham")
            st.plotly_chart(ui.style_fig(fig, 320), width="stretch")

        st.markdown("**Profil cluster** · median dan rata-rata")
        prof = p.clu.centroid_profile.copy()
        prof.columns = [" ".join(c).strip() if isinstance(c, tuple) else c for c in prof.columns]
        st.dataframe(prof, width="stretch")

    if kode := st.session_state.get(KEY_PICK):
        with preview:
            _quick_view(p, kode)

    st.divider()
    ui.disclaimer()
