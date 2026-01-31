# data/flood_detection.py
"""
홍수 탐지 알고리즘

Change Detection 방식으로 홍수 전/후 SAR 이미지를 비교하여
침수 영역을 추출합니다.

원리:
- 물은 SAR에서 낮은 backscatter(어두움)를 보임
- 홍수 시 새로 물에 잠긴 영역은 backscatter가 급격히 감소
- 변화량(dry - flood)이 임계값 이상인 픽셀 = 침수 영역
"""

import numpy as np
import rasterio
from rasterio.features import shapes
import geopandas as gpd
from shapely.geometry import shape
from pathlib import Path

from paths import (
    DATA_S1_RAW_FLOOD,
    DATA_S1_RAW_DRY,
    DATA_INUNDATION_SEOUL_HANGANG_2KM,
)


def load_sar_image(filepath: Path) -> tuple[np.ndarray, dict]:
    """SAR GeoTIFF 로드"""
    with rasterio.open(filepath) as src:
        data = src.read(1)
        profile = src.profile.copy()
        transform = src.transform
        crs = src.crs
    return data, {"profile": profile, "transform": transform, "crs": crs}


def change_detection(
    dry_image: np.ndarray,
    flood_image: np.ndarray,
    threshold: float = 3.0
) -> np.ndarray:
    """
    Change Detection으로 침수 영역 탐지

    Args:
        dry_image: 평시 SAR 이미지 (dB)
        flood_image: 홍수기 SAR 이미지 (dB)
        threshold: 변화량 임계값 (dB). 기본값 3.0 dB

    Returns:
        Binary mask (1 = 침수, 0 = 비침수)
    """
    # 변화량 계산 (평시 - 홍수기)
    # 양수 = 홍수기에 backscatter 감소 = 물에 잠김
    change = dry_image - flood_image

    # 임계값 적용
    flood_mask = (change > threshold).astype(np.uint8)

    return flood_mask, change


def calculate_flood_area(
    flood_mask: np.ndarray,
    transform: rasterio.Affine,
    crs: str = "EPSG:4326"
) -> dict:
    """
    침수 면적 계산

    Args:
        flood_mask: Binary flood mask
        transform: GeoTIFF transform
        crs: 좌표계

    Returns:
        dict: 면적 통계
    """
    # 픽셀 크기 계산 (도 단위를 미터로 근사 변환)
    # 서울 위도 37.5도 기준: 1도 ≈ 88.8km (위도), 111km (경도) × cos(37.5°) ≈ 88km
    pixel_width_deg = abs(transform.a)
    pixel_height_deg = abs(transform.e)

    # 미터로 변환 (대략적인 값)
    lat_center = 37.55  # 서울 위도
    m_per_deg_lat = 111320  # 위도 1도당 미터
    m_per_deg_lon = 111320 * np.cos(np.radians(lat_center))

    pixel_width_m = pixel_width_deg * m_per_deg_lon
    pixel_height_m = pixel_height_deg * m_per_deg_lat
    pixel_area_m2 = pixel_width_m * pixel_height_m

    # 침수 픽셀 수
    flood_pixels = np.sum(flood_mask == 1)
    total_pixels = flood_mask.size

    # 면적 계산
    flood_area_m2 = flood_pixels * pixel_area_m2
    flood_area_km2 = flood_area_m2 / 1_000_000
    flood_area_ha = flood_area_m2 / 10_000

    return {
        "flood_pixels": int(flood_pixels),
        "total_pixels": int(total_pixels),
        "flood_ratio": float(flood_pixels / total_pixels),
        "pixel_size_m": (pixel_width_m, pixel_height_m),
        "flood_area_m2": flood_area_m2,
        "flood_area_km2": flood_area_km2,
        "flood_area_ha": flood_area_ha,
    }


def mask_to_vector(
    flood_mask: np.ndarray,
    transform: rasterio.Affine,
    crs: str
) -> gpd.GeoDataFrame:
    """
    Binary mask를 벡터(GeoJSON)로 변환

    Args:
        flood_mask: Binary flood mask
        transform: GeoTIFF transform
        crs: 좌표계

    Returns:
        GeoDataFrame: 침수 영역 폴리곤
    """
    # 래스터 → 벡터 변환
    mask = flood_mask.astype(np.int16)
    results = (
        {"geometry": shape(geom), "flood": value}
        for geom, value in shapes(mask, transform=transform)
        if value == 1  # 침수 영역만
    )

    gdf = gpd.GeoDataFrame.from_records(list(results))
    if len(gdf) > 0:
        gdf = gdf.set_geometry("geometry")
        gdf = gdf.set_crs(crs)

    return gdf


def save_flood_mask(
    flood_mask: np.ndarray,
    profile: dict,
    output_path: Path
):
    """Flood mask를 GeoTIFF로 저장"""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    profile.update(dtype=rasterio.uint8, count=1, nodata=255)

    with rasterio.open(output_path, 'w', **profile) as dst:
        dst.write(flood_mask, 1)

    print(f"Flood mask 저장: {output_path}")


def main():
    """홍수 탐지 메인 파이프라인"""

    print("=" * 50)
    print("홍수 탐지 알고리즘 실행")
    print("=" * 50)

    # 1. SAR 이미지 로드
    print("\n[1/5] SAR 이미지 로딩...")
    dry_path = DATA_S1_RAW_DRY / "S1_dry_sample_VV.tif"
    flood_path = DATA_S1_RAW_FLOOD / "S1_flood_sample_VV.tif"

    dry_image, dry_meta = load_sar_image(dry_path)
    flood_image, flood_meta = load_sar_image(flood_path)

    print(f"  평시 이미지: {dry_image.shape}, mean={dry_image.mean():.2f} dB")
    print(f"  홍수 이미지: {flood_image.shape}, mean={flood_image.mean():.2f} dB")

    # 2. Change Detection
    print("\n[2/5] Change Detection 수행...")
    threshold = 3.0  # dB
    flood_mask, change_map = change_detection(dry_image, flood_image, threshold)
    print(f"  임계값: {threshold} dB")
    print(f"  변화량 범위: {change_map.min():.2f} ~ {change_map.max():.2f} dB")

    # 3. 면적 계산
    print("\n[3/5] 침수 면적 계산...")
    area_stats = calculate_flood_area(
        flood_mask,
        flood_meta["transform"],
        str(flood_meta["crs"])
    )
    print(f"  침수 픽셀: {area_stats['flood_pixels']:,} / {area_stats['total_pixels']:,}")
    print(f"  침수 비율: {area_stats['flood_ratio']*100:.2f}%")
    print(f"  침수 면적: {area_stats['flood_area_km2']:.2f} km² ({area_stats['flood_area_ha']:.1f} ha)")

    # 4. 결과 저장 (래스터)
    print("\n[4/5] 결과 저장 (래스터)...")
    mask_output = DATA_INUNDATION_SEOUL_HANGANG_2KM / "flood_mask.tif"
    save_flood_mask(flood_mask, flood_meta["profile"], mask_output)

    # 변화량 맵도 저장
    change_output = DATA_INUNDATION_SEOUL_HANGANG_2KM / "change_map.tif"
    change_profile = flood_meta["profile"].copy()
    change_profile.update(dtype=rasterio.float32, count=1)
    with rasterio.open(change_output, 'w', **change_profile) as dst:
        dst.write(change_map.astype(np.float32), 1)
    print(f"  변화량 맵 저장: {change_output}")

    # 5. 벡터 변환
    print("\n[5/5] 벡터 변환...")
    flood_gdf = mask_to_vector(
        flood_mask,
        flood_meta["transform"],
        str(flood_meta["crs"])
    )

    if len(flood_gdf) > 0:
        vector_output = DATA_INUNDATION_SEOUL_HANGANG_2KM / "flood_areas.geojson"
        flood_gdf.to_file(vector_output, driver="GeoJSON")
        print(f"  벡터 저장: {vector_output}")
        print(f"  침수 폴리곤 수: {len(flood_gdf)}")
    else:
        print("  침수 영역 없음")

    # 결과 요약
    print("\n" + "=" * 50)
    print("홍수 탐지 완료!")
    print("=" * 50)
    print(f"\n침수 면적: {area_stats['flood_area_km2']:.2f} km²")
    print(f"출력 파일:")
    print(f"  - {mask_output}")
    print(f"  - {change_output}")
    if len(flood_gdf) > 0:
        print(f"  - {vector_output}")

    return area_stats


if __name__ == "__main__":
    main()
