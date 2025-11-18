import io
from typing import Tuple

import numpy as np
from PIL import Image

import streamlit as st

# ---------- Utility functions ----------

def load_image_to_gray(file) -> Image.Image:
    """Load uploaded image file and convert to grayscale PIL Image."""
    img = Image.open(file)
    img = img.convert("L")  # grayscale
    return img


def to_numpy(img: Image.Image) -> np.ndarray:
    """Convert PIL image to float32 numpy array."""
    arr = np.array(img).astype("float32")
    return arr


def resize_to_match(img_a: Image.Image, img_b: Image.Image) -> Tuple[Image.Image, Image.Image]:
    """Resize img_b to match img_a size, if different."""
    if img_a.size != img_b.size:
        img_b = img_b.resize(img_a.size, resample=Image.BILINEAR)
    return img_a, img_b


def create_overlay(post_img: Image.Image, mask: np.ndarray, alpha: float = 0.5) -> Image.Image:
    """
    Overlay burned mask onto post-fire image.
    mask: 2D boolean array (True = burned)
    """
    post_rgb = post_img.convert("RGB")
    base = np.array(post_rgb).astype("float32")
    overlay = base.copy()

    # red color
    red = np.array([255, 0, 0], dtype="float32")

    # expand mask to 3 channels
    mask3 = mask[..., None]  # (H, W, 1)

    # alpha blending only where mask is True
    overlay[mask3] = alpha * base[mask3] + (1.0 - alpha) * red

    overlay = np.clip(overlay, 0, 255).astype("uint8")
    return Image.fromarray(overlay)


# ---------- Streamlit app ----------

st.set_page_config(
    page_title="Wildfire Burned Area Estimation (Prototype)",
    page_icon="🛰",
    layout="wide",
)

st.title("🔥 Wildfire Burned Area Estimation with Sentinel-1 (Prototype)")
st.caption(
    "First prototype app for visualizing burned area using pre-/post-fire backscatter images.\n"
    "초기 버전: 산불 전·후 이미지를 업로드해서 변화량과 피해 영역 마스크를 시각화합니다."
)

with st.expander("ℹ️ How to use / 사용 방법", expanded=True):
    st.markdown(
        """
1. **Pre-fire image**와 **Post-fire image**를 업로드합니다.  
   - 우선은 시범용으로 PNG/JPEG/GeoTIFF 모두 grayscale로 처리합니다.  
   - 나중에 Sentinel-1 backscatter(σ⁰) GeoTIFF로 교체할 수 있습니다.
2. 오른쪽에서 **Change threshold** 슬라이더를 조절해 보면서  
   어느 정도 변화량에서 'burned'로 볼지 감각적으로 맞춰봅니다.
3. **Pixel size (m)**를 입력하면, 대략적인 피해 면적(ha)을 계산합니다.

> 지금은 *입문용 프로토타입*이라서,  
> SAR 전처리/정확한 지리정보는 따로 오프라인 파이프라인에서 수행했다고 가정합니다.
"""
    )


# Sidebar: inputs
st.sidebar.header("Inputs / 설정")

pre_file = st.sidebar.file_uploader(
    "Pre-fire image (산불 전 영상)",
    type=["png", "jpg", "jpeg", "tif", "tiff"],
    key="pre_fire",
)

post_file = st.sidebar.file_uploader(
    "Post-fire image (산불 후 영상)",
    type=["png", "jpg", "jpeg", "tif", "tiff"],
    key="post_fire",
)

pixel_size_m = st.sidebar.number_input(
    "Pixel size (meters per pixel)",
    min_value=0.1,
    max_value=500.0,
    value=10.0,
    step=0.5,
    help="예: Sentinel-1 GRD는 약 10 m, Sentinel-2는 10 m/20 m 등",
)

st.sidebar.markdown("---")
st.sidebar.write("📌 **Tip**: 처음에는 샘플 이미지로 테스트 후, "
                 "나중에 Sentinel-1 σ⁰ GeoTIFF 결과를 넣어도 됩니다.")


# Main logic
if pre_file is None or post_file is None:
    st.warning("먼저 **산불 전(pre-fire)**, **산불 후(post-fire)** 이미지를 모두 업로드해주세요.")
    st.stop()

# Load images
pre_img = load_image_to_gray(pre_file)
post_img = load_image_to_gray(post_file)

# Resize to match
pre_img, post_img = resize_to_match(pre_img, post_img)

# Convert to numpy
pre_arr = to_numpy(pre_img)
post_arr = to_numpy(post_img)

if pre_arr.shape != post_arr.shape:
    st.error(f"Image shapes do not match: pre {pre_arr.shape}, post {post_arr.shape}")
    st.stop()

# Compute difference (post - pre)
diff_arr = post_arr - pre_arr

# Basic stats for slider
diff_min = float(diff_arr.min())
diff_max = float(diff_arr.max())
diff_mean = float(diff_arr.mean())
diff_std = float(diff_arr.std()) if diff_arr.std() > 0 else 1.0

st.sidebar.markdown("### Threshold 설정")
default_thr = diff_mean + diff_std
thr = st.sidebar.slider(
    "Change threshold (변화량 임계값)",
    min_value=diff_min,
    max_value=diff_max,
    value=default_thr,
    step=(diff_max - diff_min) / 100.0 if diff_max > diff_min else 0.1,
    help="이 값보다 변화량이 큰 픽셀을 'burned'로 간주합니다.",
)

# Create mask
mask = diff_arr > thr

# Burned area estimation
burned_pixels = int(mask.sum())
pixel_area_m2 = pixel_size_m ** 2
burned_area_m2 = burned_pixels * pixel_area_m2
burned_area_ha = burned_area_m2 / 10000.0  # 1 ha = 10,000 m2

# Create overlay image
overlay_img = create_overlay(post_img, mask, alpha=0.5)

# Layout: show images and results
col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("Pre-fire (산불 전)")
    st.image(pre_img, use_column_width=True)
    st.caption("Original pre-fire grayscale image (예: VV/VH backscatter).")

with col2:
    st.subheader("Post-fire (산불 후)")
    st.image(post_img, use_column_width=True)
    st.caption("Original post-fire grayscale image.")

with col3:
    st.subheader("Burned overlay (피해 영역)")
    st.image(overlay_img, use_column_width=True)
    st.caption("Red overlay shows pixels classified as burned.")

st.markdown("---")

# Metrics
st.subheader("Estimated burned area / 산불 피해 면적 추정")

col_a, col_b, col_c = st.columns(3)
with col_a:
    st.metric("Burned pixels", f"{burned_pixels:,}")
with col_b:
    st.metric("Pixel size (m)", f"{pixel_size_m:.1f} m")
with col_c:
    st.metric("Burned area (ha)", f"{burned_area_ha:,.2f} ha")

with st.expander("Advanced / 향후 개선 아이디어"):
    st.markdown(
        """
- 실제 Sentinel-1 σ⁰(dB) GeoTIFF를 사용하도록 수정
- VV/VH, dVV, dVH 등 여러 밴드를 합친 변화 지표 사용
- 자동 임계값(Otsu 등) + 지도학습(Random Forest 등)으로 확장
- GeoTIFF의 좌표계를 이용해 **실제 지리 좌표** 기반의 면적 계산
- Streamlit 지도 컴포넌트에 벡터 폴리곤으로 피해 영역 표시
"""
    )
