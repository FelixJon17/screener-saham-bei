# Skripsi Felix — Notebook & Saham Screener

Notebook analisis dan aplikasi web Streamlit untuk skripsi *Pengelompokan Saham BEI Berdasarkan PER dan PBV Menggunakan K-Means Clustering dan Karakterisasi Cluster Menggunakan Random Forest Berbasis ROE dan DER*.

Felix Jonathan — 535230119 — Teknik Informatika, Universitas Tarumanagara

## Satu folder, satu sumber hasil

```
PYTHON/
├── Dataset September.xlsx                 dataset mentah
├── 535230119_SkripsiFelix.ipynb           notebook asli    → output/
├── 535230119_SkripsiFelix_revisi.ipynb    notebook revisi  → output_revisi/
├── output_revisi/                         hasil yang DIBACA aplikasi
└── app.py, config.py, src/, views/, ...   aplikasi screener
```

Aplikasi **tidak melatih model sendiri**. Label, model K-Means, model Random Forest, evaluasi k, dan statistik sektor dibaca langsung dari `output_revisi/`. Dataset mentah `Dataset September.xlsx` dipakai untuk merekonstruksi jejak pra-pemrosesan dan memverifikasi hasil. Angka di aplikasi identik dengan notebook:

| | Notebook revisi | Aplikasi |
|---|---|---|
| Silhouette / DBI (k=3) | 0,6731 / 0,7969 | 0,6731 / 0,7969 |
| Accuracy / F1-macro RF (data uji) | 0,7063 / 0,5216 | 0,7063 / 0,5216 |
| Jumlah per label | 511 / 45 / 71 | 511 / 45 / 71 |

## Menjalankan

```bash
git clone https://github.com/FelixJon17/screener-saham-bei.git
cd screener-saham-bei
pip install -r requirements.txt
python -m streamlit run app.py
```

Akun demo: `admin` / `admin123` (Administrator) dan `investor` / `investor123` (Pengguna). Basis data akun dibuat otomatis di `data/app.db` (tidak ikut di-commit). Ganti kata sandi admin lewat halaman **Profil** bila aplikasi dipasang di server publik.

## Memperbarui hasil

- **Data di folder ini:** ganti `Dataset September.xlsx` (atau ubah nama berkas di sel 2 notebook dan `config.DEFAULT_RAW_PATH`), jalankan ulang notebook revisi, lalu muat ulang halaman aplikasi. Cache aplikasi dikunci pada waktu modifikasi berkas, jadi hasil baru langsung terbaca.
- **Hasil dari tempat lain** (misalnya notebook dijalankan di Colab): masuk sebagai admin → **Kelola Data & Model** → **Impor hasil notebook**, lalu unggah isi `output_revisi/` dan dataset mentahnya. Set impor disimpan di `data/uploads/` dan dapat diaktifkan atau dihapus dari halaman yang sama.

| Berkas | Status |
|---|---|
| `hasil_clustering.xlsx`, `model_kmeans.joblib`, `model_random_forest.joblib` | wajib |
| `statistik_sektor.csv`, `evaluasi_k.csv`, `evaluasi_rf_repeated_cv.csv` | opsional |
| dataset mentah (`.xlsx`/`.csv`) | opsional |

Hasil notebook asli (`output/`) juga dapat diimpor; model RF-nya dibungkus otomatis dengan batas winsorizing P95 seluruh data seperti di notebook asli.

## Verifikasi konsistensi

Setiap kali hasil dimuat, `src/pipeline.verify` memeriksa:

- model K-Means memprediksi ulang label yang sama untuk seluruh saham di tabel notebook;
- nama label sesuai notebook;
- pra-pemrosesan notebook (koreksi sektor KETR/VICI → dropna → PER/PBV > 0 → winsorizing P95 → Z-score sektor) direkonstruksi dari dataset mentah, lalu daftar saham, sektor, dan Z-score-nya dibandingkan dengan tabel notebook.

Data uji Random Forest direkonstruksi dengan `train_test_split(test_size=0.2, stratify=y, random_state=42)` yang sama dengan notebook. Hasilnya tampil di tab **Verifikasi** pada halaman Evaluasi Model, dan juga lewat baris perintah:

```bash
python export_results.py
python export_results.py --folder output --out hasil_notebook_asli.xlsx
```

## Struktur kode aplikasi

```
├── app.py                  titik masuk, login, navigasi per peran
├── config.py               path, nama berkas hasil, parameter & label (sama dengan notebook)
├── export_results.py       muat hasil + verifikasi + ekspor Excel (CLI)
├── data/                   app.db (akun, watchlist, riwayat impor, log) dan uploads/
├── src/
│   ├── winsorizer.py       kelas WinsorizerAtas (salinan dari notebook) untuk unpickle
│   ├── pipeline.py         memuat hasil notebook, membangun PipelineOutput, verifikasi
│   ├── data_loader.py      baca & validasi dataset mentah / tabel hasil
│   ├── preprocessing.py    rekonstruksi sel 2–8 notebook (jejak & verifikasi)
│   ├── clustering.py       silhouette per saham, centroid, profil, rekomendasi k
│   ├── classification.py   evaluasi RF hasil notebook pada data uji yang sama
│   ├── dataset_store.py    set hasil aktif, impor, riwayat
│   └── export.py, db.py, auth.py, ui.py
├── views/                  halaman (beranda, detail, sektor, evaluasi, admin, ...)
├── assets/, .streamlit/    tampilan
```

## Catatan

- **Versi scikit-learn.** Model `.joblib` dibuat dengan scikit-learn 1.9.0. Gunakan versi yang sama untuk notebook dan aplikasi.
- **Kelas `WinsorizerAtas`.** Model RF revisi menyimpan kelas ini sebagai `__main__.WinsorizerAtas`. Jika kelas di notebook diubah, salin perubahan yang sama ke `src/winsorizer.py`.
- **Keamanan impor.** Berkas `.joblib` adalah pickle dan dieksekusi saat dimuat. Hanya admin yang dapat mengimpor; impor hanya berkas yang dihasilkan sendiri dari notebook.
- **Pemilihan k = 3** tidak didukung metrik mana pun (Elbow 4, Silhouette 2, DBI 4). Aplikasi menampilkan peringatan ini di Evaluasi Model; justifikasinya perlu ditulis di skripsi.
- **Label "Valuasi Relatif Sedang"** pada data September berisi saham dengan PER sangat tinggi (median 148) tetapi PBV mendekati rata-rata sektor. Jelaskan ini di BAB IV agar label tidak dibaca sebagai "wajar".
- Sesi login disimpan di memori Streamlit (muat ulang halaman berarti masuk ulang), tanpa HTTPS bawaan dan tanpa pemulihan kata sandi lewat surel.
