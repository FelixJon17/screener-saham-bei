"""
src/dataset_store.py
Dataset yang dipakai aplikasi. Seluruh hasil dihitung langsung dari dataset
(src/pipeline.py); tidak ada berkas hasil perantara.

Urutan prioritas dataset untuk seorang pengguna:
  1. Dataset pribadi yang ia unggah di Beranda (data/pribadi/<username>/),
     hanya dipakai olehnya. Informasinya di tabel settings, kunci
     "pribadi:<username>".
  2. Dataset global yang diunggah admin di Data & Model (data/uploads/), bila
     ada yang diaktifkan. Riwayatnya di tabel `datasets`.
  3. Dataset penelitian bawaan (config.DEFAULT_RAW_PATH).

Konfigurasi data perhitungan ("positif" / "semua") diatur admin dan berlaku
untuk semua dataset.
"""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

import config
from src import db, pipeline

KEY_ACTIVE = "active_dataset_id"
KEY_DATA_MODE = "data_mode"          # "positif" | "semua"
PRIBADI_DIR = config.DATA_DIR / "pribadi"
NAMA_BERKAS = "dataset.csv"


@dataclass
class ActiveSet:
    id: int | None          # None = dataset penelitian bawaan atau dataset pribadi
    path: Path              # berkas dataset (.xlsx/.csv)
    label: str
    uploaded_by: str | None = None
    uploaded_at: str | None = None
    pribadi: bool = False   # dataset unggahan pengguna (hanya untuk dirinya)

    @property
    def is_default(self) -> bool:
        return self.id is None and not self.pribadi

    @property
    def version(self) -> float:
        """Waktu modifikasi berkas, bagian kunci cache."""
        return self.path.stat().st_mtime if self.path.exists() else 0.0


def active(username: str | None = None) -> ActiveSet:
    """Dataset yang dipakai; dataset pribadi `username` (bila ada) didahulukan."""
    if username and (info := personal(username)):
        return ActiveSet(id=None, path=personal_path(username), label=info["nama"],
                         uploaded_by=username, uploaded_at=info["waktu"], pribadi=True)
    raw = db.get_setting(KEY_ACTIVE)
    if raw:
        row = db.get_dataset(int(raw))
        if row and Path(row["stored_path"]).is_file():
            return ActiveSet(id=row["id"], path=Path(row["stored_path"]),
                             label=row["filename"], uploaded_by=row["uploaded_by"],
                             uploaded_at=row["uploaded_at"])
    path = config.DEFAULT_RAW_PATH
    return ActiveSet(id=None, path=path, label=path.stem)


# --------------------------------------------------------------------------
# Konfigurasi data perhitungan
# --------------------------------------------------------------------------
def data_mode() -> str:
    mode = db.get_setting(KEY_DATA_MODE) or config.DATA_POSITIF
    return mode if mode in config.DATA_MODES else config.DATA_POSITIF


def set_data_mode(mode: str, actor: str) -> None:
    db.set_setting(KEY_DATA_MODE, mode)
    db.log(actor, "Ganti data perhitungan", config.DATA_MODES.get(mode, mode))


def _validate(df: pd.DataFrame) -> int:
    """Menjalankan perhitungan sekali agar dataset yang disimpan pasti dapat diproses."""
    return len(pipeline.build(df, data_mode()).table)


# --------------------------------------------------------------------------
# Dataset pribadi pengguna
# --------------------------------------------------------------------------
def personal_path(username: str) -> Path:
    return PRIBADI_DIR / re.sub(r"[^a-z0-9_.]+", "_", username.lower()) / NAMA_BERKAS


def personal(username: str) -> dict | None:
    """Info dataset pribadi pengguna, atau None bila belum ada/berkasnya hilang."""
    raw = db.get_setting(f"pribadi:{username}")
    if not raw or not personal_path(username).is_file():
        return None
    return json.loads(raw)


def save_personal(username: str, df: pd.DataFrame, nama: str, berkas: str) -> dict:
    """Memvalidasi lalu menyimpan dataset pribadi. Melempar pipeline.ArtifactError."""
    n = _validate(df)
    path = personal_path(username)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    info = {"nama": nama, "berkas": berkas, "jumlah_saham": n,
            "waktu": datetime.now().strftime("%Y-%m-%d %H:%M")}
    db.set_setting(f"pribadi:{username}", json.dumps(info))
    db.log(username, "Unggah dataset pribadi", f"{nama} ({n} saham)")
    return info


def clear_personal(username: str) -> None:
    db.set_setting(f"pribadi:{username}", None)
    folder = personal_path(username).parent.resolve()
    if PRIBADI_DIR.resolve() in folder.parents:
        shutil.rmtree(folder, ignore_errors=True)
    db.log(username, "Kembali ke data penelitian")


# --------------------------------------------------------------------------
# Dataset global (admin)
# --------------------------------------------------------------------------
def save_upload(df: pd.DataFrame, label: str, berkas: str, actor: str) -> int:
    """Memvalidasi lalu menyimpan dataset global. Melempar pipeline.ArtifactError."""
    n = _validate(df)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = config.UPLOAD_DIR / stamp / NAMA_BERKAS
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    label = label.strip() or Path(berkas).stem
    ds_id = db.add_dataset(label, str(path), n, actor)
    db.log(actor, "Unggah dataset global", f"{label} ({n} saham)")
    return ds_id


def activate(dataset_id: int | None, actor: str) -> None:
    db.set_setting(KEY_ACTIVE, str(dataset_id) if dataset_id else None)
    label = db.get_dataset(dataset_id)["filename"] if dataset_id else "dataset penelitian"
    db.log(actor, "Aktifkan dataset", label)


def remove(dataset_id: int, actor: str) -> None:
    row = db.get_dataset(dataset_id)
    if not row:
        return
    if active().id == dataset_id:
        db.set_setting(KEY_ACTIVE, None)
    folder = Path(row["stored_path"]).parent.resolve()
    # hanya hapus folder di dalam data/uploads/, jangan pernah folder lain
    if config.UPLOAD_DIR.resolve() in folder.parents:
        shutil.rmtree(folder, ignore_errors=True)
    db.delete_dataset(dataset_id)
    db.log(actor, "Hapus dataset", row["filename"])
