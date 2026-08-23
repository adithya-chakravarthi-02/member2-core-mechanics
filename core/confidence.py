"""
confidence.py
Data-quality / confidence scoring for the Pavlik-harness monitoring prototype.

Purpose:
Before trusting a reading enough to run it through the safe-zone and alert
logic, we need to know whether the incoming sensor data is actually
reliable. This module inspects one hip's quaternion stream and flags:

    - Missing values          (dropped sensor packets)
    - Sudden impossible jumps (single-step orientation change too large
                                to be physically real)
    - Unrealistic angular velocity (sustained motion faster than a real
                                     hip could plausibly move)
    - Excessive noise          (jittery, inconsistent readings across
                                 recent samples)

Output feeds directly into alert_engine.py: when confidence drops below
the patient profile's minimum_confidence threshold, alert_engine.py
suppresses the normal zone/duration alert logic and reports
DATA_QUALITY_WARNING instead. This module only computes the score/reason;
the suppression decision itself lives in alert_engine.py.

LIMITATION:
This is a software research prototype only. Thresholds below are
simulated demonstration values, not clinically validated limits.
"""

from scipy.spatial.transform import Rotation as R

# Demonstration thresholds - not clinical values.
SUDDEN_JUMP_VELOCITY_DEG_PER_S = 500.0        # single-step "impossible" change
UNREALISTIC_VELOCITY_DEG_PER_S = 250.0        # sustained-too-fast movement
NOISE_MEAN_STEP_THRESHOLD_DEG = 5.0           # average per-step jitter in window


def _to_rotation(quat_wxyz):
    """Convert schema quaternion [w, x, y, z] to a scipy Rotation."""
    w, x, y, z = quat_wxyz
    return R.from_quat([x, y, z, w])


def _is_valid_quaternion(quat):
    """Basic structural check: 4 numeric values, not None."""
    if quat is None:
        return False
    if not isinstance(quat, (list, tuple)) or len(quat) != 4:
        return False
    try:
        return all(isinstance(v, (int, float)) for v in quat)
    except TypeError:
        return False


def _angular_distance_deg(quat_a, quat_b):
    """
    Angle (in degrees) of the rotation that takes quat_a to quat_b.
    Used both for jump detection (vs. previous sample) and noise detection
    (across a short recent window).
    """
    rot_a = _to_rotation(quat_a)
    rot_b = _to_rotation(quat_b)
    relative = rot_a.inv() * rot_b
    angle_rad = relative.magnitude()
    return float(angle_rad * 180.0 / 3.141592653589793)


def assess_confidence(current_quaternion, previous_quaternion=None,
                       dt_seconds=0.15, recent_quaternions=None):
    """
    Assess data quality/confidence for a single hip's thigh quaternion
    stream, for one incoming sample.

    Parameters
    ----------
    current_quaternion : list[float] or None
        This sample's thigh quaternion [w, x, y, z]. None if the sensor
        packet was dropped.
    previous_quaternion : list[float] or None
        The previous sample's thigh quaternion, used for jump/velocity
        detection. None on the very first sample of a session.
    dt_seconds : float
        Time elapsed since the previous sample, in seconds.
    recent_quaternions : list[list[float]] or None
        A short rolling window of the last N valid quaternions (oldest
        first), used to detect excessive noise. Optional - if omitted,
        noise detection is skipped for this call.

    Returns
    -------
    dict
        {
            "confidence": float,       # 0.0 to 1.0
            "quality_status": str,     # "high" | "medium" | "low"
            "reason": str,             # "none" | "missing_data" |
                                        # "sudden_orientation_jump" |
                                        # "unrealistic_angular_velocity" |
                                        # "excessive_noise" | combinations
                                        # joined with "+"
        }
    """
    # ---- Missing data check (overrides everything else) ----
    if not _is_valid_quaternion(current_quaternion):
        return {
            "confidence": 0.0,
            "quality_status": "low",
            "reason": "missing_data",
        }

    confidence = 1.0
    reasons = []

    # ---- Sudden jump / unrealistic angular velocity check ----
    if previous_quaternion is not None and _is_valid_quaternion(previous_quaternion) \
            and dt_seconds > 0:
        angular_distance = _angular_distance_deg(previous_quaternion, current_quaternion)
        angular_velocity = angular_distance / dt_seconds

        if angular_velocity > SUDDEN_JUMP_VELOCITY_DEG_PER_S:
            confidence -= 0.6
            reasons.append("sudden_orientation_jump")
        elif angular_velocity > UNREALISTIC_VELOCITY_DEG_PER_S:
            confidence -= 0.35
            reasons.append("unrealistic_angular_velocity")

    # ---- Excessive noise check (needs a short recent history) ----
    # Random sensor jitter produces consistently large step-to-step
    # distances (each sample is essentially an independent random draw
    # around the true pose), whereas real smooth movement produces small,
    # gradual steps even during genuine motion. We measure the MEAN
    # step distance across the window - not its variance - since jitter
    # is characterized by persistently large steps, not inconsistent ones.
    if recent_quaternions and len(recent_quaternions) >= 3:
        valid_recent = [q for q in recent_quaternions if _is_valid_quaternion(q)]
        if len(valid_recent) >= 3:
            step_distances = [
                _angular_distance_deg(valid_recent[i], valid_recent[i + 1])
                for i in range(len(valid_recent) - 1)
            ]
            mean_step_distance = sum(step_distances) / len(step_distances)

            if mean_step_distance > NOISE_MEAN_STEP_THRESHOLD_DEG:
                confidence -= 0.4
                reasons.append("excessive_noise")

    confidence = max(0.0, min(1.0, confidence))

    if confidence >= 0.85:
        quality_status = "high"
    elif confidence >= 0.6:
        quality_status = "medium"
    else:
        quality_status = "low"

    reason = "+".join(reasons) if reasons else "none"

    return {
        "confidence": float(confidence),
        "quality_status": quality_status,
        "reason": reason,
    }
