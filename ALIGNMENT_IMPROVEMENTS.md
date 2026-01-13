# Automatic Alignment Improvements

## Problem
Automatic alignment was stuck at 80% confidence with gaps remaining on either side of the frame.

## Root Causes
1. **Fixed thresholds** - Detection used static brightness/uniformity thresholds that didn't adapt to different lighting conditions
2. **Insufficient fine-tuning** - Only 5 attempts to clear edges, with simple step calculations
3. **Binary confidence** - Returned flat 0.8 confidence instead of scoring based on actual alignment quality
4. **Edge margin too large** - 5% edge margin excluded valid gaps near frame edges

## Solutions Implemented

### 1. Adaptive Edge Detection (`web_app.py` lines 1263-1424)

**Multi-pass approach** with progressively stricter thresholds:
- **Early passes (0-2)**: Strict detection to catch obvious gaps
  - Brightness > 0.55, Std < 0.10, Min 5px
- **Middle passes (3-5)**: Moderate detection for smaller gaps  
  - Brightness > 0.50, Std < 0.12, Min 3px
- **Final passes (6-7)**: Sensitive detection for tiny gaps
  - Brightness > 0.45, Std < 0.15, Min 2px

**Adaptive brightness thresholding**:
- Analyzes overall film brightness
- If film is bright (>0.6), increases thresholds proportionally
- Prevents false positives on bright film stock

**Dual detection criteria**:
```python
# Method 1: Traditional (bright + uniform)
gap_mask = (col_mean > threshold) & (col_std < std_thresh)

# Method 2: Uniformity-first (catches gaps regardless of absolute brightness)
gap_mask |= (col_uniformity > 0.80) & (col_mean > film_brightness * 1.1)
```

### 2. Enhanced Fine-Tuning Algorithm

**Increased attempts**: 5 → 8 passes for better coverage

**Contiguous gap detection**:
- Finds actual gap regions, not just pixel counts
- Measures gap extent more accurately
- Moves based on rightmost/leftmost gap pixels

**Adaptive step calculation**:
```python
if fine_attempt < 3:
    step_multiplier = 2.0  # Aggressive
elif fine_attempt < 6:
    step_multiplier = 1.5  # Moderate
else:
    step_multiplier = 1.2  # Precise
```

**Noise reduction**:
- Applies 3x3 median blur to film region
- Reduces false positives from scratches/dirt

### 3. Improved Confidence Scoring

**Graduated confidence** based on remaining gaps:
```python
if total_gap <= 8px:
    confidence = 90-95%  # Excellent
elif total_gap <= 15px:
    confidence = 85-90%  # Good
else:
    confidence = 75-85%  # Needs work
```

**Success threshold**:
- Early passes: ≤3px per edge
- Final passes: ≤2px per edge

**Reports actual gap widths**:
```json
{
  "confidence": 0.95,
  "left_gap_width": 1,
  "right_gap_width": 2
}
```

### 4. Enhanced Frame Detector (`frame_detector.py`)

**Reduced edge margin**: 5% → 3%
- Catches gaps closer to frame edges
- Still filters mask boundaries

**Smart edge region handling**:
- Prefers interior gaps
- Includes edge gaps if they have high scores (brightness >0.7, edge_score >0.6)

**Three-method gap detection**:
1. **Traditional**: Bright (top 70%) + Uniform (std <0.12)
2. **Uniformity-first**: High uniformity (>0.70) + Brighter than average
3. **Adaptive percentile**: Top 15% brightness + Above median uniformity
   - Only activates when brightness range >0.15
   - Handles difficult lighting conditions

**Enhanced confidence calculation**:
```python
confidence = (
    brightness_score * 0.30 +    # Gap brightness
    edge_score * 0.25 +           # Edge strength
    width_score * 0.20 +          # Gap width (20-120px optimal)
    continuity_score * 0.15 +     # Vertical uniformity
    uniformity_score * 0.10       # Column consistency
)

# Bonus for clear single gap
if len(regions) == 1:
    confidence *= 1.10
```

**Adaptive continuity threshold**:
- Uses `max(min_continuity * 0.85, median * 1.1)`
- Adjusts to actual image characteristics

## Expected Results

**Before improvements**:
- ✗ Stuck at 80% confidence
- ✗ Gaps on left/right edges
- ✗ Fixed threshold issues with bright/dark film
- ✗ Poor scoring granularity

**After improvements**:
- ✓ 90-99% confidence for good alignments
- ✓ Aggressive multi-pass edge clearing
- ✓ Adaptive to different film stocks
- ✓ Accurate confidence reflects actual alignment quality
- ✓ Better logging shows gap widths and pass-by-pass progress

## Testing Recommendations

1. **Test with different film types**:
   - Dark/underexposed film
   - Bright/overexposed film  
   - High contrast scenes

2. **Monitor logs**:
   ```
   [Fine 1] Left: 15px (2 regions), Right: 8px (1 region)
   [Fine 2] Left: 6px (1 region), Right: 3px (1 region)
   [Fine 3] Left: 2px (1 region), Right: 1px (1 region)
   ✓ Both edges clear! Total: 385 steps
   ```

3. **Check confidence scores**:
   - 95%+: Excellent alignment
   - 90-95%: Good alignment
   - 85-90%: Acceptable, may need touch-up
   - <85%: Review manually

## Related Projects

Inspiration drawn from:
- **ALT-Scann8**: Sprocket hole detection for Super8
- **ImgAlign**: RAFT optical flow alignment
- **Super8FilmScanner**: OpenCV-based alignment
- **negative_scanner**: Edge detection with progressive alignment

## Files Modified

1. `web_app.py`: Enhanced `auto_align()` method (lines 1066-1424)
2. `frame_detector.py`: 
   - Improved `find_gap_candidates_brightness()` with 3-method detection
   - Enhanced confidence calculation
   - Reduced edge margin (5% → 3%)
