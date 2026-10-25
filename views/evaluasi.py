"""
views/evaluasi.py -- Halaman Evaluasi Model (Gambar L6.5)

Spesifikasi Rancangan butir 4: Elbow Method, Silhouette Score, Davies-Bouldin
Index, Confusion Matrix, nilai Feature Importance Random Forest, serta
Accuracy, Precision, Recall, dan F1-Score. Seluruh angka berasal dari hasil
notebook.

Tata letak mengikuti wireframe: pilihan tampilan K-Means / Random Forest.
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
                    line=dict(color="#7692FF", width=3), marker=dict(size=9), name=col)
    fig.add_vline(x=best_k, line_dash="dash", line_color="#DC2626",
                  annotation_text=f"Terbaik: k={best_k}")
    fig.add_vline(x=k_pakai, line_dash="dot", line_color="#16A34A")
    fig.update_layout(title=f"{col} ({arah})", xaxis_title="Jumlah cluster (k)",
                      yaxis_title=col, xaxis=dict(dtick=1))
    return ui.style_fig(fig, 360, legend=False)


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
        st.plotly_chart(ui.style_fig(fig, 360, legend=False), width="stretch")

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
    fig.update_traces(marker=dict(size=7, opacity=.7, line=dict(width=.5, color="white")),
                      hovertemplate="<b>%{customdata[0]}</b><br>PER %{customdata[1]:.2f} · "
                                    "PBV %{customdata[2]:.2f}<extra></extra>")
    fig.for_each_trace(lambda t: t.update(name=ui.short(t.name).replace(
        "Valuasi Relatif ", "")))
    cen = r.profile[["Z-PER", "Z-PBV"]]
    fig.add_scatter(x=cen["Z-PER"], y=cen["Z-PBV"], mode="markers", name="Centroid",
                    marker=dict(symbol="x", size=14, color=ui.tc("strong"),
                                line=dict(width=2, color="white")), hoverinfo="skip")
    fig.add_hline(y=0, line_dash="dot", line_color="#7692FF")
    fig.add_vline(x=0, line_dash="dot", line_color="#7692FF")
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


def render() -> None:
    p = ui.get_pipeline()
    kiri, kanan = st.columns([2.6, 1], gap="medium", vertical_alignment="center")
    with kiri:
        ui.page_header("Evaluasi Model",
                       f"K-Means (PER, PBV) dan Random Forest (ROE, DER) · {ui.data_badge(p)}")
    with kanan.container(border=True):
        tampilan = st.radio("Pilih tampilan", ["K-Means", "Random Forest"],
                            key="evaluasi_tampilan", horizontal=True)
    st.write("")
    if tampilan == "K-Means":
        _view_kmeans(p)
    else:
        _view_rf(p)
