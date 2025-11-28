from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

# 프로젝트 내부 경로
from data.paths import (
    AOI_SEOUL_HANGANG_2KM,
    CONFIG_DIR,
    DATA_S1_RAW_DRY,
    DATA_S1_RAW_FLOOD,
)

# -----------------------------
# 1) .env 로딩
# -----------------------------
ENV_PATH = CONFIG_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    # 혹시 루트에 .env 있을 수도 있으니 한 번 더 시도
    load_dotenv()

# 기본 엔드포인트 (env에서 override 가능)
TOKEN_URL = os.getenv(
    "COPERNICUS_TOKEN_URL",
    "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
)
ODATA_URL = os.getenv(
    "COPERNICUS_ODATA_URL",
    "https://catalogue.dataspace.copernicus.eu/odata/v1",
)
DOWNLOAD_URL = os.getenv(
    "COPERNICUS_DOWNLOAD_URL",
    "https://download.dataspace.copernicus.eu/odata/v1",
)


# -----------------------------
# 2) Auth: 토큰 + Session
# -----------------------------
def get_access_token() -> str:
    username = os.getenv("COPERNICUS_USERNAME")
    password = os.getenv("COPERNICUS_PASSWORD")
    totp = os.getenv("COPERNICUS_TOTP")  # 2FA 안 쓰면 None

    if not username or not password:
        raise RuntimeError(
            "COPERNICUS_USERNAME / COPERNICUS_PASSWORD 환경변수를 설정해주세요 "
            "(config/.env 참고)."
        )

    data = {
        "grant_type": "password",
        "client_id": "cdse-public",
        "username": username,
        "password": password,
    }
    if totp:
        data["totp"] = totp

    resp = requests.post(TOKEN_URL, data=data, timeout=60)
    resp.raise_for_status()
    token_json = resp.json()
    access_token = token_json.get("access_token")
    if not access_token:
        raise RuntimeError(
            f"토큰 응답에 access_token 없음: keys={list(token_json.keys())}"
        )
    return access_token


def get_session() -> requests.Session:
    token = get_access_token()
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


# -----------------------------
# 3) AOI GeoJSON -> geography WKT
# -----------------------------
def aoi_geojson_to_geography_wkt(geojson_path: Path) -> str:
    """
    AOI GeoJSON (Polygon)을 읽어서
    OData.CSC.Intersects(area=geography'SRID=4326;POLYGON((...))')
    에 바로 넣을 수 있는 문자열을 만든다.

    ※ 전제: geometry.type == "Polygon"
    """
    geojson_path = Path(geojson_path)
    if not geojson_path.exists():
        raise FileNotFoundError(f"AOI 파일 없음: {geojson_path}")

    with geojson_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # FeatureCollection / 단일 Feature 모두 처리
    if data.get("type") == "FeatureCollection":
        features = data.get("features", [])
        if not features:
            raise ValueError("FeatureCollection 안에 feature가 없습니다.")
        geom = features[0]["geometry"]
    elif data.get("type") == "Feature":
        geom = data["geometry"]
    else:
        # 그냥 geometry라고 가정
        geom = data

    if geom.get("type") != "Polygon":
        raise ValueError(
            f"현재 코드는 Polygon AOI만 지원합니다. geometry.type={geom.get('type')}"
        )

    # 첫 번째 링(외곽 링)만 사용
    coords = geom["coordinates"][0]  # [[lon, lat], [lon, lat], ...]
    # 폴리곤은 시작점과 끝점이 같아야 함 (안 그러면 OData에서 에러)
    if coords[0] != coords[-1]:
        coords.append(coords[0])

    coord_str = ", ".join(f"{lon} {lat}" for lon, lat in coords)
    wkt_polygon = f"POLYGON(({coord_str}))"

    # 결과: geography'SRID=4326;POLYGON((lon lat, ...))'
    return f"geography'SRID=4326;{wkt_polygon}'"


# -----------------------------
# 4) Sentinel-1 검색
# -----------------------------
def search_s1_grd(
    session: requests.Session,
    *,
    start_iso: str,
    end_iso: str,
    aoi_geog_wkt: str,
    product_type: str = "IW_GRDH_1S-COG",  # Sentinel-1 GRD COG_SAFE 타입 예시
    top: int = 5,
) -> List[Dict[str, Any]]:
    """
    Sentinel-1 GRD 제품 검색
    - start_iso, end_iso: 'YYYY-MM-DDTHH:MM:SS.000Z' 형태 문자열
    - aoi_geog_wkt: aoi_geojson_to_geography_wkt() 결과
    """
    # 참고: OData 예시와 동일한 스타일
    # Collection/Name eq 'SENTINEL-1'
    # Attributes/... productType == 'IW_GRDH_1S-COG'
    # OData.CSC.Intersects(area=geography'SRID=4326;POLYGON(...))
    # ContentDate/Start gt 2022-05-20T00:00:00.000Z ...
    filter_expr = (
        "Collection/Name eq 'SENTINEL-1' and "
        f"OData.CSC.Intersects(area={aoi_geog_wkt}) and "
        "Attributes/OData.CSC.StringAttribute/any("
        "att:att/Name eq 'productType' and "
        f"att/OData.CSC.StringAttribute/Value eq '{product_type}'"
        ") and "
        f"ContentDate/Start gt {start_iso} and "
        f"ContentDate/Start lt {end_iso}"
    )

    params = {
        "$filter": filter_expr,
        "$orderby": "ContentDate/Start desc",
        "$top": str(top),
    }

    url = f"{ODATA_URL.rstrip('/')}/Products"
    resp = session.get(url, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data.get("value", [])


# -----------------------------
# 5) Sentinel-1 다운로드
# -----------------------------
def download_product_zip(
    session: requests.Session,
    *,
    product_id: str,
    out_dir: Path,
    filename: Optional[str] = None,
) -> Path:
    """
    Products(<Id>)/$zip 형태로 Sentinel-1 제품 zip 다운로드.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    base = DOWNLOAD_URL.rstrip("/")
    url = f"{base}/Products({product_id})/$zip"

    resp = session.get(url, stream=True, timeout=600)
    resp.raise_for_status()

    if filename is None:
        filename = f"{product_id}.zip"

    out_path = out_dir / filename
    with out_path.open("wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    return out_path


# -----------------------------
# 6) 메인: 홍수 1장 + 평시 1장 받기
# -----------------------------
def main():
    # (1) 세션 만들기
    session = get_session()

    # (2) AOI -> geography WKT
    aoi_geog = aoi_geojson_to_geography_wkt(AOI_SEOUL_HANGANG_2KM)

    # (3) 날짜 범위 설정
    # TODO: 실제 홍수 날짜/평시 날짜로 수정해서 쓰면 됨
    # 형식: 날짜만 신경쓰고, 시간은 00:00/23:59 정도로 잡는다.

    # 예시: 홍수 기간
    flood_start_date = "2020-08-01"
    flood_end_date = "2020-08-10"
    flood_start_iso = f"{flood_start_date}T00:00:00.000Z"
    flood_end_iso = f"{flood_end_date}T23:59:59.999Z"

    # 예시: 평시 기간
    dry_start_date = "2020-05-01"
    dry_end_date = "2020-05-31"
    dry_start_iso = f"{dry_start_date}T00:00:00.000Z"
    dry_end_iso = f"{dry_end_date}T23:59:59.999Z"

    # (4) 홍수 기간에서 검색 후 1장 다운로드
    flood_products = search_s1_grd(
        session,
        start_iso=flood_start_iso,
        end_iso=flood_end_iso,
        aoi_geog_wkt=aoi_geog,
        top=5,
    )
    if not flood_products:
        print("[WARN] 홍수 기간에 해당하는 Sentinel-1 제품이 없습니다.")
    else:
        flood_first = flood_products[0]
        pid = flood_first["Id"]
        name = flood_first["Name"]
        print("[INFO] 홍수용 제품 선택:", name)
        out_path = download_product_zip(
            session,
            product_id=pid,
            out_dir=DATA_S1_RAW_FLOOD,
            filename=f"{name}.zip",
        )
        print("[INFO] 홍수 제품 다운로드 완료:", out_path)

    # (5) 평시 기간에서 검색 후 1장 다운로드
    dry_products = search_s1_grd(
        session,
        start_iso=dry_start_iso,
        end_iso=dry_end_iso,
        aoi_geog_wkt=aoi_geog,
        top=5,
    )
    if not dry_products:
        print("[WARN] 평시 기간에 해당하는 Sentinel-1 제품이 없습니다.")
    else:
        dry_first = dry_products[0]
        pid = dry_first["Id"]
        name = dry_first["Name"]
        print("[INFO] 평시용 제품 선택:", name)
        out_path = download_product_zip(
            session,
            product_id=pid,
            out_dir=DATA_S1_RAW_DRY,
            filename=f"{name}.zip",
        )
        print("[INFO] 평시 제품 다운로드 완료:", out_path)


if __name__ == "__main__":
    main()
