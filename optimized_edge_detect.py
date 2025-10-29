#!/usr/bin/env python3
"""
35mm Film Frame Detection - Production Version
Detects BOTH left and right gaps to properly center frames
Goal: Minimize gap visibility, center frame content
"""

import cv2
import numpy as np

def detect_frame_gaps(img_path, debug=False):
    """
    Detect left and right frame boundaries (gaps).
    Returns detailed frame alignment information.
    
    Returns:
        dict with:
        - left_gap: {center, width, percent} or None
        - right_gap: {center, width, percent} or None
        - frame_width: pixels between gaps (if both detected)
        - frame_center: center position of frame content
        - status: alignment status
        - action: recommended action
        - confidence: detection confidence
    """
    
    img = cv2.imread(img_path)
    if img is None:
        return {
            'status': 'ERROR',
            'action': 'Cannot read image',
            'confidence': 0.0
        }
    
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
    
    # Calculate variance per column to detect uniformity (gaps are uniform)
    variance_profile = np.array([np.var(roi[:, max(0, i-2):min(w, i+3)]) 
                                  for i in range(w)])
    smoothed_variance = np.convolve(variance_profile, kernel, mode='same')
    
    # Detect gaps: bright AND uniform (low variance)
    median_bright = np.median(smoothed)
    std_bright = np.std(smoothed)
    brightness_threshold = median_bright + 0.7 * std_bright
    
    # Variance threshold: gaps have very low variance (uniform)
    variance_threshold = np.percentile(smoothed_variance, 25)
    
    # Combined detection: bright AND uniform
    gap_mask = (smoothed > brightness_threshold) & (smoothed_variance < variance_threshold)
    
    # Find contiguous gap regions
    gaps = []
    in_gap = False
    gap_start = 0
    
    for i in range(len(gap_mask)):
        if gap_mask[i] and not in_gap:
            gap_start = i
            in_gap = True
        elif not gap_mask[i] and in_gap:
            gap_end = i
            gap_width = gap_end - gap_start
            
            # Valid gap width: 10-250 pixels (covers various gap sizes)
            if 10 < gap_width < 250:
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
    
    # Classify gaps as left or right based on position
    left_gaps = [g for g in gaps if g['percent'] < 50]
    right_gaps = [g for g in gaps if g['percent'] >= 50]
    
    # Select most likely left and right gaps
    left_gap = max(left_gaps, key=lambda g: g['width']) if left_gaps else None
    right_gap = max(right_gaps, key=lambda g: g['width']) if right_gaps else None
    
    # Calculate frame metrics
    frame_width = None
    frame_center = None
    frame_center_percent = None
    
    if left_gap and right_gap:
        frame_width = right_gap['center'] - left_gap['center']
        frame_center = (left_gap['center'] + right_gap['center']) // 2
        frame_center_percent = (frame_center / w) * 100
    elif left_gap:
        # Only left gap visible - frame is mostly on right
        frame_center = left_gap['center'] + int(w * 0.3)  # Estimate
        frame_center_percent = (frame_center / w) * 100
    elif right_gap:
        # Only right gap visible - frame is mostly on left
        frame_center = right_gap['center'] - int(w * 0.3)  # Estimate
        frame_center_percent = (frame_center / w) * 100
    
    # Determine alignment status and action
    result = _classify_alignment(left_gap, right_gap, frame_width, frame_center_percent, w)
    
    # Add gap information
    result['left_gap'] = left_gap
    result['right_gap'] = right_gap
    result['frame_width'] = frame_width
    result['frame_center'] = frame_center
    result['frame_center_percent'] = frame_center_percent
    result['total_gaps'] = len(gaps)
    result['all_gaps'] = gaps
    
    # Calculate confidence
    confidence = 0.5
    if left_gap and right_gap:
        # Both gaps detected - high confidence
        brightness_score = min(left_gap['brightness'], right_gap['brightness']) / np.max(smoothed)
        width_score = min(1.0, frame_width / (w * 0.7))  # Expect frame to be ~70% of width
        confidence = (brightness_score * 0.6 + width_score * 0.4)
    elif left_gap or right_gap:
        # One gap detected - medium confidence
        gap = left_gap or right_gap
        confidence = min(0.8, gap['brightness'] / np.max(smoothed))
    
    result['confidence'] = confidence
    
    if debug:
        print("=" * 70)
        print(f"Image: {w}x{h}")
        print(f"Total gaps found: {len(gaps)}")
        print(f"Left gaps: {len(left_gaps)}, Right gaps: {len(right_gaps)}")
        print()
        
        if left_gap:
            print(f"LEFT GAP:  {left_gap['center']}px ({left_gap['percent']:.1f}%) - {left_gap['width']}px wide")
        else:
            print("LEFT GAP:  Not detected")
        
        if right_gap:
            print(f"RIGHT GAP: {right_gap['center']}px ({right_gap['percent']:.1f}%) - {right_gap['width']}px wide")
        else:
            print("RIGHT GAP: Not detected")
        
        if frame_width:
            print(f"FRAME WIDTH: {frame_width}px ({frame_width/w*100:.1f}% of image)")
        
        if frame_center_percent:
            print(f"FRAME CENTER: {frame_center}px ({frame_center_percent:.1f}%)")
        
        print()
        print(f"STATUS: {result['status']}")
        print(f"ACTION: {result['action']}")
        print(f"CONFIDENCE: {confidence:.2f}")
        
        # Create debug visualization
        debug_img = img.copy()
        
        # Draw all detected gaps in yellow
        for gap in gaps:
            cv2.line(debug_img, (gap['center'], 0), (gap['center'], h), (0, 255, 255), 2)
            cv2.rectangle(debug_img, (gap['start'], 0), (gap['end'], h), (0, 255, 255), 1)
        
        # Draw left gap in cyan (if detected)
        if left_gap:
            cv2.line(debug_img, (left_gap['center'], 0), (left_gap['center'], h), (255, 255, 0), 4)
            cv2.putText(debug_img, "LEFT", (left_gap['center'] - 40, 40), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
        
        # Draw right gap in magenta (if detected)
        if right_gap:
            cv2.line(debug_img, (right_gap['center'], 0), (right_gap['center'], h), (255, 0, 255), 4)
            cv2.putText(debug_img, "RIGHT", (right_gap['center'] - 50, 40), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 255), 2)
        
        # Draw frame center in green (if known)
        if frame_center:
            cv2.line(debug_img, (frame_center, 0), (frame_center, h), (0, 255, 0), 3)
            cv2.putText(debug_img, "FRAME CENTER", (frame_center - 100, h - 40), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        # Draw target zone (40-60% of width)
        target_start = int(w * 0.40)
        target_end = int(w * 0.60)
        cv2.rectangle(debug_img, (target_start, 0), (target_end, h), (0, 255, 0), 2)
        
        # Add status text
        status_text = f"{result['status']}: {result['action']}"
        cv2.putText(debug_img, status_text, (10, h - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        cv2.imwrite('/tmp/frame_detection.jpg', debug_img)
        print("\nDebug image saved to /tmp/frame_detection.jpg")
        print("=" * 70)
    
    return result


def _classify_alignment(left_gap, right_gap, frame_width, frame_center_percent, img_width):
    """
    Classify alignment status and recommend action.
    
    Target: Frame centered at 40-60% with small gaps at edges
    """
    
    # Define ideal zones
    TARGET_CENTER_MIN = 40  # Frame center should be 40-60%
    TARGET_CENTER_MAX = 60
    TARGET_CENTER_IDEAL = 50
    
    EDGE_ZONE = 15  # Gaps should be within 15% of edges
    MAX_GAP_SIZE = 100  # Maximum acceptable gap size in pixels
    
    # Case 1: Both gaps detected - best case
    if left_gap and right_gap:
        left_at_edge = left_gap['percent'] < EDGE_ZONE
        right_at_edge = right_gap['percent'] > (100 - EDGE_ZONE)
        gaps_small = left_gap['width'] < MAX_GAP_SIZE and right_gap['width'] < MAX_GAP_SIZE
        frame_centered = TARGET_CENTER_MIN <= frame_center_percent <= TARGET_CENTER_MAX
        
        if left_at_edge and right_at_edge and gaps_small and frame_centered:
            return {
                'status': 'PERFECT_ALIGNMENT',
                'action': 'CAPTURE',
                'movement': None,
                'message': f"✓ Frame centered at {frame_center_percent:.1f}%, gaps minimal"
            }
        
        elif frame_centered and gaps_small:
            return {
                'status': 'GOOD_ALIGNMENT',
                'action': 'CAPTURE_OK',
                'movement': None,
                'message': f"Frame centered at {frame_center_percent:.1f}%, acceptable"
            }
        
        elif frame_center_percent < TARGET_CENTER_MIN:
            # Frame too far left - advance forward
            distance = int((TARGET_CENTER_IDEAL - frame_center_percent) / 100 * img_width)
            return {
                'status': 'FRAME_LEFT',
                'action': 'ADVANCE_MEDIUM',
                'movement': distance,
                'message': f"Frame at {frame_center_percent:.1f}%, advance {distance}px"
            }
        
        elif frame_center_percent > TARGET_CENTER_MAX:
            # Frame too far right - back up
            distance = int((frame_center_percent - TARGET_CENTER_IDEAL) / 100 * img_width)
            return {
                'status': 'FRAME_RIGHT',
                'action': 'BACKUP_MEDIUM',
                'movement': distance,
                'message': f"Frame at {frame_center_percent:.1f}%, backup {distance}px"
            }
        
        else:
            # Frame center OK but gaps too large - fine tune
            if left_gap['width'] > right_gap['width']:
                return {
                    'status': 'NEEDS_FINE_TUNE',
                    'action': 'ADVANCE_FINE',
                    'movement': 30,
                    'message': "Large left gap, advance slightly"
                }
            else:
                return {
                    'status': 'NEEDS_FINE_TUNE',
                    'action': 'BACKUP_FINE',
                    'movement': 30,
                    'message': "Large right gap, backup slightly"
                }
    
    # Case 2: Only right gap visible - frame entering from left
    elif right_gap and not left_gap:
        if right_gap['percent'] > 75:
            # Gap far right - frame mostly off screen left, need to backup
            distance = int((right_gap['percent'] - TARGET_CENTER_IDEAL) / 100 * img_width)
            return {
                'status': 'FRAME_ENTERING_LEFT',
                'action': 'BACKUP_FINE',
                'movement': distance,
                'message': f"Gap at {right_gap['percent']:.1f}%, backup {distance}px"
            }
        else:
            # Gap in middle - multiple frames visible
            return {
                'status': 'MULTIPLE_FRAMES',
                'action': 'ADVANCE_MEDIUM',
                'movement': int(img_width * 0.3),
                'message': "Multiple frames visible, advance to next"
            }
    
    # Case 3: Only left gap visible - frame exiting to right
    elif left_gap and not right_gap:
        if left_gap['percent'] < 25:
            # Gap far left - frame mostly off screen right, advance to next
            distance = int((TARGET_CENTER_IDEAL - left_gap['percent']) / 100 * img_width)
            return {
                'status': 'FRAME_EXITING_RIGHT',
                'action': 'ADVANCE_COARSE',
                'movement': distance,
                'message': f"Gap at {left_gap['percent']:.1f}%, advance {distance}px to next frame"
            }
        else:
            # Gap in middle - uncertain state
            return {
                'status': 'UNCERTAIN',
                'action': 'ADVANCE_FINE',
                'movement': 50,
                'message': "Uncertain position, advance slightly"
            }
    
    # Case 4: No gaps detected
    else:
        return {
            'status': 'NO_GAPS_DETECTED',
            'action': 'ADVANCE_COARSE',
            'movement': int(img_width * 0.4),
            'message': "No gaps detected, advance to find next frame"
        }


def pixels_to_motor_steps(pixels, pixels_per_step=2.0):
    """
    Convert pixel distance to motor steps.
    Default: ~2 pixels per step (calibrate during use)
    """
    return int(pixels / pixels_per_step)


def get_motor_command(result, pixels_per_step=2.0):
    """
    Convert detection result to motor command.
    
    Returns:
        dict with 'command' (Arduino command string) and 'description'
    """
    
    action = result.get('action')
    movement = result.get('movement', 0)
    
    if action == 'CAPTURE' or action == 'CAPTURE_OK':
        return {
            'command': None,
            'description': '✓ Ready to capture'
        }
    
    elif action == 'ADVANCE_COARSE':
        steps = pixels_to_motor_steps(movement, pixels_per_step) if movement else 100
        return {
            'command': f'H{steps}',  # Move forward exact steps
            'description': f'Advance {steps} steps (coarse)'
        }
    
    elif action == 'ADVANCE_MEDIUM':
        steps = pixels_to_motor_steps(movement, pixels_per_step) if movement else 50
        return {
            'command': f'H{steps}',
            'description': f'Advance {steps} steps (medium)'
        }
    
    elif action == 'ADVANCE_FINE':
        steps = pixels_to_motor_steps(movement, pixels_per_step) if movement else 15
        return {
            'command': f'H{steps}',
            'description': f'Advance {steps} steps (fine)'
        }
    
    elif action == 'BACKUP_MEDIUM':
        steps = pixels_to_motor_steps(movement, pixels_per_step) if movement else 50
        return {
            'command': f'h{steps}',  # Move backward exact steps
            'description': f'Backup {steps} steps (medium)'
        }
    
    elif action == 'BACKUP_FINE':
        steps = pixels_to_motor_steps(movement, pixels_per_step) if movement else 15
        return {
            'command': f'h{steps}',
            'description': f'Backup {steps} steps (fine)'
        }
    
    else:
        return {
            'command': 'F',  # Default: advance one coarse step
            'description': 'Advance (default)'
        }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python3 optimized_edge_detect.py <image_path> [--debug]")
        print()
        print("Detects left and right frame gaps for proper 35mm alignment")
        sys.exit(1)
    
    img_path = sys.argv[1]
    debug = '--debug' in sys.argv
    
    print("=" * 70)
    print("35MM FILM FRAME DETECTION")
    print("=" * 70)
    print()
    
    result = detect_frame_gaps(img_path, debug=debug)
    
    if not debug:
        print(f"Status: {result['status']}")
        print(f"Action: {result['action']}")
        print(f"Confidence: {result['confidence']:.2f}")
        
        if result.get('frame_center_percent'):
            print(f"Frame center: {result['frame_center_percent']:.1f}%")
        
        if result.get('frame_width'):
            print(f"Frame width: {result['frame_width']}px")
        
        print()
        motor_cmd = get_motor_command(result)
        print(f"Motor command: {motor_cmd['command'] or 'NONE (aligned)'}")
        print(f"Description: {motor_cmd['description']}")
    
    print()
    print("=" * 70)
