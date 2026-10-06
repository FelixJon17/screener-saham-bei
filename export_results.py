"""
export_results.py
Memuat set hasil notebook di luar aplikasi, mencetak pemeriksaan konsistensi,
dan mengekspor seluruh hasil ke satu berkas Excel bersheet banyak.

    python export_results.py
    python export_results.py --folder output --out hasil_notebook_asli.xlsx
"""
from __future__ import annotations

import argparse

import config
from src.export import write_excel
from src.pipeline import load


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", default=str(config.MODEL_DIR))
    ap.add_argument("--out", default="Hasil_Screener_Lengkap.xlsx")
    args = ap.parse_args()

    p = load(args.folder)
    write_excel(p, args.out)

    m = p.cls.metrics
    print(f"Tersimpan       : {args.out}")
    print(f"Model RF        : {p.cls.format_model}")
    print(f"k               : {p.k}  ({len(p.table)} saham)")
    print(f"Silhouette      : {p.clu.silhouette:.4f}")
    print(f"Davies-Bouldin  : {p.clu.dbi:.4f}")
    print(f"Accuracy RF     : {m['accuracy']:.4f}  (baseline {m['baseline_kelas_mayoritas']:.4f})")
    print(f"Balanced acc.   : {m['balanced_accuracy']:.4f}")
    print(f"F1-macro        : {m['f1_macro']:.4f}  (baseline {m['baseline_f1_macro']:.4f})")
    for c in p.checks:
        print(f"{c['Status']} {c['Pemeriksaan']}: {c['Detail']}")


if __name__ == "__main__":
    main()
