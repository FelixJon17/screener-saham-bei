"""
src/compare.py
Analisis sensitivitas jumlah cluster (3.1.4): membandingkan K = 3 dengan K
lain memakai prosedur yang sama persis dengan notebook:

  - K-Means pada PER_z dan PBV_z, n_init=50, random_state=42
  - pelabelan 3.1.6: skor cluster = rata-rata koordinat centroid; skor
    terendah -> Rendah, tertinggi -> Tinggi, di antaranya -> Sedang
  - Random Forest: ROE/DER di-winsorize P95 seluruh data, split 80/20
    stratified (random_state=42), n_estimators=100, class_weight="balanced",
    tanpa penyetelan hiperparameter

Untuk K = 3 hasil di sini identik dengan notebook; itu sekaligus menjadi
bukti bahwa prosedur untuk K lain setara.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (accuracy_score, davies_bouldin_score, f1_score, precision_score,
                             recall_score, silhouette_score)
from sklearn.model_selection import train_test_split

import config

ZCOLS = ["Z_" + config.COL_PER, "Z_" + config.COL_PBV]

# Warna per peringkat skor centroid (rendah -> tinggi), dipakai bila K != 3
RANK_COLORS = ["#16A34A", "#1B2CC1", "#D97706", "#7692FF", "#DC2626", "#DB2777"]


@dataclass
class KResult:
    k: int
    labels: np.ndarray                 # cluster id per saham (urutan tabel)
    names: dict                        # cluster id -> nama label
    colors: dict                       # nama label -> warna
    profile: pd.DataFrame              # profil per cluster
    metrics: dict                      # WCSS, Silhouette, DBI, RF
    importance: dict                   # Feature Importance RF (ROE, DER)
    notes: list


def _axis_word(z: float) -> str:
    return "tinggi" if z > 0.5 else "rendah" if z < -0.5 else "setara"


def label_clusters(centers: np.ndarray) -> tuple[dict, list]:
    """Aturan 3.1.6: urutkan cluster menurut rata-rata koordinat centroid."""
    skor = centers.mean(axis=1)
    urut = [int(i) for i in np.argsort(skor)]
    names, notes = {i: config.LABEL_MID for i in urut}, []
    names[urut[0]] = config.LABEL_LOW
    names[urut[-1]] = config.LABEL_HIGH
    tengah = urut[1:-1]
    if len(tengah) > 1:
        # beberapa cluster "Sedang": bedakan dengan posisi centroid-nya
        for i in tengah:
            names[i] = (f"{config.LABEL_MID} (PER {_axis_word(centers[i, 0])}, "
                        f"PBV {_axis_word(centers[i, 1])})")
        notes.append(f"{len(tengah)} cluster berlabel Sedang; dibedakan menurut posisi "
                     "centroid (|z| > 0,5 = tinggi/rendah).")
    if not tengah:
        notes.append("K = 2 hanya menghasilkan kategori Rendah dan Tinggi.")
    return names, notes


RF_METRICS = ["RF Accuracy", "RF Precision (macro)", "RF Recall (macro)",
              "RF F1-Score (macro)", "RF F1-Score (weighted)", "Kelas terkecil di data uji"]
MIN_CLASS_FOR_RF = 10   # split 80/20 stratified butuh cukup anggota per kelas


def _rf_eval(X: pd.DataFrame, y: pd.Series, lower: int | None = None) -> tuple[dict, dict]:
    x = X.to_numpy(dtype=float)
    batas = np.percentile(x, config.WINSOR_PERCENTILE, axis=0)
    bawah = np.percentile(x, lower, axis=0) if lower else -np.inf
    X_w = np.clip(x, bawah, batas)
    X_tr, X_te, y_tr, y_te = train_test_split(
        X_w, y, test_size=config.TEST_SIZE, stratify=y, random_state=config.SPLIT_RANDOM_STATE)
    rf = RandomForestClassifier(n_estimators=config.RF_N_ESTIMATORS, class_weight="balanced",
                                random_state=config.RANDOM_STATE).fit(X_tr, y_tr)
    y_pred = rf.predict(X_te)
    m = {
        "RF Accuracy": accuracy_score(y_te, y_pred),
        "RF Precision (macro)": precision_score(y_te, y_pred, average="macro", zero_division=0),
        "RF Recall (macro)": recall_score(y_te, y_pred, average="macro", zero_division=0),
        "RF F1-Score (macro)": f1_score(y_te, y_pred, average="macro", zero_division=0),
        "RF F1-Score (weighted)": f1_score(y_te, y_pred, average="weighted", zero_division=0),
        "Kelas terkecil di data uji": int(y_te.value_counts().min()),
    }
    imp = dict(zip(["ROE", "DER"], rf.feature_importances_))
    return m, imp


def run_k(table: pd.DataFrame, k: int, lower: int | None = None) -> KResult:
    """
    table: tabel aplikasi dengan kolom Z_PER, Z_PBV, ROE %, DER, PER, PBV.
    Random Forest dilewati (metrik NaN) bila ada kelas dengan anggota kurang
    dari MIN_CLASS_FOR_RF.
    """
    X = table[ZCOLS].to_numpy(dtype=float)
    km = KMeans(n_clusters=k, n_init=config.KMEANS_N_INIT,
                random_state=config.RANDOM_STATE).fit(X)
    names, notes = label_clusters(km.cluster_centers_)

    order = np.argsort(km.cluster_centers_.mean(axis=1))  # rendah -> tinggi
    if k == 3 and len(set(names.values())) == 3:
        colors = dict(config.COLOR_MAP)
    else:
        colors = {names[c]: RANK_COLORS[r % len(RANK_COLORS)] for r, c in enumerate(order)}
        colors[config.LABEL_LOW] = config.COLOR_MAP[config.LABEL_LOW]
        colors[config.LABEL_HIGH] = config.COLOR_MAP[config.LABEL_HIGH]

    lab = pd.Series(km.labels_, index=table.index)
    d = table.assign(_c=lab)
    prof = d.groupby("_c").agg(
        n=(config.COL_KODE, "count"),
        PER_med=(config.COL_PER, "median"), PBV_med=(config.COL_PBV, "median"),
        ROE_med=(config.COL_ROE, "median"), DER_med=(config.COL_DER, "median"))
    prof.insert(0, "Label", pd.Series(names))
    prof.insert(2, "Proporsi (%)", (prof["n"] / len(d) * 100).round(1))
    prof.insert(3, "Z-PER", km.cluster_centers_[prof.index, 0])
    prof.insert(4, "Z-PBV", km.cluster_centers_[prof.index, 1])
    prof = prof.loc[order]
    prof.index.name = "Cluster"

    y = lab.map(names)
    if y.value_counts().min() >= MIN_CLASS_FOR_RF:
        rf_m, imp = _rf_eval(table[config.CHARACTERIZATION_FEATURES], y, lower)
    else:
        rf_m, imp = {m: float("nan") for m in RF_METRICS}, {}
        notes.append(f"Random Forest tidak dievaluasi: ada kategori dengan kurang dari "
                     f"{MIN_CLASS_FOR_RF} saham.")
    metrics = {
        "WCSS": float(km.inertia_),
        "Silhouette": float(silhouette_score(X, km.labels_)),
        "Davies-Bouldin": float(davies_bouldin_score(X, km.labels_)),
        "Cluster terkecil (saham)": int(prof["n"].min()),
        **rf_m,
    }
    return KResult(k=k, labels=km.labels_, names=names, colors=colors, profile=prof,
                   metrics=metrics, importance=imp, notes=notes)


# metrik -> True bila makin besar makin baik
ARAH = {"WCSS": False, "Silhouette": True, "Davies-Bouldin": False,
        "Cluster terkecil (saham)": True, "RF Accuracy": True,
        "RF Precision (macro)": True, "RF Recall (macro)": True,
        "RF F1-Score (macro)": True, "RF F1-Score (weighted)": True,
        "Kelas terkecil di data uji": True}


def metric_table(a: KResult, b: KResult) -> pd.DataFrame:
    rows = []
    for m, arah in ARAH.items():
        va, vb = a.metrics[m], b.metrics[m]
        if arah is None or np.isclose(va, vb):
            unggul = "—"
        else:
            unggul = f"K={a.k}" if (va > vb) == arah else f"K={b.k}"
        rows.append({"Metrik": m, f"K={a.k}": va, f"K={b.k}": vb, "Lebih baik": unggul})
    return pd.DataFrame(rows)


def migration(table: pd.DataFrame, a: KResult, b: KResult) -> pd.DataFrame:
    """Matriks perpindahan saham: label K=a (baris) -> label K=b (kolom)."""
    ra = pd.Series(a.labels).map(a.names).values
    rb = pd.Series(b.labels).map(b.names).values
    ct = pd.crosstab(pd.Series(ra, name=f"K={a.k}"), pd.Series(rb, name=f"K={b.k}"))
    order_a = [a.names[c] for c in a.profile.index]
    order_b = [b.names[c] for c in b.profile.index]
    return ct.reindex(index=order_a, columns=order_b, fill_value=0)
