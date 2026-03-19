"""
Sprocket Hole Detector for 35mm Film Scanner

Detects sprocket holes on the top and/or bottom edges of 35mm film for precise frame alignment.

35mm Film Standard Specifications:
- Sprocket pitch: 4.75mm (center to center)
- Sprocket holes per frame: 8 (4 top, 4 bottom)
- Sprocket hole size: ~2.8mm x 1.98mm (KS-1870 standard)
- Frame width: ~38mm (including sprocket area)
- Image area: 24mm x 36mm

This detector finds sprocket holes as bright rectangular regions and uses their
positions for precise frame alignment - much more reliable than gap detection
since sprocket holes are consistent regardless of image content.

Hardware Setup:
- Film pulled from right side through mask
- Full film visible including sprocket holes
- Sprocket rows visible at top and/or bottom of preview
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
    sprocket_fraction: float = 0.15,
) -> Tuple[np.ndarray, np.ndarray, int, int]:
    """
    Extract the top and bottom regions where sprocket holes are expected.
    
    Args:
        gray: Grayscale image
        sprocket_fraction: Fraction of image height for sprocket regions
        
    Returns:
        (top_region, bottom_region, top_y_offset, bottom_y_offset)
    """
    h, w = gray.shape[:2]
    
    # Sprocket holes are at top and bottom edges of film
    sprocket_height = int(h * sprocket_fraction)
    
    top_region = gray[0:sprocket_height, :]
    bottom_region = gray[h - sprocket_height:h, :]
    
    return top_region, bottom_region, 0, h - sprocket_height


def detect_sprocket_holes_in_region(
    region: np.ndarray,
    y_offset: int = 0,
    min_area: int = 100,
    max_area: int = 10000,
    min_aspect: float = 0.3,
    max_aspect: float = 3.0,
    brightness_threshold: float = 0.5,
) -> List[SprocketHole]:
    """
    Detect sprocket holes in a region using contour detection.
    
    Sprocket holes appear as bright rectangles (light shining through).
    Works on both dark-based (dense negative) and clear-based films by
    using CLAHE contrast enhancement and adaptive thresholding.
    
    Args:
        region: Grayscale image region (top or bottom sprocket area)
        y_offset: Y offset to add to detected positions (for global coords)
        min_area: Minimum hole area in pixels
        max_area: Maximum hole area in pixels  
        min_aspect: Minimum width/height ratio
        max_aspect: Maximum width/height ratio
        brightness_threshold: Minimum brightness (0-1) for hole detection
        
    Returns:
        List of detected SprocketHole objects
    """
    if region.size == 0:
        return []
    
    h, w = region.shape[:2]
    
    # --- CLAHE contrast enhancement ---
    # Critical for clear/transparent base stocks where the sprocket holes
    # and film base are both bright. CLAHE enhances LOCAL contrast so the
    # physical edges of sprocket holes become visible even on clear film.
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 4))
    enhanced = clahe.apply(region)
    
    # --- Multi-strategy detection ---
    # Strategy 1: Global brightness threshold (works well on dark base)
    normalized = enhanced.astype(np.float32) / 255.0
    binary_global = (normalized > brightness_threshold).astype(np.uint8) * 255
    
    # Strategy 2: Otsu's automatic threshold (adapts to histogram)
    _, binary_otsu = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Strategy 3: Adaptive threshold (LOCAL neighborhood comparison)
    # This is the key strategy for clear base stocks -- it finds regions
    # that are brighter than their immediate surroundings, regardless of
    # absolute brightness. Block size must be large enough to span a
    # sprocket hole + surrounding film.
    block_size = max(31, (min(h, w) // 4) | 1)  # Ensure odd
    binary_adaptive = cv2.adaptiveThreshold(
        enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, block_size, -8
    )
    
    # Combine all strategies (union of detections)
    binary = cv2.bitwise_or(binary_global, binary_otsu)
    binary = cv2.bitwise_or(binary, binary_adaptive)
    
    # Morphological operations to clean up
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    
    # Find contours
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    sprocket_holes = []
    
    for contour in contours:
        area = cv2.contourArea(contour)
        
        # Filter by area
        if area < min_area or area > max_area:
            continue
        
        # Get bounding rectangle
        x, y, rect_w, rect_h = cv2.boundingRect(contour)
        
        # Filter by aspect ratio (sprocket holes are roughly rectangular)
        if rect_h == 0:
            continue
        aspect = rect_w / rect_h
        if aspect < min_aspect or aspect > max_aspect:
            continue
        
        # Check if region is actually bright (use original, not enhanced)
        roi = region[y:y+rect_h, x:x+rect_w]
        if roi.size == 0:
            continue
        mean_brightness = roi.mean() / 255.0
        
        # For clear base, the absolute brightness check must be relaxed
        # because the whole image may be bright.  Instead check that the
        # hole is brighter than the region average (relative contrast).
        region_mean = region.mean() / 255.0
        relative_bright = mean_brightness > region_mean * 0.95
        absolute_bright = mean_brightness >= brightness_threshold * 0.7
        if not (relative_bright or absolute_bright):
            continue
        
        # Calculate confidence based on:
        # 1. How rectangular the contour is (sprocket holes are rectangular)
        # 2. How bright the center is
        # 3. How consistent the brightness is
        rect_area = rect_w * rect_h
        rectangularity = area / rect_area if rect_area > 0 else 0
        
        brightness_std = roi.std() / 255.0
        uniformity = 1.0 - min(1.0, brightness_std / 0.2)
        
        confidence = (rectangularity * 0.4 + mean_brightness * 0.3 + uniformity * 0.3)
        
        # Create sprocket hole object
        hole = SprocketHole(
            x=int(x + rect_w // 2),
            y=int(y + rect_h // 2 + y_offset),
            width=int(rect_w),
            height=int(rect_h),
            area=int(area),
            confidence=float(confidence),
        )
        sprocket_holes.append(hole)
    
    # Sort by X position (left to right)
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
    
    For 35mm film with 8 sprockets per frame:
    - Frame center is at sprocket positions 4-5 boundary
    - Target: center the frame in the image
    
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
    
    # Calculate sprocket pitch if not provided
    if sprocket_pitch_px is None:
        sprocket_pitch_px = calculate_sprocket_pitch(sprockets)
    
    if sprocket_pitch_px is None or sprocket_pitch_px <= 0:
        # Fallback: use average sprocket position relative to center
        avg_x = np.mean([s.x for s in sprockets])
        center = frame_width // 2
        offset = int(center - avg_x)
        confidence = 0.3  # Low confidence without pitch
        return offset, confidence
    
    # Frame pitch in pixels (8 sprockets per frame)
    frame_pitch_px = sprocket_pitch_px * 8
    
    # Find the nearest frame boundary to the image center
    center = frame_width // 2
    
    # Use sprocket positions to determine frame alignment
    # The ideal position is when a frame boundary aligns with image center
    
    # Find sprocket closest to center
    closest_sprocket = min(sprockets, key=lambda s: abs(s.x - center))
    closest_idx = sprockets.index(closest_sprocket)
    
    # Calculate which part of the frame we're in (0-7 sprocket positions)
    # Position 0 = left edge of frame, position 4 = center, position 7 = right edge
    
    # Distance from closest sprocket to center
    dist_to_center = closest_sprocket.x - center
    
    # To center a frame, we want sprocket positions 3-4 centered
    # This puts the image area (between sprockets 2-6) centered
    
    # Calculate offset needed to center the nearest frame
    # We want the midpoint between sprockets 3 and 4 (or 4 and 5) at image center
    
    # Simplified: move so nearest sprocket group is centered
    # Each sprocket represents 1/8 of a frame
    position_in_frame = (closest_idx % 8)  # 0-7
    
    # Ideal center is between sprockets 3-4 (position 3.5)
    # Calculate how far we need to move
    sprockets_to_center = 3.5 - position_in_frame
    offset_needed = int(sprockets_to_center * sprocket_pitch_px - dist_to_center)
    
    # Calculate confidence based on number of sprockets and their regularity
    if len(sprockets) >= 6:
        confidence = 0.9
    elif len(sprockets) >= 4:
        confidence = 0.7
    elif len(sprockets) >= 2:
        confidence = 0.5
    else:
        confidence = 0.3
    
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
    
    # Detect sprocket holes in each region
    top_sprockets = detect_sprocket_holes_in_region(
        top_region,
        y_offset=top_offset,
        min_area=min_sprocket_area,
        max_area=max_sprocket_area,
        brightness_threshold=brightness_threshold,
    )
    
    bottom_sprockets = detect_sprocket_holes_in_region(
        bottom_region,
        y_offset=bottom_offset,
        min_area=min_sprocket_area,
        max_area=max_sprocket_area,
        brightness_threshold=brightness_threshold,
    )
    
    # Combine all sprockets (use X positions from both rows)
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
    
    # Build debug info
    debug_info = {
        "image_size": {"width": w, "height": h},
        "sprocket_region_height": int(h * sprocket_region_fraction),
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


# Helper for JSON serialization
def detection_to_json(result: SprocketDetectionResult) -> str:
    """Serialize detection result to JSON."""
    return json.dumps(result.to_dict(), indent=2)
