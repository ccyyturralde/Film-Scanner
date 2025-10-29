#!/usr/bin/env python3
"""
35mm Film Frame Gap Detection
Optimized for 6000x4000 images, gap widths 9-74px, brightness ~182
"""

import cv2
import numpy as np

def detect_frame_gap(img_path, debug=False):
    """
    Detect bright gap between film frames.
    Returns: (gap_column, confidence, message)
    """
    
    img = cv2.imread(img_path)
    if img is None:
        return None, 0.0, "Cannot read image"
    
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Focus on middle 40% vertically to avoid edge artifacts
    y1, y2 = int(h * 0.3), int(h * 0.7)
    roi = gray[y1:y2, :]
    
    # Get brightness profile (average per column)
    brightness = np.mean(roi, axis=0)
    
    # Smooth to reduce noise
    kernel_size = max(5, int(w * 0.005))
    kernel = np.ones(kernel_size) / kernel_size
    smoothed = np.convolve(brightness, kernel, mode='same')
    
    # Find bright peaks (gaps are significantly brighter than film)
    median_bright = np.median(smoothed)
    std_bright = np.std(smoothed)
    threshold = median_bright + 0.8 * std_bright
    bright_mask = smoothed > threshold
    
    # Find contiguous bright regions
    gaps = []
    in_gap = False
    gap_start = 0
    
    for i in range(len(bright_mask)):
        if bright_mask[i] and not in_gap:
            gap_start = i
            in_gap = True
        elif not bright_mask[i] and in_gap:
            gap_end = i
            gap_width = gap_end - gap_start
            
            # Valid gap width: 7-100 pixels
            if 7 < gap_width < 100:
                gap_center = (gap_start + gap_end) // 2
                gap_brightness = np.mean(smoothed[gap_start:gap_end])
                gaps.append({
                    'center': gap_center,
                    'start': gap_start,
                    'end': gap_end,
                    'width': gap_width,
                    'brightness': gap_brightness,
                    'percent': (gap_center / w) * 100
                })
            in_gap = False
    
    if not gaps:
        return None, 0.0, "No gaps detected"
    
    # Find rightmost gap in useful range (>55%)
    target_min_pct = 55
    right_gaps = [g for g in gaps if g['percent'] > target_min_pct]
    
    if not right_gaps:
        selected = max(gaps, key=lambda g: g['center'])
    else:
        selected = max(right_gaps, key=lambda g: g['center'])
    
    # Calculate confidence
    max_bright = np.max(smoothed)
    brightness_ratio = selected['brightness'] / max_bright
    width_score = min(selected['width'] / 40, 1.0)
    confidence = (brightness_ratio * 0.7 + width_score * 0.3)
    
    message = f"Gap at {selected['percent']:.1f}%"
    
    if debug:
        print(f"Image: {w}x{h}")
        print(f"Found {len(gaps)} total gaps, {len(right_gaps)} in target range")
        print(f"\nAll gaps:")
        for i, g in enumerate(gaps):
            marker = "← SELECTED" if g == selected else ""
            print(f"  {g['center']:4d}px ({g['percent']:5.1f}%) - {g['width']:2d}px wide {marker}")
        print(f"\nSelected: {selected['center']}px ({selected['percent']:.1f}%)")
        print(f"Confidence: {confidence:.2f}")
        
        # Create debug visualization
        debug_img = img.copy()
        
        # Draw all gaps in red
        for gap in gaps:
            cv2.line(debug_img, (gap['center'], 0), (gap['center'], h), (0, 0, 255), 2)
        
        # Draw selected gap in green
        cv2.line(debug_img, (selected['center'], 0), (selected['center'], h), (0, 255, 0), 5)
        
        # Draw target zone (75-90%)
        target_min = int(w * 0.75)
        target_max = int(w * 0.90)
        cv2.rectangle(debug_img, (target_min, 0), (target_max, h), (255, 255, 0), 3)
        
        cv2.putText(debug_img, f"Gap at {selected['percent']:.1f}%", 
                    (selected['center'] - 100, 50), cv2.FONT_HERSHEY_SIMPLEX, 
                    1.5, (0, 255, 0), 3)
        
        cv2.imwrite('/tmp/gap_debug.jpg', debug_img)
        print("\nDebug image: /tmp/gap_debug.jpg")
    
    return selected['center'], confidence, message


def get_movement_command(gap_col, img_width, tolerance=8):
    """
    Determine motor command based on gap position.
    Target: 75-90% of width, ideal at 82%
    
    Returns: (action, message, steps_needed)
    """
    
    if gap_col is None:
        return 'no_gap', "No gap - advance forward", None
    
    gap_percent = (gap_col / img_width) * 100
    
    # Target zone: 75-90%, ideal at 82%
    target_min = int(img_width * 0.75)
    target_max = int(img_width * 0.90)
    target_ideal = int(img_width * 0.82)
    
    # Calculate offset from ideal
    offset = gap_col - target_ideal
    
    # Check if aligned
    if target_min <= gap_col <= target_max and abs(offset) <= tolerance:
        return 'aligned', f"✓ ALIGNED at {gap_percent:.1f}%", 0
    
    # Determine movement direction and amount
    if gap_col < target_min:
        # Too far left - need to advance
        distance = target_ideal - gap_col
        return 'advance', f"Advance {distance}px to {gap_percent:.1f}%", distance
    
    elif gap_col > target_max:
        # Too far right - need to back up
        distance = gap_col - target_ideal
        return 'backup', f"Backup {distance}px from {gap_percent:.1f}%", distance
    
    else:
        # In zone but not quite aligned
        if offset > 0:
            return 'backup', f"Fine backup {abs(offset)}px", abs(offset)
        else:
            return 'advance', f"Fine advance {abs(offset)}px", abs(offset)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python3 optimized_edge_detect.py <image_path> [--debug]")
        sys.exit(1)
    
    img_path = sys.argv[1]
    debug = '--debug' in sys.argv
    
    print("=" * 60)
    print("35MM FILM FRAME GAP DETECTION")
    print("=" * 60)
    
    gap_col, confidence, message = detect_frame_gap(img_path, debug=debug)
    
    if gap_col:
        img = cv2.imread(img_path)
        img_width = img.shape[1]
        
        action, action_msg, steps = get_movement_command(gap_col, img_width)
        
        print(f"\nGap: {gap_col}px")
        print(f"Confidence: {confidence:.2f}")
        print(f"Action: {action}")
        print(f"Message: {action_msg}")
        if steps is not None:
            print(f"Steps needed: {steps}")
    else:
        print(f"\n{message}")
    
    print("=" * 60)
