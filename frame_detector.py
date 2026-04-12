"""
Frame Gap Detector for 35mm Film Scanner

Detects inter-frame gaps (rebate areas) on 35mm film for frame alignment
WITHOUT relying on sprocket holes. Uses column brightness profiling to
find the narrow unexposed strips between exposed frames.

35mm Film Inter-Frame Gap Characteristics:
- Frame pitch: 38mm center-to-center (same as 8 sprocket pitches)
- Image area: 24mm x 36mm
- Inter-frame gap: ~2-2.5mm of unexposed film base
- Color negatives: gap is bright orange base (backlit)
- B&W negatives: gap is nearly clear (very bright backlit)
- Slides/positives: gap is opaque (dark backlit)

The gap spans the full height of the film, so column-wise brightness
averaging produces a strong 1D signal regardless of image content.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import json

import cv2
import numpy as np


FRAME_PITCH_MM = 38.0
FRAME_GAP_MM = 2.0
IMAGE_WIDTH_MM = 36.0


@dataclass
class FrameGap:
    """A detected inter-frame gap."""
    center_x: int
    width_px: int
    brightness: float
    confidence: float = 1.0

    def to_dict(self) -> dict:
        return {
            "center_x": int(self.center_x),
            "width_px": int(self.width_px),
            "brightness": round(float(self.brightness), 3),
            "confidence": round(float(self.confidence), 3),
        }


@dataclass
class FrameGapDetectionResult:
    """Result of frame gap detection for alignment."""
    offset_px: int
    confidence: float
    aligned: bool

    gaps: List[FrameGap] = field(default_factory=list)

    frame_pitch_px: Optional[float] = None
    px_per_mm: Optional[float] = None
    film_polarity: str = "negative"

    debug_info: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "offset_px": int(self.offset_px),
            "confidence": round(float(self.confidence), 3),
            "aligned": bool(self.aligned),
            "gap_count": len(self.gaps),
            "gaps": [g.to_dict() for g in self.gaps],
            "frame_pitch_px": round(float(self.frame_pitch_px), 1) if self.frame_pitch_px else None,
            "px_per_mm": round(float(self.px_per_mm), 2) if self.px_per_mm else None,
            "film_polarity": self.film_polarity,
            "debug_info": self.debug_info,
        }


def _jpeg_to_gray(jpeg_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError("Failed to decode image")
    return img


def _gaussian_smooth_1d(signal: np.ndarray, sigma: float) -> np.ndarray:
    """Smooth a 1D signal with a Gaussian kernel (no scipy dependency)."""
    ksize = int(sigma * 6) | 1
    ksize = max(3, ksize)
    kernel = cv2.getGaussianKernel(ksize, sigma).flatten()
    return np.convolve(signal, kernel, mode='same')


def detect_film_polarity(
    gray: np.ndarray,
    roi_top_frac: float = 0.20,
    roi_bottom_frac: float = 0.80,
) -> str:
    """
    Auto-detect whether the film is a negative or positive/slide.

    On a backlit negative the inter-frame gaps (film base) are brighter than
    the image areas. On a positive the gaps are darker. We look at the
    brightness histogram of the image band: negatives tend to have a
    concentration of dark pixels (dense image) with a bright tail (base),
    while positives are the reverse.

    Returns "negative" or "positive".
    """
    h, w = gray.shape[:2]
    y0, y1 = int(h * roi_top_frac), int(h * roi_bottom_frac)
    band = gray[y0:y1, :]

    profile = band.mean(axis=0).astype(np.float64)
    median_val = float(np.median(profile))
    bright_cols = float(np.sum(profile > median_val + 30))
    dark_cols = float(np.sum(profile < median_val - 30))

    # For negatives: there are more dark columns (image) and fewer bright
    # spikes (gaps/base). The bright outliers are the gaps.
    if bright_cols <= dark_cols:
        return "negative"
    return "positive"


def _find_gaps_in_profile(
    profile: np.ndarray,
    polarity: str,
    min_gap_width_px: int = 3,
    max_gap_width_px: int = 60,
) -> List[Tuple[int, int, float]]:
    """
    Find gap regions in a 1D brightness profile.

    For negatives, gaps are local brightness peaks.
    For positives, gaps are local brightness valleys (we invert first).

    Returns list of (center_x, width, peak_brightness) tuples.
    """
    prof = profile.astype(np.float64)

    if polarity == "positive":
        prof = prof.max() - prof

    # Adaptive threshold: pixels significantly above the local median are
    # candidates for gap regions.
    baseline = _gaussian_smooth_1d(prof, sigma=max(len(prof) * 0.05, 20))
    deviation = prof - baseline

    # Threshold at the 85th percentile of positive deviations — gap columns
    # should be noticeably brighter than their surroundings.
    pos_dev = deviation[deviation > 0]
    if len(pos_dev) == 0:
        return []
    thresh = float(np.percentile(pos_dev, 75))
    thresh = max(thresh, 5.0)

    binary = (deviation > thresh).astype(np.uint8)

    # Morphological cleanup
    kernel = np.ones(max(3, min_gap_width_px // 2), dtype=np.uint8)
    binary = cv2.morphologyEx(binary.reshape(1, -1), cv2.MORPH_CLOSE, kernel.reshape(1, -1)).flatten()
    binary = cv2.morphologyEx(binary.reshape(1, -1), cv2.MORPH_OPEN, kernel.reshape(1, -1)).flatten()

    # Find contiguous runs
    gaps: List[Tuple[int, int, float]] = []
    in_gap = False
    start = 0
    for i in range(len(binary)):
        if binary[i] and not in_gap:
            in_gap = True
            start = i
        elif not binary[i] and in_gap:
            in_gap = False
            width = i - start
            if min_gap_width_px <= width <= max_gap_width_px:
                center = start + width // 2
                peak_val = float(prof[start:i].max())
                gaps.append((center, width, peak_val))
    if in_gap:
        width = len(binary) - start
        if min_gap_width_px <= width <= max_gap_width_px:
            center = start + width // 2
            peak_val = float(prof[start:].max())
            gaps.append((center, width, peak_val))

    return gaps


def _validate_gaps(
    raw_gaps: List[Tuple[int, int, float]],
    image_width: int,
    expected_pitch_px: Optional[float] = None,
) -> List[FrameGap]:
    """
    Filter and score detected gaps based on consistency.

    If we know the expected frame pitch in pixels, reject gaps whose spacing
    is inconsistent. Otherwise, use the most common spacing as a reference.
    """
    if not raw_gaps:
        return []

    # Sort by x position
    raw_gaps = sorted(raw_gaps, key=lambda g: g[0])

    if len(raw_gaps) == 1:
        c, w, b = raw_gaps[0]
        return [FrameGap(center_x=c, width_px=w, brightness=b, confidence=0.5)]

    # Calculate consecutive spacings
    spacings = []
    for i in range(len(raw_gaps) - 1):
        spacings.append(raw_gaps[i + 1][0] - raw_gaps[i][0])

    if expected_pitch_px and expected_pitch_px > 0:
        ref_pitch = expected_pitch_px
    else:
        ref_pitch = float(np.median(spacings)) if spacings else None

    results: List[FrameGap] = []
    for idx, (c, w, b) in enumerate(raw_gaps):
        confidence = 0.6

        # Boost confidence if spacing to neighbours matches expected pitch
        if ref_pitch and ref_pitch > 0:
            for neighbour_idx in (idx - 1, idx + 1):
                if 0 <= neighbour_idx < len(raw_gaps):
                    dist = abs(raw_gaps[neighbour_idx][0] - c)
                    ratio = dist / ref_pitch
                    # Accept integer multiples of the pitch (gap might be missed)
                    nearest_mult = round(ratio)
                    if nearest_mult >= 1 and abs(ratio - nearest_mult) < 0.15:
                        confidence += 0.15

        # Penalise gaps near image edges (may be partial)
        edge_margin = image_width * 0.05
        if c < edge_margin or c > image_width - edge_margin:
            confidence -= 0.2

        confidence = max(0.0, min(1.0, confidence))
        results.append(FrameGap(center_x=c, width_px=w, brightness=b, confidence=confidence))

    return results


def calculate_frame_pitch(gaps: List[FrameGap]) -> Optional[float]:
    """
    Calculate frame pitch in pixels from detected gap positions.

    Uses median spacing with IQR outlier rejection (same strategy as
    sprocket pitch calculation).
    """
    if len(gaps) < 2:
        return None

    spacings = []
    sorted_gaps = sorted(gaps, key=lambda g: g.center_x)
    for i in range(len(sorted_gaps) - 1):
        dx = sorted_gaps[i + 1].center_x - sorted_gaps[i].center_x
        if dx > 0:
            spacings.append(dx)

    if not spacings:
        return None

    median_s = float(np.median(spacings))

    if len(spacings) >= 3:
        q1, q3 = float(np.percentile(spacings, 25)), float(np.percentile(spacings, 75))
        iqr = q3 - q1
        margin = max(iqr, median_s * 0.15) * 1.5
        filtered = [s for s in spacings if q1 - margin <= s <= q3 + margin]
        if filtered:
            return float(np.median(filtered))

    return median_s


def calculate_frame_offset(
    gaps: List[FrameGap],
    image_width: int,
    frame_pitch_px: Optional[float] = None,
) -> Tuple[int, float]:
    """
    Calculate pixel offset needed to center a frame in the image.

    The ideal position is when the two nearest gaps straddle the image edges
    symmetrically (one at each side), placing a complete frame in the center.

    Returns (offset_px, confidence). Positive offset = move film right.
    """
    if not gaps:
        return 0, 0.0

    center = image_width / 2.0

    if frame_pitch_px is None:
        frame_pitch_px = calculate_frame_pitch(gaps)

    if frame_pitch_px is None or frame_pitch_px <= 0:
        # Fallback: aim for the midpoint between the two closest gaps to center
        if len(gaps) >= 2:
            sorted_g = sorted(gaps, key=lambda g: g.center_x)
            best_pair = None
            best_dist = float('inf')
            for i in range(len(sorted_g) - 1):
                mid = (sorted_g[i].center_x + sorted_g[i + 1].center_x) / 2.0
                d = abs(mid - center)
                if d < best_dist:
                    best_dist = d
                    best_pair = (sorted_g[i], sorted_g[i + 1])
            if best_pair:
                mid = (best_pair[0].center_x + best_pair[1].center_x) / 2.0
                return int(center - mid), 0.4
        return 0, 0.0

    # With known pitch: find the gap arrangement that best centres a frame.
    # For each gap, compute where the frame centre would be if this gap were
    # the left boundary of a frame (frame centre = gap + pitch/2).
    sorted_g = sorted(gaps, key=lambda g: g.center_x)

    best_offset = 0
    best_confidence = 0.0

    for gap in sorted_g:
        # This gap could be the left boundary
        frame_center_if_left = gap.center_x + frame_pitch_px / 2.0
        offset_left = int(center - frame_center_if_left)

        # Or the right boundary
        frame_center_if_right = gap.center_x - frame_pitch_px / 2.0
        offset_right = int(center - frame_center_if_right)

        for offset in (offset_left, offset_right):
            # Score: how well would the gaps line up after applying this offset?
            score = 0.0
            for g in sorted_g:
                shifted = g.center_x + offset
                # Distance to nearest image edge
                dist_left_edge = abs(shifted)
                dist_right_edge = abs(shifted - image_width)
                min_edge_dist = min(dist_left_edge, dist_right_edge)
                # Good if gap is near an edge (within half a gap width of tolerance)
                if min_edge_dist < frame_pitch_px * 0.08:
                    score += g.confidence
            if score > best_confidence:
                best_confidence = score
                best_offset = offset

    # If we found no good edge alignment, fall back to centering between
    # the pair of gaps that best brackets the image center.
    if best_confidence < 0.3 and len(sorted_g) >= 2:
        for i in range(len(sorted_g) - 1):
            spacing = sorted_g[i + 1].center_x - sorted_g[i].center_x
            ratio = spacing / frame_pitch_px
            if 0.7 < ratio < 1.3:
                mid = (sorted_g[i].center_x + sorted_g[i + 1].center_x) / 2.0
                offset = int(center - mid)
                conf = min(sorted_g[i].confidence, sorted_g[i + 1].confidence) * 0.8
                if conf > best_confidence:
                    best_confidence = conf
                    best_offset = offset

    best_confidence = min(1.0, best_confidence)
    return best_offset, best_confidence


def detect_frame_gaps(
    jpeg_bytes: bytes,
    roi_top_frac: float = 0.20,
    roi_bottom_frac: float = 0.80,
    polarity: Optional[str] = None,
    smooth_sigma: float = 5.0,
    alignment_tolerance_px: int = 20,
    expected_pitch_px: Optional[float] = None,
) -> FrameGapDetectionResult:
    """
    Main frame gap detection function for alignment.

    Analyses the brightness profile across the image to find inter-frame
    gaps, then computes the offset needed to centre a frame.

    Args:
        jpeg_bytes: Preview image as JPEG bytes.
        roi_top_frac: Top of analysis band as fraction of image height.
        roi_bottom_frac: Bottom of analysis band as fraction of image height.
        polarity: "negative" or "positive" (auto-detected if None).
        smooth_sigma: Gaussian smoothing sigma for the brightness profile.
        alignment_tolerance_px: Pixels within which frame is considered aligned.
        expected_pitch_px: If known from prior calibration.

    Returns:
        FrameGapDetectionResult with alignment info and detected gaps.
    """
    try:
        gray = _jpeg_to_gray(jpeg_bytes)
    except Exception as e:
        return FrameGapDetectionResult(
            offset_px=0, confidence=0.0, aligned=False,
            debug_info={"error": str(e)},
        )

    h, w = gray.shape[:2]
    y0 = int(h * roi_top_frac)
    y1 = int(h * roi_bottom_frac)
    band = gray[y0:y1, :]

    # Auto-detect polarity if not specified
    if polarity is None:
        polarity = detect_film_polarity(gray, roi_top_frac, roi_bottom_frac)

    # Column brightness profile
    raw_profile = band.mean(axis=0).astype(np.float64)
    smoothed = _gaussian_smooth_1d(raw_profile, smooth_sigma)

    # Estimate gap width in pixels for filtering
    if expected_pitch_px:
        gap_width_est = expected_pitch_px * (FRAME_GAP_MM / FRAME_PITCH_MM)
    else:
        gap_width_est = w * 0.01  # rough 1% of width
    min_gap_w = max(3, int(gap_width_est * 0.3))
    max_gap_w = max(min_gap_w + 5, int(gap_width_est * 5.0))

    raw_gaps = _find_gaps_in_profile(smoothed, polarity, min_gap_w, max_gap_w)
    gaps = _validate_gaps(raw_gaps, w, expected_pitch_px)

    # Calculate frame pitch from gaps
    frame_pitch_px_detected = calculate_frame_pitch(gaps)
    frame_pitch = expected_pitch_px or frame_pitch_px_detected

    px_per_mm = None
    if frame_pitch and frame_pitch > 0:
        px_per_mm = frame_pitch / FRAME_PITCH_MM

    offset_px, confidence = calculate_frame_offset(gaps, w, frame_pitch)
    aligned = abs(offset_px) <= alignment_tolerance_px and confidence > 0.3

    debug_info = {
        "image_size": {"width": w, "height": h},
        "roi": {"y0": y0, "y1": y1},
        "polarity": polarity,
        "gap_count": len(gaps),
        "frame_pitch_px": round(frame_pitch, 1) if frame_pitch else None,
        "px_per_mm": round(px_per_mm, 2) if px_per_mm else None,
        "profile_min": round(float(smoothed.min()), 1),
        "profile_max": round(float(smoothed.max()), 1),
        "gap_positions": [g.center_x for g in gaps],
        "alignment_tolerance": alignment_tolerance_px,
    }

    return FrameGapDetectionResult(
        offset_px=offset_px,
        confidence=confidence,
        aligned=aligned,
        gaps=gaps,
        frame_pitch_px=frame_pitch,
        px_per_mm=px_per_mm,
        film_polarity=polarity,
        debug_info=debug_info,
    )


def calibrate_from_gaps(jpeg_bytes: bytes, polarity: Optional[str] = None) -> Optional[dict]:
    """
    Calibrate scanner using visible inter-frame gaps.

    Requires at least 2 gaps to be visible so that frame pitch can be
    measured.

    Returns calibration dict or None.
    """
    result = detect_frame_gaps(jpeg_bytes, polarity=polarity)

    if not result.frame_pitch_px or len(result.gaps) < 2:
        return None

    return {
        "frame_pitch_px": result.frame_pitch_px,
        "px_per_mm": result.px_per_mm,
        "gaps_detected": len(result.gaps),
        "confidence": result.confidence,
        "film_polarity": result.film_polarity,
    }


def detection_to_json(result: FrameGapDetectionResult) -> str:
    return json.dumps(result.to_dict(), indent=2)
