# data/generate_sample_data.py
"""
샘플 Sentinel-1 SAR 데이터 생성기 (v2)

실제 한강 GeoJSON을 사용하여 현실적인 위치에 물 영역을 생성합니다.

SAR 특성:
- 물(water): 낮은 backscatter (어둡게 보임, -20 ~ -15 dB)
- 도시(urban): 높은 backscatter (밝게 보임, -5 ~ 0 dB)
- 초목(vegetation): 중간 backscatter (-12 ~ -8 dB)
"""

import numpy as np
import geopandas as gpd
import rasterio
from rasterio.transform import from_bounds
from rasterio.features import rasterize
from pathlib import Path
from shapely.geometry import box, mapping

# 경로 설정
from paths import (
    AOI_SEOUL_HANGANG_2KM,
    KOREA_RIVERS,
    SEOUL_BOUNDARY,
    DATA_S1_RAW_FLOOD,
    DATA_S1_RAW_DRY,
)


def create_base_image(
    width: int,
    height: int,
    seed: int = 42
) -> np.ndarray:
    """
    기본 SAR 배경 이미지 생성 (도시/초목 혼합)
    """
    np.random.seed(seed)
    # 도시/초목 혼합 배경 (-10 dB 기준)
    base = np.random.normal(-8, 3, (height, width)).astype(np.float32)
    return base


def rasterize_water(
    water_gdf: gpd.GeoDataFrame,
    bounds: tuple,
    width: int,
    height: int
) -> np.ndarray:
    """
    물(한강) 영역을 래스터화
    """
    transform = from_bounds(*bounds, width, height)

    # GeoDataFrame의 geometry를 래스터화
    if len(water_gdf) == 0:
        return np.zeros((height, width), dtype=np.uint8)

    shapes = [(geom, 1) for geom in water_gdf.geometry if geom is not None]

    if not shapes:
        return np.zeros((height, width), dtype=np.uint8)

    water_mask = rasterize(
        shapes,
        out_shape=(height, width),
        transform=transform,
        fill=0,
        dtype=np.uint8
    )

    return water_mask


def generate_sar_image(
    base_image: np.ndarray,
    water_mask: np.ndarray,
    flood_expansion: float = 0.0,
    seed: int = 42
) -> np.ndarray:
    """
    SAR 이미지 생성

    Args:
        base_image: 기본 배경 이미지
        water_mask: 물 영역 마스크 (1 = 물)
        flood_expansion: 홍수 확장 비율 (0.0 ~ 1.0)
        seed: 랜덤 시드

    Returns:
        SAR backscatter 이미지 (dB)
    """
    np.random.seed(seed + 100)

    result = base_image.copy()
    height, width = result.shape

    # 물 영역: 낮은 backscatter
    water_value = -18  # dB
    water_noise = np.random.normal(water_value, 1.5, (height, width))
    result[water_mask == 1] = water_noise[water_mask == 1]

    # 홍수 시: 물 영역 확장 (dilation)
    if flood_expansion > 0:
        from scipy import ndimage

        # 물 영역을 확장 (dilation)
        expansion_pixels = int(max(height, width) * flood_expansion * 0.05)
        if expansion_pixels > 0:
            struct = ndimage.generate_binary_structure(2, 2)
            expanded_mask = ndimage.binary_dilation(
                water_mask,
                structure=struct,
                iterations=expansion_pixels
            )

            # 새로 침수된 영역 (기존 물 영역 제외)
            new_flood = expanded_mask & (water_mask == 0)

            # 새 침수 영역: 약간 더 높은 backscatter (얕은 물)
            flood_value = -15  # dB
            flood_noise = np.random.normal(flood_value, 2, (height, width))
            result[new_flood] = flood_noise[new_flood]

            # 일부 랜덤 침수 패치 추가 (도시 침수)
            n_patches = int(15 * flood_expansion)
            for _ in range(n_patches):
                px = np.random.randint(0, width - 20)
                py = np.random.randint(0, height - 15)
                pw = np.random.randint(5, 20)
                ph = np.random.randint(3, 15)
                patch_value = np.random.normal(-14, 2, (ph, pw))
                result[py:py+ph, px:px+pw] = patch_value

    # Speckle noise 추가 (SAR 특성)
    speckle = np.random.exponential(1, (height, width)).astype(np.float32)
    speckle = np.clip(speckle, 0.3, 3.0)
    result = result * speckle

    # 값 범위 제한
    result = np.clip(result, -25, 0)

    return result


def save_geotiff(
    data: np.ndarray,
    bounds: tuple,
    output_path: Path,
    crs: str = "EPSG:4326"
):
    """GeoTIFF로 저장"""
    height, width = data.shape
    transform = from_bounds(*bounds, width, height)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(
        output_path,
        'w',
        driver='GTiff',
        height=height,
        width=width,
        count=1,
        dtype=data.dtype,
        crs=crs,
        transform=transform,
    ) as dst:
        dst.write(data, 1)

    print(f"Saved: {output_path}")


def main():
    """샘플 데이터 생성 메인 함수"""

    print("=" * 50)
    print("Sample SAR Data Generator v2")
    print("Using actual Hangang geometry")
    print("=" * 50)

    # 1. AOI 및 한강 데이터 로드
    print("\n[1/5] Loading vector data...")
    aoi = gpd.read_file(AOI_SEOUL_HANGANG_2KM)
    hangang = gpd.read_file(KOREA_RIVERS)

    bounds = aoi.total_bounds  # (minx, miny, maxx, maxy)
    print(f"  AOI bounds: {bounds}")

    # 한강 필터링 (이름에 한강/Hangang 포함)
    hangang_filtered = hangang[
        hangang['name'].str.contains('한강|Hangang|Han River', case=False, na=False)
    ]
    print(f"  Hangang features: {len(hangang_filtered)}")

    # AOI와 교차하는 부분만
    hangang_clipped = gpd.clip(hangang_filtered, aoi)
    print(f"  Clipped features: {len(hangang_clipped)}")

    # 2. 이미지 크기 설정
    width, height = 800, 400  # 더 높은 해상도
    print(f"\n[2/5] Image size: {width} x {height}")

    # 3. 한강 래스터화
    print("\n[3/5] Rasterizing Hangang...")
    water_mask = rasterize_water(hangang_clipped, bounds, width, height)
    water_pixels = np.sum(water_mask == 1)
    print(f"  Water pixels: {water_pixels} ({100*water_pixels/(width*height):.1f}%)")

    # 4. 기본 배경 이미지 생성
    print("\n[4/5] Generating SAR images...")
    base_image = create_base_image(width, height, seed=42)

    # 평시(dry) 이미지
    dry_image = generate_sar_image(base_image, water_mask, flood_expansion=0.0, seed=42)
    dry_output = DATA_S1_RAW_DRY / "S1_dry_sample_VV.tif"
    save_geotiff(dry_image, bounds, dry_output)

    # 홍수기(flood) 이미지
    flood_image = generate_sar_image(base_image, water_mask, flood_expansion=0.8, seed=42)
    flood_output = DATA_S1_RAW_FLOOD / "S1_flood_sample_VV.tif"
    save_geotiff(flood_image, bounds, flood_output)

    # 5. 통계 출력
    print("\n[5/5] Statistics:")
    print(f"  Dry image:   min={dry_image.min():.1f}, max={dry_image.max():.1f}, mean={dry_image.mean():.1f} dB")
    print(f"  Flood image: min={flood_image.min():.1f}, max={flood_image.max():.1f}, mean={flood_image.mean():.1f} dB")

    change = dry_image - flood_image
    print(f"  Change:      min={change.min():.1f}, max={change.max():.1f}, mean={change.mean():.1f} dB")

    print("\n" + "=" * 50)
    print("Sample data generation complete!")
    print("=" * 50)


if __name__ == "__main__":
    main()
