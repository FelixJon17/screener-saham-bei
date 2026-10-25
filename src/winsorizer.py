"""
src/winsorizer.py
Kelas winsorizing untuk membungkus model Random Forest.

Random Forest dilatih pada ROE/DER hasil winsorizing seluruh data.
src/classification.py membungkusnya dengan kelas ini (batas yang sama) agar
aplikasi dapat memprediksi dari ROE/DER mentah.
"""
from __future__ import annotations

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin


class WinsorizerAtas(BaseEstimator, TransformerMixin):
    """Winsorizing upper-only: nilai di atas persentil q dipotong."""
    def __init__(self, q=95):
        self.q = q

    def fit(self, X, y=None):
        self.batas_ = np.percentile(np.asarray(X, dtype=float), self.q, axis=0)
        return self

    def transform(self, X):
        return np.minimum(np.asarray(X, dtype=float), self.batas_)


class WinsorizerDuaSisi(BaseEstimator, TransformerMixin):
    """Winsorizing dua sisi: nilai di bawah P(q_bawah) dan di atas P(q_atas) dipotong."""
    def __init__(self, q_bawah=5, q_atas=95):
        self.q_bawah = q_bawah
        self.q_atas = q_atas

    def fit(self, X, y=None):
        x = np.asarray(X, dtype=float)
        self.batas_bawah_ = np.percentile(x, self.q_bawah, axis=0)
        self.batas_ = np.percentile(x, self.q_atas, axis=0)
        return self

    def transform(self, X):
        return np.clip(np.asarray(X, dtype=float), self.batas_bawah_, self.batas_)


def lower_for(data_mode: str) -> int | None:
    """Persentil batas bawah winsorizing untuk konfigurasi data (None = upper-only)."""
    import config
    return config.WINSOR_LOWER_PERCENTILE if data_mode == config.DATA_SEMUA else None
