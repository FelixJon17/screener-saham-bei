"""
src/winsorizer.py
Salinan kelas WinsorizerAtas dari notebook revisi.

Model Random Forest di notebook disimpan sebagai Pipeline yang memuat kelas
ini. Karena kelas itu didefinisikan di sel notebook, pickle mencatatnya
sebagai `__main__.WinsorizerAtas`. Saat aplikasi berjalan, `__main__` adalah
proses Streamlit, sehingga kelas harus didaftarkan ke sana sebelum
`joblib.load` dipanggil (lihat register_for_unpickle).

Isi kelas harus identik dengan notebook.
"""
from __future__ import annotations

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin


class WinsorizerAtas(BaseEstimator, TransformerMixin):
    """Winsorizing upper-only: nilai di atas persentil q (dari data latih) dipotong."""
    def __init__(self, q=95):
        self.q = q

    def fit(self, X, y=None):
        self.batas_ = np.percentile(np.asarray(X, dtype=float), self.q, axis=0)
        return self

    def transform(self, X):
        return np.minimum(np.asarray(X, dtype=float), self.batas_)


def register_for_unpickle() -> None:
    import __main__
    if not hasattr(__main__, "WinsorizerAtas"):
        __main__.WinsorizerAtas = WinsorizerAtas
