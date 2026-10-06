"""
views/panduan.py -- Panduan & Glosarium

Cara kerja screener, arti kategori, dan istilah, ditulis singkat.
"""
from __future__ import annotations

import streamlit as st

import config
from src import auth, ui

LANGKAH = [
    ("Data", "PER, PBV, ROE, DER, dan sektor setiap emiten BEI."),
    ("Bersihkan", "Buang data kosong dan PER/PBV ≤ 0; batasi nilai ekstrem di "
                  f"P{config.WINSOR_PERCENTILE}."),
    ("Relatif sektor", "PER dan PBV diubah menjadi Z-score terhadap sektornya."),
    ("Kelompokkan", "K-Means membagi emiten ke 3 kategori valuasi relatif."),
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
    "Apakah Relatif Rendah berarti layak beli?":
        "Tidak. Artinya PER dan PBV rendah dibanding sektornya. Gunakan sebagai titik awal "
        "riset, bukan keputusan akhir.",
    "Mengapa PER tinggi bisa masuk Relatif Rendah?":
        "Pembandingnya adalah sektor sendiri. Di sektor ber-PER tinggi, emiten itu tetap "
        "tergolong murah.",
    "Apa arti Relatif Sedang?":
        "Sinyal campuran. Pada data saat ini didominasi emiten dengan PER sangat tinggi "
        "tetapi PBV setara sektor, bukan berarti 'wajar'.",
    "Mengapa ada emiten yang tidak muncul?":
        "Emiten dengan data tidak lengkap atau PER/PBV ≤ 0 (rugi atau ekuitas negatif) "
        "dikeluarkan.",
    "Mengapa prediksi Random Forest bisa berbeda dari kategori?":
        "Random Forest hanya melihat ROE dan DER. Perbedaan berarti profil fundamentalnya "
        "tidak khas untuk kelompok valuasinya.",
}


def render() -> None:
    ui.page_header("Panduan", "Cara kerja, kategori, dan istilah.")

    t1, t2, t3, t4 = st.tabs([":material/route: Cara kerja", ":material/label: Kategori",
                              ":material/menu_book: Glosarium", ":material/help: Tanya jawab"])

    with t1:
        steps = "".join(
            f"<div class='step'><div class='num'>{i}</div><div class='ttl'>{ui.esc(t)}</div>"
            f"<div class='txt'>{ui.esc(d)}</div></div>"
            for i, (t, d) in enumerate(LANGKAH, start=1)
        )
        st.html(f"<div class='steps'>{steps}</div>")
        st.write("")
        menu = [
            ("Screener", "Filter emiten; klik titik atau baris untuk pratinjau."),
            ("Detail Saham", "Ringkasan, persentil sektor, emiten sejenis, cek fundamental."),
            ("Sektor", "Tolok ukur dan komposisi kategori per sektor."),
            ("Watchlist", "Emiten yang Anda pantau."),
        ]
        if auth.is_admin():
            menu += [
                ("Dasbor", "Pengguna, status data, dan aktivitas."),
                ("Evaluasi Model", "Elbow, Silhouette, DBI, confusion matrix, verifikasi."),
                ("Data & Model", "Impor hasil notebook dan ekspor Excel."),
                ("Pengguna", "Kelola akun dan peran."),
            ]
        st.dataframe({"Menu": [m for m, _ in menu], "Fungsi": [f for _, f in menu]},
                     hide_index=True, width="stretch")

    with t2:
        for k in config.LABEL_ORDER:
            with st.container(border=True):
                st.html(f"<div style='display:flex;gap:12px;align-items:center'>"
                        f"{ui.badge_html(k)}<span style='color:#475569'>"
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

    st.divider()
    ui.disclaimer()
