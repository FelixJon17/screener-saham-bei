"""
src/pipeline.py
Memuat satu set hasil notebook dan merangkainya menjadi PipelineOutput.

Satu "set hasil" adalah folder berisi berkas ekspor notebook (lihat
config.ARTIFACT_NAMES) dan, bila ada, dataset mentah .xlsx/.csv. Seluruh
halaman aplikasi mengambil angka dari objek yang sama, sehingga angka di
Beranda, Detail Saham, dan Evaluasi Model dijamin berasal dari model yang
sama dengan yang dilaporkan di notebook.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

import config
from src import classification, clustering, data_loader, preprocessing
from src.winsorizer import register_for_unpickle


class ArtifactError(ValueError):
    """Set hasil tidak lengkap atau tidak konsisten."""


@dataclass
class PipelineOutput:
    folder: Path
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

    @property
    def k(self) -> int:
        return int(self.clu.model.n_clusters)

    @property
    def all_checks_ok(self) -> bool:
        return all(c["Status"] != "Gagal" for c in self.checks)


# --------------------------------------------------------------------------
# Berkas
# --------------------------------------------------------------------------
def find_raw_dataset(folder: Path) -> Path | None:
    """Berkas .xlsx/.csv apa pun di folder yang bukan berkas ekspor notebook."""
    for f in sorted(folder.iterdir()):
        if (f.suffix.lower() in (".xlsx", ".csv") and f.name not in config.ARTIFACT_NAMES
                and not f.name.startswith("~$")):
            return f
    # set bawaan: dataset mentah berada di samping notebook, bukan di output_revisi/
    if folder.resolve() == config.MODEL_DIR.resolve() and config.DEFAULT_RAW_PATH.exists():
        return config.DEFAULT_RAW_PATH
    return None


def missing_artifacts(folder: Path) -> list[str]:
    return [n for n in config.ARTIFACTS_REQUIRED if not (folder / n).exists()]


def _read_optional_csv(path: Path) -> pd.DataFrame | None:
    return pd.read_csv(path) if path.exists() else None


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


def verify(table: pd.DataFrame, km, pre: preprocessing.PreprocessResult | None) -> list[dict]:
    out = []
    X = table[clustering.ZCOLS].to_numpy(dtype=float)
    pred = km.predict(X)
    n_beda = int((pred != table["Cluster"].to_numpy()).sum())
    out.append(_check("Model K-Means menghasilkan label yang sama dengan tabel notebook",
                      n_beda == 0, f"{len(table) - n_beda} dari {len(table)} saham cocok"))

    labels = set(table["Kategori"].unique())
    asing = labels - set(config.LABEL_ORDER)
    out.append(_check("Nama label sesuai notebook", not asing,
                      ", ".join(sorted(labels)) if not asing
                      else f"label tidak dikenal: {', '.join(sorted(asing))}"))

    if pre is None:
        out.append(_check("Rekonstruksi dari dataset mentah", None,
                          "Dataset mentah tidak disertakan dalam set hasil"))
        return out

    a = pre.data.set_index(config.COL_KODE)
    b = table.set_index(config.COL_KODE)
    sama = set(a.index) == set(b.index)
    out.append(_check("Saham hasil pra-pemrosesan = saham di tabel notebook", sama,
                      f"{len(a)} vs {len(b)} saham" + ("" if sama else
                      f"; selisih {len(set(a.index) ^ set(b.index))} kode")))
    if sama:
        b = b.loc[a.index]
        dz = float(np.nanmax(np.abs(a[["PER_z", "PBV_z"]].to_numpy()
                                    - b[clustering.ZCOLS].to_numpy())))
        out.append(_check("Z-score rekonstruksi = Z-score notebook", dz < 1e-6,
                          f"selisih maksimum {dz:.2e}"))
        ds = (a[config.COL_SEKTOR] != b[config.COL_SEKTOR]).sum()
        out.append(_check("Sektor setelah koreksi sama", ds == 0, f"{ds} saham berbeda"))
    return out


# --------------------------------------------------------------------------
# Muat
# --------------------------------------------------------------------------
def load(folder: str | Path) -> PipelineOutput:
    folder = Path(folder)
    if not folder.is_dir():
        raise ArtifactError(f"Folder hasil tidak ditemukan: {folder}")
    if miss := missing_artifacts(folder):
        raise ArtifactError("Berkas hasil notebook belum lengkap: " + ", ".join(miss))

    register_for_unpickle()
    km = joblib.load(folder / config.ART_KMEANS)
    rf = joblib.load(folder / config.ART_RF)

    res = data_loader.load_result_table(folder / config.ART_TABLE)
    tbl = res.rename(columns={config.COL_Z_PER: clustering.ZCOLS[0],
                              config.COL_Z_PBV: clustering.ZCOLS[1],
                              config.COL_CLUSTER: "Cluster", config.COL_LABEL: "Kategori"})

    raw_path = find_raw_dataset(folder)
    raw = data_loader.load_dataset(raw_path) if raw_path else None
    pre = preprocessing.run(raw) if raw is not None else None
    if raw is not None:
        summary = data_loader.describe_raw(raw)
        summary["sektor_anomali_setelah_koreksi"] = sorted(
            set(pre.data[config.COL_SEKTOR]) - set(config.IDX_IC_SECTORS))
        summary["berkas"] = raw_path.name
    else:
        summary = {"n_baris": len(tbl), "n_saham_unik": tbl[config.COL_KODE].nunique(),
                   "n_duplikat_kode": 0, "n_sektor": tbl[config.COL_SEKTOR].nunique(),
                   "sektor_anomali": [], "sektor_anomali_setelah_koreksi": [], "berkas": None}

    clu = clustering.build(tbl, km)
    cls = classification.build(clu.data, rf, _read_optional_csv(folder / config.ART_RF_CV))
    k_eval = clustering.evaluasi_k(_read_optional_csv(folder / config.ART_KEVAL))

    sec_stats = _read_optional_csv(folder / config.ART_SECTOR)
    if sec_stats is not None:
        sec_stats = sec_stats.set_index(sec_stats.columns[0])
    elif pre is not None:
        sec_stats = pre.sector_stats

    return PipelineOutput(
        folder=folder, raw=raw, raw_summary=summary, pre=pre,
        k_eval=k_eval, k_reco=clustering.metric_recommendations(k_eval, km.n_clusters),
        clu=clu, cls=cls, table=_build_table(clu),
        sector_summary=_sector_summary(clu.data), sector_stats=sec_stats,
        checks=verify(tbl, km, pre),
    )
