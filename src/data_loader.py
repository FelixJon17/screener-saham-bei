"""
src/data_loader.py
Membaca dataset mentah dan memvalidasi skemanya.

Dataset mentah dipakai hanya untuk merekonstruksi jejak pra-pemrosesan
(960 → 959 → 627) dan memverifikasi bahwa tabel hasil notebook memang
berasal dari dataset tersebut. Label dan model tetap diambil dari hasil
notebook.
"""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

import config


class SchemaError(ValueError):
    """Dilempar ketika berkas tidak memiliki kolom wajib."""


def _validate(df: pd.DataFrame, required: list[str] | None = None) -> pd.DataFrame:
    required = required or config.REQUIRED_COLUMNS
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SchemaError(
            "Kolom wajib tidak ditemukan: "
            + ", ".join(missing)
            + ". Kolom yang tersedia: "
            + ", ".join(map(str, df.columns))
        )
    df = df.copy()
    df[config.COL_KODE] = df[config.COL_KODE].astype(str).str.strip().str.upper()
    df[config.COL_SEKTOR] = df[config.COL_SEKTOR].astype(str).str.strip()
    for col in (config.COL_PER, config.COL_PBV, config.COL_ROE, config.COL_DER):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def read_table(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    return pd.read_excel(path)


def load_dataset(path: str | Path) -> pd.DataFrame:
    """Dataset mentah (kolom sama dengan yang dibaca sel 2 notebook)."""
    return _validate(read_table(path))[config.REQUIRED_COLUMNS]


def load_result_table(path: str | Path) -> pd.DataFrame:
    """hasil_clustering.xlsx dari notebook."""
    return _validate(read_table(path), config.TABLE_COLUMNS)


def load_uploaded(file_bytes: bytes, filename: str) -> pd.DataFrame:
    buf = io.BytesIO(file_bytes)
    raw = pd.read_csv(buf) if filename.lower().endswith(".csv") else pd.read_excel(buf)
    return _validate(raw)[config.REQUIRED_COLUMNS]


def describe_raw(df: pd.DataFrame) -> dict:
    """Ringkasan data mentah untuk ditampilkan sebelum pra-pemrosesan."""
    numeric = [config.COL_PER, config.COL_PBV, config.COL_ROE, config.COL_DER]
    sektor_unik = sorted(df[config.COL_SEKTOR].dropna().unique().tolist())
    anomali = [s for s in sektor_unik if s not in config.IDX_IC_SECTORS]
    return {
        "n_baris": len(df),
        "n_saham_unik": df[config.COL_KODE].nunique(),
        "n_duplikat_kode": int(df[config.COL_KODE].duplicated().sum()),
        "n_sektor": len(sektor_unik),
        "sektor": sektor_unik,
        "sektor_anomali": anomali,
        "missing_per_kolom": df[numeric].isna().sum().to_dict(),
        "statistik": df[numeric].describe().T,
    }
