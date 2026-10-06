"""
src/compare.py
Perbandingan jumlah cluster (mis. K=3 vs K=4) dengan prosedur yang sama
persis dengan notebook:

  - K-Means pada PER_z dan PBV_z, n_init=50, random_state=42 (sel 9–10)
  - aturan pelabelan sel 11 (centroid sama-sama negatif -> Rendah, sama-sama
    positif dengan skor tertinggi -> Tinggi, sisanya -> Sedang)
  - Random Forest: Pipeline(WinsorizerAtas -> RF), split 80/20 stratified,
    GridSearchCV 5-fold f1_macro dengan grid yang sama (sel 13–16)

Untuk K yang dipakai notebook, hasil di sini harus identik dengan notebook;
itu sekaligus menjadi bukti bahwa prosedur untuk K lain setara.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, davies_bouldin_score,
                             f1_score, silhouette_score)
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline

import config
from src.winsorizer import WinsorizerAtas

ZCOLS = ["Z_" + config.COL_PER, "Z_" + config.COL_PBV]

PARAM_GRID = {"rf__n_estimators": [200],
              "rf__max_depth": [None, 5, 10],
              "rf__min_samples_split": [2, 10],
              "rf__min_samples_leaf": [1, 3, 5, 10]}

# Warna per peringkat skor centroid (rendah -> tinggi), dipakai bila K > 3
RANK_COLORS = ["#16A34A", "#0891B2", "#D97706", "#7C3AED", "#DC2626", "#DB2777"]


@dataclass
class KResult:
    k: int
    labels: np.ndarray                 # cluster id per saham (urutan tabel)
    names: dict                        # cluster id -> nama label
    colors: dict                       # nama label -> warna
    profile: pd.DataFrame              # profil per cluster
    metrics: dict                      # WCSS, Silhouette, DBI, RF
    best_params: dict
    notes: list


def _axis_word(z: float) -> str:
    return "tinggi" if z > 0.5 else "rendah" if z < -0.5 else "setara"


def label_clusters(centers: np.ndarray) -> tuple[dict, list]:
    """Aturan sel 11 notebook, diperluas agar label tetap unik bila K > 3."""
    k = len(centers)
    skor = centers.sum(axis=1)
    neg = [i for i in range(k) if centers[i, 0] < 0 and centers[i, 1] < 0]
    pos = [i for i in range(k) if centers[i, 0] > 0 and centers[i, 1] > 0]
    names, notes = {}, []
    if neg:
        names[min(neg, key=lambda i: skor[i])] = config.LABEL_LOW
    if pos:
        names[max(pos, key=lambda i: skor[i])] = config.LABEL_HIGH
    sisa = [i for i in range(k) if i not in names]
    for i in sisa:
        names[i] = config.LABEL_MID
    if len(neg) > 1 or len(pos) > 1:
        notes.append("Lebih dari satu cluster memenuhi syarat Rendah/Tinggi; aturan notebook "
                     "memilih yang skornya paling ekstrem, sisanya menjadi Sedang.")
    if len(sisa) > 1:
        # beberapa cluster "Sedang": bedakan dengan profil centroid-nya
        for i in sisa:
            names[i] = (f"{config.LABEL_MID} (PER {_axis_word(centers[i, 0])}, "
                        f"PBV {_axis_word(centers[i, 1])})")
        notes.append(f"{len(sisa)} cluster berlabel Sedang; dibedakan menurut posisi "
                     "centroid (|z| > 0,5 = tinggi/rendah).")
    return names, notes


def _rf_eval(X: pd.DataFrame, y: pd.Series) -> tuple[dict, dict]:
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=config.TEST_SIZE, stratify=y, random_state=config.SPLIT_RANDOM_STATE)
    pipe = Pipeline([("winsor", WinsorizerAtas(config.WINSOR_PERCENTILE)),
                     ("rf", RandomForestClassifier(class_weight="balanced",
                                                   random_state=config.RANDOM_STATE))])
    grid = GridSearchCV(pipe, PARAM_GRID, scoring="f1_macro",
                        cv=StratifiedKFold(config.GRID_CV_FOLDS, shuffle=True,
                                           random_state=config.RANDOM_STATE),
                        n_jobs=-1).fit(X_tr, y_tr)
    y_pred = grid.best_estimator_.predict(X_te)
    y_base = DummyClassifier(strategy="most_frequent").fit(X_tr, y_tr).predict(X_te)
    m = {
        "RF Accuracy": accuracy_score(y_te, y_pred),
        "RF Balanced accuracy": balanced_accuracy_score(y_te, y_pred),
        "RF F1-macro (uji)": f1_score(y_te, y_pred, average="macro"),
        "RF F1-macro (CV latih)": grid.best_score_,
        "Baseline F1-macro": f1_score(y_te, y_base, average="macro", zero_division=0),
        "Kelas terkecil di data uji": int(y_te.value_counts().min()),
    }
    params = {k.replace("rf__", ""): v for k, v in grid.best_params_.items()}
    return m, params


def run_k(table: pd.DataFrame, k: int) -> KResult:
    """table: tabel aplikasi dengan kolom Z_PER, Z_PBV, ROE %, DER, PER, PBV."""
    X = table[ZCOLS].to_numpy(dtype=float)
    km = KMeans(n_clusters=k, n_init=config.KMEANS_N_INIT,
                random_state=config.RANDOM_STATE).fit(X)
    names, notes = label_clusters(km.cluster_centers_)

    order = np.argsort(km.cluster_centers_.sum(axis=1))   # rendah -> tinggi
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
    rf_m, params = _rf_eval(table[config.CHARACTERIZATION_FEATURES], y)
    metrics = {
        "WCSS": float(km.inertia_),
        "Silhouette": float(silhouette_score(X, km.labels_)),
        "Davies-Bouldin": float(davies_bouldin_score(X, km.labels_)),
        "Cluster terkecil (saham)": int(prof["n"].min()),
        **rf_m,
    }
    return KResult(k=k, labels=km.labels_, names=names, colors=colors, profile=prof,
                   metrics=metrics, best_params=params, notes=notes)


# metrik -> True bila makin besar makin baik
ARAH = {"WCSS": False, "Silhouette": True, "Davies-Bouldin": False,
        "Cluster terkecil (saham)": True, "RF Accuracy": True,
        "RF Balanced accuracy": True, "RF F1-macro (uji)": True,
        "RF F1-macro (CV latih)": True, "Baseline F1-macro": None,
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
