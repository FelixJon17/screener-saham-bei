"""
src/classification.py
Evaluasi model Random Forest.

Model dilatih src/trainer.py dengan prosedur notebook (n_estimators=100,
class_weight="balanced") pada ROE/DER hasil winsorizing seluruh data. Data uji
direkonstruksi dengan pembagian yang identik (test_size=0.2, stratify=y,
random_state=42) sehingga confusion matrix dan metrik sama dengan notebook.
Agar aplikasi dapat memprediksi dari ROE/DER mentah, model dibungkus Pipeline
dengan batas winsorizing yang sama.

Metrik mengikuti proposal: Confusion Matrix, Accuracy, Precision, Recall,
F1-Score (macro dan weighted), dan Feature Importance.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (accuracy_score, classification_report, confusion_matrix,
                             f1_score, precision_score, recall_score)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

import config
from src.winsorizer import WinsorizerAtas, WinsorizerDuaSisi


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
    format_model: str = ""
    notes: list[str] = field(default_factory=list)


def as_pipeline(model, df: pd.DataFrame, lower: int | None = None) -> tuple[Pipeline, str]:
    if isinstance(model, Pipeline):
        return model, "Pipeline (WinsorizerAtas → Random Forest)"
    if isinstance(model, RandomForestClassifier):
        X = df[config.CHARACTERIZATION_FEATURES].to_numpy(dtype=float)
        if lower:
            w = WinsorizerDuaSisi(lower, config.WINSOR_PERCENTILE).fit(X)
            ket = f"winsorizing P{lower}–P{config.WINSOR_PERCENTILE} seluruh data"
        else:
            w = WinsorizerAtas(config.WINSOR_PERCENTILE).fit(X)
            ket = f"winsorizing P{config.WINSOR_PERCENTILE} seluruh data"
        return Pipeline([("winsor", w), ("rf", model)]), f"RandomForestClassifier ({ket})"
    raise TypeError(f"Format model Random Forest tidak dikenali: {type(model).__name__}")


def build(df: pd.DataFrame, model, lower: int | None = None) -> ClassificationResult:
    """df: tabel hasil dengan kolom Kategori. lower: persentil bawah winsorizing."""
    pipe, fmt = as_pipeline(model, df, lower)
    rf: RandomForestClassifier = pipe.named_steps["rf"]
    X = df[config.CHARACTERIZATION_FEATURES]
    y = df["Kategori"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=config.TEST_SIZE, stratify=y, random_state=config.SPLIT_RANDOM_STATE)

    y_pred = pipe.predict(X_test)
    classes = [c for c in config.LABEL_ORDER if c in rf.classes_] +               [c for c in rf.classes_ if c not in config.LABEL_ORDER]

    cm = pd.DataFrame(confusion_matrix(y_test, y_pred, labels=classes),
                      index=[f"Aktual: {c}" for c in classes],
                      columns=[f"Prediksi: {c}" for c in classes])
    rep = pd.DataFrame(classification_report(y_test, y_pred, labels=classes,
                                             output_dict=True, zero_division=0)).T

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision_macro": float(precision_score(y_test, y_pred, average="macro", zero_division=0)),
        "recall_macro": float(recall_score(y_test, y_pred, average="macro", zero_division=0)),
        "f1_macro": float(f1_score(y_test, y_pred, average="macro", zero_division=0)),
        "precision_weighted": float(precision_score(y_test, y_pred, average="weighted",
                                                    zero_division=0)),
        "recall_weighted": float(recall_score(y_test, y_pred, average="weighted", zero_division=0)),
        "f1_weighted": float(f1_score(y_test, y_pred, average="weighted", zero_division=0)),
    }

    imp = pd.DataFrame({"Variabel": ["ROE", "DER"], "Feature Importance": rf.feature_importances_})
    imp["Persentase"] = (imp["Feature Importance"] / imp["Feature Importance"].sum() * 100).round(2)
    imp = imp.sort_values("Feature Importance", ascending=False).reset_index(drop=True)

    p = rf.get_params()
    params = {k: p[k] for k in ("n_estimators", "max_depth", "min_samples_split",
                                "min_samples_leaf", "class_weight", "random_state")}

    w = pipe.named_steps["winsor"]
    caps = dict(zip(["ROE", "DER"], map(float, w.batas_)))
    if hasattr(w, "batas_bawah_"):
        caps.update({f"{k} bawah": float(v) for k, v in zip(["ROE", "DER"], w.batas_bawah_)})

    notes = [
        "Feature Importance dihitung dari penurunan Gini rata-rata pada seluruh pohon "
        "(persamaan 2.24); nilainya menunjukkan peran variabel dalam membedakan kelas, "
        "bukan hubungan sebab-akibat.",
    ]

    return ClassificationResult(
        model=pipe, classes=classes, X_train=X_train, X_test=X_test,
        y_train=y_train, y_test=y_test, y_pred=y_pred, confusion=cm, report=rep,
        metrics=metrics, feature_importance=imp, params=params, winsor_caps=caps,
        format_model=fmt, notes=notes,
    )


def predict_one(model: Pipeline, roe: float, der: float) -> dict:
    """Prediksi kategori satu saham beserta probabilitasnya."""
    x = pd.DataFrame([[roe, der]], columns=config.CHARACTERIZATION_FEATURES)
    pred = model.predict(x)[0]
    proba = dict(zip(model.classes_, model.predict_proba(x)[0]))
    return {"prediksi": pred, "probabilitas": proba}
