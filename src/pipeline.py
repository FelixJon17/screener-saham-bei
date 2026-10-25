"""
src/pipeline.py
Menghitung seluruh hasil langsung dari dataset dan merangkainya menjadi
PipelineOutput.

Dataset (Kode Saham, Sektor, PER, PBV, ROE, DER) diproses dengan prosedur
notebook lewat src/trainer.py, tanpa berkas hasil perantara (Excel/joblib).
Seluruh halaman aplikasi mengambil angka dari objek yang sama, sehingga angka
di Beranda, Detail Saham, dan Evaluasi Model berasal dari model yang sama.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

import config
from src import classification, clustering, data_loader, preprocessing, trainer
from src.winsorizer import lower_for


class ArtifactError(ValueError):
    """Dataset tidak dapat diproses."""


@dataclass
class PipelineOutput:
    source: Path | None             # berkas dataset yang dihitung
    raw: pd.DataFrame | None
    raw_summary: dict
    pre: preprocessing.PreprocessResult | None
    k_eval: pd.DataFrame
    k_reco: dict
    clu: clustering.ClusterResult
    cls: classification.ClassificationResult
    table: pd.DataFrame
    sector_summary: pd.DataFrame
    sector_stats: pd.DataFrame | None
    checks: list[dict] = field(default_factory=list)
    data_mode: str = config.DATA_POSITIF        # konfigurasi data perhitungan
    sektor_dibuang: list[str] = field(default_factory=list)

    @property
    def data_label(self) -> str:
        return config.DATA_MODES.get(self.data_mode, self.data_mode)

    @property
    def k(self) -> int:
        return int(self.clu.model.n_clusters)

    @property
    def all_checks_ok(self) -> bool:
        return all(c["Status"] != "Gagal" for c in self.checks)


# --------------------------------------------------------------------------
# Tabel turunan
# --------------------------------------------------------------------------
def _build_table(clu: clustering.ClusterResult) -> pd.DataFrame:
    cols = [config.COL_KODE, config.COL_SEKTOR, config.COL_PER, config.COL_PBV,
            config.COL_ROE, config.COL_DER, *clustering.ZCOLS,
            "Cluster", "Kategori", "Silhouette Sampel"]
    out = clu.data[cols].rename(columns={clustering.ZCOLS[0]: "Z-PER (sektor)",
                                         clustering.ZCOLS[1]: "Z-PBV (sektor)"})
    return out.sort_values(config.COL_KODE).reset_index(drop=True)


def _sector_summary(d: pd.DataFrame) -> pd.DataFrame:
    agg = d.groupby(config.COL_SEKTOR).agg(
        Jumlah=(config.COL_KODE, "count"),
        PER_rata=(config.COL_PER, "mean"), PER_median=(config.COL_PER, "median"),
        PBV_rata=(config.COL_PBV, "mean"), PBV_median=(config.COL_PBV, "median"),
        ROE_median=(config.COL_ROE, "median"), DER_median=(config.COL_DER, "median"),
    )
    share = (d.pivot_table(index=config.COL_SEKTOR, columns="Kategori",
                           values=config.COL_KODE, aggfunc="count")
             .fillna(0).astype(int))
    return agg.join(share, how="left").fillna(0).round(4)


# --------------------------------------------------------------------------
# Verifikasi konsistensi
# --------------------------------------------------------------------------
def _check(nama: str, ok: bool | None, detail: str) -> dict:
    status = "—" if ok is None else ("Lolos" if ok else "Gagal")
    return {"Pemeriksaan": nama, "Status": status, "Detail": detail}


def verify(table: pd.DataFrame, km, pre: preprocessing.PreprocessResult) -> list[dict]:
    """Pemeriksaan konsistensi hasil perhitungan."""
    out = []
    X = table[clustering.ZCOLS].to_numpy(dtype=float)
    n_beda = int((km.predict(X) != table["Cluster"].to_numpy()).sum())
    out.append(_check("Model K-Means memprediksi ulang label yang sama",
                      n_beda == 0, f"{len(table) - n_beda} dari {len(table)} saham cocok"))

    labels = set(table["Kategori"].unique())
    asing = labels - set(config.LABEL_ORDER)
    out.append(_check("Nama label sesuai aturan pelabelan 3.1.6", not asing,
                      ", ".join(sorted(labels)) if not asing
                      else f"label tidak dikenal: {', '.join(sorted(asing))}"))

    z = pre.data.groupby(config.COL_SEKTOR)[["PER_z", "PBV_z"]]
    dev = max(float(z.mean().abs().max().max()), float((z.std(ddof=config.ZSCORE_DDOF) - 1)
                                                       .abs().max().max()))
    out.append(_check("Z-score tiap sektor: rata-rata 0 dan simpangan baku 1", dev < 1e-6,
                      f"selisih maksimum {dev:.2e}"))

    terkecil = int(table["Kategori"].value_counts().min())
    out.append(_check("Setiap kategori cukup untuk split stratified", terkecil >= 2,
                      f"kategori terkecil {terkecil} saham"))

    kosong = int(table[config.REQUIRED_COLUMNS].isna().any(axis=1).sum())
    out.append(_check("Tidak ada nilai kosong pada data yang dikelompokkan", kosong == 0,
                      f"{kosong} baris kosong"))
    return out


# --------------------------------------------------------------------------
# Hitung
# --------------------------------------------------------------------------
def build(df: pd.DataFrame, data_mode: str = config.DATA_POSITIF,
          source: Path | None = None) -> PipelineOutput:
    """df: enam kolom wajib. Menjalankan prosedur notebook dan merangkai hasilnya."""
    try:
        h = trainer.compute(df, data_mode)
    except trainer.TrainError as e:
        raise ArtifactError(str(e)) from e

    tbl = h.table.rename(columns={"PER_z": clustering.ZCOLS[0], "PBV_z": clustering.ZCOLS[1],
                                  "cluster": "Cluster", "label": "Kategori"})
    summary = data_loader.describe_raw(df)
    summary["sektor_anomali_setelah_koreksi"] = sorted(
        set(h.pre.data[config.COL_SEKTOR]) - set(config.IDX_IC_SECTORS))
    summary["berkas"] = source.name if source else None

    clu = clustering.build(tbl, h.kmeans)
    cls = classification.build(clu.data, h.rf, lower_for(data_mode))
    k_eval = clustering.evaluasi_k(h.k_eval)

    return PipelineOutput(
        source=source, raw=df, raw_summary=summary, pre=h.pre,
        k_eval=k_eval, k_reco=clustering.metric_recommendations(k_eval, h.kmeans.n_clusters),
        clu=clu, cls=cls, table=_build_table(clu),
        sector_summary=_sector_summary(clu.data), sector_stats=h.pre.sector_stats,
        checks=verify(tbl, h.kmeans, h.pre), data_mode=data_mode,
        sektor_dibuang=h.sektor_dibuang,
    )


def from_file(path: str | Path, data_mode: str = config.DATA_POSITIF) -> PipelineOutput:
    """Membaca dataset .xlsx/.csv (enam kolom wajib) lalu menghitung hasilnya."""
    path = Path(path)
    if not path.exists():
        raise ArtifactError(f"Dataset tidak ditemukan: {path}")
    return build(data_loader.load_dataset(path), data_mode, path)
