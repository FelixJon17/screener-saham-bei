"""
views/admin_data.py -- Kelola Data & Model (khusus admin)

Seluruh hasil dihitung langsung dari dataset (src/pipeline.py). Admin
memilih data perhitungan (positif / seluruh data) dan mengelola dataset global
pengganti dataset penelitian. Semua perubahan di sini berlaku global untuk
seluruh pengguna.

Tab "Dataset" berisi unggah dataset, riwayat dataset, dan log aktivitas
perubahannya; tab "Model" menampilkan rekonstruksi pra-pemrosesan notebook.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
from src import auth, data_loader, dataset_store, db, pipeline, trainer, ui

KEY_UPLOADER = "upload_counter"

# Judul daftar baris yang dibuang per tahap pra-pemrosesan
JUDUL_DIBUANG = {
    "missing_value": "Data tidak lengkap",
    "per_pbv_non_positif": "Data dengan PER atau PBV ≤ 0",
}


@st.dialog("Hapus dataset?", icon=":material/delete:")
def _confirm_delete(ds_id: int, nama: str) -> None:
    st.write(f"Dataset **{nama}** akan dihapus permanen dari server.")
    a, b = st.columns(2)
    if a.button("Batal", width="stretch"):
        st.rerun()
    if b.button("Ya, hapus", type="primary", width="stretch"):
        dataset_store.remove(ds_id, auth.current_user()["username"])
        ui.clear_pipeline_cache()
        st.rerun()


def _unggah(actor: str) -> None:
    st.markdown("**Unggah dataset baru**")
    st.caption("Excel/CSV berisi Kode Saham, Sektor, PER, PBV, ROE, DER. Dataset yang "
               "diaktifkan menggantikan dataset penelitian bagi seluruh pengguna.")
    f = st.file_uploader("Dataset", type=["xlsx", "csv"], label_visibility="collapsed",
                         key=f"uploader_{st.session_state.get(KEY_UPLOADER, 0)}")
    if not f:
        return
    try:
        raw = trainer.read_file(f.getvalue(), f.name)
    except Exception as e:  # format rusak, lembar kosong, terlalu besar
        st.error(f"Berkas tidak dapat dibaca: {e}", icon=":material/error:")
        return
    guess = trainer.guess_columns(raw.columns)
    opsi = [None, *raw.columns]
    with st.expander(f"Pemetaan kolom · {sum(v is not None for v in guess.values())}/6 "
                     "terdeteksi", expanded=None in guess.values(), icon=":material/swap_horiz:"):
        cols = st.columns(3)
        mapping = {
            c: cols[i % 3].selectbox(
                c, opsi, index=opsi.index(guess[c]) if guess[c] is not None else 0,
                format_func=lambda v: "— pilih kolom —" if v is None else str(v),
                key=f"impor_map_{c}")
            for i, c in enumerate(config.REQUIRED_COLUMNS)
        }
    ui.table(raw.head(5), hide_index=True, width="stretch", height=150)

    a, b, c = st.columns([2, 1.2, 1], vertical_alignment="bottom")
    label = a.text_input("Nama dataset", value=Path(f.name).stem[:60],
                         placeholder="mis. Data Oktober 2026")
    aktifkan = b.checkbox("Langsung aktifkan", value=True)
    if c.button("Simpan", type="primary", icon=":material/upload:", width="stretch"):
        try:
            df = trainer.prepare(raw, mapping)
            with st.spinner("Menjalankan K-Means dan Random Forest…"):
                ds_id = dataset_store.save_upload(df, label, f.name, actor)
        except (trainer.TrainError, data_loader.SchemaError, pipeline.ArtifactError) as e:
            st.error(f"Dataset ditolak: {e}", icon=":material/error:")
            return
        if aktifkan:
            dataset_store.activate(ds_id, actor)
            ui.clear_pipeline_cache()
        st.session_state[KEY_UPLOADER] = st.session_state.get(KEY_UPLOADER, 0) + 1
        st.toast("Dataset disimpan" + (" dan diaktifkan" if aktifkan else ""),
                 icon=":material/check_circle:")
        st.rerun()


def _tab_dataset(actor: str, ds) -> None:
    with st.container(border=True):
        _unggah(actor)
    with st.container(border=True):
        _riwayat(actor, ds)
    with st.container(border=True):
        st.markdown("**Aktivitas perubahan dataset**")
        log = db.dataset_activity()
        if log.empty:
            st.caption("Belum ada aktivitas.")
        else:
            ui.table(log, hide_index=True, width="stretch", height=300)


def _riwayat(actor: str, ds) -> None:
    hist = db.list_datasets()
    a, b = st.columns([2, 1], vertical_alignment="center")
    a.markdown("**Riwayat dataset**")
    if not ds.is_default:
        if b.button("Kembali ke dataset penelitian", icon=":material/restore:",
                    width="stretch"):
            dataset_store.activate(None, actor)
            ui.clear_pipeline_cache()
            st.rerun()
    if hist.empty:
        st.info(f"Belum ada dataset global. Memakai `{config.DEFAULT_RAW_PATH.name}`.",
                icon=":material/info:")
        return
    hist["Status"] = hist["id"].map(lambda i: "Aktif" if i == ds.id else "")
    show = hist[["id", "Status", "filename", "n_rows", "uploaded_by", "uploaded_at"]]
    ui.table(show, hide_index=True, width="stretch",
                 column_config={"id": "ID", "filename": "Nama dataset", "n_rows": "Saham",
                                "uploaded_by": "Diunggah oleh", "uploaded_at": "Waktu"})
    opsi = dict(zip(hist["id"], hist["filename"]))
    a, b, c = st.columns([2, 1, 1], vertical_alignment="bottom")
    pilih = a.selectbox("Pilih dataset", list(opsi),
                        format_func=lambda i: f"#{i} — {opsi[i]}")
    if b.button("Aktifkan", icon=":material/check:", type="primary",
                width="stretch", disabled=pilih == ds.id):
        dataset_store.activate(int(pilih), actor)
        ui.clear_pipeline_cache()
        st.toast(f"Dataset #{pilih} diaktifkan", icon=":material/check_circle:")
        st.rerun()
    if c.button("Hapus", icon=":material/delete:", width="stretch"):
        _confirm_delete(int(pilih), opsi[pilih])


def _tab_pra(p) -> None:
    if p.pre is None:
        st.info("Dataset mentah tidak tersedia.", icon=":material/info:")
        return
    log = p.pre.log_df()
    st.markdown("**Rantai pra-pemrosesan**")
    funnel = go.Figure(go.Funnel(
        y=log["Tahap"], x=log["Baris sesudah"], textinfo="value+percent initial",
        marker=dict(color=["#1B2CC1", "#1B2CC1", "#7692FF", "#ABD2FA", "#7692FF",
                           "#ABD2FA"][: len(log)]),
    ))
    with st.container(border=True):
        ui.chart(ui.style_fig(funnel, 360, legend=False), "rantai_pra_pemrosesan",
                 width="stretch")
    ui.table(log, width="stretch", hide_index=True)

    a, b = st.columns(2)
    with a:
        st.markdown("**Koreksi sektor**")
        ui.table(p.pre.sector_fixed, hide_index=True, width="stretch")
    with b:
        st.markdown(f"**Ambang winsorizing P{config.WINSOR_PERCENTILE} (PER, PBV)**")
        ui.table(pd.DataFrame(p.pre.winsor_caps).T, width="stretch")

    if p.sector_stats is not None:
        st.markdown("**Statistik sektor (penyebut Z-score)**")
        # Header dua tingkat seperti Tabel Statistik Sektor: PER dan PBV di atas μ dan σ.
        s = p.sector_stats
        kolom = [("", "Jumlah Saham")] + [(m, x) for m in ("PER", "PBV")
                                           for x in ("Rata-rata (μ)", "Standar Deviasi (σ)")]
        tabel = pd.DataFrame(
            [[int(r["n"]), r["mu_PER"], r["sigma_PER"], r["mu_PBV"], r["sigma_PBV"]]
             for _, r in s.iterrows()],
            index=s.index.rename("Sektor"), columns=pd.MultiIndex.from_tuples(kolom))
        st.html(ui.html_table(tabel, fmt={c: "{:.4f}" for c in kolom[1:]}))

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
            judul = JUDUL_DIBUANG.get(nama, f"Data dibuang pada tahap {nama}")
            with st.expander(f"{judul} ({len(buang)} Saham)"):
                # Keterangan saham yang datanya kosong (mis. FREN) menyatu dengan tabelnya.
                if nama == "missing_value" and (note := ui.missing_note(p)):
                    st.caption(note)
                ui.table(buang, width="stretch", hide_index=True)


def _pilih_data(actor: str, ds) -> None:
    """Konfigurasi data perhitungan K-Means dan Random Forest (set bawaan)."""
    mode = dataset_store.data_mode()
    with st.container(border=True):
        a, b = st.columns([1.2, 2], vertical_alignment="center")
        with a:
            st.markdown("**Data perhitungan K-Means & Random Forest**")
            st.caption("Berlaku untuk seluruh halaman dan pengguna.")
        pilih = b.segmented_control(
            "Data perhitungan", list(config.DATA_MODES), default=mode, key="data_mode_pick",
            format_func=lambda m: config.DATA_MODES[m],
            label_visibility="collapsed", width="stretch") or mode
        if pilih != mode:
            dataset_store.set_data_mode(pilih, actor)
            ui.clear_pipeline_cache()
            st.toast(config.DATA_MODES[pilih] + " digunakan", icon=":material/check_circle:")
            st.rerun()


def render() -> None:
    actor = auth.current_user()["username"]
    ds = dataset_store.active()
    p = ui.get_pipeline(pribadi=False)

    ui.market_header(
        "Data & Model",
        f"Sumber data screener untuk seluruh pengguna · {ui.esc(ds.label)} · "
        f"{ui.esc(p.data_label)}",
        [("Emiten", str(len(p.table)), None),
         ("Sektor", str(p.table[config.COL_SEKTOR].nunique()), None),
         ("Cluster", str(p.k), None),
         ("Dataset global", str(len(db.list_datasets())), None)],
    )
    st.write("")
    _pilih_data(actor, ds)

    tabs = st.tabs([":material/database: Dataset", ":material/model_training: Model"],
                   key="data_tab", on_change="rerun")
    isi = [lambda: _tab_dataset(actor, ds), lambda: _tab_pra(p)]
    for tab, fn in zip(tabs, isi):
        if tab.open:
            with tab:
                fn()
