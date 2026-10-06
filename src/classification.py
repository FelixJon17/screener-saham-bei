"""
src/classification.py
Evaluasi model Random Forest hasil notebook.

Model dimuat dari model_random_forest.joblib; tidak ada pelatihan ulang.
Data uji direkonstruksi dengan pembagian yang identik dengan notebook
(test_size=0.2, stratify=y, random_state=42) supaya confusion matrix dan
metrik di aplikasi sama persis dengan yang dilaporkan di skripsi.

Dua format model didukung:
  - notebook revisi : Pipeline(WinsorizerAtas -> RandomForest), input ROE & DER mentah
  - notebook asli   : RandomForestClassifier yang dilatih pada ROE/DER yang sudah
                      di-winsorize P95 seluruh data. Model ini dibungkus Pipeline
                      dengan batas winsorizing yang sama agar perlakuannya seragam.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, classification_report,
                             confusion_matrix, f1_score, precision_score, recall_score)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

import config
from src.winsorizer import WinsorizerAtas


@dataclass
class ClassificationResult:
    model: Pipeline
    classes: list[str]
    X_train: pd.DataFrame
    X_test: pd.DataFrame
    y_train: pd.Series
    y_test: pd.Series
    y_pred: np.ndarray
    confusion: pd.DataFrame
    report: pd.DataFrame
    metrics: dict
    feature_importance: pd.DataFrame
    params: dict
    winsor_caps: dict
    cv_summary: pd.DataFrame | None = None     # evaluasi_rf_repeated_cv.csv
    format_model: str = ""
    notes: list[str] = field(default_factory=list)


def as_pipeline(model, df: pd.DataFrame) -> tuple[Pipeline, str]:
    if isinstance(model, Pipeline):
        return model, "Pipeline (WinsorizerAtas → Random Forest), notebook revisi"
    if isinstance(model, RandomForestClassifier):
        w = WinsorizerAtas(config.WINSOR_PERCENTILE)
        w.batas_ = np.percentile(df[config.CHARACTERIZATION_FEATURES].to_numpy(dtype=float),
                                 config.WINSOR_PERCENTILE, axis=0)
        return (Pipeline([("winsor", w), ("rf", model)]),
                "RandomForestClassifier, notebook asli (winsorizing P95 seluruh data)")
    raise TypeError(f"Format model Random Forest tidak dikenali: {type(model).__name__}")


def _parse_cv(raw: pd.DataFrame | None) -> pd.DataFrame | None:
    """Sel bertuliskan '0.7067 ± 0.0307' dipecah menjadi rata-rata dan simpangan baku."""
    if raw is None:
        return None
    raw = raw.set_index(raw.columns[0])
    raw.index.name = "Model"
    rows = {}
    for model, r in raw.iterrows():
        for metrik, sel in r.items():
            mean, _, sd = str(sel).partition("±")
            rows.setdefault(model, {})[f"{metrik} (rata-rata)"] = float(mean)
            rows[model][f"{metrik} (sd)"] = float(sd) if sd.strip() else np.nan
    return pd.DataFrame(rows).T


def build(df: pd.DataFrame, model, cv_raw: pd.DataFrame | None = None) -> ClassificationResult:
    """df: tabel hasil notebook dengan kolom Kategori."""
    pipe, fmt = as_pipeline(model, df)
    rf: RandomForestClassifier = pipe.named_steps["rf"]
    X = df[config.CHARACTERIZATION_FEATURES]
    y = df["Kategori"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=config.TEST_SIZE, stratify=y, random_state=config.SPLIT_RANDOM_STATE)

    y_pred = pipe.predict(X_test)
    classes = [c for c in config.LABEL_ORDER if c in rf.classes_] + \
              [c for c in rf.classes_ if c not in config.LABEL_ORDER]

    cm = pd.DataFrame(confusion_matrix(y_test, y_pred, labels=classes),
                      index=[f"Aktual: {c}" for c in classes],
                      columns=[f"Prediksi: {c}" for c in classes])
    rep = pd.DataFrame(classification_report(y_test, y_pred, labels=classes,
                                             output_dict=True, zero_division=0)).T

    y_base = DummyClassifier(strategy="most_frequent").fit(X_train, y_train).predict(X_test)
    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_test, y_pred)),
        "precision_macro": float(precision_score(y_test, y_pred, average="macro", zero_division=0)),
        "recall_macro": float(recall_score(y_test, y_pred, average="macro", zero_division=0)),
        "f1_macro": float(f1_score(y_test, y_pred, average="macro", zero_division=0)),
        "f1_weighted": float(f1_score(y_test, y_pred, average="weighted", zero_division=0)),
        "baseline_kelas_mayoritas": float(accuracy_score(y_test, y_base)),
        "baseline_balanced_accuracy": float(balanced_accuracy_score(y_test, y_base)),
        "baseline_f1_macro": float(f1_score(y_test, y_base, average="macro", zero_division=0)),
    }

    perm = permutation_importance(pipe, X_test, y_test, scoring="f1_macro",
                                  n_repeats=config.PERM_REPEATS,
                                  random_state=config.RANDOM_STATE)
    imp = pd.DataFrame({
        "Variabel": ["ROE", "DER"],
        "MDI": rf.feature_importances_,
        "Permutation (data uji)": perm.importances_mean,
        "Permutation sd": perm.importances_std,
    })
    imp["Persentase"] = (imp["MDI"] / imp["MDI"].sum() * 100).round(2)
    imp = imp.sort_values("MDI", ascending=False).reset_index(drop=True)

    p = rf.get_params()
    params = {k: p[k] for k in ("n_estimators", "max_depth", "min_samples_split",
                                "min_samples_leaf", "class_weight", "random_state")}

    caps = dict(zip(["ROE", "DER"], map(float, pipe.named_steps["winsor"].batas_)))

    notes = []
    if metrics["accuracy"] < metrics["baseline_kelas_mayoritas"]:
        notes.append(
            f"Accuracy ({metrics['accuracy']:.4f}) di bawah baseline kelas mayoritas "
            f"({metrics['baseline_kelas_mayoritas']:.4f}) karena distribusi kelas timpang. "
            "Balanced accuracy dan F1-macro lebih tepat sebagai metrik utama.")
    notes.append(
        "Feature importance MDI bias terhadap variabel berkardinalitas tinggi (Strobl et al., "
        "2007); permutation importance pada data uji ditampilkan sebagai pembanding.")

    return ClassificationResult(
        model=pipe, classes=classes, X_train=X_train, X_test=X_test,
        y_train=y_train, y_test=y_test, y_pred=y_pred, confusion=cm, report=rep,
        metrics=metrics, feature_importance=imp, params=params, winsor_caps=caps,
        cv_summary=_parse_cv(cv_raw), format_model=fmt, notes=notes,
    )


def predict_one(model: Pipeline, roe: float, der: float) -> dict:
    """Prediksi kategori satu saham beserta probabilitasnya."""
    x = pd.DataFrame([[roe, der]], columns=config.CHARACTERIZATION_FEATURES)
    pred = model.predict(x)[0]
    proba = dict(zip(model.classes_, model.predict_proba(x)[0]))
    return {"prediksi": pred, "probabilitas": proba}
