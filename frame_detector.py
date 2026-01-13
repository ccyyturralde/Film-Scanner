"""
Frame edge / gap detector for film scanning previews.

Uses multiple detection methods for robustness:
1. Column brightness analysis - gaps are uniformly bright columns
2. Vertical edge detection - find strong vertical edges bounding the gap
3. Combined scoring - high confidence when methods agree

The gap between frames is where backlight shines through - it's:
- Brighter than surrounding film
- Vertically uniform (constant color top to bottom)
- Bounded by sharp vertical edges

This detector is designed to work reliably on Raspberry Pi.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
import json

import cv2
import numpy as np


def _to_python_type(val):
    """Convert numpy types to native Python types for JSON serialization."""
    if val is None:
        return None
    if isinstance(val, (np.integer, np.int64, np.int32)):
        return int(val)
    if isinstance(val, (np.floating, np.float64, np.float32)):
        return float(val)
    if isinstance(val, np.ndarray):
        return val.tolist()
    if isinstance(val, dict):
        return {k: _to_python_type(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_to_python_type(v) for v in val]
    return val


@dataclass
class GapRegion:
    """A detected gap region (uniform bright columns)."""
    start_x: int  # Left edge of gap (in cropped coordinates)
    end_x: int    # Right edge of gap
    width: int
    mean_brightness: float = 0.0
    edge_score: float = 0.0  # How strong the bounding vertical edges are
    global_start_x: int = 0  # In full image coordinates
    global_end_x: int = 0
    
    @property
    def center_x(self) -> int:
        """Center of gap in global coordinates."""
        return (self.global_start_x + self.global_end_x) // 2
    
    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "start_x": int(self.start_x),
            "end_x": int(self.end_x),
            "width": int(self.width),
            "mean_brightness": float(self.mean_brightness),
            "edge_score": float(self.edge_score),
            "global_start_x": int(self.global_start_x),
            "global_end_x": int(self.global_end_x),
            "center_x": int(self.center_x),
        }


@dataclass
class DetectionResult:
    """Summary of detection suitable for motor alignment."""
    offset_px: int  # positive means gap is to the right of center
    confidence: float
    gap_x: Optional[int]  # X position of the gap center in full image coordinates
    gaps: Optional[List[GapRegion]] = None
    polarity: str = "bright"
    debug_info: Optional[dict] = None
    
    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "offset_px": int(self.offset_px) if self.offset_px is not None else 0,
            "confidence": float(self.confidence) if self.confidence is not None else 0.0,
            "gap_x": int(self.gap_x) if self.gap_x is not None else None,
            "gaps": [g.to_dict() for g in (self.gaps or [])],
            "polarity": self.polarity,
            "debug_info": _to_python_type(self.debug_info),
        }


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
    y0, y1 = int(bright_rows[0]), int(bright_rows[-1] + 1)
    
    # Find first/last columns with bright content
    bright_cols = np.where(col_sums > threshold)[0]
    if len(bright_cols) == 0:
        return (0, 0, w, h)
    x0, x1 = int(bright_cols[0]), int(bright_cols[-1] + 1)
    
    # Add small margin and clamp
    margin_x = int(0.01 * (x1 - x0))
    margin_y = int(0.01 * (y1 - y0))
    x0 = max(0, x0 + margin_x)
    x1 = min(w, x1 - margin_x)
    y0 = max(0, y0 + margin_y)
    y1 = min(h, y1 - margin_y)
    
    return (int(x0), int(y0), int(x1), int(y1))


def compute_column_stats(gray: np.ndarray) -> dict:
    """
    Compute per-column statistics for gap detection.
    
    Returns dict with:
        col_mean: mean brightness per column (0-1)
        col_std: std dev per column (0-1)  
        col_vertical_uniformity: how uniform each column is vertically (0-1, higher = more uniform)
    """
    # Convert to float for calculations
    img = gray.astype(np.float32) / 255.0
    
    col_mean = img.mean(axis=0)
    col_std = img.std(axis=0)
    
    # Compute vertical uniformity: low std = high uniformity
    # Normalize to 0-1 where 1 = perfectly uniform
    max_possible_std = 0.5  # Maximum possible std for 0-1 values
    col_uniformity = 1.0 - np.clip(col_std / max_possible_std, 0, 1)
    
    return {
        "col_mean": col_mean,
        "col_std": col_std,
        "col_uniformity": col_uniformity,
    }


def detect_vertical_edges(gray: np.ndarray) -> np.ndarray:
    """
    Detect vertical edges in the image.
    Returns an array of edge strength per column (sum of Sobel response).
    """
    # Apply Sobel filter for vertical edges (horizontal gradient)
    sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobel_x = np.abs(sobel_x)
    
    # Sum edge strength vertically to get per-column edge score
    edge_strength = sobel_x.sum(axis=0)
    
    # Normalize to 0-1
    max_edge = edge_strength.max()
    if max_edge > 0:
        edge_strength = edge_strength / max_edge
    
    return edge_strength


def compute_vertical_continuity(gray: np.ndarray, threshold: float = 0.6) -> np.ndarray:
    """
    Compute how vertically continuous (full-height) bright columns are.
    
    Returns a score per column (0-1) where 1 means the column is bright
    throughout its full height.
    
    This helps distinguish real inter-frame gaps (full height) from
    bright areas in film content (partial height).
    """
    h, w = gray.shape[:2]
    
    # Normalize to 0-1
    img = gray.astype(np.float32) / 255.0
    
    # For each column, check what fraction of rows are above threshold
    bright_per_col = (img > threshold).sum(axis=0) / h
    
    return bright_per_col


def compute_column_uniformity(gray: np.ndarray) -> np.ndarray:
    """
    Compute how UNIFORM each column is from top to bottom.
    
    This is the key distinguishing feature of a gap vs film content:
    - A gap will have the SAME brightness from top to bottom (high uniformity)
    - Film content will have varying brightness (low uniformity)
    
    Returns a score per column (0-1) where 1 means perfectly uniform.
    Unlike vertical_continuity, this works regardless of brightness level.
    """
    # Normalize to 0-1
    img = gray.astype(np.float32) / 255.0
    
    # Compute std deviation along each column (axis=0)
    col_std = img.std(axis=0)
    
    # Convert std to uniformity score (lower std = higher uniformity)
    # A std of 0 means perfect uniformity (score=1)
    # A std of 0.3 means low uniformity (score~=0)
    uniformity = np.clip(1.0 - (col_std / 0.3), 0, 1)
    
    return uniformity


def find_gap_candidates_brightness(
    stats: dict,
    mean_threshold: float = 0.70,
    std_threshold: float = 0.12,
    vertical_continuity: Optional[np.ndarray] = None,
    min_continuity: float = 0.85,
    column_uniformity: Optional[np.ndarray] = None,
    min_uniformity: float = 0.70,
) -> np.ndarray:
    """
    Create a 1D mask where gap candidates (bright uniform columns) are True.
    
    A column is considered a gap candidate if it passes EITHER:
    
    Method 1 (traditional - bright + low std):
    - Mean brightness is above mean_threshold (relative to max)
    - Standard deviation is below std_threshold (uniform)
    - (Optional) Vertical continuity is above min_continuity (full height)
    
    Method 2 (uniformity-first - works regardless of absolute brightness):
    - Column uniformity is above min_uniformity (very consistent top-to-bottom)
    - Mean brightness is significantly above the minimum (brighter than film content)
    - Vertical continuity is above min_continuity (full height)
    
    Method 3 (adaptive - for difficult lighting):
    - Uses percentile-based thresholding to find the brightest columns
    - Combines with uniformity to reduce false positives
    """
    col_mean = stats["col_mean"]
    col_std = stats["col_std"]
    
    # Get the maximum and minimum mean brightness as reference
    max_mean = float(col_mean.max()) if col_mean.max() > 0 else 1.0
    min_mean = float(col_mean.min())
    mean_range = max_mean - min_mean
    
    # Method 1: Gap columns are bright (high mean) AND uniform (low std)
    bright_mask = col_mean > (mean_threshold * max_mean)
    uniform_mask = col_std < std_threshold
    gap_mask_method1 = bright_mask & uniform_mask
    
    # Method 2: Use column uniformity as primary indicator
    # A gap needs to be brighter than film content but doesn't need to be max brightness
    gap_mask_method2 = np.zeros_like(col_mean, dtype=bool)
    if column_uniformity is not None:
        # Column is uniform AND brighter than the average
        mid_brightness = (max_mean + min_mean) / 2
        brighter_than_mid = col_mean > mid_brightness
        high_uniformity = column_uniformity > min_uniformity
        gap_mask_method2 = brighter_than_mid & high_uniformity
    
    # Method 3: Adaptive percentile-based detection (for difficult cases)
    gap_mask_method3 = np.zeros_like(col_mean, dtype=bool)
    if mean_range > 0.15:  # Only use if there's sufficient brightness variation
        # Find columns in the top 15% of brightness
        brightness_p85 = np.percentile(col_mean, 85)
        very_bright = col_mean >= brightness_p85
        
        # And are also more uniform than average
        if column_uniformity is not None:
            uniformity_median = np.median(column_uniformity)
            above_median_uniformity = column_uniformity > uniformity_median
            gap_mask_method3 = very_bright & above_median_uniformity
    
    # Combine all three methods - a column is a gap if it passes ANY method
    gap_mask = gap_mask_method1 | gap_mask_method2 | gap_mask_method3
    
    # Apply vertical continuity filter if provided (applies to all methods)
    if vertical_continuity is not None:
        # Use adaptive continuity threshold
        continuity_median = np.median(vertical_continuity)
        adaptive_min_continuity = max(min_continuity * 0.85, continuity_median * 1.1)
        continuity_mask = vertical_continuity > min(adaptive_min_continuity, 0.95)
        gap_mask = gap_mask & continuity_mask
    
    return gap_mask


def find_gap_candidates_edges(
    edge_strength: np.ndarray,
    gray_cropped: np.ndarray,
    min_edge_prominence: float = 0.3,
    max_gap_width: int = 200,
) -> List[Tuple[int, int, float]]:
    """
    Find gap candidates by looking for pairs of strong vertical edges
    that bound a bright region.
    
    Returns list of (start_x, end_x, score) tuples.
    """
    candidates = []
    
    # Find local maxima in edge strength (potential gap boundaries)
    # Use a simple peak finder
    window = 15
    peaks = []
    
    for i in range(window, len(edge_strength) - window):
        if edge_strength[i] >= min_edge_prominence:
            # Check if this is a local maximum
            if edge_strength[i] == edge_strength[i-window:i+window+1].max():
                peaks.append((i, float(edge_strength[i])))
    
    # Find pairs of peaks that could bound a gap
    for i, (x1, strength1) in enumerate(peaks):
        for x2, strength2 in peaks[i+1:]:
            width = x2 - x1
            if 10 <= width <= max_gap_width:
                # Check if region between is bright
                region = gray_cropped[:, x1:x2]
                region_mean = region.mean() / 255.0
                
                if region_mean > 0.6:  # Must be bright
                    # Score based on edge strength and brightness
                    score = (strength1 + strength2) / 2 * region_mean
                    candidates.append((x1, x2, float(score)))
    
    return candidates


def find_gap_regions(
    gap_mask: np.ndarray, 
    min_width: int = 5, 
    max_width: int = 500,
    x_offset: int = 0,
    stats: Optional[dict] = None,
    edge_strength: Optional[np.ndarray] = None,
) -> List[GapRegion]:
    """
    Find contiguous gap regions from the mask.
    Optionally enriches with brightness and edge score data.
    
    Returns list of GapRegion sorted by combined score (best first).
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
                region = GapRegion(
                    start_x=int(start),
                    end_x=int(i - 1),
                    width=int(width),
                    global_start_x=int(start + x_offset),
                    global_end_x=int(i - 1 + x_offset),
                )
                
                # Enrich with stats if available
                if stats is not None:
                    region.mean_brightness = float(stats["col_mean"][start:i].mean())
                
                if edge_strength is not None:
                    # Edge score from boundaries
                    left_edge = float(edge_strength[max(0, start-5):start+5].max())
                    right_edge = float(edge_strength[max(0, i-5):min(len(edge_strength), i+5)].max())
                    region.edge_score = (left_edge + right_edge) / 2
                
                regions.append(region)
            in_gap = False
    
    # Handle gap at end
    if in_gap:
        width = len(gap_mask) - start
        if min_width <= width <= max_width:
            region = GapRegion(
                start_x=int(start),
                end_x=int(len(gap_mask) - 1),
                width=int(width),
                global_start_x=int(start + x_offset),
                global_end_x=int(len(gap_mask) - 1 + x_offset),
            )
            if stats is not None:
                region.mean_brightness = float(stats["col_mean"][start:].mean())
            regions.append(region)
    
    # Sort by combined score (brightness + edge strength + proximity to center)
    def score(r: GapRegion, total_width: int = 0) -> float:
        base_score = r.mean_brightness * 0.4 + r.edge_score * 0.3
        
        # Prefer reasonable gap widths
        if 20 <= r.width <= 150:
            width_bonus = 0.2
        elif 10 <= r.width <= 200:
            width_bonus = 0.1
        else:
            width_bonus = 0.0
        
        # Slight preference for gaps closer to center (helps with half-frame alignment)
        if total_width > 0:
            gap_center_local = (r.start_x + r.end_x) / 2
            distance_from_center = abs(gap_center_local - total_width / 2)
            center_score = 0.1 * (1.0 - distance_from_center / (total_width / 2))
        else:
            center_score = 0.0
        
        return base_score + width_bonus + center_score
    
    # Get the width for center scoring
    total_w = len(gap_mask) if len(gap_mask) > 0 else 1
    regions.sort(key=lambda r: score(r, total_w), reverse=True)
    
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
    mean_threshold: float = 0.70,
    std_threshold: float = 0.12,
    min_gap_width: int = 8,
    max_gap_width: int = 300,
    expected_gap_fraction: Optional[float] = None,
    gap_window_fraction: float = 0.3,
    use_edge_detection: bool = True,
    # Legacy parameters (ignored but kept for API compatibility)
    brightness_threshold: float = 0.4,
    diff_threshold: float = 0.35,
    vertical_crop: float = 0.85,
    smooth_ksize: int = 11,
    min_prominence_ratio: float = 0.10,
    min_distance_ratio: float = 0.05,
) -> DetectionResult:
    """
    Detect frame gaps using combined brightness and edge detection.
    
    This first crops to the lit region (excluding black mask borders),
    then uses multiple methods to find the gap:
    1. Column brightness analysis (bright + uniform columns)
    2. Vertical edge detection (strong edges bounding the gap)
    
    Args:
        jpeg_bytes: Preview image bytes (JPEG).
        roi: Optional ROI to crop before analysis.
        mean_threshold: Column mean must be > this * max_mean (0-1).
        std_threshold: Column std dev must be < this (0-1).
        min_gap_width: Minimum gap width in pixels.
        max_gap_width: Maximum gap width in pixels.
        expected_gap_fraction: Expected X position of gap (0-1), for filtering.
        gap_window_fraction: Window around expected_gap_fraction to search.
        use_edge_detection: Whether to use edge detection in addition to brightness.
    
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
        cropped_h = gray_cropped.shape[0]
    
    # Apply median blur to reduce noise/scratches
    gray_blurred = cv2.medianBlur(gray_cropped, 5)
    
    # Compute vertical continuity (helps distinguish full-height gaps from partial bright areas)
    vertical_continuity = compute_vertical_continuity(gray_cropped, threshold=0.5)
    
    # Compute column uniformity (key feature: gaps are uniform top-to-bottom regardless of brightness)
    column_uniformity = compute_column_uniformity(gray_cropped)
    
    # Method 1: Column brightness analysis with vertical continuity filter
    stats = compute_column_stats(gray_blurred)
    gap_mask = find_gap_candidates_brightness(
        stats,
        mean_threshold=mean_threshold,
        std_threshold=std_threshold,
        vertical_continuity=vertical_continuity,
        min_continuity=0.80,  # Must be bright for at least 80% of height
        column_uniformity=column_uniformity,
        min_uniformity=0.70,  # Must be very uniform from top to bottom
    )
    
    # Method 2: Edge detection
    edge_strength = None
    if use_edge_detection:
        edge_strength = detect_vertical_edges(gray_cropped)
    
    # Compute effective max gap width
    effective_max_gap = min(max_gap_width, int(0.15 * cropped_w))
    effective_max_gap = max(effective_max_gap, 100)  # At least 100px
    
    # Find gap regions
    regions = find_gap_regions(
        gap_mask,
        min_width=min_gap_width,
        max_width=effective_max_gap,
        x_offset=lit_x0,
        stats=stats,
        edge_strength=edge_strength,
    )
    
    # Filter out gaps at the extreme edges of the lit region
    # Real inter-frame gaps should be in the interior, not at the mask boundary
    # Use a smaller margin to catch gaps closer to edges
    edge_margin = int(0.03 * cropped_w)  # 3% margin from edges (reduced from 5%)
    interior_regions = []
    edge_regions = []
    
    for r in regions:
        # Check if gap center is within interior (not at edges)
        gap_center_local = (r.start_x + r.end_x) // 2
        if edge_margin <= gap_center_local <= (cropped_w - edge_margin):
            interior_regions.append(r)
        else:
            edge_regions.append(r)
    
    # Prefer interior gaps, but include edge gaps if they're strong enough
    if interior_regions:
        regions = interior_regions
    elif edge_regions:
        # Use edge regions but only if they have high scores
        regions = [r for r in edge_regions if r.mean_brightness > 0.7 and r.edge_score > 0.6]
        if not regions:
            regions = edge_regions  # Fall back to all edge regions
    
    # Build debug info (all native Python types)
    debug_info = {
        "gap_count": int(len(regions)),
        "lit_region": {
            "x0": int(lit_x0),
            "y0": int(lit_y0),
            "x1": int(lit_x1),
            "y1": int(lit_y1),
        },
        "cropped_size": {"w": int(cropped_w), "h": int(cropped_h)},
        "col_mean_max": float(stats["col_mean"].max()),
        "col_mean_min": float(stats["col_mean"].min()),
        "col_std_min": float(stats["col_std"].min()),
        "col_std_max": float(stats["col_std"].max()),
        "mean_threshold": float(mean_threshold),
        "std_threshold": float(std_threshold),
    }
    
    if edge_strength is not None:
        debug_info["edge_strength_max"] = float(edge_strength.max())
        debug_info["edge_strength_mean"] = float(edge_strength.mean())
    
    debug_info["vertical_continuity_max"] = float(vertical_continuity.max())
    debug_info["vertical_continuity_mean"] = float(vertical_continuity.mean())
    debug_info["column_uniformity_max"] = float(column_uniformity.max())
    debug_info["column_uniformity_mean"] = float(column_uniformity.mean())
    
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
            if abs(r.center_x - hint_x) <= half_window
        ]
        if filtered:
            regions = filtered
    
    # Pick the best gap (first after sorting by score)
    best_gap = regions[0]
    
    # Gap center in full image coordinates
    gap_center_x = best_gap.center_x
    
    # Compute offset from image center
    center = full_width // 2
    offset = gap_center_x - center
    
    # Calculate confidence based on multiple factors
    # 1. Gap brightness relative to surroundings
    brightness_score = min(1.0, best_gap.mean_brightness / 0.75)  # Slightly more forgiving
    
    # 2. Edge score (if available)
    edge_score = best_gap.edge_score if best_gap.edge_score > 0 else 0.5
    
    # 3. Gap width reasonableness (prefer 20-120px gaps, wider range)
    if 25 <= best_gap.width <= 120:
        width_score = 1.0
    elif 15 <= best_gap.width <= 150:
        width_score = 0.85  # Better score for reasonable widths
    elif 10 <= best_gap.width <= 200:
        width_score = 0.70
    else:
        width_score = 0.4
    
    # 4. Vertical continuity bonus (from debug_info if available)
    continuity_score = debug_info.get("vertical_continuity_max", 0.5)
    
    # 5. Column uniformity bonus (gaps should be very uniform)
    uniformity_score = debug_info.get("column_uniformity_max", 0.5)
    
    # Combined confidence with enhanced scoring
    confidence = (
        brightness_score * 0.30 +
        edge_score * 0.25 +
        width_score * 0.20 +
        continuity_score * 0.15 +
        uniformity_score * 0.10
    )
    
    # Bonus for having only one clear gap (more confident)
    if len(regions) == 1:
        confidence = min(1.0, confidence * 1.10)
    elif len(regions) == 2:
        confidence = min(1.0, confidence * 1.05)
    
    confidence = min(1.0, max(0.0, confidence))
    
    debug_info["best_gap"] = best_gap.to_dict()
    debug_info["brightness_score"] = float(brightness_score)
    debug_info["edge_score"] = float(edge_score)
    debug_info["width_score"] = float(width_score)
    debug_info["gap_widths"] = [int(r.width) for r in regions[:5]]
    
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


# Helper to ensure all detection results are JSON-serializable
def detection_to_json(result: DetectionResult) -> str:
    """Serialize DetectionResult to JSON string."""
    return json.dumps(result.to_dict())
