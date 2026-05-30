"""
Sprocket Hole Detector for 35mm Film Scanner

Detects sprocket holes on the top and/or bottom edges of 35mm film for precise
frame alignment.

35mm Film Standard Specifications:
- Sprocket pitch: 4.75mm (center to center)
- Sprocket holes per frame: 8 (4 top, 4 bottom)
- Sprocket hole size: ~2.8mm x 1.98mm (KS-1870 standard)
- Frame width: ~38mm (including sprocket area)
- Image area: 24mm x 36mm

This detector finds sprocket holes as bright regions and uses their X positions
for alignment.  Holes may be only partially visible (top/bottom clipped by the
scanning window) — the detector handles this by relaxing aspect-ratio and area
constraints and focusing on the regular horizontal spacing pattern.

Hardware Setup:
- Film advanced by pancake stepper + belt + rollers with silicone O-rings
  (friction drive — no sprocket engagement)
- Sprocket rows partially visible (~70%) at top and/or bottom of preview
- Top and bottom of each sprocket hole may be clipped by the scanning gate
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
import json

import cv2
import numpy as np


@dataclass
class SprocketHole:
    """A detected sprocket hole."""
    x: int          # Center X position
    y: int          # Center Y position
    width: int      # Hole width in pixels
    height: int     # Hole height in pixels
    area: int       # Hole area in pixels
    confidence: float = 1.0
    
    def to_dict(self) -> dict:
        return {
            "x": int(self.x),
            "y": int(self.y),
            "width": int(self.width),
            "height": int(self.height),
            "area": int(self.area),
            "confidence": float(self.confidence),
        }


@dataclass 
class SprocketDetectionResult:
    """Result of sprocket hole detection for frame alignment."""
    # Alignment info
    offset_px: int                    # Offset from ideal alignment (positive = move right)
    confidence: float                 # Detection confidence (0-1)
    aligned: bool                     # True if within alignment tolerance
    
    # Detected sprocket holes
    sprocket_holes: List[SprocketHole] = field(default_factory=list)
    top_sprockets: List[SprocketHole] = field(default_factory=list)
    bottom_sprockets: List[SprocketHole] = field(default_factory=list)
    
    # Calibration data
    sprocket_pitch_px: Optional[float] = None  # Measured pixels per sprocket
    px_per_mm: Optional[float] = None          # Pixels per millimeter
    
    # Debug info
    debug_info: Optional[dict] = None
    
    def to_dict(self) -> dict:
        return {
            "offset_px": int(self.offset_px),
            "confidence": float(self.confidence),
            "aligned": bool(self.aligned),
            "sprocket_count": len(self.sprocket_holes),
            "top_sprocket_count": len(self.top_sprockets),
            "bottom_sprocket_count": len(self.bottom_sprockets),
            "sprocket_pitch_px": float(self.sprocket_pitch_px) if self.sprocket_pitch_px else None,
            "px_per_mm": float(self.px_per_mm) if self.px_per_mm else None,
            "sprocket_holes": [s.to_dict() for s in self.sprocket_holes],
            "debug_info": self.debug_info,
        }


# 35mm film constants
SPROCKET_PITCH_MM = 4.75          # mm between sprocket centers
SPROCKETS_PER_FRAME = 8           # 4 top + 4 bottom
SPROCKET_WIDTH_MM = 2.8           # Standard sprocket width
SPROCKET_HEIGHT_MM = 1.98         # Standard sprocket height
FRAME_PITCH_MM = 38.0             # Distance between frame centers (8 sprockets * 4.75mm)


def jpeg_bytes_to_gray(jpeg_bytes: bytes) -> np.ndarray:
    """Decode JPEG bytes to grayscale image."""
    arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError("Failed to decode image")
    return img


def jpeg_bytes_to_color(jpeg_bytes: bytes) -> np.ndarray:
    """Decode JPEG bytes to BGR color image."""
    arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode image")
    return img


def find_sprocket_regions(
    gray: np.ndarray,
    sprocket_fraction: float = 0.18,
) -> Tuple[np.ndarray, np.ndarray, int, int]:
    """
    Extract the top and bottom regions where sprocket holes are expected.
    
    With a friction-drive transport (belt + silicone O-ring rollers), the
    sprocket holes are partially visible at the film edges — typically ~70%
    of the hole height is clipped by the scanning gate.  We use a generous
    region fraction (18% of image height) to capture whatever is visible.
    
    Args:
        gray: Grayscale image
        sprocket_fraction: Fraction of image height for sprocket regions
        
    Returns:
        (top_region, bottom_region, top_y_offset, bottom_y_offset)
    """
    h, w = gray.shape[:2]
    sprocket_height = int(h * sprocket_fraction)
    
    top_region = gray[0:sprocket_height, :]
    bottom_region = gray[h - sprocket_height:h, :]
    
    return top_region, bottom_region, 0, h - sprocket_height


def detect_sprocket_holes_in_region(
    region: np.ndarray,
    y_offset: int = 0,
    min_area: int = 50,
    max_area: int = 15000,
    min_aspect: float = 0.15,
    max_aspect: float = 8.0,
    brightness_threshold: float = 0.45,
    edge_region: bool = False,
) -> List[SprocketHole]:
    """
    Detect sprocket holes in a region using contour detection.
    
    Sprocket holes appear as bright regions (light shining through).
    Handles partially visible holes (top/bottom clipped by scanning gate)
    where only ~70% of the hole height is visible.  Clipped holes appear
    as wide bright bands rather than neat rectangles, so aspect ratio and
    area constraints are relaxed.

    Args:
        region: Grayscale image region (top or bottom sprocket area)
        y_offset: Y offset to add to detected positions (for global coords)
        min_area: Minimum hole area in pixels
        max_area: Maximum hole area in pixels  
        min_aspect: Minimum width/height ratio (wide for clipped holes)
        max_aspect: Maximum width/height ratio
        brightness_threshold: Minimum brightness (0-1) for hole detection
        edge_region: True if this region is at the very edge of the image
                     (relaxes the brightness check for clipped sprockets)
        
    Returns:
        List of detected SprocketHole objects
    """
    if region.size == 0:
        return []
    
    h, w = region.shape[:2]
    
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 4))
    enhanced = clahe.apply(region)
    
    # Strategy 1: Global brightness threshold
    normalized = enhanced.astype(np.float32) / 255.0
    binary_global = (normalized > brightness_threshold).astype(np.uint8) * 255
    
    # Strategy 2: Otsu's automatic threshold
    _, binary_otsu = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Strategy 3: Adaptive threshold for clear base stocks
    block_size = max(31, (min(h, w) // 4) | 1)
    binary_adaptive = cv2.adaptiveThreshold(
        enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, block_size, -8
    )
    
    binary = cv2.bitwise_or(binary_global, binary_otsu)
    binary = cv2.bitwise_or(binary, binary_adaptive)
    
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    sprocket_holes = []
    region_mean = region.mean() / 255.0
    
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area or area > max_area:
            continue
        
        x, y, rect_w, rect_h = cv2.boundingRect(contour)
        if rect_h == 0 or rect_w == 0:
            continue
        
        aspect = rect_w / rect_h
        
        # Clipped sprocket holes touching the region edge appear very wide
        # relative to their visible height.  Accept wider aspect ratios for
        # detections that touch the top or bottom row of the region.
        touches_edge = (y <= 1) or (y + rect_h >= h - 1)
        effective_max_aspect = max_aspect * 2.0 if touches_edge else max_aspect
        
        if aspect < min_aspect or aspect > effective_max_aspect:
            continue
        
        roi = region[y:y+rect_h, x:x+rect_w]
        if roi.size == 0:
            continue
        mean_brightness = roi.mean() / 255.0
        
        relative_bright = mean_brightness > region_mean * 0.92
        absolute_bright = mean_brightness >= brightness_threshold * 0.6
        if not (relative_bright or absolute_bright):
            continue
        
        rect_area = rect_w * rect_h
        rectangularity = area / rect_area if rect_area > 0 else 0
        brightness_std = roi.std() / 255.0
        uniformity = 1.0 - min(1.0, brightness_std / 0.2)
        
        confidence = rectangularity * 0.3 + mean_brightness * 0.3 + uniformity * 0.2
        # Partial sprockets touching the edge are expected — don't penalize
        if touches_edge:
            confidence += 0.1
        else:
            confidence += 0.1 * rectangularity
        confidence = min(1.0, confidence)
        
        hole = SprocketHole(
            x=int(x + rect_w // 2),
            y=int(y + rect_h // 2 + y_offset),
            width=int(rect_w),
            height=int(rect_h),
            area=int(area),
            confidence=float(confidence),
        )
        sprocket_holes.append(hole)
    
    sprocket_holes.sort(key=lambda s: s.x)
    
    return sprocket_holes


def detect_sprockets_edge_profile(
    gray: np.ndarray,
    edge: str = "top",
    smooth_sigma: float = 8.0,
    band_height: int = 20,
) -> List[SprocketHole]:
    """
    Detect sprocket holes using the film-edge transition zone.

    At the very edge of the film (where it meets the black surround),
    sprocket holes are dramatically brighter than the film rebate because
    pure backlight passes through the hole vs filtered through film base.
    This contrast is strongest in the narrow transition band (10-20 rows)
    right at the film edge.

    This approach is specifically designed for partially-clipped sprockets
    where the scanning gate cuts off the outer portion of each hole.
    It finds the film edge automatically, then looks at the brightness
    pattern in the transition zone.

    Args:
        gray: Full grayscale image.
        edge: "top" or "bottom".
        smooth_sigma: Gaussian sigma for smoothing the 1D profile.
        band_height: Height of the transition band to analyze.

    Returns:
        List of SprocketHole objects with accurate X positions.
    """
    h, w = gray.shape[:2]
    if h < 50 or w < 100:
        return []

    # Find the film edge: scan inward from the edge to find where
    # brightness first exceeds a threshold (film starts).
    search_depth = min(h // 3, 400)

    if edge == "top":
        row_means = [float(gray[r, :].mean()) for r in range(search_depth)]
        edge_row = 0
        for r, m in enumerate(row_means):
            if m > 25:
                edge_row = r
                break
        band_start = max(0, edge_row - 5)
        band_end = min(h, edge_row + band_height)
        y_offset = band_start
    else:
        row_means = [float(gray[h - 1 - r, :].mean()) for r in range(search_depth)]
        edge_row = 0
        for r, m in enumerate(row_means):
            if m > 25:
                edge_row = r
                break
        band_end = min(h, h - edge_row + 5)
        band_start = max(0, band_end - band_height)
        y_offset = band_start

    band = gray[band_start:band_end, :]
    if band.size == 0:
        return []

    profile = band.mean(axis=0).astype(np.float64)

    # Smooth
    ksize = max(3, int(smooth_sigma * 6) | 1)
    kernel = cv2.getGaussianKernel(ksize, smooth_sigma).flatten()
    smoothed = np.convolve(profile, kernel, mode='same')

    # Find the lit portion of the image (skip black borders)
    lit_mask = smoothed > 8
    lit_idx = np.where(lit_mask)[0]
    if len(lit_idx) < 50:
        return []
    ls, le = int(lit_idx[0]), int(lit_idx[-1])
    lit = smoothed[ls:le]
    if len(lit) < 50:
        return []

    # In the transition zone, sprocket holes are peaks above the median.
    # The film rebate between holes is dimmer because light passes through
    # the film base rather than a clear hole.
    med = float(np.median(lit))
    thresh = med * 1.2

    # Find bright runs (sprocket holes) above threshold
    runs: List[Tuple[int, int]] = []
    in_run = False
    start = 0
    for i in range(len(lit)):
        if lit[i] > thresh and not in_run:
            in_run = True
            start = i
        elif (lit[i] <= thresh or i == len(lit) - 1) and in_run:
            in_run = False
            run_width = i - start
            if 15 < run_width < 500:
                runs.append((start + run_width // 2, run_width))

    sprocket_holes: List[SprocketHole] = []
    for center, run_w in runs:
        x_global = center + ls
        peak_val = float(smoothed[x_global]) / 255.0
        conf = min(1.0, max(0.3, peak_val * 0.8 + 0.2))

        hole = SprocketHole(
            x=x_global,
            y=int(band_start + (band_end - band_start) // 2),
            width=run_w,
            height=band_end - band_start,
            area=run_w * (band_end - band_start),
            confidence=conf,
        )
        sprocket_holes.append(hole)

    sprocket_holes.sort(key=lambda s: s.x)
    return sprocket_holes


def calculate_sprocket_pitch(sprockets: List[SprocketHole]) -> Optional[float]:
    """
    Calculate the average pixel distance between sprocket holes.
    
    Uses median + IQR outlier rejection to handle missed or false sprocket
    detections (common on clear base stocks).
    
    Returns pixels per sprocket pitch, or None if insufficient data.
    """
    if len(sprockets) < 2:
        return None
    
    # Calculate distances between consecutive sprockets
    distances = []
    for i in range(len(sprockets) - 1):
        dx = sprockets[i + 1].x - sprockets[i].x
        if dx > 0:  # Only positive distances (left to right)
            distances.append(dx)
    
    if not distances:
        return None
    
    median_d = float(np.median(distances))
    
    # Reject outliers using IQR (inter-quartile range)
    # This handles cases where a sprocket was missed (distance ~2x pitch)
    # or a false detection split one pitch into two (~0.5x pitch)
    if len(distances) >= 3:
        q1 = float(np.percentile(distances, 25))
        q3 = float(np.percentile(distances, 75))
        iqr = q3 - q1
        lower = q1 - 1.5 * max(iqr, median_d * 0.15)
        upper = q3 + 1.5 * max(iqr, median_d * 0.15)
        filtered = [d for d in distances if lower <= d <= upper]
        if filtered:
            return float(np.median(filtered))
    
    return median_d


def find_frame_boundaries(
    sprockets: List[SprocketHole],
    sprocket_pitch_px: float,
    frame_width: int,
) -> List[Tuple[int, int]]:
    """
    Find frame boundaries based on sprocket positions.
    
    Each 35mm frame spans 8 sprocket pitches (4 sprockets on each edge).
    Frame boundaries occur at every 8th sprocket.
    
    Args:
        sprockets: Detected sprocket holes (sorted by X)
        sprocket_pitch_px: Measured pixels per sprocket pitch
        frame_width: Image width in pixels
        
    Returns:
        List of (left_x, right_x) frame boundary tuples
    """
    if not sprockets or sprocket_pitch_px <= 0:
        return []
    
    # Each frame is 8 sprocket pitches wide
    frame_pitch_px = sprocket_pitch_px * 8
    
    boundaries = []
    
    # Find frame boundaries relative to first sprocket
    first_x = sprockets[0].x
    
    # Calculate how many frames fit
    total_width = sprockets[-1].x - first_x if len(sprockets) > 1 else frame_width
    num_frames = max(1, int(total_width / frame_pitch_px) + 1)
    
    for i in range(num_frames):
        left_x = int(first_x + i * frame_pitch_px)
        right_x = int(left_x + frame_pitch_px)
        
        if left_x < frame_width and right_x > 0:
            boundaries.append((max(0, left_x), min(frame_width, right_x)))
    
    return boundaries


def calculate_alignment_offset(
    sprockets: List[SprocketHole],
    frame_width: int,
    sprocket_pitch_px: Optional[float] = None,
    target_position: str = "center",
) -> Tuple[int, float]:
    """
    Calculate how many pixels to move for proper frame alignment.
    
    Uses the sprocket grid to detect and correct drift.  All sprockets lie
    on a regular grid with spacing ``sprocket_pitch_px``.  The sub-pitch
    phase of the image center on this grid is a reliable drift signal that
    is consistent regardless of how many sprockets are visible or which
    physical sprocket numbers they correspond to.
    
    Limitation: sprocket holes alone cannot identify frame boundaries
    (they are all identical and equally spaced).  This function corrects
    drift within ±half a sprocket pitch (~2.4 mm).  For initial absolute
    frame positioning, use the frame-gap detector or manual alignment.
    
    Args:
        sprockets: Detected sprocket holes
        frame_width: Image width in pixels
        sprocket_pitch_px: Measured sprocket pitch (auto-calculated if None)
        target_position: "center" to center frame, "left_edge" for left alignment
        
    Returns:
        (offset_px, confidence) - positive offset means move film right
    """
    if not sprockets:
        return 0, 0.0
    
    if sprocket_pitch_px is None:
        sprocket_pitch_px = calculate_sprocket_pitch(sprockets)
    
    center = frame_width / 2.0
    
    if sprocket_pitch_px is None or sprocket_pitch_px <= 0:
        avg_x = np.mean([s.x for s in sprockets])
        return int(center - avg_x), 0.3
    
    # Compute the sub-pitch drift.  Every sprocket position x satisfies
    # x = grid_origin + k * pitch for some integer k.  The quantity
    # (center - x) mod pitch is the same for ALL sprockets (since they
    # differ by integer multiples of pitch).  Wrapping to ±pitch/2 gives
    # the signed correction needed.
    #
    # We compute from each sprocket independently and take the median
    # to be robust against one or two outlier detections.
    half_pitch = sprocket_pitch_px / 2.0
    residuals = []
    for s in sprockets:
        r = (center - s.x) % sprocket_pitch_px
        if r > half_pitch:
            r -= sprocket_pitch_px
        residuals.append(r)
    
    offset_needed = int(round(float(np.median(residuals))))
    
    # Confidence: more detected sprockets with tighter residual agreement.
    if len(residuals) >= 2:
        spread = float(np.std(residuals))
        regularity = max(0.0, 1.0 - spread / half_pitch)
    else:
        regularity = 0.5
    
    if len(sprockets) >= 6:
        count_factor = 0.9
    elif len(sprockets) >= 4:
        count_factor = 0.7
    elif len(sprockets) >= 2:
        count_factor = 0.5
    else:
        count_factor = 0.3
    
    confidence = count_factor * (0.4 + 0.6 * regularity)
    
    return offset_needed, confidence


def detect_sprockets(
    jpeg_bytes: bytes,
    sprocket_region_fraction: float = 0.18,
    min_sprocket_area: int = 50,
    max_sprocket_area: int = 15000,
    brightness_threshold: float = 0.45,
    alignment_tolerance_px: int = 20,
) -> SprocketDetectionResult:
    """
    Main sprocket detection function for frame alignment.
    
    Detects sprocket holes in top and bottom regions of the image,
    calculates sprocket pitch, and determines alignment offset.
    
    Args:
        jpeg_bytes: Preview image as JPEG bytes
        sprocket_region_fraction: Fraction of image height for sprocket areas
        min_sprocket_area: Minimum sprocket hole area in pixels
        max_sprocket_area: Maximum sprocket hole area in pixels
        brightness_threshold: Minimum brightness for hole detection (0-1)
        alignment_tolerance_px: Pixels within which frame is considered aligned
        
    Returns:
        SprocketDetectionResult with alignment info and detected holes
    """
    try:
        gray = jpeg_bytes_to_gray(jpeg_bytes)
    except Exception as e:
        return SprocketDetectionResult(
            offset_px=0,
            confidence=0.0,
            aligned=False,
            debug_info={"error": str(e)},
        )
    
    h, w = gray.shape[:2]
    
    # Extract sprocket regions
    top_region, bottom_region, top_offset, bottom_offset = find_sprocket_regions(
        gray, sprocket_region_fraction
    )
    
    # Try the edge-profile method first (robust for partially clipped
    # sprockets), then fall back to contour detection.
    top_edge = detect_sprockets_edge_profile(gray, edge="top")
    bottom_edge = detect_sprockets_edge_profile(gray, edge="bottom")
    edge_total = len(top_edge) + len(bottom_edge)

    top_contour = detect_sprocket_holes_in_region(
        top_region,
        y_offset=top_offset,
        min_area=min_sprocket_area,
        max_area=max_sprocket_area,
        brightness_threshold=brightness_threshold,
        edge_region=True,
    )
    bottom_contour = detect_sprocket_holes_in_region(
        bottom_region,
        y_offset=bottom_offset,
        min_area=min_sprocket_area,
        max_area=max_sprocket_area,
        brightness_threshold=brightness_threshold,
        edge_region=True,
    )
    contour_total = len(top_contour) + len(bottom_contour)

    # Pick the method that found more sprockets.  Edge-profile is
    # preferred when available since it gives more consistent X positions
    # for partially-clipped sprockets.
    if edge_total >= contour_total and edge_total >= 3:
        top_sprockets = top_edge
        bottom_sprockets = bottom_edge
        detection_method = "edge_profile"
    else:
        top_sprockets = top_contour
        bottom_sprockets = bottom_contour
        detection_method = "contour"
    
    all_sprockets = top_sprockets + bottom_sprockets
    
    # For alignment, prefer the row with more detections
    if len(top_sprockets) >= len(bottom_sprockets):
        primary_sprockets = top_sprockets
        secondary_sprockets = bottom_sprockets
    else:
        primary_sprockets = bottom_sprockets
        secondary_sprockets = top_sprockets
    
    # Calculate sprocket pitch
    sprocket_pitch_px = calculate_sprocket_pitch(primary_sprockets)
    
    # If primary row doesn't have enough, try secondary
    if sprocket_pitch_px is None and len(secondary_sprockets) >= 2:
        sprocket_pitch_px = calculate_sprocket_pitch(secondary_sprockets)
    
    # Calculate pixels per mm if we have pitch
    px_per_mm = None
    if sprocket_pitch_px:
        px_per_mm = sprocket_pitch_px / SPROCKET_PITCH_MM
    
    # Calculate alignment offset
    offset_px, confidence = calculate_alignment_offset(
        primary_sprockets,
        w,
        sprocket_pitch_px,
    )
    
    # Determine if aligned
    aligned = abs(offset_px) <= alignment_tolerance_px and confidence > 0.5
    
    debug_info = {
        "image_size": {"width": w, "height": h},
        "sprocket_region_height": int(h * sprocket_region_fraction),
        "detection_method": detection_method,
        "top_sprocket_count": len(top_sprockets),
        "bottom_sprocket_count": len(bottom_sprockets),
        "total_sprocket_count": len(all_sprockets),
        "sprocket_pitch_px": float(sprocket_pitch_px) if sprocket_pitch_px else None,
        "px_per_mm": float(px_per_mm) if px_per_mm else None,
        "frame_pitch_px": float(sprocket_pitch_px * 8) if sprocket_pitch_px else None,
        "alignment_tolerance": alignment_tolerance_px,
    }
    
    # Add sprocket positions for debugging
    if primary_sprockets:
        debug_info["sprocket_x_positions"] = [s.x for s in primary_sprockets]
        debug_info["sprocket_confidences"] = [s.confidence for s in primary_sprockets]
    
    return SprocketDetectionResult(
        offset_px=offset_px,
        confidence=confidence,
        aligned=aligned,
        sprocket_holes=all_sprockets,
        top_sprockets=top_sprockets,
        bottom_sprockets=bottom_sprockets,
        sprocket_pitch_px=sprocket_pitch_px,
        px_per_mm=px_per_mm,
        debug_info=debug_info,
    )


def calibrate_from_sprockets(
    jpeg_bytes: bytes,
    known_sprocket_count: int = 8,
) -> Optional[dict]:
    """
    Calibrate scanner using visible sprocket holes.
    
    If you can see a known number of sprockets, this calculates
    the pixel-to-mm conversion and frame pitch.
    
    Args:
        jpeg_bytes: Image with known number of sprocket holes visible
        known_sprocket_count: How many sprocket pitches are visible
        
    Returns:
        Calibration dict with px_per_mm, frame_pitch_px, etc.
    """
    result = detect_sprockets(jpeg_bytes)
    
    if not result.sprocket_pitch_px:
        return None
    
    # Calculate conversions
    px_per_mm = result.sprocket_pitch_px / SPROCKET_PITCH_MM
    frame_pitch_px = result.sprocket_pitch_px * SPROCKETS_PER_FRAME
    
    return {
        "sprocket_pitch_px": result.sprocket_pitch_px,
        "px_per_mm": px_per_mm,
        "frame_pitch_px": frame_pitch_px,
        "sprockets_detected": len(result.sprocket_holes),
        "top_sprockets": len(result.top_sprockets),
        "bottom_sprockets": len(result.bottom_sprockets),
        "confidence": result.confidence,
    }


def detect_frame_edge_sprocket(
    jpeg_bytes: bytes,
    edge: str = "left",
    sprocket_region_fraction: float = 0.18,
) -> Tuple[Optional[int], float]:
    """
    Detect if there's a partial sprocket hole at the specified edge.
    
    This is useful for fine-tuning alignment - you want to push
    partial sprocket holes out of the frame area.
    
    Args:
        jpeg_bytes: Preview image
        edge: "left" or "right"
        sprocket_region_fraction: Fraction of height for sprocket area
        
    Returns:
        (edge_x, confidence) - X position of partial sprocket, or None
    """
    try:
        gray = jpeg_bytes_to_gray(jpeg_bytes)
    except:
        return None, 0.0
    
    h, w = gray.shape[:2]
    
    # Look at the edge region
    edge_width = int(w * 0.15)  # 15% of width from edge
    
    if edge == "left":
        edge_region = gray[:, 0:edge_width]
        x_offset = 0
    else:
        edge_region = gray[:, w - edge_width:w]
        x_offset = w - edge_width
    
    # Extract sprocket area from edge region
    sprocket_h = int(h * sprocket_region_fraction)
    top_edge = edge_region[0:sprocket_h, :]
    bottom_edge = edge_region[h - sprocket_h:h, :]
    
    # Look for bright regions (partial sprocket holes)
    combined = np.vstack([top_edge, bottom_edge])
    
    # Column brightness profile
    col_brightness = combined.mean(axis=0) / 255.0
    
    # Find brightest columns near the edge
    if edge == "left":
        # Look for brightness peak near left edge
        search_region = col_brightness[:edge_width // 2]
        if len(search_region) > 0 and search_region.max() > 0.5:
            peak_x = int(np.argmax(search_region))
            confidence = float(search_region.max())
            return peak_x + x_offset, confidence
    else:
        # Look for brightness peak near right edge
        search_region = col_brightness[edge_width // 2:]
        if len(search_region) > 0 and search_region.max() > 0.5:
            peak_x = int(np.argmax(search_region)) + edge_width // 2
            confidence = float(search_region.max())
            return peak_x + x_offset, confidence
    
    return None, 0.0


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

    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
    binary = cv2.erode(binary, kernel, iterations=1)

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

    shrink_x = max(1, min(10, int(round(0.003 * w))))
    shrink_y = max(1, min(10, int(round(0.003 * h))))
    x += shrink_x
    y += shrink_y
    bw = max(1, bw - 2 * shrink_x)
    bh = max(1, bh - 2 * shrink_y)

    if inner_shrink > 0:
        inner_x = int(round(inner_shrink * bw))
        inner_y = int(round(inner_shrink * bh))
        if bw - 2 * inner_x >= 8 and bh - 2 * inner_y >= 4:
            x += inner_x
            y += inner_y
            bw -= 2 * inner_x
            bh -= 2 * inner_y

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


# Helper for JSON serialization
def detection_to_json(result: SprocketDetectionResult) -> str:
    """Serialize detection result to JSON."""
    return json.dumps(result.to_dict(), indent=2)
