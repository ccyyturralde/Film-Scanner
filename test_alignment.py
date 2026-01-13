#!/usr/bin/env python3
"""
Test script for automatic alignment improvements.

Usage:
    python3 test_alignment.py [image_path]
    
If no image provided, will attempt to connect to capture card.
"""

import sys
import cv2
import numpy as np
from frame_detector import detect_frame_gap, jpeg_bytes_to_color
import json

def test_alignment_detection(image_source):
    """Test alignment detection on an image."""
    
    # Load image
    if isinstance(image_source, str):
        print(f"Loading image: {image_source}")
        img = cv2.imread(image_source)
        if img is None:
            print(f"✗ Failed to load image: {image_source}")
            return False
        
        # Encode as JPEG
        success, jpeg_bytes = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not success:
            print("✗ Failed to encode image as JPEG")
            return False
        jpeg_bytes = jpeg_bytes.tobytes()
        print(f"✓ Image loaded: {img.shape[1]}x{img.shape[0]}")
    else:
        jpeg_bytes = image_source
        img = jpeg_bytes_to_color(jpeg_bytes)
        print(f"✓ Frame captured: {img.shape[1]}x{img.shape[0]}")
    
    # Test with different parameter sets
    test_configs = [
        {
            "name": "Default",
            "params": {
                "mean_threshold": 0.70,
                "std_threshold": 0.12,
                "min_gap_width": 8,
            }
        },
        {
            "name": "Strict",
            "params": {
                "mean_threshold": 0.75,
                "std_threshold": 0.10,
                "min_gap_width": 10,
            }
        },
        {
            "name": "Relaxed",
            "params": {
                "mean_threshold": 0.65,
                "std_threshold": 0.15,
                "min_gap_width": 5,
            }
        },
    ]
    
    print("\n" + "="*60)
    print("TESTING ALIGNMENT DETECTION")
    print("="*60)
    
    best_result = None
    best_confidence = 0.0
    
    for config in test_configs:
        print(f"\n--- {config['name']} Configuration ---")
        print(f"Parameters: {config['params']}")
        
        try:
            result = detect_frame_gap(
                jpeg_bytes,
                roi={"x0": 0.05, "x1": 0.95, "y0": 0.15, "y1": 0.85},
                **config['params']
            )
            
            print(f"\nResults:")
            print(f"  Confidence: {result.confidence:.1%}")
            print(f"  Gap X: {result.gap_x}px" if result.gap_x else "  No gap detected")
            print(f"  Offset from center: {result.offset_px}px")
            print(f"  Gaps found: {len(result.gaps) if result.gaps else 0}")
            
            if result.gaps:
                print(f"\n  Gap details:")
                for i, gap in enumerate(result.gaps[:3]):  # Show top 3
                    print(f"    {i+1}. x={gap.center_x}px, width={gap.width}px, "
                          f"brightness={gap.mean_brightness:.2f}, edge={gap.edge_score:.2f}")
            
            if result.debug_info:
                print(f"\n  Debug info:")
                print(f"    Mean brightness: {result.debug_info.get('col_mean_min', 0):.2f} - "
                      f"{result.debug_info.get('col_mean_max', 0):.2f}")
                print(f"    Std dev: {result.debug_info.get('col_std_min', 0):.2f} - "
                      f"{result.debug_info.get('col_std_max', 0):.2f}")
                if 'edge_strength_max' in result.debug_info:
                    print(f"    Edge strength max: {result.debug_info['edge_strength_max']:.2f}")
                print(f"    Vertical continuity max: {result.debug_info.get('vertical_continuity_max', 0):.2f}")
                print(f"    Column uniformity max: {result.debug_info.get('column_uniformity_max', 0):.2f}")
            
            if result.confidence > best_confidence:
                best_confidence = result.confidence
                best_result = (config['name'], result)
                
        except Exception as e:
            print(f"  ✗ Error: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    if best_result:
        config_name, result = best_result
        print(f"Best configuration: {config_name}")
        print(f"Confidence: {result.confidence:.1%}")
        print(f"Gap position: {result.gap_x}px" if result.gap_x else "No gap detected")
        print(f"Offset: {result.offset_px}px")
        
        # Visualize if we have the image
        if img is not None and result.gaps:
            visualize_result(img, result)
    else:
        print("✗ No successful detection")
    
    return best_result is not None


def visualize_result(img, result):
    """Visualize detection result on the image."""
    vis = img.copy()
    h, w = vis.shape[:2]
    
    # Draw center line
    center_x = w // 2
    cv2.line(vis, (center_x, 0), (center_x, h), (255, 0, 0), 2)
    cv2.putText(vis, "CENTER", (center_x + 5, 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
    
    # Draw ROI if available
    if result.debug_info and 'lit_region' in result.debug_info:
        lit = result.debug_info['lit_region']
        cv2.rectangle(vis, (lit['x0'], lit['y0']), (lit['x1'], lit['y1']), 
                     (255, 255, 0), 2)
    
    # Draw detected gaps
    if result.gaps:
        for i, gap in enumerate(result.gaps):
            color = (0, 255, 0) if i == 0 else (0, 255, 255)  # Green for best, yellow for others
            thickness = 3 if i == 0 else 2
            
            # Draw gap region
            cv2.rectangle(vis, 
                         (gap.global_start_x, 0), 
                         (gap.global_end_x, h), 
                         color, thickness)
            
            # Draw center line
            cv2.line(vis, (gap.center_x, 0), (gap.center_x, h), color, 1)
            
            # Label
            label = f"Gap {i+1}" if i > 0 else "BEST GAP"
            cv2.putText(vis, label, (gap.global_start_x, 60 + i*30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
    
    # Draw offset arrow
    if result.gap_x:
        offset_color = (0, 0, 255) if abs(result.offset_px) > 50 else (0, 255, 0)
        cv2.arrowedLine(vis, (center_x, h - 50), (result.gap_x, h - 50), 
                       offset_color, 3, tipLength=0.3)
        cv2.putText(vis, f"Offset: {result.offset_px}px", 
                   (min(center_x, result.gap_x), h - 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, offset_color, 2)
    
    # Add confidence overlay
    conf_color = (0, 255, 0) if result.confidence > 0.90 else (0, 255, 255) if result.confidence > 0.75 else (0, 0, 255)
    cv2.putText(vis, f"Confidence: {result.confidence:.0%}", (10, 30),
               cv2.FONT_HERSHEY_SIMPLEX, 1.0, conf_color, 2)
    
    # Save and display
    output_path = "alignment_test_result.jpg"
    cv2.imwrite(output_path, vis)
    print(f"\n✓ Visualization saved to: {output_path}")
    
    # Try to display (may not work headless)
    try:
        cv2.imshow("Alignment Detection Result", vis)
        print("Press any key to close...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    except:
        print("(Display not available - running headless)")


def main():
    if len(sys.argv) > 1:
        # Test with image file
        image_path = sys.argv[1]
        success = test_alignment_detection(image_path)
    else:
        print("Usage: python3 test_alignment.py <image_path>")
        print("\nOr run without arguments to test with capture card (if available)")
        
        # Try capture card
        try:
            print("\nAttempting to connect to capture card...")
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                print("✗ No capture card found")
                return 1
            
            print("✓ Capture card connected")
            print("Capturing frame...")
            
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                print("✗ Failed to capture frame")
                return 1
            
            # Encode as JPEG
            success, jpeg_bytes = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not success:
                print("✗ Failed to encode frame")
                return 1
            
            success = test_alignment_detection(jpeg_bytes.tobytes())
        except Exception as e:
            print(f"✗ Error: {e}")
            return 1
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
