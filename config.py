from datetime import timedelta, timezone
from pathlib import Path

# --------------------------------------------------------------------------
# Path
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
# Seluruh hasil dihitung langsung dari dataset (src/trainer.py), tanpa berkas
# hasil perantara. Konfigurasi data perhitungan (dipilih admin):
#   "positif" : PER > 0 dan PBV > 0 (627 saham, sesuai proposal)
#   "semua"   : seluruh saham kecuali nilai kosong (959 saham)
DATA_POSITIF = "positif"
DATA_SEMUA = "semua"
DATA_MODES = {
    DATA_POSITIF: "Data positif (PER > 0 dan PBV > 0)",
    DATA_SEMUA: "Seluruh data (kecuali nilai kosong)",
}
DEFAULT_RAW_PATH = BASE_DIR / "Dataset September.xlsx"   # dataset penelitian

# --------------------------------------------------------------------------
# Skema kolom (sama dengan notebook)
# --------------------------------------------------------------------------
COL_KODE = "Kode Saham"
COL_SEKTOR = "Sektor"
COL_PER = "PER"
COL_PBV = "PBV"
COL_ROE = "ROE %"
COL_DER = "DER"

REQUIRED_COLUMNS = [COL_KODE, COL_SEKTOR, COL_PER, COL_PBV, COL_ROE, COL_DER]

# Kolom tambahan pada hasil_clustering.xlsx
COL_Z_PER = "PER_z"
COL_Z_PBV = "PBV_z"
COL_CLUSTER = "cluster"
COL_LABEL = "label"
TABLE_COLUMNS = REQUIRED_COLUMNS + [COL_Z_PER, COL_Z_PBV, COL_CLUSTER, COL_LABEL]

CLUSTER_FEATURES = [COL_PER, COL_PBV]
CHARACTERIZATION_FEATURES = [COL_ROE, COL_DER]

# --------------------------------------------------------------------------
# Parameter notebook (untuk rekonstruksi & tampilan, bukan pelatihan)
# --------------------------------------------------------------------------
# Koreksi sektor yang dilakukan di sel 2 notebook
SECTOR_FIXES = {"KETR": "Infrastructures", "VICI": "Consumer Non-Cyclicals"}

WINSOR_PERCENTILE = 95          # upper-only, market-wide (PER/PBV, lalu ROE/DER)
WINSOR_LOWER_PERCENTILE = 5     # batas bawah, hanya untuk konfigurasi data "semua"
ZSCORE_DDOF = 1
K_RANGE_NOTEBOOK = "2–6"
KMEANS_N_INIT = 50
RANDOM_STATE = 42

TEST_SIZE = 0.20                # train_test_split(..., stratify=y, random_state=42)
SPLIT_RANDOM_STATE = 42
RF_N_ESTIMATORS = 100           # class_weight="balanced", parameter lain bawaan, tanpa tuning

IDX_IC_SECTORS = [
    "Energy",
    "Basic Materials",
    "Industrials",
    "Consumer Non-Cyclicals",
    "Consumer Cyclicals",
    "Healthcare",
    "Financials",
    "Properties & Real Estate",
    "Technology",
    "Infrastructures",
    "Transportation & Logistic",
]

# Label persis seperti di notebook (pelabelan 3.1.6)
LABEL_LOW = "Valuasi Relatif Rendah"
LABEL_MID = "Valuasi Relatif Sedang"
LABEL_HIGH = "Valuasi Relatif Tinggi"
LABEL_ORDER = [LABEL_LOW, LABEL_MID, LABEL_HIGH]

# --------------------------------------------------------------------------
# Aplikasi
# --------------------------------------------------------------------------
APP_TITLE = "Pengelompokan Saham BEI Berdasarkan PER dan PBV"
APP_SUBTITLE = "K-Means Clustering & Karakterisasi Random Forest (ROE, DER)"
APP_AUTHOR = "Felix Jonathan - 535230119"
APP_INSTITUTION = "Teknik Informatika, Universitas Tarumanagara"

APP_NAME = "ValuMap"
APP_TAGLINE = "Screener Saham BEI"

# Zona waktu seluruh catatan waktu (login, pendaftaran, unggah dataset, log).
# Server hosting memakai UTC, sehingga waktu dikonversi eksplisit ke WIB.
TIMEZONE = timezone(timedelta(hours=7), "WIB")
LOGO_ICON = BASE_DIR / "assets" / "logo_icon.png"
LOGO_WIDE = BASE_DIR / "assets" / "logo.svg"

# Halaman Tentang (views/tentang.py)
THESIS_TITLE = ("Pengelompokan Saham BEI Berdasarkan PER dan PBV Menggunakan K-Means "
                "Clustering dan Karakterisasi Cluster Menggunakan Random Forest Berbasis "
                "ROE dan DER")
ABOUT_AUTHOR = "Felix Jonathan"
ABOUT_NIM = "535230119"
ABOUT_PRODI = "Program Studi Teknik Informatika"
ABOUT_FAKULTAS = "Fakultas Teknologi Informasi"
ABOUT_UNIV = "Universitas Tarumanagara"
PEMBIMBING_1 = "TONY, S.Kom., M.Kom., Ph.D."
PEMBIMBING_2 = "ARNOLD KAUDIN, S.E., M.M., M.Com., Ph.D."
PEMBIMBING_1_INST = "Universitas Tarumanagara"
PEMBIMBING_2_INST = "Universitas Ciputra"

# --------------------------------------------------------------------------
# Akun, peran, dan penyimpanan aplikasi
# --------------------------------------------------------------------------
DB_PATH = DATA_DIR / "app.db"
UPLOAD_DIR = DATA_DIR / "uploads"

ROLE_ADMIN = "admin"
ROLE_USER = "user"
ROLE_LABEL = {ROLE_ADMIN: "Administrator", ROLE_USER: "Pengguna"}

SEED_ACCOUNTS = [
    {"username": "admin", "password": "admin123",
     "full_name": "Administrator", "role": ROLE_ADMIN},
    {"username": "investor", "password": "investor123",
     "full_name": "Investor Demo", "role": ROLE_USER},
]

PASSWORD_MIN_LENGTH = 6
PBKDF2_ITERATIONS = 200_000
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCK_SECONDS = 30
ALLOW_SELF_REGISTER = True

# --------------------------------------------------------------------------
# Tampilan
# --------------------------------------------------------------------------
# Palet antarmuka (sama dengan .streamlit/config.toml dan assets/style.css)
NAVY = "#091540"
ROYAL = "#1B2CC1"
PERI = "#7692FF"
SKY = "#ABD2FA"
INK = "#0E1A45"       # teks utama
MUTED = "#5B6B92"     # teks sekunder
LINE = "#D5E1F5"      # garis & border

# Warna kategori valuasi tetap semantik (hijau = murah, merah = mahal) agar
# langsung terbaca seperti pada screener saham pada umumnya.
COLOR_MAP = {
    LABEL_LOW: "#12A150",
    LABEL_MID: "#E08A00",
    LABEL_HIGH: "#E0323C",
}
COLOR_FALLBACK = MUTED
COLOR_PRIMARY = ROYAL

# Label operasional (batasan rancangan butir 8–9 dan Spesifikasi 1.5): kategori
# relatif rendah, sedang, tinggi dibaca sebagai undervalue, fair value, overvalue.
# Bukan hasil perbandingan nilai intrinsik.
LABEL_OPS = {
    LABEL_LOW: "Undervalue",
    LABEL_MID: "Fair Value",
    LABEL_HIGH: "Overvalue",
}
LABEL_SHORT = {k: f"{k.replace('Valuasi ', '')} ({v})" for k, v in LABEL_OPS.items()}
# Nama ringkas untuk sumbu grafik dan matriks (Rendah / Sedang / Tinggi)
LABEL_TINY = {k: k.replace("Valuasi Relatif ", "") for k in LABEL_OPS}
LABEL_DESC = {
    LABEL_LOW: "PER dan PBV di bawah rata-rata sektor.",
    LABEL_MID: "Sinyal campuran: umumnya PER tinggi, PBV setara sektor.",
    LABEL_HIGH: "PER dan PBV di atas rata-rata sektor.",
}
