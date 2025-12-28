"""
Frame edge / gap detector for film scanning previews.

Uses column-statistics approach inspired by negative_scanner project:
- First crops to the bright lit region (excluding black mask borders)
- Computes per-column mean and standard deviation
- Gaps between frames are columns that are BRIGHT (high mean) AND UNIFORM (low std)
- Finds contiguous gap regions for alignment

This is much simpler and more robust than peak-finding approaches.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np


@dataclass
class GapRegion:
    """A detected gap region (uniform bright columns)."""
    start_x: int  # Left edge of gap (in cropped coordinates)
    end_x: int    # Right edge of gap
    width: int
    mean_brightness: float
    global_start_x: int = 0  # In full image coordinates
    global_end_x: int = 0


@dataclass
class DetectionResult:
    """Summary of detection suitable for motor alignment."""
    offset_px: int  # positive means gap is to the right of center
    confidence: float
    gap_x: Optional[int]  # X position of the gap center in full image coordinates
    gaps: Optional[List[GapRegion]] = None
    polarity: str = "bright"
    debug_info: Optional[dict] = None


def jpeg_bytes_to_color(jpeg_bytes: bytes) -> np.ndarray:
    """Decode JPEG bytes to a BGR color image."""
    arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode preview image")
    return img


def jpeg_bytes_to_gray(jpeg_bytes: bytes) -> np.ndarray:
    """Decode JPEG bytes to a uint8 grayscale image."""
    arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError("Failed to decode preview image")
    return img


def find_lit_region(gray: np.ndarray, threshold_ratio: float = 0.3) -> Tuple[int, int, int, int]:
    """
    Find the lit (bright) region of the image, excluding dark mask borders.
    
    Returns (x0, y0, x1, y1) of the bounding box of the bright region.
    """
    h, w = gray.shape[:2]
    
    # Use Otsu's method to find threshold between dark mask and lit region
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Find rows and columns that have significant bright content
    row_sums = binary.mean(axis=1)
    col_sums = binary.mean(axis=0)
    
    threshold = binary.max() * threshold_ratio
    
    # Find first/last rows with bright content
    bright_rows = np.where(row_sums > threshold)[0]
    if len(bright_rows) == 0:
        return (0, 0, w, h)
    y0, y1 = bright_rows[0], bright_rows[-1] + 1
    
    # Find first/last columns with bright content
    bright_cols = np.where(col_sums > threshold)[0]
    if len(bright_cols) == 0:
        return (0, 0, w, h)
    x0, x1 = bright_cols[0], bright_cols[-1] + 1
    
    # Add small margin and clamp
    margin_x = int(0.01 * (x1 - x0))
    margin_y = int(0.01 * (y1 - y0))
    x0 = max(0, x0 + margin_x)
    x1 = min(w, x1 - margin_x)
    y0 = max(0, y0 + margin_y)
    y1 = min(h, y1 - margin_y)
    
    return (x0, y0, x1, y1)


def compute_column_stats(gray: np.ndarray) -> dict:
    """
    Compute per-column statistics.
    
    Returns dict with:
        col_mean: mean brightness per column (0-1)
        col_std: std dev per column (0-1)
    """
    # Convert to float for calculations
    img = gray.astype(np.float32) / 255.0
    
    col_mean = img.mean(axis=0)
    col_std = img.std(axis=0)
    
    return {
        "col_mean": col_mean,
        "col_std": col_std,
    }


def find_gap_mask(
    stats: dict,
    mean_threshold: float = 0.7,
    std_threshold: float = 0.12,
) -> np.ndarray:
    """
    Create a 1D mask where gaps (uniform bright columns) are True.
    
    A column is considered a gap if:
    - Mean brightness is above mean_threshold (bright column)
    - Standard deviation is below std_threshold (uniform - no texture)
    """
    col_mean = stats["col_mean"]
    col_std = stats["col_std"]
    
    # Get the maximum mean brightness as reference
    max_mean = col_mean.max() if col_mean.max() > 0 else 1.0
    
    # Gap columns are bright (high mean) AND uniform (low std)
    bright_mask = col_mean > (mean_threshold * max_mean)
    uniform_mask = col_std < std_threshold
    
    gap_mask = bright_mask & uniform_mask
    
    return gap_mask


def find_gap_regions(
    gap_mask: np.ndarray, 
    min_width: int = 5, 
    max_width: int = 500,  # Real gaps are narrow
    x_offset: int = 0
) -> List[GapRegion]:
    """
    Find contiguous gap regions from the mask.
    Filters by both min and max width (real gaps are narrow).
    Returns list of GapRegion sorted by width (largest valid gap first).
    """
    regions = []
    in_gap = False
    start = 0
    
    for i, is_gap in enumerate(gap_mask):
        if is_gap and not in_gap:
            in_gap = True
            start = i
        elif not is_gap and in_gap:
            width = i - start
            if min_width <= width <= max_width:
                regions.append(GapRegion(
                    start_x=start,
                    end_x=i - 1,
                    width=width,
                    mean_brightness=0.0,
                    global_start_x=start + x_offset,
                    global_end_x=i - 1 + x_offset,
                ))
            in_gap = False
    
    # Handle gap at end
    if in_gap:
        width = len(gap_mask) - start
        if min_width <= width <= max_width:
            regions.append(GapRegion(
                start_x=start,
                end_x=len(gap_mask) - 1,
                width=width,
                mean_brightness=0.0,
                global_start_x=start + x_offset,
                global_end_x=len(gap_mask) - 1 + x_offset,
            ))
    
    # Sort by width (largest first, but all are within valid range)
    regions.sort(key=lambda r: r.width, reverse=True)
    
    return regions


def _normalize_roi(roi, width: int, height: int):
    """Normalize ROI dictionary into pixel coordinates."""
    try:
        if not isinstance(roi, dict):
            return None

        x0 = float(roi.get("x0", 0.0))
        x1 = float(roi.get("x1", 1.0))
        y0 = float(roi.get("y0", 0.0))
        y1 = float(roi.get("y1", 1.0))

        if max(x0, x1, y0, y1) > 1.5:
            x0, x1, y0, y1 = x0 / 100.0, x1 / 100.0, y0 / 100.0, y1 / 100.0

        x0 = max(0.0, min(1.0, x0))
        x1 = max(0.0, min(1.0, x1))
        y0 = max(0.0, min(1.0, y0))
        y1 = max(0.0, min(1.0, y1))

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
    roi: Optional[dict] = None,
    mean_threshold: float = 0.75,
    std_threshold: float = 0.10,
    min_gap_width: int = 8,
    expected_gap_fraction: Optional[float] = None,
    gap_window_fraction: float = 0.3,
    # Legacy parameters (ignored but kept for API compatibility)
    brightness_threshold: float = 0.4,
    diff_threshold: float = 0.35,
    vertical_crop: float = 0.85,
    smooth_ksize: int = 11,
    min_prominence_ratio: float = 0.10,
    min_distance_ratio: float = 0.05,
) -> DetectionResult:
    """
    Detect frame gaps using column statistics approach.
    
    This first crops to the lit region (excluding black mask borders),
    then looks for columns that are bright AND uniform - indicating the
    backlight shining through gaps between frames.
    
    Args:
        jpeg_bytes: Preview image bytes (JPEG).
        roi: Optional ROI to crop before analysis.
        mean_threshold: Column mean must be > this * max_mean (0-1).
        std_threshold: Column std dev must be < this (0-1).
        min_gap_width: Minimum gap width in pixels.
        expected_gap_fraction: Expected X position of gap (0-1), for filtering.
        gap_window_fraction: Window around expected_gap_fraction to search.
    
    Returns:
        DetectionResult with offset from center and confidence.
    """
    # Decode image
    try:
        color = jpeg_bytes_to_color(jpeg_bytes)
    except Exception as e:
        return DetectionResult(
            offset_px=0,
            confidence=0.0,
            gap_x=None,
            debug_info={"error": str(e)},
        )
    
    gray = cv2.cvtColor(color, cv2.COLOR_BGR2GRAY)
    full_height, full_width = gray.shape[:2]
    
    # First, find the lit region to exclude black mask borders
    lit_x0, lit_y0, lit_x1, lit_y1 = find_lit_region(gray)
    
    # Crop to lit region
    gray_cropped = gray[lit_y0:lit_y1, lit_x0:lit_x1]
    
    if gray_cropped.size == 0:
        return DetectionResult(
            offset_px=0,
            confidence=0.0,
            gap_x=None,
            debug_info={"error": "Empty lit region"},
        )
    
    cropped_h, cropped_w = gray_cropped.shape[:2]
    
    # Further crop top/bottom by a small percentage to avoid edge artifacts
    edge_crop_y = int(0.05 * cropped_h)
    if edge_crop_y > 0 and cropped_h - 2 * edge_crop_y > 10:
        gray_cropped = gray_cropped[edge_crop_y:cropped_h - edge_crop_y, :]
    
    # Apply median blur to reduce noise/scratches
    gray_cropped = cv2.medianBlur(gray_cropped, 5)
    
    # Compute column statistics
    stats = compute_column_stats(gray_cropped)
    
    # Find gap mask
    gap_mask = find_gap_mask(
        stats,
        mean_threshold=mean_threshold,
        std_threshold=std_threshold,
    )
    
    # Find gap regions (with x_offset to convert back to full image coords)
    # Real inter-frame gaps are narrow - typically 1-5% of frame width
    # Use max_width to filter out large bright areas in film content
    max_gap_width = int(0.08 * cropped_w)  # Max 8% of cropped width
    max_gap_width = max(max_gap_width, 300)  # But at least 300px for high-res images
    
    regions = find_gap_regions(gap_mask, min_width=min_gap_width, max_width=max_gap_width, x_offset=lit_x0)
    
    debug_info = {
        "gap_count": len(regions),
        "lit_region": {"x0": lit_x0, "y0": lit_y0, "x1": lit_x1, "y1": lit_y1},
        "cropped_size": {"w": cropped_w, "h": cropped_h},
        "col_mean_max": float(stats["col_mean"].max()),
        "col_mean_min": float(stats["col_mean"].min()),
        "col_std_min": float(stats["col_std"].min()),
        "col_std_max": float(stats["col_std"].max()),
    }
    
    if not regions:
        return DetectionResult(
            offset_px=0,
            confidence=0.0,
            gap_x=None,
            gaps=[],
            debug_info=debug_info,
        )
    
    # If we have an expected gap position, filter candidates
    if expected_gap_fraction is not None:
        hint_x = expected_gap_fraction * full_width
        half_window = gap_window_fraction * full_width * 0.5
        
        filtered = [
            r for r in regions
            if abs(((r.global_start_x + r.global_end_x) / 2) - hint_x) <= half_window
        ]
        if filtered:
            regions = filtered
    
    # Pick the best gap (widest after filtering)
    best_gap = regions[0]  # Already sorted by width
    
    # Gap center in full image coordinates
    gap_center_x = (best_gap.global_start_x + best_gap.global_end_x) // 2
    
    # Compute offset from image center
    center = full_width // 2
    offset = gap_center_x - center
    
    # Confidence based on gap width relative to cropped region
    # Wider gaps and more uniform columns = higher confidence
    gap_fraction = best_gap.width / max(1, cropped_w)
    confidence = min(1.0, gap_fraction * 5.0 + 0.3)  # Scale so typical gaps give ~0.5-0.8
    
    debug_info["best_gap_width"] = best_gap.width
    debug_info["best_gap_center"] = gap_center_x
    debug_info["gap_widths"] = [r.width for r in regions[:5]]
    
    return DetectionResult(
        offset_px=int(offset),
        confidence=float(confidence),
        gap_x=int(gap_center_x),
        gaps=regions,
        polarity="bright",
        debug_info=debug_info,
    )


def detect_bright_region_roi(
    image_input,
    min_area_ratio: float = 0.05,
    padding: float = 0.0,
    inner_shrink: float = 0.01,
) -> Optional[dict]:
    """
    Detect the largest bright region (lit film window) within a mostly dark mask.
    
    Args:
        image_input: Either JPEG bytes or a grayscale numpy array.
    
    Returns ROI as normalized fractions {x0,x1,y0,y1} or None if not found.
    """
    if isinstance(image_input, bytes):
        gray = jpeg_bytes_to_gray(image_input)
    elif isinstance(image_input, np.ndarray):
        if image_input.ndim == 3:
            gray = cv2.cvtColor(image_input, cv2.COLOR_BGR2GRAY)
        else:
            gray = image_input
    else:
        return None
    
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
    best_box: Optional[Tuple[int, int, int, int]] = None
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

    # Slightly shrink the detected box
    shrink_x = max(1, min(10, int(round(0.003 * w))))
    shrink_y = max(1, min(10, int(round(0.003 * h))))
    x += shrink_x
    y += shrink_y
    bw = max(1, bw - 2 * shrink_x)
    bh = max(1, bh - 2 * shrink_y)

    # Further crop inward
    if inner_shrink > 0:
        inner_x = int(round(inner_shrink * bw))
        inner_y = int(round(inner_shrink * bh))
        if bw - 2 * inner_x >= 8 and bh - 2 * inner_y >= 4:
            x += inner_x
            y += inner_y
            bw -= 2 * inner_x
            bh -= 2 * inner_y

    # Add optional padding and clamp
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
