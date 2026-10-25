"""
src/trainer.py
Menjalankan prosedur notebook langsung di aplikasi (tanpa berkas hasil).

Langkahnya sama dengan 535230119_SkripsiFelix.ipynb: koreksi sektor, buang
nilai kosong, (konfigurasi "positif") buang PER/PBV <= 0, winsorizing, Z-score
per sektor, evaluasi K = 2..6, K-Means K = 3 (n_init=50), pelabelan 3.1.6,
lalu Random Forest (n_estimators=100, class_weight="balanced") pada ROE/DER
dengan split 80:20 stratified. Pada dataset penelitian hasilnya identik dengan
notebook.

compute() dipakai src/pipeline.py untuk dataset penelitian, dataset global
yang diunggah admin, dan dataset pribadi pengguna. Modul ini tidak mengimpor
Streamlit.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import davies_bouldin_score, silhouette_samples, silhouette_score
from sklearn.model_selection import train_test_split

import config
from src import compare, data_loader, preprocessing
from src.winsorizer import lower_for

MAX_ROWS = 5000
MIN_SAHAM = 30

# Nama kolom yang dikenali otomatis (dibandingkan setelah dinormalisasi).
ALIASES = {
    config.COL_KODE: ["kode saham", "kode", "kode emiten", "emiten", "ticker", "symbol",
                      "simbol", "saham", "stock", "code", "stock code"],
    config.COL_SEKTOR: ["sektor", "sector", "sektor idx", "idx sector", "industri", "industry"],
    config.COL_PER: ["per", "pe", "p/e", "pe ratio", "price to earnings", "price earning ratio"],
    config.COL_PBV: ["pbv", "pb", "p/b", "price to book", "price to book value"],
    config.COL_ROE: ["roe %", "roe", "roe%", "roe (%)", "return on equity"],
    config.COL_DER: ["der", "de", "d/e", "debt to equity", "debt to equity ratio"],
}


class TrainError(ValueError):
    """Pesan kesalahan yang aman ditampilkan langsung ke pengguna."""


# --------------------------------------------------------------------------
# Membaca berkas dan memetakan kolom
# --------------------------------------------------------------------------
def _norm(name) -> str:
    return re.sub(r"[^a-z0-9%/]+", " ", str(name).lower()).strip()


def read_file(data: bytes, filename: str) -> pd.DataFrame:
    """Excel (lembar pertama) atau CSV (pemisah , atau ; dikenali otomatis)."""
    buf = io.BytesIO(data)
    if filename.lower().endswith(".csv"):
        raw = pd.read_csv(buf, sep=None, engine="python")
    else:
        raw = pd.read_excel(buf)
    raw = raw.dropna(how="all").dropna(axis=1, how="all")
    raw.columns = [str(c).strip() for c in raw.columns]
    if raw.empty:
        raise TrainError("Berkas kosong.")
    if len(raw) > MAX_ROWS:
        raise TrainError(f"Maksimal {MAX_ROWS} baris; berkas berisi {len(raw)} baris.")
    return raw


def guess_columns(columns) -> dict:
    """Kolom wajib -> nama kolom berkas yang paling cocok (atau None)."""
    norm = {c: _norm(c) for c in columns}
    out, used = {}, set()
    for target, aliases in ALIASES.items():
        names = [_norm(target)] + [_norm(a) for a in aliases]
        hit = next((c for n in names for c, v in norm.items() if v == n and c not in used), None)
        out[target] = hit
        if hit is not None:
            used.add(hit)
    return out


def _to_number(s: pd.Series) -> pd.Series:
    """Menerima "12,5" (format Indonesia) maupun "12.5"."""
    if pd.api.types.is_numeric_dtype(s):
        return s
    t = s.astype(str).str.strip().str.replace("%", "", regex=False)
    koma = t.str.contains(",", regex=False) & ~t.str.contains(".", regex=False)
    return pd.to_numeric(t.where(~koma, t.str.replace(",", ".", regex=False)), errors="coerce")


def prepare(raw: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    kosong = [k for k in config.REQUIRED_COLUMNS if not mapping.get(k)]
    if kosong:
        raise TrainError("Kolom belum dipetakan: " + ", ".join(kosong))
    dipakai = [mapping[k] for k in config.REQUIRED_COLUMNS]
    if len(set(dipakai)) < len(dipakai):
        raise TrainError("Satu kolom berkas dipetakan ke lebih dari satu atribut.")
    df = raw[dipakai].copy()
    df.columns = config.REQUIRED_COLUMNS
    for c in (config.COL_PER, config.COL_PBV, config.COL_ROE, config.COL_DER):
        df[c] = _to_number(df[c])
    df = data_loader.normalize(df)
    df = df[df[config.COL_KODE].ne("") & df[config.COL_KODE].ne("NAN")]
    return df.drop_duplicates(config.COL_KODE).reset_index(drop=True)


# --------------------------------------------------------------------------
# Pelatihan (prosedur notebook)
# --------------------------------------------------------------------------
def _single_sectors(df: pd.DataFrame, data_mode: str) -> list[str]:
    """Sektor yang setelah pembersihan tidak punya Z-score (< 2 saham atau tanpa variasi)."""
    pre = preprocessing.run(df, data_mode).data
    z = pre[["PER_z", "PBV_z"]].to_numpy(dtype=float)
    bad = pre.loc[~np.isfinite(z).all(axis=1), config.COL_SEKTOR]
    return sorted(bad.unique())


@dataclass
class Hasil:
    """Hasil satu kali menjalankan prosedur notebook."""
    data: pd.DataFrame              # dataset setelah sektor tunggal dibuang (masukan)
    table: pd.DataFrame             # tabel hasil: kolom notebook + cluster, label, silhouette
    pre: preprocessing.PreprocessResult
    kmeans: KMeans
    rf: RandomForestClassifier
    k_eval: pd.DataFrame            # K, WCSS, Silhouette, DBI untuk K = 2..6
    sektor_dibuang: list[str]


def compute(df: pd.DataFrame, data_mode: str = config.DATA_POSITIF) -> Hasil:
    """df: enam kolom wajib (data_loader.normalize / prepare). Melempar TrainError."""
    buang = _single_sectors(df, data_mode)
    if buang:
        df = df[~df[config.COL_SEKTOR].isin(buang)].reset_index(drop=True)
    pre = preprocessing.run(df, data_mode)
    d = pre.data.copy()
    if len(d) < MIN_SAHAM:
        raise TrainError(f"Setelah dibersihkan tersisa {len(d)} saham; minimal {MIN_SAHAM}.")

    X_k = d[["PER_z", "PBV_z"]].to_numpy(dtype=float)
    hasil = []
    for k in range(2, 7):
        km = KMeans(n_clusters=k, n_init=config.KMEANS_N_INIT,
                    random_state=config.RANDOM_STATE).fit(X_k)
        hasil.append({"K": k, "WCSS": km.inertia_,
                      "Silhouette": silhouette_score(X_k, km.labels_),
                      "DBI": davies_bouldin_score(X_k, km.labels_)})

    kmeans = KMeans(n_clusters=3, n_init=config.KMEANS_N_INIT,
                    random_state=config.RANDOM_STATE).fit(X_k)
    label, _ = compare.label_clusters(kmeans.cluster_centers_)
    d["cluster"] = kmeans.labels_
    d["label"] = d["cluster"].map(label)
    d["silhouette"] = silhouette_samples(X_k, kmeans.labels_)
    if d["label"].value_counts().min() < 2:
        raise TrainError("Ada kategori dengan kurang dari 2 saham; Random Forest tidak dapat "
                         "dilatih. Gunakan dataset yang lebih besar.")

    lower = lower_for(data_mode)
    for c in config.CHARACTERIZATION_FEATURES:
        atas = np.percentile(d[c], config.WINSOR_PERCENTILE)
        bawah = np.percentile(d[c], lower) if lower else -np.inf
        d[c + "_w"] = np.clip(d[c], bawah, atas)
    X = d[[c + "_w" for c in config.CHARACTERIZATION_FEATURES]]
    y = d["label"]
    X_tr, _, y_tr, _ = train_test_split(X, y, test_size=config.TEST_SIZE, stratify=y,
                                        random_state=config.SPLIT_RANDOM_STATE)
    rf = RandomForestClassifier(n_estimators=config.RF_N_ESTIMATORS, class_weight="balanced",
                                random_state=config.RANDOM_STATE).fit(X_tr, y_tr)

    return Hasil(data=df, table=d, pre=pre, kmeans=kmeans, rf=rf,
                 k_eval=pd.DataFrame(hasil), sektor_dibuang=buang)
