"""
Frame edge / gap detector for film scanning previews.

Key idea: compute a vertical intensity profile across the preview (mean over
rows), smooth it, then find bright gap peaks between frames. Returns the
offset in pixels from the image center to the strongest gap plus a confidence
score. Inspired by the negative_scanner project.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np


@dataclass
class GapDetection:
    """Single detected gap/edge candidate."""

    x: int
    prominence: float
    width: int


@dataclass
class DetectionResult:
    """Summary of detection suitable for motor alignment."""

    offset_px: int  # positive means gap is to the right of center
    confidence: float
    gap_x: Optional[int]
    profile: Optional[np.ndarray] = None
    smoothed: Optional[np.ndarray] = None
    gaps: Optional[List[GapDetection]] = None
    polarity: str = "bright"  # whether we locked onto a bright or dark gap


def jpeg_bytes_to_gray(jpeg_bytes: bytes) -> np.ndarray:
    """Decode JPEG bytes to a uint8 grayscale image."""

    arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError("Failed to decode preview image")
    return img


def vertical_profile(gray: np.ndarray) -> np.ndarray:
    """Compute average intensity per column (float32)."""

    if gray.ndim != 2:
        raise ValueError("Expected grayscale image")
    return gray.mean(axis=0).astype(np.float32)


def _smooth_profile(profile: np.ndarray, ksize: int = 11) -> np.ndarray:
    """Gaussian smooth; ksize must be odd."""

    ksize = max(3, ksize | 1)  # force odd and >=3
    # cv2.GaussianBlur requires 2D input; reshape 1D profile to single-row 2D array
    profile_2d = profile.reshape(1, -1)
    smoothed_2d = cv2.GaussianBlur(profile_2d, (ksize, 1), 0, borderType=cv2.BORDER_REPLICATE)
    return smoothed_2d.flatten()


def _find_gaps(smoothed: np.ndarray, min_prominence: float, min_distance: int) -> List[GapDetection]:
    """
    Find bright peaks (gaps) in the smoothed profile using a simple derivative
    and prominence heuristic (no scipy dependency).
    """

    # First derivative to locate rising/falling edges
    deriv = np.diff(smoothed)
    # Simple zero-crossing at local maxima
    maxima = []
    for i in range(1, len(smoothed) - 1):
        if smoothed[i] > smoothed[i - 1] and smoothed[i] >= smoothed[i + 1]:
            maxima.append(i)

    gaps: List[GapDetection] = []
    for idx in maxima:
        left = idx - 1
        while left > 0 and smoothed[left] < smoothed[left - 1]:
            left -= 1
        right = idx + 1
        while right < len(smoothed) - 1 and smoothed[right] < smoothed[right + 1]:
            right += 1

        prominence = smoothed[idx] - 0.5 * (smoothed[left] + smoothed[right])
        width = right - left + 1

        if prominence >= min_prominence:
            gaps.append(GapDetection(x=idx, prominence=float(prominence), width=width))

    # Enforce minimum distance between peaks by keeping stronger ones
    if not gaps:
        return []

    gaps = sorted(gaps, key=lambda g: g.prominence, reverse=True)
    kept: List[GapDetection] = []
    for g in gaps:
        if all(abs(g.x - k.x) >= min_distance for k in kept):
            kept.append(g)
    return kept


def _normalize_roi(roi, width: int, height: int):
    """
    Normalize ROI dictionary into pixel coordinates.

    ROI may be provided as 0-1 floats or 0-100 percentages. Values are clamped
    to [0, 1]. Returns (x0, x1, y0, y1) ints or None if invalid.
    """
    try:
        if not isinstance(roi, dict):
            return None

        x0 = float(roi.get("x0", 0.0))
        x1 = float(roi.get("x1", 1.0))
        y0 = float(roi.get("y0", 0.0))
        y1 = float(roi.get("y1", 1.0))

        # Allow percentage input
        if max(x0, x1, y0, y1) > 1.5:
            x0, x1, y0, y1 = x0 / 100.0, x1 / 100.0, y0 / 100.0, y1 / 100.0

        # Clamp to [0, 1]
        x0 = max(0.0, min(1.0, x0))
        x1 = max(0.0, min(1.0, x1))
        y0 = max(0.0, min(1.0, y0))
        y1 = max(0.0, min(1.0, y1))

        # Ensure valid ordering and minimum width/height
        if x1 <= x0 or y1 <= y0:
            return None

        x0_px = int(round(x0 * width))
        x1_px = int(round(x1 * width))
        y0_px = int(round(y0 * height))
        y1_px = int(round(y1 * height))

        if x1_px - x0_px < 8 or y1_px - y0_px < 4:
            return None

        return x0_px, x1_px, y0_px, y1_px
    except Exception:
        return None


def detect_frame_gap(
    jpeg_bytes: bytes,
    smooth_ksize: int = 11,
    min_prominence_ratio: float = 0.10,
    min_distance_ratio: float = 0.05,
    roi: Optional[dict] = None,
) -> DetectionResult:
    """
    Detect brightest gap and return offset from image center.

    Args:
        jpeg_bytes: preview image bytes (JPEG).
        smooth_ksize: gaussian kernel width for smoothing (pixels).
        min_prominence_ratio: fraction of (max - min) used as minimum peak prominence.
        min_distance_ratio: fraction of image width for minimum gap separation.
        roi: Optional dict specifying region of interest:
             {"x0": start, "x1": end, "y0": start, "y1": end}
             Values may be 0-1 fractions or 0-100 percentages.
    """

    # Decode color to allow channel selection; fall back to gray if needed
    arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    color = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if color is None:
        raise ValueError("Failed to decode preview image")

    base_gray = cv2.cvtColor(color, cv2.COLOR_BGR2GRAY)
    full_height, full_width = base_gray.shape[:2]

    # Apply ROI crop in both color and gray space
    roi_bounds = _normalize_roi(roi, width=full_width, height=full_height) if roi else None
    roi_x_offset = 0
    if roi_bounds:
        x0, x1, y0, y1 = roi_bounds
        color = color[y0:y1, x0:x1]
        base_gray = base_gray[y0:y1, x0:x1]
        roi_x_offset = x0

    if color.size == 0 or base_gray.size == 0:
        return DetectionResult(offset_px=0, confidence=0.0, gap_x=None, profile=None, smoothed=None, gaps=[])

    # Pick the strongest color channel (highest variance) to maximize contrast
    channel_stds = [color[..., i].std() for i in range(3)]
    best_ch = int(np.argmax(channel_stds))
    working = color[..., best_ch]

    # Contrast enhancement (CLAHE) to make gaps stand out on flat scans
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    working = clahe.apply(working)

    # Downsample horizontally for stability and speed
    target_width = 512
    h, w = working.shape[:2]
    if w > target_width:
        scale = target_width / float(w)
        new_h = max(1, int(round(h * scale)))
        working = cv2.resize(working, (target_width, new_h), interpolation=cv2.INTER_AREA)
        width_scale = w / float(target_width)
    else:
        width_scale = 1.0

    # Intensity profile
    profile = vertical_profile(working)
    smoothed_intensity = _smooth_profile(profile, smooth_ksize)

    # Gradient-based profile (strong for sharp vertical bars)
    blurred = cv2.GaussianBlur(working, (5, 5), 0)
    sobel = cv2.Sobel(blurred, cv2.CV_32F, 1, 0, ksize=3)
    grad = np.abs(sobel)
    grad_profile = grad.mean(axis=0).astype(np.float32)
    smoothed_grad = _smooth_profile(grad_profile, smooth_ksize)

    def _confidence_from_gap(gap: GapDetection, span: float, signal_len: int) -> float:
        prominence_norm = gap.prominence / max(span, 1e-6)
        width_norm = max(0.35, min(1.0, gap.width / max(1.0, 0.1 * signal_len)))
        return float(np.clip(prominence_norm * (0.5 + 0.5 * width_norm), 0.0, 1.0))

    def _best_gap_for_signal(signal: np.ndarray, polarity: str):
        span = float(signal.max() - signal.min() + 1e-6)
        min_prominence = min_prominence_ratio * span
        min_distance = max(8, int(len(signal) * min_distance_ratio))
        found = _find_gaps(signal, min_prominence=min_prominence, min_distance=min_distance)
        if not found:
            return None
        best_gap = max(found, key=lambda g: g.prominence)
        confidence = _confidence_from_gap(best_gap, span, len(signal))
        gap_global_x = roi_x_offset + int(round(best_gap.x * width_scale))
        return {
            "gap": best_gap,
            "confidence": confidence,
            "gap_x": gap_global_x,
            "polarity": polarity,
            "gaps": found,
        }

    candidates = []
    candidates.append(_best_gap_for_signal(smoothed_intensity, "intensity-bright"))
    candidates.append(_best_gap_for_signal(-smoothed_intensity, "intensity-dark"))
    candidates.append(_best_gap_for_signal(smoothed_grad, "gradient-bright"))
    candidates.append(_best_gap_for_signal(-smoothed_grad, "gradient-dark"))
    candidates = [c for c in candidates if c]

    if not candidates:
        return DetectionResult(offset_px=0, confidence=0.0, gap_x=None, profile=profile, smoothed=smoothed_intensity, gaps=[])

    best = max(candidates, key=lambda c: c["confidence"])
    center = full_width // 2
    offset = best["gap_x"] - center

    return DetectionResult(
        offset_px=int(offset),
        confidence=float(best["confidence"]),
        gap_x=int(best["gap_x"]),
        profile=profile,
        smoothed=smoothed_intensity,
        gaps=best["gaps"],
        polarity=best["polarity"],
    )


def detect_bright_region_roi(
    jpeg_bytes: bytes,
    min_area_ratio: float = 0.05,
    padding: float = 0.0,
    inner_shrink: float = 0.01,
) -> Optional[dict]:
    """
    Detect the largest bright region (lit film window) within a mostly dark mask.

    Returns ROI as normalized fractions {x0,x1,y0,y1} or None if not found.
    """
    gray = jpeg_bytes_to_gray(jpeg_bytes)
    h, w = gray.shape[:2]

    # Smooth to reduce noise, then Otsu threshold to separate bright/dark
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Morphological close to fill small holes, then a light erode to tighten edges
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
    binary = cv2.erode(binary, kernel, iterations=1)

    # Find largest contour
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    area_threshold = min_area_ratio * w * h
    best_box: Optional[Tuple[int, int, int, int]] = None  # x, y, bw, bh
    best_area = 0

    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        area = bw * bh
        if area >= area_threshold and area > best_area:
            best_area = area
            best_box = (x, y, bw, bh)

    if not best_box:
        return None

    x, y, bw, bh = best_box

    # Slightly shrink the detected box to avoid including mask edges
    shrink_x = max(1, min(10, int(round(0.003 * w))))
    shrink_y = max(1, min(10, int(round(0.003 * h))))
    x += shrink_x
    y += shrink_y
    bw = max(1, bw - 2 * shrink_x)
    bh = max(1, bh - 2 * shrink_y)

    # Further crop inward within the bright region so we ignore mask edges
    if inner_shrink > 0:
        inner_x = int(round(inner_shrink * bw))
        inner_y = int(round(inner_shrink * bh))
        if bw - 2 * inner_x >= 8 and bh - 2 * inner_y >= 4:
            x += inner_x
            y += inner_y
            bw -= 2 * inner_x
            bh -= 2 * inner_y

    # Add optional padding (as fraction of image size) and clamp
    pad_x = int(round(padding * w))
    pad_y = int(round(padding * h))
    x0 = max(0, x - pad_x)
    y0 = max(0, y - pad_y)
    x1 = min(w, x + bw + pad_x)
    y1 = min(h, y + bh + pad_y)

    if x1 <= x0 or y1 <= y0:
        return None

    return {
        "x0": round(x0 / w, 4),
        "x1": round(x1 / w, 4),
        "y0": round(y0 / h, 4),
        "y1": round(y1 / h, 4),
    }
