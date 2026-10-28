"""
views/panduan.py -- Panduan & Glosarium

Cara kerja screener, arti kategori, dan istilah, ditulis singkat.
"""
from __future__ import annotations

import streamlit as st

import config
from src import auth, ui

LANGKAH = [
    ("Input Data", "Data harus memuat Kode Saham, Sektor, PER, PBV, ROE, dan DER dari saham BEI."),
    ("Pra-Pemrosesan Data", "Menghilangkan missing value, PER/PBV ≤ 0, membatasi nilai ekstrem di "
                  f"P{config.WINSOR_PERCENTILE}."),
    ("Standardisasi Relatif Sektor", "Standardisi PER dan PBV menjadi Z-score terhadap sektornya."),
    ("Pengelompokan", "K-Means Clustering menjadi 3 kategori valuasi relatif."),
    ("Karakterisasi", "Random Forest menguji apakah ROE dan DER menjelaskan kategori."),
    ("Evaluasi Model", "Menggunakan metrik Elbow, Silhouette, dan Davies Bouldiin Index pada K-Means Clustering"
    "Accuracy, Precision."),
]

# Glosarium dari laporan skripsi, hanya istilah yang dipakai di aplikasi ini
# (urut abjad).
GLOSARIUM = [
    ('Accuracy',
     'Metrik evaluasi klasifikasi yang menunjukkan proporsi prediksi benar terhadap keseluruhan data yang dievaluasi.'),
    ('Bursa Efek Indonesia (BEI)',
     'Lembaga yang menyelenggarakan dan menyediakan sistem perdagangan efek di Indonesia.'),
    ('Centroid',
     'Titik pusat suatu cluster pada algoritma K-Means, dihitung sebagai rata-rata seluruh anggota cluster tersebut.'),
    ('Clustering',
     'Proses pengelompokan objek berdasarkan tingkat kemiripan karakteristik tanpa menggunakan label kelas yang telah ditentukan sebelumnya.'),
    ('Confusion Matrix',
     'Tabel evaluasi yang membandingkan kelas aktual dengan kelas hasil prediksi suatu model klasifikasi.'),
    ('Davies-Bouldin Index',
     'Metrik evaluasi clustering yang mengukur kualitas pemisahan antar-cluster, dengan nilai lebih rendah menunjukkan hasil yang lebih baik.'),
    ('Debt to Equity Ratio (DER)',
     'Rasio solvabilitas yang membandingkan total liabilitas perusahaan dengan total ekuitasnya.'),
    ('Decision Tree',
     'Model prediktif berbentuk struktur pohon yang membagi data berdasarkan ambang nilai pada setiap simpul.'),
    ('Elbow Method',
     'Metode penentuan jumlah cluster dengan mengamati titik ketika penurunan nilai inertia mulai melandai membentuk pola menyerupai siku.'),
    ('Fair Value',
     'Kondisi ketika harga pasar suatu aset dinilai telah mencerminkan nilai intrinsik atau karakteristik fundamentalnya secara wajar.'),
    ('Feature Importance',
     'Ukuran kuantitatif kontribusi setiap variabel terhadap proses pengambilan keputusan suatu model prediktif.'),
    ('F1-Score',
     'Rata-rata harmonis antara precision dan recall.'),
    ('Gini Impurity',
     'Ukuran ketidakmurnian suatu simpul pada pohon keputusan, bernilai nol ketika seluruh anggota simpul berasal dari satu kelas yang sama.'),
    ('IDX Stock Screener',
     'Fitur pada situs resmi Bursa Efek Indonesia yang memungkinkan pengguna menyaring dan mengunduh data saham berdasarkan berbagai kriteria.'),
    ('Inertia',
     'Jumlah kuadrat jarak antara setiap data dengan centroid cluster-nya; disebut juga within-cluster sum of squares.'),
    ('K-Means Clustering',
     'Algoritma clustering yang membagi data ke dalam K kelompok berdasarkan kedekatannya terhadap centroid.'),
    ('Mean Decrease in Impurity (MDI)',
     'Ukuran feature importance yang menjumlahkan penurunan ketidakmurnian pada seluruh simpul yang menggunakan suatu variabel, dengan pembobotan proporsi data.'),
    ('Nilai Intrinsik',
     'Estimasi nilai wajar suatu aset yang diperoleh dari analisis kondisi fundamental perusahaan, terlepas dari harga pasar saat ini.'),
    ('Outlier',
     'Data yang nilainya menyimpang secara signifikan dari pola umum sebagian besar data lain.'),
    ('Overvalue',
     'Kondisi ketika harga pasar suatu aset dinilai relatif lebih tinggi dibandingkan nilai intrinsik atau karakteristik fundamentalnya.'),
    ('Precision',
     'Proporsi prediksi positif yang benar-benar termasuk kelas tersebut.'),
    ('Price to Book Value (PBV)',
     'Rasio valuasi yang membandingkan harga pasar saham dengan nilai buku per saham.'),
    ('Price to Earning Ratio (PER)',
     'Rasio valuasi yang membandingkan harga pasar saham dengan laba per saham.'),
    ('Random Forest',
     'Metode ensemble learning yang membangun sejumlah pohon keputusan dan menggabungkan hasilnya melalui pemungutan suara mayoritas.'),
    ('Recall',
     'Proporsi data yang benar-benar termasuk suatu kelas dan berhasil diprediksi dengan benar oleh model.'),
    ('Return on Equity (ROE)',
     'Rasio profitabilitas yang mengukur kemampuan perusahaan menghasilkan laba bersih dari modal sendiri.'),
    ('Sektor',
     'Klasifikasi kelompok industri perusahaan tercatat sesuai standar IDX Industrial Classification (IDX-IC).'),
    ('Silhouette Score',
     'Metrik evaluasi clustering yang mengukur kesesuaian data terhadap cluster-nya sendiri dibandingkan cluster terdekat, dengan rentang nilai −1 hingga 1.'),
    ('Standardisasi Z-Score',
     'Transformasi data dengan mengurangi nilai data dengan rata-ratanya lalu membaginya dengan standar deviasi.'),
    ('Stratified Sampling',
     'Teknik pembagian data yang mempertahankan proporsi setiap kelas pada setiap bagian hasil pembagian.'),
    ('Undervalue',
     'Kondisi ketika harga pasar suatu aset dinilai relatif lebih rendah dibandingkan nilai intrinsik atau karakteristik fundamentalnya.'),
    ('Winsorizing',
     'Metode penanganan nilai ekstrem dengan mengganti nilai di luar ambang persentil tertentu ke nilai ambang tersebut, tanpa menghapus baris data.'),
]

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

    t1, t2, t3, t4 = st.tabs([":material/route: Alur Model", ":material/label: Kategori Cluster",
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
        q = st.text_input("Cari Istilah", placeholder="mis. silhouette",
                          icon=":material/search:").strip().lower()
        # Pencarian hanya pada nama istilah, bukan isi definisinya.
        cocok = [(i, d) for i, d in GLOSARIUM if q in i.lower()]
        st.caption(f"{len(cocok)} dari {len(GLOSARIUM)} istilah")
        if not cocok:
            st.info("Istilah tidak ditemukan.", icon=":material/search_off:")
        for istilah, arti in cocok:
            with st.expander(istilah):
                st.write(arti)

    with t4:
        for tanya, jawab in FAQ.items():
            with st.expander(tanya):
                st.write(jawab)
