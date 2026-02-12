## 1. 전체 파이프라인 한 줄 요약

1. **프로젝트 세팅**
2. **관심 지역/사건 정의** (어디, 언제 난 홍수인지)
3. **Sentinel-1 데이터 가져오기** (전(前)·후(後) 장면)
4. **SAR 전처리** (캘리브레이션 → 필터링 → 지형보정 → 클리핑)
5. **홍수/수역 추출** (threshold / change detection 등)
6. **“도시” 마스크와 결합** (도시 영역 안의 물만 골라내기)
7. **벡터화 & 통계 산출** (면적, 행정구역별 집계)
8. **Streamlit 앱에서 시각화 & 인터랙션**

이제 단계별로, 어떤 작업을 하고 어떤 라이브러리를 쓰면 좋은지 정리해볼게요.

---

## 2. 단계별 작업 순서 (with 추천 라이브러리)

### (0) 프로젝트 & 환경 세팅

- **폴더 구조 예시**

  - `data/raw/` : 원본 Sentinel-1, DEM, 벡터
  - `data/processed/` : 보정 끝난 GeoTIFF, 마스크
  - `src/` : 처리 스크립트 (preprocess, flood_detect 등)
  - `app/` : Streamlit 앱 코드

- **Python 버전**: 3.10 근처 추천

**기본 라이브러리**

```bash
uv sync
```

SAR 쪽은 난이도에 따라 2옵션으로 생각하면 편합니다.

- **Option A (현실적인 조합)**

  - ESA **SNAP** 로 대부분의 SAR 전처리 (GUI 아니면 gpt 그래프) → 결과를 GeoTIFF로 저장
  - Python에서는 **rasterio / rioxarray / geopandas**로 후처리 + 분석 + 시각화

- **Option B (풀 파이썬)**

  - `sentinelsat` : Sentinel-1 다운로드
  - `xsar` 또는 `pyroSAR` : Calibration / terrain correction 등 (조금 러닝커브 있음)

초반에는 **Option A (SNAP + Python)** 조합을 추천해요. 파이썬은 일단 “완제품 GeoTIFF” 기준으로 파이프라인을 만드는 게 훨씬 수월합니다.

---

### (1) 관심 지역(AOI) & 홍수 이벤트 정의

- **AOI**: 도시 경계, 행정구역(구/동 경계) 등

  - 파일: `shp`, `geojson` 등을 준비
  - 라이브러리: `geopandas`, `shapely`

- **이벤트**: 홍수 날짜 범위 (예: 2020-08-01 ~ 2020-08-05)와
  비교용 **평상시(pre-flood) 날짜** (예: 2020-07 중 비 없던 날)

👉 이 정보가 있어야 Sentinel-1 검색/다운로드 조건을 잘 줄 수 있어요.

---

### (2) Sentinel-1 데이터 가져오기

**방법 1. 수동 다운로드(처음엔 이게 빠름)**

- Copernicus Data Space / ASF Vertex / Alaska Satellite Facility에서

  - 플랫폼: Sentinel-1
  - 제품: **GRD**
  - 모드: IW (Interferometric Wide)
  - Polarization: VV 또는 VV+VH
  - 홍수 전/후 날짜 각각 1–2장씩 다운로드

- 다운로드 결과(압축 해제 후 SAFE or GeoTIFF)를 `data/raw/`에 정리

**방법 2. 파이썬으로 자동 다운로드**

- `sentinelsat` 사용

  - 조건: 플랫폼, 센서모드, 날짜 범위, AOI(GeoJSON) 등

```bash
uv add sentinelsat
```

---

### (3) SAR 전처리 (핵심)

여기는 **SNAP에서 처리 + GeoTIFF export** 추천.

필수 단계(전형적인 홍수 지도 워크플로):

1. **Radiometric Calibration**

   - DN → σ⁰ (sigma nought) 또는 γ⁰

2. **Speckle Filtering**

   - Lee / Refined Lee 등

3. **Terrain Correction (Range-Doppler TC)**

   - DEM(SRTM 등) 써서 지형보정 + 투영 (예: EPSG:32652, 5186 등)

4. **Subset**

   - AOI 근처로 잘라서 파일 크기 줄이기

→ 결과:

- `data/processed/s1_flood_VV.tif`
- `data/processed/s1_preflood_VV.tif` 같은 GeoTIFF

Python에서 이걸 읽을 때:

- `rasterio`, `rioxarray` (`rioxarray.open_rasterio`)
- 좌표계, 해상도, AOI 기준으로 다시 잘라야 하면 `rioxarray.clip` + `geopandas` 사용

---

### (4) 홍수/수역 추출 (Flood Mapping)

가장 기본적인 방법: **threshold + change detection**

1. **전/후 장면 읽기**

   - `xarray` or `rioxarray` 활용해서 두 장면의 VV/VH 밴드 읽기

2. **change feature 만들기**

   - 예: `diff = pre_flood - flood` 또는 `ratio = pre_flood / flood`
   - 물이 차면 SAR backscatter가 보통 크게 줄어듦 → diff가 +로 큼

3. **thresholding**

   - 간단: 수동 threshold (예: diff > 2 dB)
   - 자동: Otsu 등 (라이브러리: `scikit-image`의 `threshold_otsu`)

```bash
uv add scikit-image
```

4. **후처리**

   - 작은 잡영역 제거 (size filter: `scipy.ndimage` or `skimage.morphology`)
   - DEM 또는 경사도(gradient) 사용해서 **고지대 물** 제거 (실제론 잘 안 고임)

5. **binary flood mask 생성**

   - 1 = 침수, 0 = 비침수

---

### (5) “도시 영역”과 겹치기 (Urban Flood)

1. **도시/건물/도로 등 벡터 데이터 구하기**

   - OSM (건물/도로/도시경계), 행정구역 shapefile 등

2. `geopandas` 로 읽어서 AOI + 좌표계 맞추기
3. **flood mask를 polygon으로 vectorize**

   - `rasterio.features.shapes` → flood polygon GeoDataFrame

4. **overlay**

   - `geopandas.overlay(flood_polygons, urban_polygons, how="intersection")`
   - 결과: “도시 영역 내 침수 영역”

이 단계에서 면적 계산(`geometry.area`)해서

- 전체 침수 면적
- 행정구역별 침수 면적
  같은 통계를 미리 뽑아두면, Streamlit에서 바로 써먹기 좋습니다.

---

### (6) 통계 & 검증

- **통계**

  - 총 침수 면적(km²)
  - 구/동별 침수 면적 Top N

- **검증 (기본적인 sanity check)**

  - 고지대에 침수 표시가 떴는지 확인
  - 실제 뉴스/사진/보고서의 침수 범위와 대략 맞는지 눈으로 확인

- 이때 `folium`/`leafmap`으로 빠르게 web-map 띄워보면 편해요.

---

### (7) Streamlit 앱에서 보여주기

#### 구조 아이디어

- `app/app.py` (메인)
- 레이아웃:

  - 왼쪽 sidebar:

    - 날짜 선택 (pre / post 또는 여러 이벤트 중 선택)
    - threshold 슬라이더
    - 레이어 on/off 체크박스 (기본물, 침수, 도시, 행정구역 등)

  - 메인 영역:

    - 지도(침수범람도 + 베이스맵)
    - 아래에 통계 그래프 / 표

#### Streamlit + 지도 시각화

**필수 라이브러리**

```bash
uv add streamlit streamlit-folium folium geopandas rasterio
```

- Raster(침수 mask, backscatter):

  - 간단: PNG 이미지로 렌더해서 overlay
  - 혹은 `folium.raster_layers.ImageOverlay`

- Vector(도시 경계, 침수 영역 폴리곤):

  - `geopandas` → GeoJSON → `folium.GeoJson` 레이어

- Streamlit 연동:

  - `from streamlit_folium import st_folium`
  - `m = folium.Map(...)` 만든 후 `st_folium(m, width=..., height=...)`

#### 아주 간단한 뼈대 예시

```python
# app/app.py
import streamlit as st
import geopandas as gpd
import rasterio
from streamlit_folium import st_folium
import folium

st.set_page_config(layout="wide", page_title="Urban Flood Mapping")

st.sidebar.title("설정")
threshold = st.sidebar.slider("Flood threshold", -5.0, 5.0, 1.5, 0.1)

st.title("Sentinel-1 Urban Flood Inundation Mapping")

# TODO: 처리된 데이터 불러오기 (예: GeoJSON, GeoTIFF 경로)
# flood_gdf = gpd.read_file("data/processed/flood_urban.gpkg")
# aoi_gdf = gpd.read_file("data/aoi/aoi.geojson")

# 예시로 지도만 생성
center = [35.87, 128.60]  # 예: 대구 근처
m = folium.Map(location=center, zoom_start=12)

# TODO: 여기서 flood_gdf, aoi_gdf를 folium.GeoJson으로 add

st_folium(m, width=900, height=600)
```

---

## 3. 정리: 단계별 추천 라이브러리 한 번에

- **데이터 가져오기**

  - `sentinelsat` (자동 다운로드, 선택)
  - 수동 다운로드도 OK

- **Raster / Vector 처리**

  - `rasterio`, `rioxarray`, `xarray`
  - `geopandas`, `shapely`, `pyproj`
  - `numpy`, `pandas`

- **홍수 추출 (이미지 처리)**

  - `scikit-image` (Otsu 등)
  - `scipy` (morphology / filtering, 선택)

- **시각화 / 앱**

  - `matplotlib`, `plotly`
  - `folium`, `streamlit-folium`, (또는 `leafmap`)
  - `streamlit`
