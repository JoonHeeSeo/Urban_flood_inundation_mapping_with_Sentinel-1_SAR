import geopandas as gpd
from .paths import SEOUL_BOUNDARY, KOREA_RIVERS, AOI_SEOUL_HANGANG_2KM


def _to_polygon_only(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Polygon / MultiPolygon 만 남기고, 하나의 폴리곤 레이어로 정리."""
    # 1) Polygon / MultiPolygon만 필터
    gdf = gdf[gdf.geometry.type.isin(["Polygon", "MultiPolygon"])].copy()
    if gdf.empty:
        raise ValueError("Polygon / MultiPolygon geometry가 없습니다.")

    # 2) 전체를 하나로 union (MultiPolygon 될 수 있음)
    geom = gdf.unary_union

    # 3) GeoDataFrame으로 만들고 explode → 전부 Polygon 타입으로 맞추기
    gdf_out = gpd.GeoDataFrame(geometry=[geom], crs=gdf.crs)
    gdf_out = gdf_out.explode(index_parts=False)

    return gdf_out


def build_seoul_hangang_aoi(buffer_m: int = 2000):
    gdf_seoul = gpd.read_file(SEOUL_BOUNDARY)
    gdf_riv   = gpd.read_file(KOREA_RIVERS)

    # CRS 설정/변환 (둘 다 WGS84로)
    if gdf_seoul.crs is None:
        gdf_seoul.set_crs(epsg=4326, inplace=True)
    else:
        gdf_seoul = gdf_seoul.to_crs(epsg=4326)

    if gdf_riv.crs is None:
        gdf_riv.set_crs(epsg=4326, inplace=True)
    else:
        gdf_riv = gdf_riv.to_crs(epsg=4326)

    # 한강 필터
    if "name" in gdf_riv.columns:
        mask = gdf_riv["name"].astype(str).str.contains("한강|Hangang|Han River", na=False)
        gdf_hangang = gdf_riv[mask].copy()
        if gdf_hangang.empty:
            gdf_hangang = gdf_riv.copy()
    else:
        gdf_hangang = gdf_riv.copy()

    # ✅ 한강 / 서울 모두 Polygon-only로 통일
    gdf_hangang = _to_polygon_only(gdf_hangang)
    gdf_seoul   = _to_polygon_only(gdf_seoul)

    # 서울 영역과 교차
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
