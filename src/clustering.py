"""
src/clustering.py
Membangun ringkasan K-Means dari hasil notebook.

Label cluster dibaca langsung dari hasil_clustering.xlsx (kolom `label`), dan
model K-Means dari model_kmeans.joblib. Modul ini hanya menghitung turunan
yang tidak diekspor notebook: silhouette per saham, centroid, profil cluster,
dan rekomendasi k dari evaluasi_k.csv.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import davies_bouldin_score, silhouette_samples, silhouette_score

import config


@dataclass
class ClusterResult:
    data: pd.DataFrame                       # tabel notebook + Silhouette Sampel
    model: KMeans
    centroids_z: pd.DataFrame
    centroid_profile: pd.DataFrame
    label_map: dict
    label_notes: list[str] = field(default_factory=list)
    silhouette: float = float("nan")
    dbi: float = float("nan")
    inertia: float = float("nan")


ZCOLS = ["Z_" + config.COL_PER, "Z_" + config.COL_PBV]


def evaluasi_k(raw: pd.DataFrame | None) -> pd.DataFrame:
    """evaluasi_k.csv notebook (K, WCSS, Silhouette, DBI) -> format tampilan."""
    if raw is None:
        return pd.DataFrame(columns=["k", "Inertia (WCSS)", "Silhouette Score",
                                     "Davies-Bouldin Index"])
    out = raw.rename(columns={"K": "k", "WCSS": "Inertia (WCSS)",
                              "Silhouette": "Silhouette Score", "DBI": "Davies-Bouldin Index"})
    out["Penurunan Inertia (%)"] = out["Inertia (WCSS)"].pct_change().mul(-100).round(2)
    return out


def elbow_point(eval_df: pd.DataFrame) -> int:
    """Titik siku: jarak terjauh ke garis yang menghubungkan k pertama dan terakhir."""
    k = eval_df["k"].to_numpy(dtype=float)
    y = eval_df["Inertia (WCSS)"].to_numpy(dtype=float)
    p1, p2 = np.array([k[0], y[0]]), np.array([k[-1], y[-1]])
    line = (p2 - p1) / np.linalg.norm(p2 - p1)
    pts = np.column_stack([k, y]) - p1
    dist = np.linalg.norm(pts - np.outer(pts @ line, line), axis=1)
    return int(k[int(np.argmax(dist))])


def metric_recommendations(eval_df: pd.DataFrame, k_dipakai: int) -> dict:
    if eval_df.empty:
        return {"elbow": None, "silhouette": None, "dbi": None, "dipakai": k_dipakai}
    return {
        "elbow": elbow_point(eval_df),
        "silhouette": int(eval_df.loc[eval_df["Silhouette Score"].idxmax(), "k"]),
        "dbi": int(eval_df.loc[eval_df["Davies-Bouldin Index"].idxmin(), "k"]),
        "dipakai": k_dipakai,
    }


def build(table: pd.DataFrame, km: KMeans) -> ClusterResult:
    """
    table: hasil_clustering.xlsx dengan kolom sudah diganti nama:
           Z_PER, Z_PBV, Cluster, Kategori.
    """
    X = table[ZCOLS].to_numpy(dtype=float)
    labels = table["Cluster"].to_numpy()
    out = table.copy()
    out["Silhouette Sampel"] = silhouette_samples(X, labels)

    label_map = (out.groupby("Cluster")["Kategori"]
                 .agg(lambda s: s.mode().iat[0]).to_dict())

    centroids = pd.DataFrame(km.cluster_centers_, columns=ZCOLS)
    centroids.index.name = "Cluster"
    centroids["Jumlah Anggota"] = out["Cluster"].value_counts().sort_index()
    centroids["Kategori"] = pd.Series(label_map)

    profile_cols = [config.COL_PER, config.COL_PBV, config.COL_ROE, config.COL_DER]
    profile = out.groupby("Cluster")[profile_cols].agg(["median", "mean"]).round(4)
    profile.insert(0, "Kategori", pd.Series(label_map))
    profile.insert(1, "n", out["Cluster"].value_counts().sort_index())

    notes = [
        "Aturan pelabelan notebook (sel 11): cluster dengan centroid Z-PER dan Z-PBV "
        "sama-sama negatif → Valuasi Relatif Rendah; sama-sama positif → Valuasi Relatif "
        "Tinggi; selain itu → Valuasi Relatif Sedang. Bila lebih dari satu cluster "
        "memenuhi syarat, dipilih yang jumlah Z-nya paling ekstrem.",
    ]
    for cid, r in centroids.iterrows():
        notes.append(f"Cluster {cid}: Z-PER {r[ZCOLS[0]]:+.4f}, Z-PBV {r[ZCOLS[1]]:+.4f} "
                     f"→ {r['Kategori']} ({int(r['Jumlah Anggota'])} saham)")

    return ClusterResult(
        data=out, model=km, centroids_z=centroids, centroid_profile=profile,
        label_map=label_map, label_notes=notes,
        silhouette=float(silhouette_score(X, labels)),
        dbi=float(davies_bouldin_score(X, labels)),
        inertia=float(km.inertia_),
    )
