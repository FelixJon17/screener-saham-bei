"""
views/beranda.py -- Halaman Beranda/Screener (Gambar L6.2)

Spesifikasi Rancangan butir 1: tabel seluruh saham, tampilan visual
clustering, dan klasifikasi label (undervalue, fair value, overvalue),
dilengkapi filter berdasarkan sektor dan kategori valuasi.

Tata letak mengikuti wireframe: kartu ringkasan hasil clustering, panel
filter (sektor, kategori cluster, rentang PER, rentang PBV), tabel hasil
screening, unduh CSV beserta catatan, lalu visual clustering. Baris tabel
atau titik grafik dapat diklik untuk membuka Detail Saham.

Pengguna yang sudah masuk dapat mengunggah dataset sendiri (Kode Saham,
Sektor, PER, PBV, ROE, DER). Dataset diproses dengan prosedur notebook
(src/trainer.py) dan seluruh halaman memakai hasilnya, hanya untuk pengguna itu.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

import config
from src import auth, data_loader, dataset_store, pipeline, trainer, ui

KEY_PICK = "beranda_pick"
SEMUA = "Semua"


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


def _hero(p, df: pd.DataFrame) -> None:
    """Banner judul halaman."""
    st.html(
        "<div class='scr-hero slim'><div class='txt'>"
        "<div class='eyebrow'>IDX Equity Screener</div>"
        "<div class='ttl'>Beranda</div>"
        "<div class='sub'>Pengelompokan valuasi saham relatif terhadap sektor</div></div>"
        f"<div class='chips'><span>K-Means K = {p.k}</span><span>PER · PBV</span>"
        "<span>Random Forest · ROE · DER</span></div></div>"
    )


TEMPLATE = pd.DataFrame(
    [["BBCA", "Financials", 23.1, 4.6, 21.2, 0.0],
     ["TLKM", "Infrastructures", 12.4, 2.1, 16.8, 0.9],
     ["UNVR", "Consumer Non-Cyclicals", 25.3, 30.5, 120.4, 3.1]],
    columns=config.REQUIRED_COLUMNS)


@st.dialog("Unggah dataset Anda", width="large", icon=":material/upload_file:")
def _dialog_unggah(username: str) -> None:
    st.caption("Excel/CSV dengan enam kolom berikut. Hasilnya dipakai di seluruh halaman, "
               "hanya untuk akun Anda.")
    st.html("<div class='req-cols'>" + "".join(f"<span>{ui.esc(c)}</span>"
                                               for c in config.REQUIRED_COLUMNS) + "</div>")
    f = st.file_uploader("Berkas", type=["xlsx", "csv"], label_visibility="collapsed",
                         key="unggah_berkas")
    if not f:
        st.download_button("Unduh template", TEMPLATE.to_csv(index=False).encode("utf-8"),
                           file_name="template_dataset.csv", mime="text/csv",
                           icon=":material/download:", type="tertiary")
        return
    try:
        raw = trainer.read_file(f.getvalue(), f.name)
    except trainer.TrainError as e:
        st.error(str(e), icon=":material/error:")
        return
    except Exception as e:  # format rusak, lembar kosong, dsb.
        st.error(f"Berkas tidak dapat dibaca: {e}", icon=":material/error:")
        return

    guess = trainer.guess_columns(raw.columns)
    belum = [k for k, v in guess.items() if v is None]
    opsi = [None, *raw.columns]
    with st.expander(f"Pemetaan kolom · {6 - len(belum)}/6 terdeteksi", expanded=bool(belum),
                     icon=":material/swap_horiz:"):
        cols = st.columns(3)
        mapping = {
            c: cols[i % 3].selectbox(
                c, opsi, index=opsi.index(guess[c]) if guess[c] is not None else 0,
                format_func=lambda v: "— pilih kolom —" if v is None else str(v),
                key=f"unggah_map_{c}")
            for i, c in enumerate(config.REQUIRED_COLUMNS)
        }
    ui.table(raw.head(5), hide_index=True, width="stretch", height=150)
    mode = dataset_store.data_mode()
    st.caption(f"{len(raw)} baris · data perhitungan: {config.DATA_MODES[mode]}")

    a, b = st.columns([2, 1], vertical_alignment="bottom")
    nama = a.text_input("Nama dataset", value=Path(f.name).stem[:60], max_chars=60)
    if b.button("Proses & gunakan", type="primary", icon=":material/play_arrow:",
                width="stretch"):
        try:
            df = trainer.prepare(raw, mapping)
            with st.spinner("Menjalankan K-Means dan Random Forest…"):
                dataset_store.save_personal(username, df, nama.strip() or Path(f.name).stem,
                                            f.name)
        except (trainer.TrainError, data_loader.SchemaError, pipeline.ArtifactError) as e:
            st.error(str(e), icon=":material/error:")
            return
        st.session_state.pop(KEY_PICK, None)
        st.rerun()


def _kembali(username: str) -> None:
    dataset_store.clear_personal(username)
    st.session_state.pop(KEY_PICK, None)


def _bar_dataset(p) -> None:
    """Dataset yang sedang dipakai + tombol unggah / kembali ke data penelitian."""
    u = auth.current_user()
    ds = ui.active_set()
    with st.container(border=True, key="dataset_bar"):
        a, b, c = st.columns([3.2, 1.2, 1.4], vertical_alignment="center")
        if ds.pribadi:
            buang = p.sektor_dibuang
            a.html("<div class='ds-bar'><span class='ic pri'>⇪</span><div>"
                   f"<b>Dataset Anda: {ui.esc(ds.label)}</b><small>{len(p.table)} saham · "
                   f"diunggah {ui.esc(ds.uploaded_at or '')}"
                   + (f" · sektor tunggal dibuang: {ui.esc(', '.join(buang))}" if buang else "")
                   + "</small></div></div>")
            c.button("Kembali ke data penelitian", icon=":material/restart_alt:",
                     on_click=_kembali, args=(u["username"],), width="stretch")
        else:
            a.html("<div class='ds-bar'><span class='ic'>▦</span><div>"
                   f"<b>{'Data penelitian' if ds.is_default else 'Dataset'}: "
                   f"{ui.esc(ds.label)}</b>"
                   f"<small>{len(p.table)} saham · {ui.esc(p.data_label)}</small></div></div>")
        if (b if ds.pribadi else c).button("Unggah dataset", icon=":material/upload:", type="primary",
                    width="stretch", help=None if u else "Masuk untuk mengunggah dataset"):
            if not u:
                ui.goto("masuk")
            _dialog_unggah(u["username"])


def _ringkasan(df: pd.DataFrame) -> None:
    """Kartu Total Saham, Relatif Rendah, Relatif Sedang, Relatif Tinggi."""
    total = max(len(df), 1)
    ikon = {config.LABEL_LOW: "▼", config.LABEL_MID: "◆", config.LABEL_HIGH: "▲"}
    cards = [
        "<div class='kpi-card total' style='--c:var(--royal);--bg:rgba(27,44,193,.10)'>"
        "<div class='top'><span class='ic'>Σ</span><span class='lbl'>Total Saham</span></div>"
        f"<div class='val'>{len(df)} <small>emiten</small></div>"
        "<div class='bar'><span style='width:100%'></span></div>"
        f"<div class='ft'><span>{df[config.COL_SEKTOR].nunique()} sektor IDX-IC</span>"
        f"<span>median PER {ui.fmt_num(df[config.COL_PER].median())}</span></div></div>"
    ]
    for k in config.LABEL_ORDER:
        sub = df[df["Kategori"] == k]
        pct = len(sub) / total * 100
        c = ui.color_of(k)
        cards.append(
            f"<div class='kpi-card' style='--c:{c};--bg:{c}1F'>"
            f"<div class='top'><span class='ic'>{ikon[k]}</span>"
            f"<span class='lbl'>{ui.esc(ui.tiny(k))}</span>"
            f"<span class='op'>{ui.esc(config.LABEL_OPS[k])}</span></div>"
            f"<div class='val'>{len(sub)} <small>saham</small></div>"
            f"<div class='bar'><span style='width:{pct:.1f}%'></span></div>"
            f"<div class='ft'><span>{pct:.1f}% saham</span>".replace(".", ",")
            + f"<span>median PER {ui.fmt_num(sub[config.COL_PER].median())}</span></div></div>"
        )
    st.html(f"<div class='kpi-grid'>{''.join(cards)}</div>")


def _rentang(label: str, key: str) -> tuple[float | None, float | None]:
    st.caption(label)
    a, b = st.columns(2, gap="small")
    lo = a.number_input(f"{label} min", value=None, min_value=0.0, placeholder="Min",
                        key=f"{key}_min", label_visibility="collapsed")
    hi = b.number_input(f"{label} max", value=None, min_value=0.0, placeholder="Max",
                        key=f"{key}_max", label_visibility="collapsed")
    return lo, hi


FILTER_KEYS = {"f_sektor": SEMUA, "f_kategori": SEMUA, "f_per_min": None, "f_per_max": None,
               "f_pbv_min": None, "f_pbv_max": None}


def _reset_filter() -> None:
    for k, v in FILTER_KEYS.items():
        st.session_state[k] = v


def _panel_filter(df: pd.DataFrame) -> pd.DataFrame:
    aktif = sum(st.session_state.get(k, v) != v for k, v in FILTER_KEYS.items())
    with st.container(border=True, key="panel_filter"):
        a, b = st.columns([2.8, 1], vertical_alignment="center", gap="small")
        a.html(f"<div class='pf-head'><span class='ic'>⚲</span><b>Panel Filter</b>"
               + (f"<span class='n'>{aktif}</span>" if aktif else "") + "</div>")
        b.button("Reset", type="tertiary", on_click=_reset_filter, disabled=not aktif,
                 key="f_reset", width="stretch")
        sektor = st.selectbox("Sektor", [SEMUA] + sorted(df[config.COL_SEKTOR].unique()),
                              key="f_sektor")
        kat_opsi = [k for k in config.LABEL_ORDER if k in df["Kategori"].unique()]
        kategori = st.selectbox("Kategori cluster", [SEMUA] + kat_opsi, key="f_kategori",
                                format_func=lambda k: k if k == SEMUA else ui.short(k))
        per_lo, per_hi = _rentang("Rentang PER", "f_per")
        pbv_lo, pbv_hi = _rentang("Rentang PBV", "f_pbv")

    view = df
    if sektor != SEMUA:
        view = view[view[config.COL_SEKTOR] == sektor]
    if kategori != SEMUA:
        view = view[view["Kategori"] == kategori]
    for col, lo, hi in ((config.COL_PER, per_lo, per_hi), (config.COL_PBV, pbv_lo, pbv_hi)):
        if lo is not None:
            view = view[view[col] >= lo]
        if hi is not None:
            view = view[view[col] <= hi]
    return view


def _tabel(view: pd.DataFrame, total: int) -> None:
    with st.container(border=True, key="tabel_box"):
        a, b = st.columns([3, 1], vertical_alignment="center")
        a.html(f"<div class='tb-head'><b>Hasil Screening</b>"
               f"<span class='cnt'>{len(view)} / {total} saham</span></div>")
        b.caption("Klik baris untuk detail")
        t = view[[config.COL_KODE, config.COL_SEKTOR, config.COL_PER, config.COL_PBV,
                  config.COL_ROE, config.COL_DER, "Kategori"]].copy()
        t["Status"] = t.pop("Kategori").map(config.LABEL_OPS)
        warna = {config.LABEL_OPS[k]: ui.color_of(k) for k in config.LABEL_ORDER}
        gaya = (t.style
                .format(precision=2, subset=[config.COL_PER, config.COL_PBV, config.COL_ROE,
                                             config.COL_DER])
                .map(lambda v: f"background-color:{warna.get(v, '')}2E;color:{warna.get(v, '')}",
                     subset=["Status"]))
        ui.table(
            gaya, width="stretch", hide_index=True, height=430, selection_mode="single-row",
            key="tabel_saham", row_height=36,
            on_select=_pick_row("tabel_saham", view[config.COL_KODE].tolist()),
            column_config={
                config.COL_KODE: st.column_config.TextColumn("Kode Saham", pinned=True),
                config.COL_ROE: st.column_config.NumberColumn("ROE (%)"),
                "Status": st.column_config.TextColumn("Status", alignment="center",
                                                      width="small"),
            },
        )


def _pilihan(p, kode: str) -> None:
    """Baris ringkas untuk saham yang diklik: buka Detail Saham."""
    row = p.table[p.table[config.COL_KODE] == kode]
    if row.empty:
        return
    row = row.iloc[0]
    with st.container(border=True):
        a, b, c = st.columns([3.5, 1, 0.8], vertical_alignment="center")
        a.html(f"<div style='display:flex;gap:10px;align-items:center;flex-wrap:wrap'>"
               f"<b style='font-size:1.15rem'>{ui.esc(kode)}</b>{ui.badge_html(row['Kategori'])}"
               f"<span style='color:var(--muted)'>{ui.esc(row[config.COL_SEKTOR])} · "
               f"PER {ui.fmt_num(row[config.COL_PER])} · PBV {ui.fmt_num(row[config.COL_PBV])}"
               f"</span></div>")
        if b.button("Lihat detail", icon=":material/open_in_new:", type="primary",
                    width="stretch"):
            ui.goto("detail", kode_terpilih=kode)
        if c.button("Tutup", icon=":material/close:", width="stretch"):
            st.session_state.pop(KEY_PICK, None)
            st.rerun()


def _visual(view: pd.DataFrame) -> None:
    with st.container(border=True):
        a, b = st.columns([2, 1.3], vertical_alignment="center")
        a.html(f"<div class='tb-head'><b>Plot Clustering</b>"
               f"<span class='cnt'>{len(view)} saham</span></div>")
        sumbu = b.segmented_control(
            "Sumbu", ["Z-score sektor", "PER & PBV asli"], default="Z-score sektor",
            label_visibility="collapsed", key="sumbu_visual") or "Z-score sektor"
        if sumbu == "Z-score sektor":
            fig = ui.scatter_cluster(view, "Z-PER (sektor)", "Z-PBV (sektor)",
                                     highlight=st.session_state.get(KEY_PICK))
            ui.zero_lines(fig)
            fig.update_xaxes(title="Z-PER relatif sektor")
            fig.update_yaxes(title="Z-PBV relatif sektor")
        else:
            fig = ui.scatter_cluster(view, config.COL_PER, config.COL_PBV, log=True,
                                     highlight=st.session_state.get(KEY_PICK))
            fig.update_xaxes(title="PER (skala log)")
            fig.update_yaxes(title="PBV (skala log)")
        st.plotly_chart(fig, width="stretch", selection_mode="points", key="peta_valuasi",
                        on_select=lambda: _pick_point("peta_valuasi"))
        st.caption("Z = 0: setara rata-rata sektor · ±1: satu simpangan baku")


def render() -> None:
    p = ui.get_pipeline()
    df = p.table

    _hero(p, df)
    st.write("")
    _bar_dataset(p)
    _ringkasan(df)
    st.write("")

    kiri, kanan = st.columns([1, 3.3], gap="medium")
    with kiri:
        view = _panel_filter(df)
    with kanan:
        if view.empty:
            st.warning("Tidak ada saham yang cocok. Longgarkan filter.",
                       icon=":material/filter_alt_off:")
        else:
            _tabel(view, len(df))
        a, b = st.columns([1, 3], vertical_alignment="center")
        a.download_button("Unduh Hasil (CSV)", view.to_csv(index=False).encode("utf-8"),
                          file_name="hasil_screener.csv", mime="text/csv",
                          icon=":material/download:", width="stretch",
                          disabled=view.empty)
        b.caption("Label valuasi bersifat operasional, bukan rekomendasi jual atau beli.")
        if note := ui.missing_note(p):
            st.caption(f":material/info: {note}")

    if kode := st.session_state.get(KEY_PICK):
        _pilihan(p, kode)

    if not view.empty:
        _visual(view)
