# data/paths.py
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# === base dirs ===
DATA_DIR    = ROOT / "data"
CONFIG_DIR  = ROOT / "config"

# --- vector data (행정구역, 하천, AOI 등) ---
DATA_VECTOR = DATA_DIR / "vector"

SEOUL_BOUNDARY = DATA_VECTOR / "seoul_boundary.geojson"
KOREA_RIVERS   = DATA_VECTOR / "hangang_line.geojson"
AOI_SEOUL_HANGANG_2KM = DATA_VECTOR / "seoul_hangang_2km_aoi.geojson"

# --- Sentinel-1 ---
DATA_S1          = DATA_DIR / "sentinel1"
DATA_S1_RAW      = DATA_S1 / "raw"
DATA_S1_RAW_FLOOD = DATA_S1_RAW / "flood"
DATA_S1_RAW_DRY   = DATA_S1_RAW / "dry"

DATA_S1_PRE          = DATA_S1 / "preprocessed"
DATA_S1_PRE_FLOOD    = DATA_S1_PRE / "flood"
DATA_S1_PRE_DRY      = DATA_S1_PRE / "dry"

# --- products (최종 결과) ---
DATA_PRODUCTS = DATA_DIR / "products"
DATA_INUNDATION = DATA_PRODUCTS / "inundation"
DATA_INUNDATION_SEOUL_HANGANG_2KM = DATA_INUNDATION / "seoul_hangang_2km"