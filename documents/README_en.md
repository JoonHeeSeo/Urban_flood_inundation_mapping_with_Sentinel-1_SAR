# Wildfire Burned Area Estimation with Sentinel-1 SAR

## Overview

This project estimates **wildfire burned area** using **Sentinel-1 SAR** imagery.  
The focus is on building an **accessible, first SAR workflow** that is:

- Simple enough for a first project with SAR
- Intuitive and visually understandable for non-experts
- Still technically solid and extensible for future work

The main idea is to compare **pre-fire** and **post-fire** Sentinel-1 backscatter and extract the burned area using change detection and (optionally) a simple machine learning classifier.

---

## Objectives

1. **Estimate burned area** for 1–3 wildfire case studies using Sentinel-1 SAR.
2. **Produce clear visualizations** (maps and statistics) that are easy to understand:
   - Burned area polygons/masks over a basemap or optical imagery
   - Summary statistics such as total burned area (ha) and burned fraction (%)
3. **Evaluate accuracy** by comparing SAR-derived burned area with:
   - Reference polygons (if available), or
   - Manually interpreted burned area from optical imagery
4. (Optional) **Compare methods**:
   - Simple change + threshold vs. a basic supervised classifier (e.g., Random Forest)

The priority is to **finish a clean, end-to-end pipeline** rather than to build a highly complex model.

---

## Why Sentinel-1 SAR for wildfires?

- **All-weather, day/night**: SAR can observe burned areas even when clouds or smoke are present.
- **Free and global**: Sentinel-1 GRD products are freely available.
- **Sensitive to surface changes**: Fire changes vegetation structure and surface roughness, which affects SAR backscatter (σ⁰).

This makes Sentinel-1 an attractive choice for **rapid mapping of wildfire damage**, especially as a first SAR project.

---

## Data

### Core data

- **SAR imagery**
  - Sentinel-1 GRD (C-band)
  - Acquisition pairs:  
    - **Pre-fire**: a few days before the wildfire  
    - **Post-fire**: shortly after the wildfire
  - Polarizations: VV, VH (as available)

- **Reference data** (for evaluation)
  - Burned area polygons from official sources (if available), **or**
  - Burned area delineated manually from high-resolution imagery (e.g., Sentinel-2, commercial basemaps)

### Optional supporting data

- **Optical imagery** (for visualization and/or manual interpretation)
  - Sentinel-2, Landsat, or high-resolution basemaps

- **Land cover data**
  - Used to mask non-vegetated areas (urban, water, etc.) to reduce false positives

---

## Methodology

### 1. Case study selection

Select **1–3 wildfire events** that:

- Have clear burned areas visible in optical imagery
- Have suitable Sentinel-1 passes before and after the fire

### 2. Pre-processing (Sentinel-1)

Basic pre-processing steps (can be done in SNAP, Google Earth Engine, or a Python workflow):

1. Apply orbit file
2. Remove thermal noise
3. Radiometric calibration to σ⁰ (dB)
4. Speckle filtering (e.g., Refined Lee)
5. Terrain correction (e.g., Range-Doppler)
6. Subset to the area of interest (AOI)

The goal is to obtain **geometrically corrected backscatter images** for VV/VH, both pre- and post-fire.

### 3. Feature construction

From pre- and post-fire images, compute:

- Raw backscatter (dB):  
  - `VV_pre`, `VV_post`, `VH_pre`, `VH_post`
- Change features:  
  - `dVV = VV_post - VV_pre`  
  - `dVH = VH_post - VH_pre`
- (Optional) simple texture features (e.g., local mean or standard deviation in a 3×3 or 5×5 window)

### 4. Method A: Change detection + thresholding (MVP)

1. Compute a simple change metric, e.g.:
   - `change = dVV` or a combination such as `dVV + dVH`
2. Apply an automatic threshold (e.g., Otsu) to separate “changed” vs. “unchanged” pixels.
3. Post-process the mask:
   - Remove very small patches
   - Fill small holes
   - (Optional) restrict to vegetated land cover only

This yields a **burned area candidate mask** without any complex machine learning.

### 5. Method B (optional): Supervised classification

To slightly increase sophistication:

1. Collect sample pixels for two classes:
   - Burned
   - Unburned
2. Use features such as:
   - `VV_pre`, `VV_post`, `VH_pre`, `VH_post`, `dVV`, `dVH`, (optional texture)
3. Train a simple classifier:
   - Random Forest, XGBoost, or similar
4. Apply the classifier to generate a **burned probability map** and a final burned area mask.

### 6. Accuracy assessment

Compare the SAR-derived burned area with reference data:

- Compute confusion matrix at pixel level (or sample points)
- Report metrics such as:
  - Overall accuracy
  - Precision, recall, F1-score for the burned class
  - Intersection over Union (IoU) of burned areas

---

## Visualization

Visual communication is a key goal of this project.

Recommended outputs:

1. **Before/After imagery**
   - Side-by-side or swipe viewer:
     - Pre-fire optical/SAR vs. post-fire optical/SAR

2. **Burned area overlay**
   - Basemap or optical imagery + burned area mask/polygon in semi-transparent red

3. **Summary statistics**
   - Total burned area (ha)
   - Burned area as a percentage of forest/vegetation area

These visualizations should make sense **even to non-experts**.

---

## Project structure (example)

```text
.
├── data/
│   ├── raw/          # Original Sentinel-1, reference data
│   ├── processed/    # Pre-processed SAR, masks, etc.
├── notebooks/
│   ├── 01_explore_data.ipynb
│   ├── 02_preprocessing.ipynb
│   ├── 03_change_detection.ipynb
│   ├── 04_classification_optional.ipynb
├── src/
│   ├── preprocessing.py
│   ├── features.py
│   ├── change_detection.py
│   ├── classification.py   # optional
│   ├── evaluation.py
├── outputs/
│   ├── figures/
│   ├── maps/
│   └── reports/
└── README.md
```

This is only a suggestion; feel free to adapt it to your preferred workflow (e.g., pure notebooks, GEE scripts, etc.).

---

## Getting started

1. Choose the platform/tooling:
   - SNAP GUI
   - Google Earth Engine
   - Python + SNAP / snappy / rasterio / xarray, etc.
2. Download pre- and post-fire Sentinel-1 GRD for your case study.
3. Run the basic pre-processing pipeline.
4. Implement the **change detection + thresholding** MVP first.
5. Add evaluation and visualizations.
6. (Optional) Add the supervised classification method.

---

## Future work

Once the basic burned area mapping workflow is complete, the project can be extended by:

- Estimating **burn severity** instead of only burned/unburned
- Analyzing the relationship between **meteorological conditions** (wind, humidity, drought indices) and burned area
- Scaling up to **larger regions** or **multiple fire seasons**
- Using more advanced models (U-Net, temporal deep learning, multi-sensor fusion)

For now, the priority is to **build a clean, understandable, and reproducible Sentinel-1 burned area mapping pipeline**.
