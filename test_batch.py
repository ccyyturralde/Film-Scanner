#!/usr/bin/env python3
"""
Quick Batch Test - Test new detection on all your images
"""

import sys
import os
import glob

# Import the new detection
try:
    from optimized_edge_detect import detect_frame_gaps
except ImportError:
    print("ERROR: Cannot import optimized_edge_detect.py")
    print("Make sure you're running from the same directory")
    sys.exit(1)

def test_image(img_path, verbose=True):
    """Test detection on a single image"""
    
    result = detect_frame_gaps(img_path, debug=False)
    
    if verbose:
        print(f"\n{'='*70}")
        print(f"File: {os.path.basename(img_path)}")
        print(f"{'='*70}")
        
        if result.get('left_gap'):
            lg = result['left_gap']
            print(f"LEFT GAP:  {lg['center']:4d}px ({lg['percent']:5.1f}%) - {lg['width']:2d}px wide")
        else:
            print("LEFT GAP:  Not detected")
        
        if result.get('right_gap'):
            rg = result['right_gap']
            print(f"RIGHT GAP: {rg['center']:4d}px ({rg['percent']:5.1f}%) - {rg['width']:2d}px wide")
        else:
            print("RIGHT GAP: Not detected")
        
        if result.get('frame_width'):
            print(f"FRAME WIDTH: {result['frame_width']}px")
        
        if result.get('frame_center_percent'):
            print(f"FRAME CENTER: {result['frame_center_percent']:.1f}%")
        
        print(f"\nSTATUS: {result['status']}")
        print(f"ACTION: {result['action']}")
        print(f"CONFIDENCE: {result['confidence']:.2f}")
        print(f"MESSAGE: {result['message']}")
    
    return result

def main():
    # Test on project images
    test_dir = "/mnt/project"
    
    if len(sys.argv) > 1:
        test_dir = sys.argv[1]
    
    print("="*70)
    print("FILM SCANNER - BATCH DETECTION TEST")
    print("="*70)
    print(f"\nTesting images in: {test_dir}")
    
    # Find all JPG images
    images = glob.glob(os.path.join(test_dir, "*.jpg"))
    images.extend(glob.glob(os.path.join(test_dir, "*.JPG")))
    
    if not images:
        print(f"\nNo JPG images found in {test_dir}")
        sys.exit(1)
    
    print(f"Found {len(images)} images\n")
    
    # Test each image
    results = []
    for img_path in sorted(images):
        result = test_image(img_path, verbose=True)
        results.append({
            'filename': os.path.basename(img_path),
            'result': result
        })
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    aligned = sum(1 for r in results if r['result']['action'] in ['CAPTURE', 'CAPTURE_OK'])
    needs_adjustment = len(results) - aligned
    avg_confidence = sum(r['result']['confidence'] for r in results) / len(results)
    
    print(f"\nTotal images: {len(results)}")
    print(f"Aligned (ready to capture): {aligned}")
    print(f"Needs adjustment: {needs_adjustment}")
    print(f"Average confidence: {avg_confidence:.2f}")
    
    print("\nDetailed results:")
    for r in results:
        status = r['result']['status']
        action = r['result']['action']
        conf = r['result']['confidence']
        
        status_icon = "✓" if action in ['CAPTURE', 'CAPTURE_OK'] else "→"
        print(f"  {status_icon} {r['filename']:30s} {status:20s} {action:20s} (conf: {conf:.2f})")
    
    print("\n" + "="*70)
    print("\nTo see detailed debug visualizations:")
    print("  python3 optimized_edge_detect.py /path/to/image.jpg --debug")
    print("\nDebug images will be saved to /tmp/frame_detection.jpg")
    print("="*70)

if __name__ == "__main__":
    main()
