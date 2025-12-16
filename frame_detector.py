"""
Frame edge / gap detector for film scanning previews.

Key idea: compute a vertical intensity profile across the preview (mean over
rows), smooth it, then find bright gap peaks between frames. Returns the
offset in pixels from the image center to the strongest gap plus a confidence
score. Inspired by the negative_scanner project.
"""

from dataclasses import dataclass
from typing import List, Optional

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


def detect_frame_gap(
    jpeg_bytes: bytes,
    smooth_ksize: int = 15,
    min_prominence_ratio: float = 0.25,
    min_distance_ratio: float = 0.05,
) -> DetectionResult:
    """
    Detect brightest gap and return offset from image center.

    Args:
        jpeg_bytes: preview image bytes (JPEG).
        smooth_ksize: gaussian kernel width for smoothing (pixels).
        min_prominence_ratio: fraction of (max - min) used as minimum peak prominence.
        min_distance_ratio: fraction of image width for minimum gap separation.
    """

    gray = jpeg_bytes_to_gray(jpeg_bytes)
    profile = vertical_profile(gray)
    smoothed = _smooth_profile(profile, smooth_ksize)

    span = float(smoothed.max() - smoothed.min() + 1e-6)
    min_prominence = min_prominence_ratio * span
    min_distance = max(8, int(len(smoothed) * min_distance_ratio))

    gaps = _find_gaps(smoothed, min_prominence=min_prominence, min_distance=min_distance)
    if not gaps:
        return DetectionResult(offset_px=0, confidence=0.0, gap_x=None, profile=profile, smoothed=smoothed, gaps=[])

    # Choose strongest peak (highest prominence)
    best = max(gaps, key=lambda g: g.prominence)
    center = len(smoothed) // 2
    offset = best.x - center

    # Confidence: normalized prominence * width factor
    prominence_norm = best.prominence / span
    width_norm = min(1.0, best.width / max(1.0, 0.1 * len(smoothed)))
    confidence = float(np.clip(prominence_norm * (0.5 + 0.5 * width_norm), 0.0, 1.0))

    return DetectionResult(
        offset_px=int(offset),
        confidence=confidence,
        gap_x=best.x,
        profile=profile,
        smoothed=smoothed,
        gaps=gaps,
    )
