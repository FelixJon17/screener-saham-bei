"""
views/admin_data.py -- Kelola Data & Model (khusus admin)

Seluruh hasil dihitung langsung dari dataset (src/pipeline.py). Admin
memilih data perhitungan (positif / seluruh data), mengunggah dataset global
pengganti dataset penelitian, dan mengekspor hasil ke Excel. Semua perubahan
di sini berlaku global untuk seluruh pengguna.

Tab "Pra-pemrosesan" dan "Verifikasi" menampilkan rekonstruksi
pra-pemrosesan notebook dan pemeriksaan konsistensi hasil.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
from src import auth, data_loader, dataset_store, db, export, pipeline, trainer, ui

KEY_UPLOADER = "upload_counter"


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


def _tab_impor(actor: str) -> None:
    st.caption("Unggah dataset global (Excel/CSV: Kode Saham, Sektor, PER, PBV, ROE, DER) "
               "untuk menggantikan dataset penelitian bagi seluruh pengguna.")
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


def _tab_riwayat(actor: str, ds) -> None:
    hist = db.list_datasets()
    if not ds.is_default:
        if st.button("Kembali ke dataset penelitian", icon=":material/restore:"):
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
        ui.table(p.sector_stats.round(4), width="stretch")

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

    if note := ui.missing_note(p):
        st.info(note, icon=":material/info:")
    for nama, buang in p.pre.dropped.items():
        if len(buang):
            with st.expander(f"Baris dibuang pada tahap: {nama} ({len(buang)})"):
                ui.table(buang, width="stretch", hide_index=True)


def _tab_verifikasi(p) -> None:
    if p.all_checks_ok:
        st.success("Seluruh pemeriksaan konsistensi lolos.", icon=":material/verified:")
    else:
        st.error("Ada pemeriksaan yang gagal.", icon=":material/error:")
    ui.table(pd.DataFrame(p.checks), hide_index=True, width="stretch")
    if p.source is not None and p.source.exists():
        st.caption(f"Dataset: {p.source.name} · "
                   f"{round(p.source.stat().st_size / 1024, 1)} KB · diubah "
                   + pd.Timestamp(p.source.stat().st_mtime, unit="s", tz="UTC")
                   .tz_convert(config.TIMEZONE).strftime("%Y-%m-%d %H:%M"))


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


def _tab_parameter(actor: str) -> None:
    p = ui.get_pipeline(pribadi=False)
    st.caption("Parameter perhitungan (sama dengan notebook).")
    prm = p.cls.params
    caps = p.cls.winsor_caps
    rentang = (lambda v: f"{v} {caps[v + ' bawah']:.4f} s.d. {caps[v]:.4f}"
               if f"{v} bawah" in caps else f"{v} {caps[v]:.4f}")
    ui.table(pd.DataFrame([
        ("Data perhitungan", f"{p.data_label} · {len(p.table)} saham"),
        ("Koreksi sektor", ", ".join(f"{k} → {v}" for k, v in config.SECTOR_FIXES.items())),
        ("Winsorizing PER/PBV", f"{ui.winsor_text(p)}, seluruh data"),
        ("Standardisasi", f"Z-score per sektor, ddof={config.ZSCORE_DDOF}"),
        ("K-Means", f"k={p.k}, n_init={p.clu.model.n_init}, "
                    f"random_state={p.clu.model.random_state}"),
        ("Winsorizing ROE/DER", f"{ui.winsor_text(p)}, seluruh data "
                                f"({rentang('ROE')}; {rentang('DER')})"),
        ("Random Forest", ", ".join(f"{k}={v}" for k, v in prm.items())),
        ("Pembagian data", f"uji {int(config.TEST_SIZE * 100)}%, stratified, "
                           f"random_state={config.SPLIT_RANDOM_STATE}"),
        ("Penyetelan hiperparameter", "Tidak dilakukan (data uji dipakai sekali)"),
    ], columns=["Parameter", "Nilai"]), hide_index=True, width="stretch")
    if st.button("Hitung ulang", icon=":material/refresh:"):
        ui.clear_pipeline_cache()
        db.log(actor, "Hitung ulang hasil")
        st.rerun()


def _tab_ekspor() -> None:
    p = ui.get_pipeline(pribadi=False)
    st.caption("Seluruh hasil dalam satu berkas Excel bersheet banyak.")
    st.download_button(
        "Unduh Excel hasil lengkap", data=lambda: export.excel_bytes(p),
        file_name="Hasil_Screener_Lengkap.xlsx", type="primary",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        icon=":material/table_view:", on_click="ignore",
    )
    st.download_button(
        "Unduh CSV hasil clustering", p.table.to_csv(index=False).encode("utf-8"),
        file_name="hasil_clustering.csv", mime="text/csv",
        icon=":material/download:", on_click="ignore",
    )


def render() -> None:
    actor = auth.current_user()["username"]
    ds = dataset_store.active()
    p = ui.get_pipeline(pribadi=False)

    ok = p.all_checks_ok
    ui.market_header(
        "Data & Model",
        f"Sumber data screener untuk seluruh pengguna · {ui.esc(ds.label)} · "
        f"{ui.esc(p.data_label)}",
        [("Emiten", str(len(p.table)), None),
         ("Cluster", str(p.k), None),
         ("Verifikasi", "Lolos" if ok else "Gagal", "#16A34A" if ok else "#DC2626"),
         ("Dataset global", str(len(db.list_datasets())), None)],
    )
    st.write("")
    _pilih_data(actor, ds)

    tabs = st.tabs([":material/upload: Unggah dataset", ":material/history: Riwayat",
                    ":material/filter_alt: Pra-pemrosesan", ":material/verified: Verifikasi",
                    ":material/tune: Parameter", ":material/download: Ekspor"],
                   key="data_tab", on_change="rerun")
    isi = [lambda: _tab_impor(actor), lambda: _tab_riwayat(actor, ds),
           lambda: _tab_pra(p),
           lambda: _tab_verifikasi(p), lambda: _tab_parameter(actor), _tab_ekspor]
    for tab, fn in zip(tabs, isi):
        if tab.open:
            with tab:
                fn()
