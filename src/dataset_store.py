"""
src/dataset_store.py
Pengelolaan "set hasil" notebook yang aktif untuk seluruh pengguna.

Satu set hasil = satu folder berisi berkas ekspor notebook (hasil_clustering.xlsx,
model_kmeans.joblib, model_random_forest.joblib, dan berkas .csv opsional)
ditambah dataset mentah (opsional). Set bawaan ada di config.MODEL_DIR. Admin
dapat mengimpor set baru (misalnya setelah notebook dijalankan pada data bulan
berikutnya); berkasnya disimpan di data/uploads/<waktu>/ dan riwayatnya dicatat
di tabel `datasets` (kolom stored_path berisi path folder).
"""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import config
from src import db, pipeline

KEY_ACTIVE = "active_dataset_id"


@dataclass
class ActiveSet:
    id: int | None          # None = set bawaan (folder model/)
    path: Path
    label: str
    uploaded_by: str | None = None
    uploaded_at: str | None = None

    @property
    def is_default(self) -> bool:
        return self.id is None

    @property
    def version(self) -> float:
        """Waktu modifikasi terbaru di folder, dipakai sebagai bagian kunci cache."""
        files = list(self.path.glob("*")) if self.path.is_dir() else []
        if self.is_default and config.DEFAULT_RAW_PATH.exists():
            files.append(config.DEFAULT_RAW_PATH)
        return max((f.stat().st_mtime for f in files), default=0.0)


def active() -> ActiveSet:
    raw = db.get_setting(KEY_ACTIVE)
    if raw:
        row = db.get_dataset(int(raw))
        if row and Path(row["stored_path"]).is_dir():
            return ActiveSet(id=row["id"], path=Path(row["stored_path"]),
                             label=row["filename"], uploaded_by=row["uploaded_by"],
                             uploaded_at=row["uploaded_at"])
    return ActiveSet(id=None, path=config.MODEL_DIR, label="Bawaan (output_revisi)")


def save_upload(files: list[tuple[str, bytes]], label: str, actor: str) -> int:
    """
    Menyimpan berkas ke folder baru, lalu memuatnya dengan pipeline.load untuk
    memastikan set hasil valid. Folder dihapus kembali bila gagal dimuat.
    Melempar pipeline.ArtifactError atau galat pemuatan model.
    """
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = config.UPLOAD_DIR / stamp
    folder.mkdir(parents=True, exist_ok=True)
    try:
        for name, data in files:
            safe = re.sub(r"[^A-Za-z0-9 ._-]+", "_", Path(name).name)
            (folder / safe).write_bytes(data)
        p = pipeline.load(folder)
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    label = label.strip() or f"Impor {stamp}"
    ds_id = db.add_dataset(label, str(folder), len(p.table), actor)
    db.log(actor, "Impor hasil notebook", f"{label} ({len(p.table)} saham)")
    return ds_id


def activate(dataset_id: int | None, actor: str) -> None:
    db.set_setting(KEY_ACTIVE, str(dataset_id) if dataset_id else None)
    label = db.get_dataset(dataset_id)["filename"] if dataset_id else "set bawaan"
    db.log(actor, "Aktifkan set hasil", label)


def remove(dataset_id: int, actor: str) -> None:
    row = db.get_dataset(dataset_id)
    if not row:
        return
    if active().id == dataset_id:
        db.set_setting(KEY_ACTIVE, None)
    folder = Path(row["stored_path"]).resolve()
    # hanya hapus folder di dalam data/uploads/, jangan pernah folder lain
    if config.UPLOAD_DIR.resolve() in folder.parents:
        shutil.rmtree(folder, ignore_errors=True)
    db.delete_dataset(dataset_id)
    db.log(actor, "Hapus set hasil", row["filename"])
