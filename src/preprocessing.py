"""
src/preprocessing.py
Pra-pemrosesan sesuai notebook (3.1.2–3.1.3): koreksi sektor, buang nilai
kosong, (data positif) buang PER/PBV <= 0, winsorizing, lalu Z-score PER dan
PBV per sektor. Dipakai src/trainer.py dan ditampilkan sebagai jejak
pra-pemrosesan di halaman admin.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

import config


@dataclass
class PreprocessResult:
    data: pd.DataFrame                      # 627 baris setelah pembersihan, dengan Z-score
    log: list[dict] = field(default_factory=list)
    winsor_caps: dict = field(default_factory=dict)
    sector_stats: pd.DataFrame | None = None
    dropped: dict = field(default_factory=dict)   # nama tahap -> DataFrame yang dibuang
    sector_fixed: pd.DataFrame | None = None

    def log_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.log)


def _record(res: PreprocessResult, tahap: str, sebelum: int, sesudah: int, ket: str) -> None:
    res.log.append({"Tahap": tahap, "Baris sebelum": sebelum, "Baris sesudah": sesudah,
                    "Dibuang": sebelum - sesudah, "Keterangan": ket})


def fix_sectors(df: pd.DataFrame, res: PreprocessResult) -> pd.DataFrame:
    """Sel 2 notebook: dua saham dengan nilai sektor di luar IDX-IC dikoreksi."""
    out = df.copy()
    mask = out[config.COL_KODE].isin(config.SECTOR_FIXES)
    before = out.loc[mask, [config.COL_KODE, config.COL_SEKTOR]].copy()
    for kode, sektor in config.SECTOR_FIXES.items():
        out.loc[out[config.COL_KODE] == kode, config.COL_SEKTOR] = sektor
    before["Sektor baru"] = before[config.COL_KODE].map(config.SECTOR_FIXES)
    res.sector_fixed = before.rename(columns={config.COL_SEKTOR: "Sektor lama"})
    _record(res, "Koreksi sektor", len(df), len(out),
            ", ".join(f"{k} → {v}" for k, v in config.SECTOR_FIXES.items()))
    return out


def drop_missing(df: pd.DataFrame, res: PreprocessResult) -> pd.DataFrame:
    cols = [config.COL_PER, config.COL_PBV, config.COL_ROE, config.COL_DER]
    mask = df[cols].isna().any(axis=1)
    res.dropped["missing_value"] = df[mask].copy()
    out = df[~mask].reset_index(drop=True)
    _record(res, "Penghapusan missing value", len(df), len(out),
            "Nilai kosong pada PER/PBV/ROE/DER")
    return out


def drop_non_positive(df: pd.DataFrame, res: PreprocessResult) -> pd.DataFrame:
    mask = (df[config.COL_PER] <= 0) | (df[config.COL_PBV] <= 0)
    res.dropped["per_pbv_non_positif"] = df[mask].copy()
    out = df[~mask].reset_index(drop=True)
    _record(res, "Penghapusan PER ≤ 0 atau PBV ≤ 0", len(df), len(out),
            "Rasio valuasi non-positif")
    return out


def winsorize(df: pd.DataFrame, res: PreprocessResult, lower: int | None = None) -> pd.DataFrame:
    """
    Sel winsorizing notebook: P95 market-wide (np.percentile, interpolasi linear).
    lower diisi (mis. 5) untuk konfigurasi data "semua": winsorizing dua sisi.
    """
    out = df.copy()
    for col in config.CLUSTER_FEATURES:
        cap = float(np.percentile(out[col], config.WINSOR_PERCENTILE))
        floor = float(np.percentile(out[col], lower)) if lower else -np.inf
        res.winsor_caps[col] = {"persentil": config.WINSOR_PERCENTILE, "batas_atas": cap,
                                "n_dipotong": int(((out[col] > cap) | (out[col] < floor)).sum())}
        if lower:
            res.winsor_caps[col]["batas_bawah"] = floor
        out[f"{col}_w"] = np.clip(out[col], floor, cap)
    total = sum(v["n_dipotong"] for v in res.winsor_caps.values())
    nama = (f"Winsorizing P{lower}–P{config.WINSOR_PERCENTILE}" if lower
            else f"Winsorizing P{config.WINSOR_PERCENTILE}")
    _record(res, f"{nama} (PER, PBV)", len(df), len(out),
            f"{total} nilai dipotong; tidak ada baris dihapus")
    return out


def sector_zscore(df: pd.DataFrame, res: PreprocessResult) -> pd.DataFrame:
    """Sel 7–8 notebook: Z-score per sektor, ddof=1."""
    out = df.copy()
    g = out.groupby(config.COL_SEKTOR)
    for col in config.CLUSTER_FEATURES:
        out[f"{col}_z"] = g[f"{col}_w"].transform(
            lambda s: (s - s.mean()) / s.std(ddof=config.ZSCORE_DDOF))
    res.sector_stats = g.agg(
        n=(config.COL_KODE, "count"),
        mu_PER=("PER_w", "mean"), sigma_PER=("PER_w", lambda s: s.std(ddof=config.ZSCORE_DDOF)),
        mu_PBV=("PBV_w", "mean"), sigma_PBV=("PBV_w", lambda s: s.std(ddof=config.ZSCORE_DDOF)),
    )
    _record(res, "Standardisasi Z-score per sektor", len(df), len(out),
            f"ddof={config.ZSCORE_DDOF}")
    return out


def run(df_raw: pd.DataFrame, data_mode: str = config.DATA_POSITIF) -> PreprocessResult:
    """data_mode "positif": buang PER/PBV <= 0; "semua": pertahankan, winsorizing dua sisi."""
    res = PreprocessResult(data=pd.DataFrame())
    _record(res, "Data mentah", len(df_raw), len(df_raw), "Sebelum pra-pemrosesan")
    df = fix_sectors(df_raw, res)
    df = drop_missing(df, res)
    if data_mode == config.DATA_POSITIF:
        df = drop_non_positive(df, res)
    lower = config.WINSOR_LOWER_PERCENTILE if data_mode == config.DATA_SEMUA else None
    df = winsorize(df, res, lower)
    df = sector_zscore(df, res)
    res.data = df
    return res
