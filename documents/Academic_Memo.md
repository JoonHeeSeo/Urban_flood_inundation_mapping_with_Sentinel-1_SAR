## 1. SNAP 이 뭐냐?

한 줄로 말하면:

> **SNAP = ESA(유럽우주국)가 만든 위성(Sentinel 시리즈 등)용 무료 원격탐사 처리 툴박스**

조금 풀어서:

- **정식 이름**: Sentinel Application Platform (SNAP)

- **만든 곳**: ESA (Sentinel-1/2/3 같은 Copernicus 위성 운영하는 기관)

- **용도**:

  - SAR (Sentinel-1), 광학(Sentinel-2), 해양(Sentinel-3) 등 **위성 데이터 전처리/분석 전용 툴**
  - 특히 **Sentinel-1 SAR 전처리 파이프라인이 아주 잘 정리**되어 있음

    - Orbit file 적용
    - Radiometric calibration (σ⁰, γ⁰)
    - Speckle filtering
    - Terrain correction (Range-Doppler Terrain Correction)
    - Subset / Reprojection …

- **사용 방식** 두 가지:

  1. **GUI**: 마우스로 클릭하면서 처리(처음 할 땐 이게 직관적)
  2. **Graph Processing Tool (GPT)**:

     - XML로 “그래프(파이프라인)”를 정의 → 커맨드라인에서 한 번에 돌림
     - ex) `gpt my_s1_preprocess.xml -Pinput=... -Poutput=...`
     - 프로젝트에서는 **이 GPT 그래프를 고정해두고, 여러 장의 Sentinel-1 씬을 배치 처리**하는 식으로 쓰기 좋음

- **우리 프로젝트에서의 위치**:

  - “(0) 원시 Sentinel-1 데이터 → (1) 지형보정된 GeoTIFF(σ⁰/γ⁰)” 까지
    **전처리는 전부 SNAP에 맡기고**,
  - 그 다음:

    - Python(rasterio/rioxarray/xarray)에서 **침수 추정 / 마스크 생성 / 분석 / 시각화**
    - Streamlit으로 웹 앱

즉, SNAP은 **“SAR용 QGIS + 특화된 전처리 엔진”** 정도로 생각하면 편해요.
