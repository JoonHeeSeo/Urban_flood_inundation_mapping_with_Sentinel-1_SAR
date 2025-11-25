# data/paths.py
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DATA_RAW   = ROOT / "data" / "raw"
DATA_AOI   = ROOT / "data" / "aoi"
DATA_EXT   = ROOT / "data" / "external"
CONFIG_DIR = ROOT / "config"

SEOUL_BOUNDARY = DATA_RAW / "seoul_boundary_dummy.geojson"
KOREA_RIVERS   = DATA_RAW / "hangang_line_dummy.geojson"

AOI_SEOUL_HANGANG_2KM = DATA_AOI / "seoul_hangang_2km_aoi_dummy.geojson"
