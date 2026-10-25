"""
export_results.py
Memuat set hasil notebook di luar aplikasi, mencetak pemeriksaan konsistensi,
dan mengekspor seluruh hasil ke satu berkas Excel bersheet banyak.

    python export_results.py
    python export_results.py --data semua --out hasil_seluruh_data.xlsx
"""
from __future__ import annotations

import argparse

import config
from src.export import write_excel
from src.pipeline import from_file


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=str(config.DEFAULT_RAW_PATH))
    ap.add_argument("--data", default=config.DATA_POSITIF, choices=list(config.DATA_MODES))
    ap.add_argument("--out", default="Hasil_Screener_Lengkap.xlsx")
    args = ap.parse_args()

    p = from_file(args.dataset, args.data)
    write_excel(p, args.out)

    m = p.cls.metrics
    print(f"Tersimpan       : {args.out}")
    print(f"Model RF        : {p.cls.format_model}")
    print(f"k               : {p.k}  ({len(p.table)} saham)")
    print(f"Silhouette      : {p.clu.silhouette:.4f}")
    print(f"Davies-Bouldin  : {p.clu.dbi:.4f}")
    print(f"Accuracy RF     : {m['accuracy']:.4f}")
    print(f"Precision macro : {m['precision_macro']:.4f}")
    print(f"Recall macro    : {m['recall_macro']:.4f}")
    print(f"F1-macro        : {m['f1_macro']:.4f}")
    for c in p.checks:
        print(f"{c['Status']} {c['Pemeriksaan']}: {c['Detail']}")


if __name__ == "__main__":
    main()
