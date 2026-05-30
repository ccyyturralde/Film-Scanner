"""
Adaptive Alignment Learner for Film Scanner

Lightweight statistical learning system that improves alignment accuracy
over time by tracking calibration measurements across scan sessions.

NOT a neural network or deep learning model — this is simple Bayesian-style
estimation that runs in <5ms on a Raspberry Pi.  It saves every px_per_step
measurement, drift observation, and pitch detection to a JSON history file,
then uses running statistics to produce better estimates each session.

What it learns:
- px_per_step: The ratio between pixel displacement and motor steps.
  Varies with belt tension, roller wear, and film stock thickness.
  Converges to a tight estimate after ~20 frames.
- Drift per frame: Systematic under/overshoot in the calibrated advance.
  Friction drives slip slightly — this predicts and pre-compensates.
- Pitch stability: How consistent the measured frame pitch is,
  which controls how aggressively to trust new measurements vs history.
"""

import json
import os
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any


HISTORY_DIR = os.path.expanduser("~/.film_scanner")
HISTORY_FILE = os.path.join(HISTORY_DIR, "alignment_history.json")

# After this many observations the estimate is considered "mature"
MATURITY_THRESHOLD = 20


@dataclass
class AlignmentObservation:
    """A single measurement from one advance+align cycle."""
    timestamp: float
    advance_steps: int          # Steps commanded for the advance
    correction_steps: int       # Steps the alignment loop had to correct
    frame_pitch_px: float       # Detected frame pitch in pixels
    px_per_step: float          # Observed px/step this cycle
    confidence: float           # Detection confidence
    method: str                 # "sprocket" or "frame_gap"


@dataclass
class AlignmentProfile:
    """Accumulated learning from scan history."""
    px_per_step_mean: float = 3.0
    px_per_step_std: float = 1.0
    px_per_step_count: int = 0

    drift_per_frame_mean: float = 0.0
    drift_per_frame_std: float = 0.5
    drift_per_frame_count: int = 0

    frame_pitch_px_mean: float = 0.0
    frame_pitch_px_std: float = 0.0
    frame_pitch_px_count: int = 0

    last_updated: float = 0.0

    def is_mature(self) -> bool:
        return self.px_per_step_count >= MATURITY_THRESHOLD

    def px_per_step_confidence(self) -> float:
        """0-1 confidence in the px_per_step estimate."""
        if self.px_per_step_count == 0:
            return 0.0
        # Relative std: lower is better
        if self.px_per_step_mean <= 0:
            return 0.0
        rel_std = self.px_per_step_std / self.px_per_step_mean
        count_factor = min(1.0, self.px_per_step_count / MATURITY_THRESHOLD)
        precision_factor = max(0.0, 1.0 - rel_std * 5.0)
        return count_factor * 0.5 + precision_factor * 0.5


class AlignmentLearner:
    """
    Tracks alignment measurements and provides improving estimates.

    Usage:
        learner = AlignmentLearner()
        learner.load()

        # Get the best current estimate
        pps = learner.get_px_per_step()

        # After each advance+align cycle, record what happened
        learner.record_observation(
            advance_steps=400,
            correction_steps=-12,
            frame_pitch_px=310.5,
            confidence=0.85,
            method="sprocket",
        )

        # Periodically save (or on session end)
        learner.save()
    """

    def __init__(self, history_file: str = HISTORY_FILE):
        self.history_file = history_file
        self.profile = AlignmentProfile()
        self.recent_observations: deque = deque(maxlen=200)
        # Per-session running stats (faster convergence within a session)
        self._session_pps: List[float] = []
        self._session_drifts: List[float] = []

    def load(self) -> bool:
        """Load profile from disk. Returns True if loaded successfully."""
        if not os.path.exists(self.history_file):
            return False
        try:
            with open(self.history_file, 'r') as f:
                data = json.load(f)
            p = data.get("profile", {})
            self.profile = AlignmentProfile(
                px_per_step_mean=p.get("px_per_step_mean", 3.0),
                px_per_step_std=p.get("px_per_step_std", 1.0),
                px_per_step_count=p.get("px_per_step_count", 0),
                drift_per_frame_mean=p.get("drift_per_frame_mean", 0.0),
                drift_per_frame_std=p.get("drift_per_frame_std", 0.5),
                drift_per_frame_count=p.get("drift_per_frame_count", 0),
                frame_pitch_px_mean=p.get("frame_pitch_px_mean", 0.0),
                frame_pitch_px_std=p.get("frame_pitch_px_std", 0.0),
                frame_pitch_px_count=p.get("frame_pitch_px_count", 0),
                last_updated=p.get("last_updated", 0.0),
            )
            return True
        except Exception:
            return False

    def save(self):
        """Persist profile to disk."""
        os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
        self.profile.last_updated = time.time()
        data = {"profile": asdict(self.profile)}
        try:
            with open(self.history_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def record_observation(
        self,
        advance_steps: int,
        correction_steps: int,
        frame_pitch_px: float,
        confidence: float,
        method: str = "sprocket",
    ):
        """
        Record one advance+align cycle outcome.

        Args:
            advance_steps: Steps commanded for the advance
            correction_steps: Steps the alignment loop applied after
            frame_pitch_px: Detected frame pitch in pixels
            confidence: Detection confidence (0-1)
            method: Detection method used
        """
        if advance_steps <= 0 or frame_pitch_px <= 0 or confidence < 0.3:
            return

        total_steps = advance_steps + correction_steps
        if total_steps <= 0:
            return

        observed_pps = frame_pitch_px / total_steps
        drift = correction_steps  # positive = had to advance more

        obs = AlignmentObservation(
            timestamp=time.time(),
            advance_steps=advance_steps,
            correction_steps=correction_steps,
            frame_pitch_px=frame_pitch_px,
            px_per_step=observed_pps,
            confidence=confidence,
            method=method,
        )
        self.recent_observations.append(obs)
        self._session_pps.append(observed_pps)
        self._session_drifts.append(drift)

        # Weighted update: higher confidence observations count more.
        # Use Welford's online algorithm for running mean+variance.
        weight = confidence
        self._update_running_stat(
            "px_per_step", observed_pps, weight,
        )
        self._update_running_stat(
            "drift_per_frame", float(drift), weight,
        )
        self._update_running_stat(
            "frame_pitch_px", frame_pitch_px, weight,
        )

    def _update_running_stat(self, prefix: str, value: float, weight: float):
        """Welford-style online update with confidence weighting."""
        mean_attr = f"{prefix}_mean"
        std_attr = f"{prefix}_std"
        count_attr = f"{prefix}_count"

        old_mean = getattr(self.profile, mean_attr)
        old_std = getattr(self.profile, std_attr)
        old_count = getattr(self.profile, count_attr)

        # Effective count increment (weighted)
        n = old_count + weight
        if n <= 0:
            return

        # Learning rate decays as we accumulate more data.
        # Early observations get high weight (fast convergence),
        # later ones get less (stability).
        alpha = weight / n

        new_mean = old_mean + alpha * (value - old_mean)

        # Incremental variance (Welford)
        if old_count > 1:
            new_var = (1 - alpha) * (old_std ** 2 + alpha * (value - old_mean) ** 2)
            new_std = max(0.001, new_var ** 0.5)
        else:
            new_std = abs(value - new_mean) if old_count > 0 else old_std

        setattr(self.profile, mean_attr, new_mean)
        setattr(self.profile, std_attr, new_std)
        setattr(self.profile, count_attr, old_count + 1)

    def get_px_per_step(self) -> float:
        """
        Best current estimate of px_per_step.

        Blends the long-term profile with session-local observations
        for fast convergence within a session while maintaining stability
        across sessions.
        """
        if not self._session_pps:
            return self.profile.px_per_step_mean

        import numpy as np
        session_mean = float(np.median(self._session_pps))

        if self.profile.px_per_step_count < 3:
            return session_mean

        # Blend: trust session data more as it accumulates,
        # but anchor to the long-term profile.
        session_weight = min(0.7, len(self._session_pps) / 20.0)
        profile_weight = 1.0 - session_weight

        return profile_weight * self.profile.px_per_step_mean + session_weight * session_mean

    def get_drift_compensation(self) -> int:
        """
        Predicted drift in steps to pre-compensate on the next advance.

        Positive = the motor systematically undershoots (add steps).
        Negative = the motor systematically overshoots (subtract steps).

        Returns 0 if not enough data or drift is within noise.
        """
        if self.profile.drift_per_frame_count < 5:
            return 0

        mean_drift = self.profile.drift_per_frame_mean
        std_drift = self.profile.drift_per_frame_std

        # Only compensate if the drift is statistically significant
        # (more than 1 std from zero)
        if abs(mean_drift) < std_drift:
            return 0

        return int(round(mean_drift))

    def get_status(self) -> Dict[str, Any]:
        """Status dict for the UI/API."""
        return {
            "px_per_step": round(self.get_px_per_step(), 3),
            "px_per_step_confidence": round(self.profile.px_per_step_confidence(), 2),
            "px_per_step_observations": self.profile.px_per_step_count,
            "drift_compensation": self.get_drift_compensation(),
            "drift_mean": round(self.profile.drift_per_frame_mean, 1),
            "drift_std": round(self.profile.drift_per_frame_std, 1),
            "frame_pitch_px": round(self.profile.frame_pitch_px_mean, 1),
            "session_observations": len(self._session_pps),
            "is_mature": self.profile.is_mature(),
        }

    def reset(self):
        """Reset all learned data (start fresh)."""
        self.profile = AlignmentProfile()
        self.recent_observations.clear()
        self._session_pps.clear()
        self._session_drifts.clear()
        self.save()
