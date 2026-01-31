"""
Urban Flood Inundation Mapping with Sentinel-1 SAR

서울/한강 지역 도시 홍수 침수 분석 시각화 앱
"""

import json
from pathlib import Path

import numpy as np
import folium
import streamlit as st
from streamlit_folium import st_folium
import rasterio
import geopandas as gpd

# 경로 설정
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
VECTOR_DIR = DATA_DIR / "vector"
PRODUCTS_DIR = DATA_DIR / "products" / "inundation" / "seoul_hangang_2km"

# ---------- Data Loading ----------

@st.cache_data
def load_aoi():
    """AOI GeoJSON 로드"""
    aoi_path = VECTOR_DIR / "seoul_hangang_2km_aoi.geojson"
    if aoi_path.exists():
        return gpd.read_file(aoi_path)
    return None


@st.cache_data
def load_flood_areas():
    """침수 영역 GeoJSON 로드"""
    flood_path = PRODUCTS_DIR / "flood_areas.geojson"
    if flood_path.exists():
        gdf = gpd.read_file(flood_path)
        # 단순화하여 로딩 속도 개선
        gdf["geometry"] = gdf["geometry"].simplify(0.001)
        return gdf
    return None


@st.cache_data
def load_flood_stats():
    """침수 통계 계산"""
    mask_path = PRODUCTS_DIR / "flood_mask.tif"
    if not mask_path.exists():
        return None

    with rasterio.open(mask_path) as src:
        mask = src.read(1)
        transform = src.transform

    # 픽셀 크기 계산 (서울 위도 기준)
    lat_center = 37.55
    m_per_deg_lat = 111320
    m_per_deg_lon = 111320 * np.cos(np.radians(lat_center))

    pixel_width_m = abs(transform.a) * m_per_deg_lon
    pixel_height_m = abs(transform.e) * m_per_deg_lat
    pixel_area_m2 = pixel_width_m * pixel_height_m

    flood_pixels = int(np.sum(mask == 1))
    total_pixels = int(mask.size)

    return {
        "flood_pixels": flood_pixels,
        "total_pixels": total_pixels,
        "flood_ratio": flood_pixels / total_pixels if total_pixels > 0 else 0,
        "flood_area_km2": flood_pixels * pixel_area_m2 / 1_000_000,
        "flood_area_ha": flood_pixels * pixel_area_m2 / 10_000,
    }


@st.cache_data
def load_sar_images():
    """SAR 이미지 로드"""
    dry_path = DATA_DIR / "sentinel1" / "raw" / "dry" / "S1_dry_sample_VV.tif"
    flood_path = DATA_DIR / "sentinel1" / "raw" / "flood" / "S1_flood_sample_VV.tif"

    images = {}

    if dry_path.exists():
        with rasterio.open(dry_path) as src:
            images["dry"] = src.read(1)
            images["bounds"] = src.bounds

    if flood_path.exists():
        with rasterio.open(flood_path) as src:
            images["flood"] = src.read(1)

    return images if images else None


# ---------- Map Creation ----------

def create_flood_map(aoi_gdf, flood_gdf, center=(37.55, 126.99)):
    """침수 영역 지도 생성"""
    m = folium.Map(
        location=center,
        zoom_start=11,
        tiles="CartoDB positron"
    )

    # AOI 경계 표시
    if aoi_gdf is not None:
        folium.GeoJson(
            aoi_gdf.to_json(),
            name="AOI (한강 2km 버퍼)",
            style_function=lambda x: {
                "fillColor": "transparent",
                "color": "#3388ff",
                "weight": 2,
                "dashArray": "5, 5"
            }
        ).add_to(m)

    # 침수 영역 표시
    if flood_gdf is not None and len(flood_gdf) > 0:
        # 너무 많은 폴리곤은 성능 이슈 → 상위 500개만
        flood_sample = flood_gdf.head(500)

        folium.GeoJson(
            flood_sample.to_json(),
            name="침수 영역",
            style_function=lambda x: {
                "fillColor": "#ff4444",
                "color": "#cc0000",
                "weight": 0.5,
                "fillOpacity": 0.6
            }
        ).add_to(m)

    # 레이어 컨트롤
    folium.LayerControl().add_to(m)

    return m


# ---------- Streamlit App ----------

st.set_page_config(
    page_title="Urban Flood Mapping - Seoul/Hangang",
    page_icon="🌊",
    layout="wide",
)

st.title("🌊 Urban Flood Inundation Mapping")
st.caption("서울/한강 지역 도시 홍수 침수 분석 | Sentinel-1 SAR 기반")

# 데이터 로드
aoi = load_aoi()
flood_areas = load_flood_areas()
stats = load_flood_stats()
sar_images = load_sar_images()

# 데이터 확인
data_ready = all([
    aoi is not None,
    stats is not None,
])

if not data_ready:
    st.warning("⚠️ 분석 데이터가 없습니다. 먼저 다음 스크립트를 실행하세요:")
    st.code("""
# 1. 샘플 SAR 데이터 생성
cd data && python generate_sample_data.py

# 2. 홍수 탐지 실행
cd data && python flood_detection.py
    """)
    st.stop()

# 사이드바: 정보
st.sidebar.header("📊 분석 정보")
st.sidebar.markdown("""
**데이터 소스**
- AOI: 서울 한강 2km 버퍼
- 센서: Sentinel-1 SAR (VV)
- 방법: Change Detection

**분석 파라미터**
- 임계값: 3.0 dB
- 기준: 평시 vs 홍수기
""")

# 메인 레이아웃
tab1, tab2, tab3 = st.tabs(["🗺️ 지도", "📈 SAR 이미지", "📋 상세 정보"])

# 탭 1: 지도
with tab1:
    st.subheader("침수 영역 지도")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("침수 면적", f"{stats['flood_area_km2']:.2f} km²")
    with col2:
        st.metric("침수 비율", f"{stats['flood_ratio']*100:.1f}%")
    with col3:
        st.metric("침수 픽셀", f"{stats['flood_pixels']:,}")

    # 지도 표시
    flood_map = create_flood_map(aoi, flood_areas)
    st_folium(flood_map, width=None, height=500, use_container_width=True)

    st.caption("🔴 빨간 영역: 침수 추정 지역 | 🔵 파란 점선: AOI 경계")

# 탭 2: SAR 이미지
with tab2:
    st.subheader("SAR 이미지 비교")

    if sar_images:
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**평시 (Dry Season)**")
            if "dry" in sar_images:
                # 정규화하여 표시
                dry_norm = (sar_images["dry"] - sar_images["dry"].min()) / (sar_images["dry"].max() - sar_images["dry"].min() + 1e-6)
                st.image(dry_norm, caption=f"Mean: {sar_images['dry'].mean():.2f} dB", use_container_width=True)

        with col2:
            st.markdown("**홍수기 (Flood Season)**")
            if "flood" in sar_images:
                flood_norm = (sar_images["flood"] - sar_images["flood"].min()) / (sar_images["flood"].max() - sar_images["flood"].min() + 1e-6)
                st.image(flood_norm, caption=f"Mean: {sar_images['flood'].mean():.2f} dB", use_container_width=True)

        # 변화량 표시
        if "dry" in sar_images and "flood" in sar_images:
            st.markdown("---")
            st.markdown("**변화량 (Dry - Flood)**")
            change = sar_images["dry"] - sar_images["flood"]

            # 변화량을 컬러맵으로 표시
            change_norm = (change - change.min()) / (change.max() - change.min() + 1e-6)
            st.image(change_norm, caption=f"Range: {change.min():.2f} ~ {change.max():.2f} dB", use_container_width=True)
            st.caption("밝은 영역: backscatter 감소 (침수 가능성 높음)")
    else:
        st.info("SAR 이미지가 없습니다.")

# 탭 3: 상세 정보
with tab3:
    st.subheader("분석 상세 정보")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 📊 침수 통계")
        st.json({
            "침수 픽셀 수": stats["flood_pixels"],
            "전체 픽셀 수": stats["total_pixels"],
            "침수 비율 (%)": round(stats["flood_ratio"] * 100, 2),
            "침수 면적 (km²)": round(stats["flood_area_km2"], 2),
            "침수 면적 (ha)": round(stats["flood_area_ha"], 1),
        })

    with col2:
        st.markdown("### 📁 출력 파일")
        files = [
            ("flood_mask.tif", "침수 마스크 (래스터)"),
            ("change_map.tif", "변화량 맵 (래스터)"),
            ("flood_areas.geojson", "침수 영역 (벡터)"),
        ]
        for fname, desc in files:
            fpath = PRODUCTS_DIR / fname
            status = "✅" if fpath.exists() else "❌"
            st.write(f"{status} `{fname}` - {desc}")

    st.markdown("---")
    st.markdown("### 🔬 방법론")
    st.markdown("""
    1. **SAR 데이터**: Sentinel-1 GRD (VV 편파)
    2. **Change Detection**: 평시 - 홍수기 backscatter 차이 계산
    3. **임계값 적용**: 변화량 > 3.0 dB → 침수로 분류
    4. **후처리**: 벡터 변환, 면적 계산

    > SAR(합성개구레이다)에서 물은 정반사로 인해 낮은 backscatter를 보입니다.
    > 홍수 시 새로 물에 잠긴 영역은 backscatter가 급격히 감소합니다.
    """)

# 푸터
st.markdown("---")
st.caption("🛰️ Sentinel-1 SAR 기반 도시 홍수 분석 | 개인 연습 프로젝트")
