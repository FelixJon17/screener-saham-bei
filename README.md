# ValuMap — Screener Saham BEI

Notebook analisis dan aplikasi web Streamlit untuk skripsi *Pengelompokan Saham BEI Berdasarkan PER dan PBV Menggunakan K-Means Clustering dan Karakterisasi Cluster Menggunakan Random Forest Berbasis ROE dan DER*.

Felix Jonathan — 535230119 — Teknik Informatika, Universitas Tarumanagara

## Satu dataset, dihitung langsung

```
PYTHON/
├── Dataset September.xlsx                 dataset penelitian (Kode, Sektor, PER, PBV, ROE, DER)
├── 535230119_SkripsiFelix.ipynb           notebook (mengikuti Bab III proposal)
└── app.py, config.py, src/, views/, ...   aplikasi screener
```

Aplikasi **menghitung seluruh hasil langsung dari dataset** dengan prosedur yang sama dengan notebook (`src/trainer.py`): pra-pemrosesan, Z-score per sektor, evaluasi K = 2–6, K-Means K = 3, pelabelan, dan Random Forest. Tidak ada berkas hasil perantara (Excel/joblib). Hasil dihitung sekali (±3–5 detik) lalu disimpan di cache. Angka di aplikasi identik dengan notebook:

| | Notebook | Aplikasi |
|---|---|---|
| Silhouette / DBI (K = 3) | 0,6731 / 0,7969 | 0,6731 / 0,7969 |
| Accuracy / F1-macro RF (data uji) | 0,6905 / 0,4687 | 0,6905 / 0,4687 |
| Jumlah per label | 511 / 45 / 71 | 511 / 45 / 71 |

## Konfigurasi data

Data perhitungan dipilih admin di **Data & Model**, dan di notebook lewat variabel `DATA` di sel "Konfigurasi Data":

- `"positif"` (bawaan, sesuai proposal): PER > 0 dan PBV > 0, 627 saham, winsorizing atas P95.
- `"semua"`: 959 saham kecuali FREN yang kosong, winsorizing dua sisi P5–P95.

## Menjalankan

```bash
git clone https://github.com/FelixJon17/screener-saham-bei.git
cd screener-saham-bei
pip install -r requirements.txt
python -m streamlit run app.py
```

Akun demo: `admin` / `admin123` (Administrator) dan `investor` / `investor123` (Pengguna). Basis data akun dibuat otomatis di `data/app.db` (tidak ikut di-commit). Ganti kata sandi admin lewat halaman **Profil** bila aplikasi dipasang di server publik.

## Memperbarui data

- **Dataset penelitian:** ganti `Dataset September.xlsx` (atau ubah `config.DEFAULT_RAW_PATH`), lalu muat ulang aplikasi. Cache dikunci pada waktu modifikasi berkas, jadi hasil baru langsung dihitung.
- **Dataset global (admin):** **Data & Model → Unggah dataset**, lalu unggah Excel/CSV berisi enam kolom wajib. Dataset disimpan di `data/uploads/` dan dapat diaktifkan atau dihapus di tab Riwayat.
- **Dataset pribadi (pengguna):** **Beranda → Unggah dataset**. Hasilnya hanya dipakai akun tersebut (`data/pribadi/<username>/`).

## Verifikasi konsistensi

Setiap kali hasil dihitung, `src/pipeline.verify` memeriksa:

- model K-Means memprediksi ulang label yang sama untuk seluruh saham;
- nama label sesuai aturan pelabelan 3.1.6;
- Z-score tiap sektor berrata-rata 0 dan bersimpangan baku 1;
- setiap kategori cukup untuk split stratified;
- tidak ada nilai kosong pada data yang dikelompokkan.

Hasilnya tampil di tab **Verifikasi** pada halaman Data & Model, dan juga lewat baris perintah:

```bash
python export_results.py                     # dataset penelitian, data positif
python export_results.py --data semua        # seluruh data
```

## Struktur kode aplikasi

```
├── app.py                  titik masuk, login, navigasi per peran
├── config.py               path, parameter & label (sama dengan notebook)
├── export_results.py       hitung + verifikasi + ekspor Excel (CLI)
├── data/                   app.db (akun, pengaturan, riwayat dataset, log), uploads/, pribadi/
├── src/
│   ├── trainer.py          prosedur notebook: pra-pemrosesan, K-Means, pelabelan, Random Forest
│   ├── pipeline.py         merangkai hasil menjadi PipelineOutput, verifikasi
│   ├── data_loader.py      baca & validasi dataset
│   ├── preprocessing.py    pra-pemrosesan sel 3.1.2–3.1.3 (jejak pra-pemrosesan)
│   ├── clustering.py       silhouette per saham, centroid, profil, rekomendasi K
│   ├── classification.py   evaluasi RF pada data uji yang sama dengan notebook
│   ├── compare.py          analisis sensitivitas K (3.1.4)
│   ├── dataset_store.py    dataset aktif: penelitian, global (admin), pribadi (pengguna)
│   └── export.py, db.py, auth.py, ui.py, theme.py, winsorizer.py
├── views/                  halaman (beranda, detail, sektor, evaluasi, admin, ...)
├── assets/, .streamlit/    tampilan
```

## Catatan

- **Versi scikit-learn.** Gunakan versi yang sama dengan notebook (`scikit-learn>=1.9,<1.10`, sesuai `requirements.txt`) agar hasil identik.
- **Pemilihan K = 3** mengikuti proposal 3.1.4: dipakai karena Silhouette 0,6731 ≥ 0,51, walaupun Silhouette terbaik di K = 2 dan DBI terbaik di K = 4. Keduanya ditampilkan sebagai analisis sensitivitas di Evaluasi Model.
- **Label "Valuasi Relatif Sedang"** pada data September berisi saham dengan PER sangat tinggi (median 148) tetapi PBV mendekati rata-rata sektor.
- Sesi login disimpan sebagai cookie bertanda tangan HMAC selama 7 hari (diset lewat JavaScript, bukan HttpOnly), tanpa HTTPS bawaan dan tanpa pemulihan kata sandi lewat surel.
