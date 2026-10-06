"""
views/evaluasi.py -- Halaman Evaluasi Model (Gambar 3.6)

Isi sesuai Spesifikasi Rancangan butir 4: Elbow Method, Silhouette Score,
Davies-Bouldin Index, Confusion Matrix, Feature Importance, serta Accuracy,
Precision, Recall, dan F1-Score. Seluruh angka berasal dari hasil notebook
yang diimpor; tab Verifikasi menunjukkan bahwa angka itu konsisten.

Tab "K=3 vs K=4" menjalankan ulang prosedur notebook untuk kedua nilai K
(src/compare.py). Hasil K=3 di tab itu identik dengan notebook.

Halaman ini hanya didaftarkan untuk peran admin (lihat app.py).
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


def _elbow_fig(ev: pd.DataFrame, k_pakai: int, k_elbow: int) -> go.Figure:
    fig = go.Figure()
    fig.add_scatter(x=ev["k"], y=ev["Inertia (WCSS)"], mode="lines+markers",
                    name="Inertia", line=dict(color=config.COLOR_PRIMARY, width=3),
                    marker=dict(size=9), fill="tozeroy", fillcolor="rgba(37,99,235,.08)")
    fig.add_vline(x=k_elbow, line_dash="dash", line_color="#DC2626",
                  annotation_text=f"Siku terdeteksi: k={k_elbow}")
    fig.add_vline(x=k_pakai, line_dash="dot", line_color="#16A34A",
                  annotation_text=f"Dipakai: k={k_pakai}", annotation_position="bottom right")
    fig.update_layout(title="Elbow Method", xaxis_title="Jumlah cluster (k)",
                      yaxis_title="Inertia (WCSS)", xaxis=dict(dtick=1))
    return ui.style_fig(fig, 400, legend=False)


def _metric_fig(ev: pd.DataFrame, col: str, best_k: int, arah: str,
                k_pakai: int) -> go.Figure:
    fig = go.Figure()
    fig.add_scatter(x=ev["k"], y=ev[col], mode="lines+markers",
                    line=dict(color="#7C3AED", width=3), marker=dict(size=9), name=col)
    fig.add_vline(x=best_k, line_dash="dash", line_color="#DC2626",
                  annotation_text=f"Terbaik: k={best_k}")
    fig.add_vline(x=k_pakai, line_dash="dot", line_color="#16A34A")
    fig.update_layout(title=f"{col} ({arah})", xaxis_title="Jumlah cluster (k)",
                      yaxis_title=col, xaxis=dict(dtick=1))
    return ui.style_fig(fig, 360, legend=False)


def _tab_clustering(p) -> None:
    ev, reco = p.k_eval, p.k_reco
    if ev.empty:
        st.info(f"`{config.ART_KEVAL}` tidak tersedia.", icon=":material/info:")
    else:
        c = st.columns(4)
        c[0].metric("k dipakai", reco["dipakai"], border=True)
        c[1].metric("Elbow menyarankan", reco["elbow"], border=True,
                    help="Titik dengan jarak terjauh ke garis k pertama–terakhir.")
        c[2].metric("Silhouette menyarankan", reco["silhouette"], border=True)
        c[3].metric("DBI menyarankan", reco["dbi"], border=True)

        if reco["dipakai"] not in {reco["elbow"], reco["silhouette"], reco["dbi"]}:
            st.warning(f"Tidak ada metrik yang menunjuk k={reco['dipakai']} sebagai terbaik.",
                       icon=":material/insights:")

        with st.container(border=True):
            st.plotly_chart(_elbow_fig(ev, reco["dipakai"], reco["elbow"]), width="stretch")
        a, b = st.columns(2)
        with a.container(border=True):
            st.plotly_chart(_metric_fig(ev, "Silhouette Score", reco["silhouette"],
                                        "makin tinggi makin baik", reco["dipakai"]),
                            width="stretch")
        with b.container(border=True):
            st.plotly_chart(_metric_fig(ev, "Davies-Bouldin Index", reco["dbi"],
                                        "makin rendah makin baik", reco["dipakai"]),
                            width="stretch")

        st.markdown(f"**Tabel evaluasi k (notebook, K = {config.K_RANGE_NOTEBOOK})**")
        st.dataframe(ev.round(4), width="stretch", hide_index=True)

    st.markdown("**Centroid dan pelabelan**")
    st.dataframe(p.clu.centroids_z.round(4), width="stretch")
    for n in p.clu.label_notes:
        st.write("- " + n)

    st.markdown("**Profil setiap cluster (nilai asli)**")
    prof = p.clu.centroid_profile.copy()
    prof.columns = [" ".join(c).strip() if isinstance(c, tuple) else c for c in prof.columns]
    st.dataframe(prof, width="stretch")


def _tab_rf(p) -> None:
    m, cls = p.cls.metrics, p.cls
    c = st.columns(4)
    c[0].metric("Accuracy", f"{m['accuracy']:.4f}", border=True)
    c[1].metric("Balanced accuracy", f"{m['balanced_accuracy']:.4f}", border=True,
                help="Rata-rata recall setiap kelas; tidak terpengaruh ketimpangan kelas.")
    c[2].metric("Precision (macro)", f"{m['precision_macro']:.4f}", border=True)
    c[3].metric("F1-Score (macro)", f"{m['f1_macro']:.4f}", border=True)

    st.markdown("**Pembanding: menebak kelas mayoritas (data uji)**")
    st.dataframe(pd.DataFrame({
        "Accuracy": [m["baseline_kelas_mayoritas"], m["accuracy"]],
        "Balanced accuracy": [m["baseline_balanced_accuracy"], m["balanced_accuracy"]],
        "F1-macro": [m["baseline_f1_macro"], m["f1_macro"]],
    }, index=["Tebak kelas mayoritas", "Random Forest"]).round(4), width="stretch")

    st.markdown(f"**Repeated Stratified K-Fold ({config.REPEATED_CV}) pada seluruh data**")
    if cls.cv_summary is None:
        st.info(f"`{config.ART_RF_CV}` tidak tersedia.", icon=":material/info:")
    else:
        cv = cls.cv_summary
        tampil = pd.DataFrame({
            met: [f"{r[f'{met} (rata-rata)']:.4f} ± {r[f'{met} (sd)']:.4f}"
                  for _, r in cv.iterrows()]
            for met in ["Accuracy", "Balanced accuracy", "F1-macro"]
        }, index=cv.index)
        st.dataframe(tampil, width="stretch")
        st.caption("Rata-rata ± simpangan baku dari 50 kali latih–uji.")

    a, b = st.columns([1.2, 1])
    with a.container(border=True):
        st.plotly_chart(ui.heatmap_confusion(cls.confusion, "Confusion Matrix (data uji)"),
                        width="stretch")
    with b.container(border=True):
        imp = cls.feature_importance.melt(
            id_vars="Variabel", value_vars=["MDI", "Permutation (data uji)"],
            var_name="Metode", value_name="Nilai")
        fig = px.bar(imp, x="Nilai", y="Variabel", color="Metode", barmode="group",
                     orientation="h", text_auto=".3f", title="Feature Importance",
                     color_discrete_sequence=["#2563EB", "#7C3AED"])
        fig.update_traces(marker_cornerradius=8)
        fig.update_layout(xaxis_title="Nilai kepentingan", yaxis_title="")
        st.plotly_chart(ui.style_fig(fig, 420), width="stretch")

    st.markdown("**Precision, Recall, dan F1-Score per kelas**")
    st.dataframe(cls.report.round(4), width="stretch")

    st.markdown("**Feature Importance**")
    st.dataframe(cls.feature_importance.round(4), width="stretch", hide_index=True)

    st.markdown("**Model yang dimuat**")
    info = [("Format", cls.format_model),
            ("Data latih / uji", f"{len(cls.X_train)} / {len(cls.X_test)} "
                                 f"(test_size={config.TEST_SIZE}, stratified, "
                                 f"random_state={config.SPLIT_RANDOM_STATE})"),
            ("Batas winsorizing ROE / DER",
             f"{ui.fmt_num(cls.winsor_caps['ROE'], 4)} / {ui.fmt_num(cls.winsor_caps['DER'], 4)}")]
    info += [(f"Hyperparameter: {k}", str(v)) for k, v in cls.params.items()]
    st.dataframe(pd.DataFrame(info, columns=["Item", "Nilai"]), hide_index=True,
                 width="stretch")

    for n in cls.notes:
        st.caption(n)
    st.caption("RF hanya memakai ROE dan DER, sedangkan label berasal dari PER dan PBV; "
               "akurasi sedang adalah temuan, bukan kegagalan model.")


def _tab_pre(p) -> None:
    if p.pre is None:
        st.info("Dataset mentah tidak tersedia.", icon=":material/info:")
        return
    log = p.pre.log_df()
    st.markdown("**Rantai pra-pemrosesan (rekonstruksi sel 2–8 notebook)**")
    funnel = go.Figure(go.Funnel(
        y=log["Tahap"], x=log["Baris sesudah"], textinfo="value+percent initial",
        marker=dict(color=["#1D4ED8", "#2563EB", "#3B82F6", "#60A5FA", "#7C3AED",
                           "#8B5CF6"][: len(log)]),
    ))
    with st.container(border=True):
        st.plotly_chart(ui.style_fig(funnel, 360, legend=False), width="stretch")
    st.dataframe(log, width="stretch", hide_index=True)

    a, b = st.columns(2)
    with a:
        st.markdown("**Koreksi sektor**")
        st.dataframe(p.pre.sector_fixed, hide_index=True, width="stretch")
    with b:
        st.markdown(f"**Ambang winsorizing P{config.WINSOR_PERCENTILE} (PER, PBV)**")
        st.dataframe(pd.DataFrame(p.pre.winsor_caps).T, width="stretch")

    if p.sector_stats is not None:
        st.markdown("**Statistik sektor (penyebut Z-score)**")
        st.dataframe(p.sector_stats.round(4), width="stretch")

    st.markdown("**Data mentah sebelum pembersihan**")
    r = p.raw_summary
    cc = st.columns(4)
    cc[0].metric("Baris", r["n_baris"], border=True)
    cc[1].metric("Kode unik", r["n_saham_unik"], border=True)
    cc[2].metric("Kode duplikat", r["n_duplikat_kode"], border=True)
    cc[3].metric("Nilai sektor unik (mentah)", r["n_sektor"], border=True)
    if r["sektor_anomali"]:
        st.caption("Nilai sektor di luar IDX-IC pada data mentah: "
                   + ", ".join(r["sektor_anomali"])
                   + ". Seluruhnya dikoreksi oleh notebook."
                   if not r["sektor_anomali_setelah_koreksi"] else
                   "Nilai sektor di luar IDX-IC yang masih tersisa setelah koreksi: "
                   + ", ".join(r["sektor_anomali_setelah_koreksi"]))

    for nama, buang in p.pre.dropped.items():
        if len(buang):
            with st.expander(f"Baris dibuang pada tahap: {nama} ({len(buang)})"):
                st.dataframe(buang, width="stretch", hide_index=True)


def _tab_verifikasi(p) -> None:
    if p.all_checks_ok:
        st.success("Data aplikasi konsisten dengan hasil notebook.",
                   icon=":material/verified:")
    else:
        st.error("Ada pemeriksaan yang gagal. Pastikan semua berkas berasal dari satu "
                 "eksekusi notebook.", icon=":material/error:")
    st.dataframe(pd.DataFrame(p.checks), hide_index=True, width="stretch")

    st.markdown("**Berkas sumber**")
    rows = []
    files = [f for f in sorted(p.folder.iterdir()) if f.is_file()]
    raw = p.raw_summary.get("berkas")
    if raw and not (p.folder / raw).exists() and config.DEFAULT_RAW_PATH.name == raw:
        files.append(config.DEFAULT_RAW_PATH)
    for f in files:
        peran = ("wajib" if f.name in config.ARTIFACTS_REQUIRED else
                 "opsional" if f.name in config.ARTIFACTS_OPTIONAL else "dataset mentah")
        rows.append({"Berkas": f.name, "Peran": peran,
                     "Ukuran (KB)": round(f.stat().st_size / 1024, 1),
                     "Diubah": pd.Timestamp(f.stat().st_mtime, unit="s")
                     .strftime("%Y-%m-%d %H:%M")})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def _scatter_k(data: pd.DataFrame, r: compare.KResult) -> go.Figure:
    nama = pd.Series(r.labels).map(r.names).values
    d = data.assign(Label=nama)
    order = [r.names[c] for c in r.profile.index]
    fig = px.scatter(d, x=compare.ZCOLS[0], y=compare.ZCOLS[1], color="Label",
                     color_discrete_map=r.colors, category_orders={"Label": order},
                     custom_data=[config.COL_KODE, config.COL_PER, config.COL_PBV],
                     title=f"K = {r.k}")
    fig.update_traces(marker=dict(size=7, opacity=.7, line=dict(width=.5, color="white")),
                      hovertemplate="<b>%{customdata[0]}</b><br>PER %{customdata[1]:.2f} · "
                                    "PBV %{customdata[2]:.2f}<extra></extra>")
    fig.for_each_trace(lambda t: t.update(name=ui.short(t.name).replace(
        "Valuasi Relatif ", "")))
    cen = r.profile[["Z-PER", "Z-PBV"]]
    fig.add_scatter(x=cen["Z-PER"], y=cen["Z-PBV"], mode="markers", name="Centroid",
                    marker=dict(symbol="x", size=14, color="#0F172A",
                                line=dict(width=2, color="white")), hoverinfo="skip")
    fig.add_hline(y=0, line_dash="dot", line_color="#94A3B8")
    fig.add_vline(x=0, line_dash="dot", line_color="#94A3B8")
    fig.update_layout(xaxis_title="Z-PER relatif sektor", yaxis_title="Z-PBV relatif sektor",
                      legend=dict(font=dict(size=10)))
    return ui.style_fig(fig, 470)


def _profil_tabel(r: compare.KResult) -> None:
    prof = r.profile.copy()
    prof["Label"] = prof["Label"].str.replace("Valuasi Relatif ", "", regex=False)
    st.dataframe(prof, width="stretch", column_config={
        "Proporsi (%)": st.column_config.NumberColumn(format="%.1f"),
        "Z-PER": st.column_config.NumberColumn(format="%+.2f"),
        "Z-PBV": st.column_config.NumberColumn(format="%+.2f"),
        "PER_med": st.column_config.NumberColumn("PER med", format="%.2f"),
        "PBV_med": st.column_config.NumberColumn("PBV med", format="%.2f"),
        "ROE_med": st.column_config.NumberColumn("ROE med (%)", format="%.2f"),
        "DER_med": st.column_config.NumberColumn("DER med", format="%.2f"),
    })


def _tab_banding(p) -> None:
    a, b = ui.get_comparison(3, 4)
    tabel = compare.metric_table(a, b)
    menang_a = int((tabel["Lebih baik"] == f"K={a.k}").sum())
    menang_b = int((tabel["Lebih baik"] == f"K={b.k}").sum())

    ui.market_header(
        f"K = {a.k} vs K = {b.k}",
        "Prosedur notebook dijalankan ulang untuk kedua K: K-Means n_init=50, aturan label "
        "sel 11, Random Forest dengan GridSearch dan split yang sama.",
        [(f"Unggul K={a.k}", str(menang_a), config.COLOR_PRIMARY),
         (f"Unggul K={b.k}", str(menang_b), "#7C3AED"),
         (f"F1 RF K={a.k}", f"{a.metrics['RF F1-macro (uji)']:.4f}", None),
         (f"F1 RF K={b.k}", f"{b.metrics['RF F1-macro (uji)']:.4f}", None)],
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
            w[row["Lebih baik"]] = "background-color:#DCFCE7;font-weight:700"
        return ["" if c not in w else w[c] for c in row.index]

    kiri, kanan = st.columns([1.15, 1])
    with kiri:
        st.markdown("**Ringkasan metrik**")
        st.dataframe(tampil.style.apply(_warna, axis=1), hide_index=True, width="stretch",
                     height=388)
    with kanan:
        st.markdown("**Perpindahan emiten**")
        mig = compare.migration(p.clu.data, a, b)
        pendek = lambda s: s.replace("Valuasi Relatif ", "")
        fig = px.imshow(mig.values, text_auto=True,
                        x=[pendek(c) for c in mig.columns], y=[pendek(i) for i in mig.index],
                        color_continuous_scale=["#F8FAFC", "#1D4ED8"],
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
        f"Parameter RF terbaik · K={a.k}: "
        + ", ".join(f"{k}={v}" for k, v in a.best_params.items())
        + f" · K={b.k}: " + ", ".join(f"{k}={v}" for k, v in b.best_params.items()))
    for n in b.notes:
        st.caption(n)
    st.caption("Hijau = nilai lebih baik. WCSS selalu turun saat K bertambah, sehingga tidak "
               "dapat berdiri sendiri sebagai alasan memilih K.")


def render() -> None:
    p = ui.get_pipeline()
    m = p.cls.metrics
    ui.market_header(
        "Evaluasi Model",
        f"K-Means (PER, PBV) dan Random Forest (ROE, DER) · evaluasi K = "
        f"{config.K_RANGE_NOTEBOOK}",
        [("k", str(p.k), None),
         ("Silhouette", f"{p.clu.silhouette:.4f}", "#7C3AED"),
         ("Davies-Bouldin", f"{p.clu.dbi:.4f}", "#0891B2"),
         ("F1-macro RF", f"{m['f1_macro']:.4f}", "#16A34A"),
         ("Baseline F1", f"{m['baseline_f1_macro']:.4f}", None)],
    )
    st.write("")

    # on_change="rerun": hanya tab yang dibuka yang dijalankan, sehingga perbandingan K
    # (± 30 detik pada pemuatan pertama) tidak menghambat tab lain.
    t1, t2, t3, t4, t5 = st.tabs(
        [":material/hub: Clustering", ":material/forest: Random Forest",
         ":material/compare_arrows: K=3 vs K=4", ":material/filter_alt: Pra-pemrosesan",
         ":material/verified: Verifikasi"],
        key="evaluasi_tab", on_change="rerun")
    for tab, fn in ((t1, _tab_clustering), (t2, _tab_rf), (t3, _tab_banding),
                    (t4, _tab_pre), (t5, _tab_verifikasi)):
        if tab.open:
            with tab:
                fn(p)
