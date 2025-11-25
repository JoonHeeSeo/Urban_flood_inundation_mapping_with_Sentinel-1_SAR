# data/aoi_builder.py
import geopandas as gpd
from .paths import SEOUL_BOUNDARY, KOREA_RIVERS, AOI_SEOUL_HANGANG_2KM

def build_seoul_hangang_aoi(buffer_m: int = 2000):
    gdf_seoul = gpd.read_file(SEOUL_BOUNDARY)
    gdf_riv   = gpd.read_file(KOREA_RIVERS)

    # CRS 설정/변환
    if gdf_seoul.crs is None:
        gdf_seoul.set_crs(epsg=4326, inplace=True)
    else:
        gdf_seoul = gdf_seoul.to_crs(epsg=4326)

    if gdf_riv.crs is None:
        gdf_riv.set_crs(epsg=4326, inplace=True)
    else:
        gdf_riv = gdf_riv.to_crs(epsg=4326)

    # 한강 필터 (dummy: 전체 사용, OSM 쓸 때 name 기반 필터)
    if "name" in gdf_riv.columns:
        mask = gdf_riv["name"].astype(str).str.contains("한강|Hangang|Han River", na=False)
        gdf_hangang = gdf_riv[mask]
        if gdf_hangang.empty:
            gdf_hangang = gdf_riv
    else:
        gdf_hangang = gdf_riv

    # 서울 영역과 교차 (dummy에선 사실상 큰 의미는 없지만 구조는 유지)
    gdf_hangang_seoul = gpd.overlay(gdf_hangang, gdf_seoul, how="intersection")

    # 버퍼 + AOI 생성
    gdf_m = gdf_hangang_seoul.to_crs(epsg=3857)
    gdf_buf = gdf_m.buffer(buffer_m)
    gdf_buf = gpd.GeoDataFrame(geometry=gdf_buf, crs="EPSG:3857").to_crs(epsg=4326)

    gdf_aoi = gdf_buf.dissolve()
    AOI_SEOUL_HANGANG_2KM.parent.mkdir(parents=True, exist_ok=True)
    gdf_aoi.to_file(AOI_SEOUL_HANGANG_2KM, driver="GeoJSON")
    return AOI_SEOUL_HANGANG_2KM

if __name__ == "__main__":
    from pathlib import Path

    out = build_seoul_hangang_aoi()
    print(f"AOI saved to: {Path(out).resolve()}")