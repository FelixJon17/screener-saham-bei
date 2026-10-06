"""
config.py
Satu-satunya sumber kebenaran untuk parameter aplikasi.

Aplikasi berada satu folder dengan notebook dan TIDAK melatih model sendiri.
Seluruh hasil (label cluster, model K-Means, model Random Forest, evaluasi k,
statistik sektor) dibaca dari output_revisi/ yang ditulis oleh sel terakhir
`535230119_SkripsiFelix_revisi.ipynb`.
Parameter metodologis di bawah ini hanya dipakai untuk (1) merekonstruksi
jejak pra-pemrosesan dan pembagian data uji agar dapat diverifikasi, dan
(2) ditampilkan kepada pengguna. Nilainya HARUS sama dengan notebook.
"""
from pathlib import Path

# --------------------------------------------------------------------------
# Path
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
# Set hasil bawaan: folder output notebook revisi dan dataset mentah yang dibaca
# notebook. Menjalankan ulang notebook otomatis memperbarui aplikasi.
MODEL_DIR = BASE_DIR / "output_revisi"
DEFAULT_RAW_PATH = BASE_DIR / "Dataset September.xlsx"

# Nama berkas hasil ekspor notebook (sel terakhir notebook)
ART_TABLE = "hasil_clustering.xlsx"
ART_KMEANS = "model_kmeans.joblib"
ART_RF = "model_random_forest.joblib"
ART_SECTOR = "statistik_sektor.csv"
ART_KEVAL = "evaluasi_k.csv"
ART_RF_CV = "evaluasi_rf_repeated_cv.csv"          # hanya ada di versi revisi
ARTIFACTS_REQUIRED = [ART_TABLE, ART_KMEANS, ART_RF]
ARTIFACTS_OPTIONAL = [ART_SECTOR, ART_KEVAL, ART_RF_CV]
ARTIFACT_NAMES = ARTIFACTS_REQUIRED + ARTIFACTS_OPTIONAL

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

WINSOR_PERCENTILE = 95          # upper-only, PER/PBV market-wide; ROE/DER dari data latih
ZSCORE_DDOF = 1
K_RANGE_NOTEBOOK = "2–6"
KMEANS_N_INIT = 50
RANDOM_STATE = 42

TEST_SIZE = 0.20                # train_test_split(..., stratify=y, random_state=42)
SPLIT_RANDOM_STATE = 42
GRID_CV_FOLDS = 5
REPEATED_CV = "5-fold × 10 ulangan"
PERM_REPEATS = 30

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

# Label persis seperti di notebook (sel 11)
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
COLOR_MAP = {
    LABEL_LOW: "#16A34A",
    LABEL_MID: "#D97706",
    LABEL_HIGH: "#DC2626",
}
COLOR_FALLBACK = "#64748B"
COLOR_PRIMARY = "#2563EB"

LABEL_SHORT = {
    LABEL_LOW: "Relatif Rendah",
    LABEL_MID: "Relatif Sedang",
    LABEL_HIGH: "Relatif Tinggi",
}
LABEL_DESC = {
    LABEL_LOW: "PER dan PBV di bawah rata-rata sektor.",
    LABEL_MID: "Sinyal campuran: umumnya PER tinggi, PBV setara sektor.",
    LABEL_HIGH: "PER dan PBV di atas rata-rata sektor.",
}
