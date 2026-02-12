# Urban Flood Inundation Mapping with Sentinel-1 SAR

[![Streamlit Demo](https://img.shields.io/badge/Demo-Streamlit-blue)](https://urban-flood-inundation-mapping-with-sentinel-1-sar.streamlit.app/)

Detect and visualize urban flood areas in Seoul (Han River region) using Sentinel-1 SAR imagery.

**Live demo:** https://urban-flood-inundation-mapping-with-sentinel-1-sar.streamlit.app/

## Features

- Detects flooded areas by comparing SAR backscatter between normal and flood periods
- Uses change detection: water shows up as dark pixels in SAR (low backscatter), so newly flooded areas can be identified when backscatter drops significantly
- Outputs flood masks as GeoTIFF and vector (GeoJSON) formats
- Visualizes results on an interactive map

## Project Structure

```
├── data/
│   ├── vector/                    # GeoJSON files (Seoul boundary, Han River, AOI)
│   ├── sentinel1/raw/             # SAR images (dry/flood periods)
│   ├── generate_sample_data.py    # Creates sample SAR data for testing
│   ├── flood_detection.py         # Main detection algorithm
│   └── download_sentinel1.py      # Copernicus API downloader (optional)
├── service/
│   └── app.py                     # Streamlit dashboard
└── config/
    └── event_seoul_hangang_2020.yaml
```

## Quick Start

### 1. Install dependencies

```bash
uv sync
```

### 2. Generate sample data (no Copernicus account needed)

```bash
cd data
uv run python generate_sample_data.py
```

This creates synthetic SAR images based on actual Han River geometry. Good enough for testing the pipeline.

### 3. Run flood detection

```bash
uv run python flood_detection.py
```

Outputs:
- `data/products/inundation/seoul_hangang_2km/flood_mask.tif`
- `data/products/inundation/seoul_hangang_2km/flood_areas.geojson`

### 4. Launch the dashboard

```bash
uv run streamlit run service/app.py
```

## How it works

### SAR basics

SAR (Synthetic Aperture Radar) measures surface roughness via backscatter:
- **Water**: smooth surface → specular reflection → low backscatter (dark)
- **Urban areas**: buildings, corners → high backscatter (bright)
- **Vegetation**: moderate backscatter

### Change Detection approach

```
flood_mask = (dry_image - flood_image) > threshold
```

When an area floods, backscatter drops. By comparing a normal period image with a flood period image, we can identify newly inundated areas.

Current threshold: **3.0 dB** (adjustable)

## Data Sources

| Data | Source |
|------|--------|
| Seoul boundary | OpenStreetMap |
| Han River | OpenStreetMap |
| Sentinel-1 GRD | Copernicus Dataspace (or sample data) |

## Using real Sentinel-1 data

If you want to use actual satellite imagery instead of sample data:

1. Create account at [Copernicus Dataspace](https://dataspace.copernicus.eu/)
2. Copy `config/.env.example` to `config/.env` and fill in credentials
3. Run `uv run python data/download_sentinel1.py`

Note: Real SAR data requires preprocessing (calibration, speckle filtering, terrain correction). The sample data skips this step.

## Tech Stack

- **Vector processing**: geopandas, shapely
- **Raster processing**: rasterio, numpy
- **Visualization**: Streamlit, Folium
- **SAR download**: Copernicus OData API

## Limitations

- Sample data is synthetic (based on actual geometry but not real SAR values)
- No radiometric calibration in current pipeline
- Threshold is static (could use Otsu or ML-based methods)
- Urban flood detection is tricky due to double-bounce effects

## Future ideas

- [ ] Integrate SNAP for proper SAR preprocessing
- [ ] Add Otsu automatic thresholding
- [ ] Time series analysis
- [ ] Administrative district statistics

## References

- [Copernicus Emergency Management Service](https://emergency.copernicus.eu/)
- Twele et al. (2016) - Sentinel-1 flood mapping
- ESA Sentinel-1 User Guide

---

*This is a learning project. Results are not validated for actual emergency response.*
