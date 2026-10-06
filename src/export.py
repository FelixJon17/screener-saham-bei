"""
src/export.py
Menulis seluruh hasil ke satu berkas Excel bersheet banyak. Dipakai oleh
export_results.py (baris perintah) dan halaman Kelola Data & Model (tombol
unduh), sehingga isi keduanya selalu identik.
"""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

from src.pipeline import PipelineOutput


def write_excel(p: PipelineOutput, target: str | Path | io.BytesIO) -> None:
    with pd.ExcelWriter(target, engine="openpyxl") as xw:
        pd.DataFrame(p.checks).to_excel(xw, sheet_name="00_Verifikasi", index=False)
        if p.pre is not None:
            p.pre.log_df().to_excel(xw, sheet_name="01_Log_Prapemrosesan", index=False)
            pd.DataFrame(p.pre.winsor_caps).T.to_excel(xw, sheet_name="02_Ambang_Winsorizing")
        if p.sector_stats is not None:
            p.sector_stats.to_excel(xw, sheet_name="03_Statistik_Sektor")
        p.table.to_excel(xw, sheet_name="04_Hasil_Clustering", index=False)
        p.clu.centroids_z.to_excel(xw, sheet_name="05_Centroid")
        p.clu.centroid_profile.to_excel(xw, sheet_name="06_Profil_Cluster")
        p.k_eval.to_excel(xw, sheet_name="07_Evaluasi_k", index=False)
        p.sector_summary.to_excel(xw, sheet_name="08_Ringkasan_Sektor")
        p.cls.confusion.to_excel(xw, sheet_name="09_Confusion_Matrix")
        p.cls.report.to_excel(xw, sheet_name="10_Precision_Recall_F1")
        p.cls.feature_importance.to_excel(xw, sheet_name="11_Feature_Importance", index=False)
        if p.cls.cv_summary is not None:
            p.cls.cv_summary.to_excel(xw, sheet_name="12_Repeated_CV")
        pd.Series(p.cls.metrics).rename("Nilai").to_frame().to_excel(
            xw, sheet_name="13_Metrik_Ringkas")
        if p.pre is not None:
            for nama, buang in p.pre.dropped.items():
                if len(buang):
                    buang.to_excel(xw, sheet_name=f"X_{nama[:24]}", index=False)


def excel_bytes(p: PipelineOutput) -> bytes:
    buf = io.BytesIO()
    write_excel(p, buf)
    return buf.getvalue()
