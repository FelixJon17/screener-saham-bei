"""
views/panduan.py -- Panduan & Glosarium

Cara kerja screener, arti kategori, dan istilah, ditulis singkat.
"""
from __future__ import annotations

import streamlit as st

import config
from src import auth, ui

LANGKAH = [
    ("Input Data", "Kode Saham, Sektor, PER, PBV, ROE, dan DER setiap emiten BEI."),
    ("Pra-Pemrosesan Data", "Buang data kosong dan PER/PBV ≤ 0; batasi nilai ekstrem di "
                  f"P{config.WINSOR_PERCENTILE}."),
    ("Relatif sektor", "PER dan PBV diubah menjadi Z-score terhadap sektornya."),
    ("Pengelompokan", "K-Means Clustering menjadi 3 kategori valuasi relatif."),
    ("Karakterisasi", "Random Forest menguji apakah ROE dan DER menjelaskan kategori."),
]

GLOSARIUM = {
    "PER (Price to Earnings Ratio)": "Harga / laba per saham. Makin rendah, makin murah "
                                     "terhadap laba.",
    "PBV (Price to Book Value)": "Harga / nilai buku per saham. PBV 1 = harga setara "
                                 "nilai buku.",
    "ROE (Return on Equity)": "Laba bersih / ekuitas (%). Efisiensi menghasilkan laba dari "
                              "modal sendiri.",
    "DER (Debt to Equity Ratio)": "Total utang / ekuitas. Makin tinggi, makin bergantung "
                                  "pada utang.",
    "Z-score relatif sektor": "Jarak dari rata-rata sektor dalam satuan simpangan baku. "
                              "0 = setara rata-rata sektor.",
    "Winsorizing": "Nilai di atas persentil tertentu diganti dengan nilai persentil itu "
                   "agar angka ekstrem tidak mendominasi.",
    "K-Means": "Algoritma pengelompokan berdasarkan jarak ke titik pusat (centroid).",
    "Silhouette": "Seberapa khas emiten untuk cluster-nya (−1 s.d. 1).",
    "Random Forest": "Kumpulan pohon keputusan; di sini menebak kategori hanya dari ROE "
                     "dan DER.",
}

FAQ = {
    "Apakah Relatif Rendah (Undervalue) berarti layak beli?":
        "Tidak. Undervalue, Fair Value, dan Overvalue adalah label operasional: PER dan PBV "
        "relatif terhadap rata-rata sektornya, bukan hasil perhitungan nilai intrinsik. "
        "Gunakan sebagai titik awal riset, bukan keputusan akhir.",
    "Mengapa PER tinggi bisa masuk Relatif Rendah?":
        "Pembandingnya adalah sektor sendiri. Di sektor ber-PER tinggi, emiten itu tetap "
        "tergolong murah.",
    "Apa arti Relatif Sedang (Fair Value)?":
        "Cluster dengan skor centroid di antara Rendah dan Tinggi. Pada data saat ini "
        "didominasi emiten dengan PER sangat tinggi tetapi PBV setara sektor.",
    "Mengapa ada emiten yang tidak muncul?":
        "Emiten dengan data kosong, dan (pada data positif) PER/PBV ≤ 0, dikeluarkan. "
        "Pada dataset penelitian, saham FREN tidak dimasukkan dalam perhitungan karena "
        "tidak memiliki data PER, PBV, ROE, dan DER.",
    "Mengapa prediksi Random Forest bisa berbeda dari kategori?":
        "Random Forest hanya melihat ROE dan DER. Perbedaan berarti profil fundamentalnya "
        "tidak khas untuk kelompok valuasinya.",
}


def render() -> None:
    ui.page_header("Panduan", "Alur kerja, kategori, dan istilah.")

    t1, t2, t3, t4 = st.tabs([":material/route: Alur Kerja", ":material/label: Kategori",
                              ":material/menu_book: Glosarium", ":material/help: FAQ"])

    with t1:
        steps = "".join(
            f"<div class='step'><div class='num'>{i}</div><div class='ttl'>{ui.esc(t)}</div>"
            f"<div class='txt'>{ui.esc(d)}</div></div>"
            for i, (t, d) in enumerate(LANGKAH, start=1)
        )
        st.html(f"<div class='steps'>{steps}</div>")
        st.write("")
        menu = [
            ("Beranda / Screener", "Tabel seluruh saham, visual clustering, filter sektor, "
                                   "kategori, rentang PER dan PBV."),
            ("Detail Saham", "PER, PBV, ROE, DER satu saham, posisi dalam cluster, "
                             "perbandingan rata-rata sektor, hasil Random Forest."),
            ("Perbandingan Sektor", "Rata-rata PER dan PBV per sektor, komposisi cluster, "
                                    "sebaran PER terhadap PBV."),
            ("Evaluasi Model", "Elbow, Silhouette, DBI, confusion matrix, feature importance, "
                               "accuracy, precision, recall, F1."),
            ("Tentang", "Identitas skripsi, penulis, dan dosen pembimbing."),
            ("Kartu nama di sidebar", "Profil: ubah nama dan kata sandi."),
        ]
        if auth.is_admin():
            menu += [
                ("Pengguna", "Kelola akun: tambah, ubah peran, reset sandi, nonaktifkan."),
                ("Data & Model", "Data perhitungan, dataset global, pra-pemrosesan, "
                                 "verifikasi, ekspor Excel."),
            ]
        ui.table({"Menu": [m for m, _ in menu], "Fungsi": [f for _, f in menu]},
                     hide_index=True, width="stretch")

    with t2:
        for k in config.LABEL_ORDER:
            with st.container(border=True):
                st.html(f"<div style='display:flex;gap:12px;align-items:center'>"
                        f"{ui.badge_html(k)}<span style='color:var(--muted)'>"
                        f"{ui.esc(config.LABEL_DESC[k])}</span></div>")

    with t3:
        q = st.text_input("Cari istilah", placeholder="mis. silhouette",
                          icon=":material/search:").lower()
        for istilah, arti in GLOSARIUM.items():
            if q and q not in istilah.lower() and q not in arti.lower():
                continue
            with st.expander(istilah):
                st.write(arti)

    with t4:
        for tanya, jawab in FAQ.items():
            with st.expander(tanya):
                st.write(jawab)
