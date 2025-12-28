#!/usr/bin/env python3
"""
Test the frame gap detector on sample images.
Run this locally to verify detection before deploying to Pi.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from frame_detector import detect_frame_gap, compute_column_stats, find_gap_mask, find_gap_regions
import cv2
import numpy as np


def test_image(image_path: str, expected_aligned: bool, frame_mode: str):
    """Test gap detection on a single image."""
    print(f"\n{'='*60}")
    print(f"Testing: {os.path.basename(image_path)}")
    print(f"Expected: {'ALIGNED' if expected_aligned else 'UNALIGNED'} ({frame_mode} frame)")
    print(f"{'='*60}")
    
    # Load image
    img = cv2.imread(image_path)
    if img is None:
        print(f"  ERROR: Could not load image")
        return False
    
    h, w = img.shape[:2]
    print(f"  Image size: {w}x{h}")
    
    # Convert to JPEG bytes (simulating capture card output)
    success, jpeg_bytes = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not success:
        print(f"  ERROR: Could not encode image")
        return False
    
    jpeg_bytes = jpeg_bytes.tobytes()
    print(f"  JPEG size: {len(jpeg_bytes)} bytes")
    
    # Run detection
    result = detect_frame_gap(
        jpeg_bytes,
        roi=None,
        expected_gap_fraction=None,
        gap_window_fraction=1.0,
        brightness_threshold=0.3,
        std_threshold=0.20,
        diff_threshold=0.40,
        min_gap_width=3,
    )
    
    # Print results
    print(f"\n  Detection Results:")
    print(f"    Confidence: {result.confidence:.3f}")
    print(f"    Gap X: {result.gap_x}")
    print(f"    Offset from center: {result.offset_px}px")
    print(f"    Gaps found: {result.debug_info.get('gap_count', 0) if result.debug_info else 0}")
    
    if result.debug_info:
        debug = result.debug_info
        print(f"    Brightness max: {debug.get('brightness_max', 0):.3f}")
        print(f"    Std min: {debug.get('std_min', 0):.3f}")
        if 'best_gap_width' in debug:
            print(f"    Best gap width: {debug['best_gap_width']}px")
    
    # Check alignment logic
    gap_count = result.debug_info.get('gap_count', 0) if result.debug_info else 0
    
    if frame_mode == "full":
        # Full frame: aligned means NO gap visible
        detected_aligned = (gap_count == 0 or result.confidence == 0)
        print(f"\n  Full frame logic:")
        print(f"    No gap visible? {gap_count == 0}")
        print(f"    Detected as: {'ALIGNED' if detected_aligned else 'UNALIGNED'}")
    else:
        # Half frame: aligned means gap is centered
        # Consider aligned if gap is within 10% of center
        center_tolerance = w * 0.10
        if result.gap_x:
            gap_from_center = abs(result.gap_x - (w // 2))
            detected_aligned = gap_from_center < center_tolerance
            print(f"\n  Half frame logic:")
            print(f"    Gap at: {result.gap_x}px, center: {w//2}px")
            print(f"    Distance from center: {gap_from_center}px (tolerance: {center_tolerance:.0f}px)")
            print(f"    Detected as: {'ALIGNED' if detected_aligned else 'UNALIGNED'}")
        else:
            detected_aligned = False
            print(f"\n  Half frame logic:")
            print(f"    No gap detected - cannot be aligned")
    
    # Compare to expected
    match = detected_aligned == expected_aligned
    print(f"\n  Result: {'✓ PASS' if match else '✗ FAIL'}")
    
    return match


def visualize_detection(image_path: str, output_path: str = None):
    """Visualize gap detection on an image."""
    from frame_detector import find_lit_region
    
    img = cv2.imread(image_path)
    if img is None:
        print(f"Could not load {image_path}")
        return
    
    h, w = img.shape[:2]
    
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Find lit region (excluding black borders)
    lit_x0, lit_y0, lit_x1, lit_y1 = find_lit_region(gray)
    
    # Crop to lit region
    gray_cropped = gray[lit_y0:lit_y1, lit_x0:lit_x1]
    
    # Further crop top/bottom
    cropped_h = gray_cropped.shape[0]
    edge_crop_y = int(0.05 * cropped_h)
    if edge_crop_y > 0:
        gray_cropped = gray_cropped[edge_crop_y:cropped_h - edge_crop_y, :]
    
    gray_cropped = cv2.medianBlur(gray_cropped, 5)
    
    stats = compute_column_stats(gray_cropped)
    gap_mask = find_gap_mask(stats, mean_threshold=0.75, std_threshold=0.10)
    
    # Real gaps are narrow - max 8% of width or 300px
    cropped_w = gray_cropped.shape[1]
    max_gap_width = max(int(0.08 * cropped_w), 300)
    regions = find_gap_regions(gap_mask, min_width=8, max_width=max_gap_width, x_offset=lit_x0)
    
    # Draw lit region bounds
    cv2.rectangle(img, (lit_x0, lit_y0), (lit_x1, lit_y1), (255, 255, 0), 2)
    
    # Draw detected gap regions
    for region in regions:
        cv2.rectangle(img, (region.global_start_x, lit_y0), (region.global_end_x, lit_y1), (0, 255, 0), 4)
        cv2.putText(img, f"GAP ({region.width}px)", (region.global_start_x, lit_y0 - 10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    
    # Draw center line
    center = w // 2
    cv2.line(img, (center, 0), (center, h), (255, 0, 0), 2)
    cv2.putText(img, "CENTER", (center + 10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
    
    # Draw stats
    text_y = h - 80
    cv2.putText(img, f"Gaps: {len(regions)}", (10, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    cv2.putText(img, f"Mean max: {stats['col_mean'].max():.2f}", (10, text_y + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    cv2.putText(img, f"Std min: {stats['col_std'].min():.2f}", (10, text_y + 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    
    if output_path:
        cv2.imwrite(output_path, img)
        print(f"Saved visualization to {output_path}")
    else:
        cv2.imshow("Detection", img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()


def main():
    sample_dir = Path(__file__).parent / "Sample frames"
    
    # Define test cases based on user's description:
    # 7860, 7861 - aligned full frame
    # 7864 - aligned half frame
    # 7862, 7863 - unaligned full frame (gap visible)
    # 7865, 7866 - unaligned half frame (multiple gaps)
    
    test_cases = [
        ("_MG_7860.jpg", True, "full"),   # Aligned full frame
        ("_MG_7861.jpg", True, "full"),   # Aligned full frame
        ("_MG_7862.jpg", False, "full"),  # Unaligned full frame (gap visible)
        ("_MG_7863.jpg", False, "full"),  # Unaligned full frame (gap visible)
        ("_MG_7864.jpg", True, "half"),   # Aligned half frame (gap centered)
        ("_MG_7865.jpg", False, "half"),  # Unaligned half frame (multiple gaps)
        ("_MG_7866.jpg", False, "half"),  # Unaligned half frame (multiple gaps)
    ]
    
    print("\n" + "="*70)
    print("FRAME GAP DETECTOR TEST")
    print("="*70)
    
    results = []
    for filename, expected_aligned, frame_mode in test_cases:
        image_path = sample_dir / filename
        if image_path.exists():
            passed = test_image(str(image_path), expected_aligned, frame_mode)
            results.append((filename, passed))
        else:
            print(f"\nSkipping {filename} - file not found")
            results.append((filename, None))
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, r in results if r is True)
    failed = sum(1 for _, r in results if r is False)
    skipped = sum(1 for _, r in results if r is None)
    
    for filename, result in results:
        status = "✓ PASS" if result is True else ("✗ FAIL" if result is False else "- SKIP")
        print(f"  {status}: {filename}")
    
    print(f"\nTotal: {passed} passed, {failed} failed, {skipped} skipped")
    
    # Generate visualizations
    print("\n" + "="*70)
    print("GENERATING VISUALIZATIONS")
    print("="*70)
    
    output_dir = sample_dir / "detection_output"
    output_dir.mkdir(exist_ok=True)
    
    for filename, _, _ in test_cases:
        image_path = sample_dir / filename
        if image_path.exists():
            output_path = output_dir / f"detected_{filename}"
            visualize_detection(str(image_path), str(output_path))
    
    print(f"\nVisualization images saved to: {output_dir}")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

