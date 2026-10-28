"""
views/evaluasi.py -- Halaman Evaluasi Model (Gambar L6.5)

Spesifikasi Rancangan butir 4: Elbow Method, Silhouette Score, Davies-Bouldin
Index, Confusion Matrix, nilai Feature Importance Random Forest, serta
Accuracy, Precision, Recall, dan F1-Score. Seluruh angka berasal dari hasil
notebook.

Tata letak mengikuti wireframe: pilihan tampilan K-Means / Random Forest,
ditambah tampilan Gabungan yang merangkum keduanya per kategori valuasi.
Tampilan Random Forest berisi kartu Accuracy, Precision, Recall, F1-Score,
confusion matrix, diagram batang horizontal Feature Importance (MDI), dan
tabel evaluasi tambahan. Tampilan K-Means memuat analisis sensitivitas K
(3.1.4, src/compare.py). Rekonstruksi pra-pemrosesan dan verifikasi
konsistensi ada di halaman admin Data & Model.

Halaman ini terbuka untuk semua akun yang sudah masuk (lihat app.py).
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import config
from src import compare, ui

FMT_METRIK = {"WCSS": "{:.2f}", "Cluster terkecil (saham)": "{:.0f}",
              "Kelas terkecil di data uji": "{:.0f}"}

WARNA_TERBAIK = "#E08A00"


def _k_fig(ev: pd.DataFrame, col: str, k_pakai: int, k_best: int, label_best: str,
           warna: str, fill: bool = False) -> go.Figure:
    """Grafik satu metrik terhadap K: pita untuk K dipakai, label untuk K terbaik."""
    fig = go.Figure(go.Scatter(
        x=ev["k"], y=ev[col], mode="lines+markers", name=col,
        line=dict(color=warna, width=2.5),
        marker=dict(size=9, color=warna, line=dict(width=2, color=ui.tc("plot_bg"))),
        fill="tozeroy" if fill else None,
        fillcolor=ui._hex_rgba(warna, .08) if fill else None,
        hovertemplate="K = %{x}<br>" + col + ": %{y:.4f}<extra></extra>",
    ))
    ui.mark_k(fig, k_pakai, f"Dipakai · K={k_pakai}", ui.accent(config.ROYAL), band=True)
    if k_best != k_pakai:
        y_best = float(ev.loc[ev["k"] == k_best, col].iat[0])
        # Titik minimum (DBI) diberi label di bawahnya agar tidak menimpa garis.
        ui.mark_k(fig, k_best, f"{label_best} K={k_best}", WARNA_TERBAIK, y=y_best,
                  below=y_best <= ev[col].min() and not fill)
    fig.update_xaxes(dtick=1, title="Jumlah cluster (K)")
    fig.update_yaxes(title=None)
    if not fill:
        lo, hi = ev[col].min(), ev[col].max()
        pad = (hi - lo) * .18 or .05
        fig.update_yaxes(range=[lo - pad * 2.2, hi + pad * 2.2])
    fig = ui.style_fig(fig, 300, legend=False)
    fig.update_layout(margin=dict(t=30, b=30, l=10, r=10))
    return fig


def _view_kmeans(p) -> None:
    ev, reco = p.k_eval, p.k_reco
    c = st.columns(4)
    c[0].metric("K dipakai", p.k, border=True)
    c[1].metric("WCSS (Elbow)", f"{p.clu.inertia:.2f}", border=True)
    c[2].metric("Silhouette Score", f"{p.clu.silhouette:.4f}", border=True,
                help="Makin tinggi makin baik (-1 s.d. 1).")
    c[3].metric("Davies-Bouldin Index", f"{p.clu.dbi:.4f}", border=True,
                help="Makin rendah makin baik.")

    if ev.empty:
        st.info("Evaluasi K tidak tersedia.", icon=":material/info:")
    else:
        sil_k = ev.loc[ev["k"] == reco["dipakai"], "Silhouette Score"]
        if len(sil_k) and sil_k.iat[0] >= 0.51:
            st.info(f"K = {reco['dipakai']} dipakai (Silhouette {sil_k.iat[0]:.4f} ≥ 0,51). "
                    f"Saran metrik: Elbow K = {reco['elbow']} · Silhouette K = "
                    f"{reco['silhouette']} · DBI K = {reco['dbi']}.", icon=":material/insights:")
        elif len(sil_k):
            st.warning(f"Silhouette K = {reco['dipakai']} ({sil_k.iat[0]:.4f}) di bawah 0,51.",
                       icon=":material/insights:")

        # Tiga metrik sejajar agar mudah dibandingkan untuk K yang sama.
        grafik = [
            ("Elbow Method", "Inertia (WCSS), siku = penurunan mulai melandai",
             "Inertia (WCSS)", reco["elbow"], "Siku", ui.accent(config.ROYAL), True),
            ("Silhouette Score", "Makin tinggi makin baik", "Silhouette Score",
             reco["silhouette"], "Terbaik", config.PERI, False),
            ("Davies-Bouldin Index", "Makin rendah makin baik", "Davies-Bouldin Index",
             reco["dbi"], "Terbaik", config.PERI, False),
        ]
        for kol, (judul, ket, col, k_best, lbl, warna, fill) in zip(
                st.columns(3, gap="small"), grafik):
            with kol.container(border=True, height="stretch"):
                st.markdown(f"**{judul}**")
                st.caption(ket)
                st.plotly_chart(_k_fig(ev, col, reco["dipakai"], k_best, lbl, warna, fill),
                                width="stretch", config={"displayModeBar": False})

        with st.container(border=True):
            st.markdown(f"**Tabel Evaluasi K = {config.K_RANGE_NOTEBOOK}**")
            ui.table(ev.round(4), width="stretch", hide_index=True)

    with st.container(border=True):
        st.markdown("**Profil Centroid**")
        ui.table(p.clu.centroids_z.round(4), width="stretch")
        st.caption(p.clu.label_notes[0])

    with st.expander("Analisis Sensitivitas K", expanded=False,
                     icon=":material/compare_arrows:"):
        _tab_banding(p)

def _view_rf(p) -> None:
    m, cls = p.cls.metrics, p.cls
    c = st.columns(4)
    c[0].metric("Accuracy", f"{m['accuracy']:.4f}", border=True)
    c[1].metric("Precision", f"{m['precision_macro']:.4f}", border=True, help="Macro average.")
    c[2].metric("Recall", f"{m['recall_macro']:.4f}", border=True, help="Macro average.")
    c[3].metric("F1-Score", f"{m['f1_macro']:.4f}", border=True, help="Macro average.")

    a, b = st.columns([1.15, 1], gap="medium")
    with a.container(border=True, height="stretch"):
        st.markdown("**Confusion Matrix**")
        n = len(cls.classes)
        st.caption(f"Aktual terhadap prediksi · {len(cls.X_test)} saham data uji")
        st.plotly_chart(ui.heatmap_confusion(cls.confusion, ""), width="stretch")
    with b.container(border=True, height="stretch"):
        st.markdown("**Feature Importance**")
        st.caption("MDI (penurunan Gini rata-rata)")
        imp = cls.feature_importance
        fig = px.bar(imp, x="Feature Importance", y="Variabel", orientation="h",
                     text_auto=".4f", color_discrete_sequence=[ui.accent(config.ROYAL)])
        fig.update_traces(marker_cornerradius=8)
        fig.update_layout(xaxis_title="Nilai kepentingan", yaxis_title="",
                          yaxis=dict(autorange="reversed"))
        st.plotly_chart(ui.horizontal(ui.style_fig(fig, 360, legend=False)), width="stretch")

    with st.container(border=True):
        st.markdown("**Tabel Evaluasi Tambahan**")
        st.caption("Per kelas, macro, dan weighted average")
        rep = cls.report.copy()
        nama = {"accuracy": "Accuracy", "macro avg": "Macro average",
                "weighted avg": "Weighted average"}
        rep.index = [ui.short(i) if i in config.LABEL_ORDER else nama.get(i, i)
                     for i in rep.index]
        ui.table(rep.round(4), width="stretch", column_config={
            "precision": "Precision", "recall": "Recall", "f1-score": "F1-Score",
            "support": st.column_config.NumberColumn("Support", format="%d")})

    st.caption("Label berasal dari clustering PER dan PBV, Random Forest menggunakan ROE dan DER")

def _scatter_k(data: pd.DataFrame, r: compare.KResult) -> go.Figure:
    nama = pd.Series(r.labels).map(r.names).values
    d = data.assign(Label=nama)
    order = [r.names[c] for c in r.profile.index]
    fig = px.scatter(d, x=compare.ZCOLS[0], y=compare.ZCOLS[1], color="Label",
                     color_discrete_map=r.colors, category_orders={"Label": order},
                     custom_data=[config.COL_KODE, config.COL_PER, config.COL_PBV],
                     title=f"K = {r.k}")
    fig.update_traces(marker=dict(size=7, opacity=.8,
                                  line=dict(width=.5, color=ui.tc("plot_bg"))),
                      hovertemplate="<b>%{customdata[0]}</b><br>PER %{customdata[1]:.2f} · "
                                    "PBV %{customdata[2]:.2f}<extra></extra>")
    fig.for_each_trace(lambda t: t.update(name=ui.short(t.name).replace(
        "Valuasi Relatif ", "")))
    cen = r.profile[["Z-PER", "Z-PBV"]]
    fig.add_scatter(x=cen["Z-PER"], y=cen["Z-PBV"], mode="markers", name="Centroid",
                    marker=dict(symbol="x", size=14, color=ui.tc("strong"),
                                line=dict(width=2, color=ui.tc("plot_bg"))),
                    hoverinfo="skip")
    ui.zero_lines(fig)
    fig.update_layout(xaxis_title="Z-PER relatif sektor", yaxis_title="Z-PBV relatif sektor",
                      legend=dict(font=dict(size=10)))
    return ui.style_fig(fig, 470)

def _profil_tabel(r: compare.KResult) -> None:
    prof = r.profile.copy()
    prof["Label"] = prof["Label"].str.replace("Valuasi Relatif ", "", regex=False)
    ui.table(prof, width="stretch", column_config={
        "Proporsi (%)": st.column_config.NumberColumn(format="%.1f"),
        "Z-PER": st.column_config.NumberColumn(format="%+.2f"),
        "Z-PBV": st.column_config.NumberColumn(format="%+.2f"),
        "PER_med": st.column_config.NumberColumn("PER med", format="%.2f"),
        "PBV_med": st.column_config.NumberColumn("PBV med", format="%.2f"),
        "ROE_med": st.column_config.NumberColumn("ROE med (%)", format="%.2f"),
        "DER_med": st.column_config.NumberColumn("DER med", format="%.2f"),
    })


def _tab_banding(p) -> None:
    reco = p.k_reco
    kandidat = sorted({k for k in (reco.get("silhouette"), reco.get("dbi"))
                       if k and k != p.k}) or [4]
    alasan = {reco.get("silhouette"): "Silhouette terbaik", reco.get("dbi"): "DBI terbaik"}
    kb = st.segmented_control(
        "K pembanding", kandidat, default=kandidat[-1], key="sens_k",
        format_func=lambda k: f"K = {k}" + (f" · {alasan[k]}" if k in alasan else ""))         or kandidat[-1]
    a, b = ui.get_comparison(p.k, int(kb))
    tabel = compare.metric_table(a, b)
    menang_a = int((tabel["Lebih baik"] == f"K={a.k}").sum())
    menang_b = int((tabel["Lebih baik"] == f"K={b.k}").sum())

    ui.market_header(
        f"K = {a.k} vs K = {b.k}",
        "Prosedur yang sama dengan notebook untuk kedua K",
        [(f"Unggul K={a.k}", str(menang_a), config.COLOR_PRIMARY),
         (f"Unggul K={b.k}", str(menang_b), "#7692FF"),
         (f"F1 RF K={a.k}", f"{a.metrics['RF F1-Score (macro)']:.4f}", None),
         (f"F1 RF K={b.k}", f"{b.metrics['RF F1-Score (macro)']:.4f}", None)],
    )
    st.write("")

    tampil = tabel.copy()
    for col in (f"K={a.k}", f"K={b.k}"):
        tampil[col] = [FMT_METRIK.get(m, "{:.4f}").format(v)
                       for m, v in zip(tabel["Metrik"], tabel[col])]
    tampil.insert(1, "Kelompok", ["Clustering"] * 4 + ["Random Forest"] * 6)

    def _warna(row):
        w = {f"K={a.k}": "", f"K={b.k}": ""}
        if row["Lebih baik"] in w:
            w[row["Lebih baik"]] = f"background-color:{ui.tc('ok_bg')};font-weight:700"
        return ["" if c not in w else w[c] for c in row.index]

    kiri, kanan = st.columns([1.15, 1])
    with kiri:
        st.markdown("**Ringkasan metrik**")
        ui.table(tampil.style.apply(_warna, axis=1), hide_index=True, width="stretch",
                     height=388)
    with kanan:
        st.markdown("**Perpindahan emiten**")
        mig = compare.migration(p.clu.data, a, b)
        pendek = lambda s: s.replace("Valuasi Relatif ", "")
        fig = px.imshow(mig.values, text_auto=True,
                        x=[pendek(c) for c in mig.columns], y=[pendek(i) for i in mig.index],
                        color_continuous_scale=[ui.tc("scale_lo"), ui.tc("scale_hi")],
                        labels=dict(x=f"K={b.k}", y=f"K={a.k}", color="Emiten"))
        fig.update_layout(coloraxis_showscale=False, xaxis_tickangle=-20)
        st.plotly_chart(ui.style_fig(fig, 388, legend=False), width="stretch")

    c1, c2 = st.columns(2)
    with c1.container(border=True):
        st.plotly_chart(_scatter_k(p.clu.data, a), width="stretch")
    with c2.container(border=True):
        st.plotly_chart(_scatter_k(p.clu.data, b), width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**Profil cluster K={a.k}**")
        _profil_tabel(a)
    with c2:
        st.markdown(f"**Profil cluster K={b.k}**")
        _profil_tabel(b)

    st.caption(
        f"Feature Importance RF · K={a.k}: "
        + ", ".join(f"{k} {v:.4f}" for k, v in a.importance.items())
        + f" · K={b.k}: " + ", ".join(f"{k} {v:.4f}" for k, v in b.importance.items()))
    st.caption("Hijau = lebih baik. WCSS selalu turun saat K bertambah.")

def _kartu_skor(items: list[tuple[str, str, str, str]]) -> str:
    """Kartu skor 2 x 2: (nama, nilai, keterangan, penanda HTML)."""
    return "<div class='ev-score'>" + "".join(
        f"<div class='it'><div class='k'>{ui.esc(k)}{pil}</div><div class='v'>{v}</div>"
        f"<div class='h'>{ui.esc(h)}</div></div>" for k, v, h, pil in items) + "</div>"


def _view_gabungan(p) -> None:
    """Ringkasan K-Means dan Random Forest: alur, skor utama, dan hasil per kategori."""
    m, cls, clu = p.cls.metrics, p.cls, p.clu
    n = len(p.table)
    cnt = p.table["Kategori"].value_counts()
    kategori = [k for k in config.LABEL_ORDER if k in cnt.index]
    lap = cls.report
    lolos = clu.silhouette >= 0.51
    top = cls.feature_importance.iloc[0]

    # -------------------------------------------------------------- alur
    langkah = [
        ("Data", f"{n} saham", "PER dan PBV diubah menjadi Z-score relatif sektor."),
        ("K-Means", f"K = {p.k}", f"Silhouette {clu.silhouette:.4f} · DBI {clu.dbi:.4f}"),
        ("Label valuasi", f"{len(kategori)} kategori",
         " · ".join(f"{ui.tiny(k)} {cnt[k]}" for k in kategori)),
        ("Random Forest", "ROE & DER",
         f"Accuracy {m['accuracy']:.4f} · F1 {m['f1_macro']:.4f}"),
    ]
    st.html("<div class='ev-flow'>" + "".join(
        f"<div class='st'><div class='n'>Langkah {i}</div><div class='t'>{ui.esc(t)} · "
        f"{ui.esc(v)}</div><div class='d'>{ui.esc(d)}</div></div>"
        for i, (t, v, d) in enumerate(langkah, start=1)) + "</div>")
    st.write("")

    # --------------------------------------------------------- skor utama
    a, b = st.columns(2, gap="medium")
    with a.container(border=True, height="stretch"):
        st.markdown("**K-Means** · kualitas pengelompokan")
        st.caption("Dari Z-score PER dan PBV terhadap rata-rata sektor")
        pil = (f"<span class='ev-pill {'ok' if lolos else 'no'}'>"
               f"{'≥ 0,51' if lolos else '< 0,51'}</span>")
        reco = p.k_reco
        st.html(_kartu_skor([
            ("Silhouette Score", f"{clu.silhouette:.4f}", "Makin tinggi makin baik", pil),
            ("Davies-Bouldin Index", f"{clu.dbi:.4f}", "Makin rendah makin baik", ""),
            ("WCSS (Inertia)", f"{clu.inertia:.2f}", "Jarak total saham ke centroid", ""),
            ("K dipakai", f"{p.k}", f"Saran: Elbow {reco['elbow']} · Silhouette "
                                    f"{reco['silhouette']} · DBI {reco['dbi']}", ""),
        ]))
    with b.container(border=True, height="stretch"):
        st.markdown("**Random Forest** · ROE dan DER mengenali label")
        st.caption(f"Data uji {len(cls.X_test)} saham (20%), macro average")
        st.html(_kartu_skor([
            ("Accuracy", f"{m['accuracy']:.4f}", "Prediksi tepat dari seluruh data uji", ""),
            ("Precision", f"{m['precision_macro']:.4f}", "Ketepatan prediksi per kelas", ""),
            ("Recall", f"{m['recall_macro']:.4f}", "Kelas yang berhasil dikenali", ""),
            ("F1-Score", f"{m['f1_macro']:.4f}", "Keseimbangan precision dan recall", ""),
        ]))

    # ------------------------------------------------------ per kategori
    with st.container(border=True):
        st.markdown("**Per kategori valuasi**")
        st.caption("Hasil K-Means (anggota dan centroid) berdampingan dengan kinerja Random "
                   "Forest pada kelas yang sama")
        cen = clu.centroids_z.set_index("Kategori")
        kolom = [("K-Means", "Jumlah saham"), ("K-Means", "Proporsi (%)"),
                 ("K-Means", "Z-PER centroid"), ("K-Means", "Z-PBV centroid"),
                 ("Random Forest", "Precision"), ("Random Forest", "Recall"),
                 ("Random Forest", "F1-Score"), ("Random Forest", "Data uji")]
        isi = [[int(cnt[k]), cnt[k] / n * 100, cen.loc[k, "Z_PER"], cen.loc[k, "Z_PBV"],
                lap.loc[k, "precision"], lap.loc[k, "recall"], lap.loc[k, "f1-score"],
                int(lap.loc[k, "support"])] for k in kategori]
        tabel = pd.DataFrame(isi, columns=pd.MultiIndex.from_tuples(kolom),
                             index=pd.Index([ui.dot_html(k) + ui.esc(ui.short(k))
                                             for k in kategori], name="Kategori"))
        fmt = {c: "{:.4f}" for c in kolom[4:7]}
        fmt.update({kolom[1]: "{:.1f}", kolom[2]: "{:+.2f}", kolom[3]: "{:+.2f}"})
        st.html(ui.html_table(tabel, fmt=fmt))
        st.write("")

        kiri, kanan = st.columns([1.4, 1], gap="medium")
        with kiri:
            nama = [ui.tiny(k) for k in kategori]
            prop = [cnt[k] / n * 100 for k in kategori]
            f1 = [lap.loc[k, "f1-score"] * 100 for k in kategori]
            fig = go.Figure()
            fig.add_bar(x=nama, y=prop, name="Proporsi saham (K-Means)",
                        marker=dict(color=[ui.color_of(k) for k in kategori], cornerradius=6),
                        text=[f"{v:.1f}%" for v in prop], textposition="outside",
                        cliponaxis=False, hovertemplate="%{x}: %{y:.1f}% saham<extra></extra>")
            fig.add_bar(x=nama, y=f1, name="F1-Score (Random Forest)",
                        marker=dict(color=ui.accent(config.ROYAL), opacity=.45, cornerradius=6),
                        text=[f"{v / 100:.2f}" for v in f1], textposition="outside",
                        cliponaxis=False, hovertemplate="%{x}: F1 %{y:.1f}%<extra></extra>")
            fig.update_layout(barmode="group", bargap=.35)
            fig.update_yaxes(range=[0, 110], ticksuffix="%")
            st.plotly_chart(ui.style_fig(fig, 300), width="stretch")
        with kanan:
            terbaik = max(kategori, key=lambda k: lap.loc[k, "f1-score"])
            terlemah = min(kategori, key=lambda k: lap.loc[k, "f1-score"])
            besar = max(kategori, key=lambda k: cnt[k])
            poin = [
                f"K-Means membentuk <b>{p.k} kategori</b> dengan Silhouette "
                f"<b>{clu.silhouette:.4f}</b> ({'memenuhi' if lolos else 'di bawah'} batas "
                f"0,51) dan DBI <b>{clu.dbi:.4f}</b>.",
                f"Kategori terbesar: <b>{ui.esc(ui.short(besar))}</b>, {cnt[besar]} saham "
                f"({cnt[besar] / n * 100:.1f}%).",
                f"Random Forest dengan ROE dan DER mencapai Accuracy "
                f"<b>{m['accuracy']:.4f}</b> dan F1-Score <b>{m['f1_macro']:.4f}</b>.",
                f"Paling mudah dikenali: <b>{ui.esc(ui.tiny(terbaik))}</b> (F1 "
                f"{lap.loc[terbaik, 'f1-score']:.4f}); paling sulit: "
                f"<b>{ui.esc(ui.tiny(terlemah))}</b> (F1 {lap.loc[terlemah, 'f1-score']:.4f}).",
                f"Variabel paling berpengaruh: <b>{ui.esc(top['Variabel'])}</b> "
                f"({top['Persentase']:.2f}% Feature Importance).",
            ]
            st.markdown("**Ringkasan**")
            st.html("<ul class='ev-note'>" + "".join(f"<li>{x}</li>" for x in poin) + "</ul>")

    st.caption("Label berasal dari clustering PER dan PBV; Random Forest hanya memakai ROE "
               "dan DER untuk mengenali label tersebut.")


def render() -> None:
    p = ui.get_pipeline()
    kiri, kanan = st.columns([2.2, 1.4], gap="medium", vertical_alignment="center")
    with kiri:
        ui.page_header("Evaluasi Model",
                       f"K-Means (PER, PBV) dan Random Forest (ROE, DER) · {ui.data_badge(p)}")
    with kanan.container(border=True):
        tampilan = st.radio("Pilih tampilan", ["K-Means", "Random Forest", "Gabungan"],
                            key="evaluasi_tampilan", horizontal=True)
    st.write("")
    if tampilan == "K-Means":
        _view_kmeans(p)
    elif tampilan == "Random Forest":
        _view_rf(p)
    else:
        _view_gabungan(p)
