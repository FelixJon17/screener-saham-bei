"""
views/admin_data.py -- Kelola Data & Model (khusus admin)

Aplikasi tidak melatih model sendiri. Admin mengimpor berkas hasil notebook
(folder output_revisi/), memilih set hasil yang aktif, dan mengekspor hasil
ke Excel. Semua perubahan di sini berlaku global untuk seluruh pengguna.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import config
from src import auth, dataset_store, db, export, ui

KEY_UPLOADER = "upload_counter"


@st.dialog("Hapus set hasil?", icon=":material/delete:")
def _confirm_delete(ds_id: int, nama: str) -> None:
    st.write(f"Set hasil **{nama}** beserta seluruh berkasnya akan dihapus permanen dari "
             "server. Tindakan ini tidak dapat dibatalkan.")
    a, b = st.columns(2)
    if a.button("Batal", width="stretch"):
        st.rerun()
    if b.button("Ya, hapus", type="primary", width="stretch"):
        dataset_store.remove(ds_id, auth.current_user()["username"])
        ui.clear_pipeline_cache()
        st.rerun()


def _tab_impor(actor: str) -> None:
    st.caption("Unggah isi folder `output_revisi/` dan dataset mentah (opsional).")
    st.dataframe(pd.DataFrame(
        [(n, "wajib") for n in config.ARTIFACTS_REQUIRED]
        + [(n, "opsional") for n in config.ARTIFACTS_OPTIONAL]
        + [("Dataset mentah (.xlsx/.csv, nama bebas)", "opsional")],
        columns=["Berkas", "Status"]), hide_index=True, width="stretch")

    files = st.file_uploader(
        "Pilih berkas hasil notebook", type=["xlsx", "csv", "joblib"],
        accept_multiple_files=True,
        key=f"uploader_{st.session_state.get(KEY_UPLOADER, 0)}")
    if not files:
        return

    names = [f.name for f in files]
    kurang = [n for n in config.ARTIFACTS_REQUIRED if n not in names]
    mentah = [n for n in names if n not in config.ARTIFACT_NAMES and not n.endswith(".joblib")]
    c = st.columns(3)
    c[0].metric("Berkas dipilih", len(files), border=True)
    c[1].metric("Berkas wajib", f"{3 - len(kurang)} / 3", border=True)
    c[2].metric("Dataset mentah", mentah[0] if mentah else "—", border=True)
    if kurang:
        st.error("Berkas wajib belum ada: " + ", ".join(kurang), icon=":material/error:")
        return
    if len(mentah) > 1:
        st.error("Hanya boleh satu dataset mentah. Ditemukan: " + ", ".join(mentah),
                 icon=":material/error:")
        return

    st.warning("Impor hanya berkas .joblib dari notebook Anda sendiri.",
               icon=":material/shield:")
    a, b, _ = st.columns([2, 1.3, 1], vertical_alignment="bottom")
    label = a.text_input("Nama set hasil", placeholder="mis. Data Oktober 2026")
    aktifkan = b.checkbox("Langsung aktifkan", value=True)
    if st.button("Impor & periksa", type="primary", icon=":material/upload:"):
        try:
            with st.spinner("Memuat model dan memeriksa konsistensi…"):
                ds_id = dataset_store.save_upload(
                    [(f.name, f.getvalue()) for f in files], label, actor)
        except Exception as e:  # berkas rusak, versi scikit-learn berbeda, dsb.
            st.error(f"Set hasil ditolak: {e}", icon=":material/error:")
            return
        if aktifkan:
            dataset_store.activate(ds_id, actor)
            ui.clear_pipeline_cache()
        st.session_state[KEY_UPLOADER] = st.session_state.get(KEY_UPLOADER, 0) + 1
        st.toast("Set hasil diimpor" + (" dan diaktifkan" if aktifkan else ""),
                 icon=":material/check_circle:")
        st.rerun()


def _tab_riwayat(actor: str, ds) -> None:
    hist = db.list_datasets()
    if not ds.is_default:
        if st.button("Kembali ke set bawaan", icon=":material/restore:"):
            dataset_store.activate(None, actor)
            ui.clear_pipeline_cache()
            st.rerun()
    if hist.empty:
        st.info(f"Belum ada impor. Memakai `{config.MODEL_DIR.name}/`.",
                icon=":material/info:")
        return
    hist["Status"] = hist["id"].map(lambda i: "Aktif" if i == ds.id else "")
    show = hist[["id", "Status", "filename", "n_rows", "uploaded_by", "uploaded_at"]]
    st.dataframe(show, hide_index=True, width="stretch",
                 column_config={"id": "ID", "filename": "Nama set", "n_rows": "Saham",
                                "uploaded_by": "Diimpor oleh", "uploaded_at": "Waktu"})
    opsi = dict(zip(hist["id"], hist["filename"]))
    a, b, c = st.columns([2, 1, 1], vertical_alignment="bottom")
    pilih = a.selectbox("Pilih set hasil", list(opsi),
                        format_func=lambda i: f"#{i} — {opsi[i]}")
    if b.button("Aktifkan", icon=":material/check:", type="primary",
                width="stretch", disabled=pilih == ds.id):
        dataset_store.activate(int(pilih), actor)
        ui.clear_pipeline_cache()
        st.toast(f"Set hasil #{pilih} diaktifkan", icon=":material/check_circle:")
        st.rerun()
    if c.button("Hapus", icon=":material/delete:", width="stretch"):
        _confirm_delete(int(pilih), opsi[pilih])


def _tab_parameter(actor: str) -> None:
    p = ui.get_pipeline()
    st.caption("Dibaca dari model notebook. Ubah di notebook, lalu muat ulang.")
    prm = p.cls.params
    st.dataframe(pd.DataFrame([
        ("Koreksi sektor", ", ".join(f"{k} → {v}" for k, v in config.SECTOR_FIXES.items())),
        ("Winsorizing PER/PBV", f"P{config.WINSOR_PERCENTILE} ekor atas, seluruh data"),
        ("Standardisasi", f"Z-score per sektor, ddof={config.ZSCORE_DDOF}"),
        ("K-Means", f"k={p.k}, n_init={p.clu.model.n_init}, "
                    f"random_state={p.clu.model.random_state}"),
        ("Winsorizing ROE/DER", f"P{config.WINSOR_PERCENTILE} dari data latih "
                                f"(ROE {p.cls.winsor_caps['ROE']:.4f}, "
                                f"DER {p.cls.winsor_caps['DER']:.4f})"),
        ("Random Forest", ", ".join(f"{k}={v}" for k, v in prm.items())),
        ("Pembagian data", f"uji {int(config.TEST_SIZE * 100)}%, stratified, "
                           f"random_state={config.SPLIT_RANDOM_STATE}"),
        ("Tuning", f"GridSearchCV {config.GRID_CV_FOLDS}-fold, scoring=f1_macro"),
        ("Evaluasi stabilitas", f"Repeated Stratified K-Fold {config.REPEATED_CV}"),
    ], columns=["Parameter", "Nilai"]), hide_index=True, width="stretch")
    if st.button("Muat ulang hasil notebook", icon=":material/refresh:"):
        ui.clear_pipeline_cache()
        db.log(actor, "Muat ulang hasil notebook")
        st.rerun()


def _tab_ekspor() -> None:
    p = ui.get_pipeline()
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
    p = ui.get_pipeline()

    ok = p.all_checks_ok
    ui.market_header(
        "Data & Model",
        f"Sumber data screener untuk seluruh pengguna · {ui.esc(ds.label)}",
        [("Emiten", str(len(p.table)), None),
         ("Cluster", str(p.k), None),
         ("Verifikasi", "Lolos" if ok else "Gagal", "#16A34A" if ok else "#DC2626"),
         ("Riwayat impor", str(len(db.list_datasets())), None)],
    )
    st.write("")

    t1, t2, t3, t4 = st.tabs([":material/upload: Impor", ":material/history: Riwayat",
                              ":material/tune: Parameter", ":material/download: Ekspor"])
    with t1:
        _tab_impor(actor)
    with t2:
        _tab_riwayat(actor, ds)
    with t3:
        _tab_parameter(actor)
    with t4:
        _tab_ekspor()
