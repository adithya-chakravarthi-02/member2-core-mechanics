"""
scenarios.py
Defines simulated movement scenarios for the Pavlik-harness prototype.
Each function returns a list of raw records following the fixed data schema.
"""

import numpy as np
from scipy.spatial.transform import Rotation as R


def _quat_wxyz(rotation: R):
    """Convert scipy Rotation (x,y,z,w) to our schema order (w,x,y,z)."""
    x, y, z, w = rotation.as_quat()
    return [w, x, y, z]


def _identity_quat():
    return [1.0, 0.0, 0.0, 0.0]


def _thigh_quat(flexion_deg, abduction_deg):
    """
    Build a simple thigh quaternion relative to identity pelvis,
    using flexion (rotation about X) and abduction (rotation about Y).
    This is a simplified simulation, not real biomechanics.
    """
    rot = R.from_euler('xy', [flexion_deg, abduction_deg], degrees=True)
    return _quat_wxyz(rot)


def normal_movement(duration_seconds=10, interval_seconds=0.15):
    """
    Both hips stay comfortably inside the safe zone the whole time.
    Expected result: no alert, status stays 'normal'.
    """
    records = []
    t = 0.0
    while t < duration_seconds:
        flexion = 100 + np.random.uniform(-2, 2)
        abduction = 45 + np.random.uniform(-2, 2)

        records.append({
            "timestamp": round(t, 3),
            "pelvis_quaternion": _identity_quat(),
            "left_thigh_quaternion": _thigh_quat(flexion, abduction),
            "right_thigh_quaternion": _thigh_quat(flexion, abduction),
        })
        t += interval_seconds
    return records


def brief_left_excursion(duration_seconds=10, interval_seconds=0.15,
                          excursion_start=4.0, excursion_length=1.5):
    """
    Left hip briefly moves outside the safe zone (shorter than the
    brief_event_limit_seconds threshold), then returns to normal.
    Right hip stays normal throughout.
    Expected result: left side logs a brief excursion, NOT a sustained alert.
    """
    records = []
    t = 0.0
    while t < duration_seconds:
        # Right hip: always normal
        right_flexion = 100 + np.random.uniform(-2, 2)
        right_abduction = 45 + np.random.uniform(-2, 2)

        # Left hip: normal, except during the excursion window
        if excursion_start <= t < excursion_start + excursion_length:
            left_flexion = 130 + np.random.uniform(-2, 2)   # outside 90-110 range
            left_abduction = 45 + np.random.uniform(-2, 2)
        else:
            left_flexion = 100 + np.random.uniform(-2, 2)
            left_abduction = 45 + np.random.uniform(-2, 2)

        records.append({
            "timestamp": round(t, 3),
            "pelvis_quaternion": _identity_quat(),
            "left_thigh_quaternion": _thigh_quat(left_flexion, left_abduction),
            "right_thigh_quaternion": _thigh_quat(right_flexion, right_abduction),
        })
        t += interval_seconds
    return records


def brief_right_excursion(duration_seconds=10, interval_seconds=0.15,
                           excursion_start=4.0, excursion_length=1.5):
    """
    Right hip briefly moves outside the safe zone (shorter than brief limit).
    Left hip stays normal throughout.
    Expected result: right side logs a brief excursion, NOT a sustained alert.
    """
    records = []
    t = 0.0
    while t < duration_seconds:
        left_flexion = 100 + np.random.uniform(-2, 2)
        left_abduction = 45 + np.random.uniform(-2, 2)

        if excursion_start <= t < excursion_start + excursion_length:
            right_flexion = 130 + np.random.uniform(-2, 2)
            right_abduction = 45 + np.random.uniform(-2, 2)
        else:
            right_flexion = 100 + np.random.uniform(-2, 2)
            right_abduction = 45 + np.random.uniform(-2, 2)

        records.append({
            "timestamp": round(t, 3),
            "pelvis_quaternion": _identity_quat(),
            "left_thigh_quaternion": _thigh_quat(left_flexion, left_abduction),
            "right_thigh_quaternion": _thigh_quat(right_flexion, right_abduction),
        })
        t += interval_seconds
    return records


def sustained_left_excursion(duration_seconds=15, interval_seconds=0.15,
                              excursion_start=3.0, excursion_length=10.0):
    """
    Left hip moves outside the safe zone for LONGER than the sustained limit (8s).
    Right hip stays normal.
    Expected result: left side triggers a SUSTAINED alert.
    """
    records = []
    t = 0.0
    while t < duration_seconds:
        right_flexion = 100 + np.random.uniform(-2, 2)
        right_abduction = 45 + np.random.uniform(-2, 2)

        if excursion_start <= t < excursion_start + excursion_length:
            left_flexion = 130 + np.random.uniform(-2, 2)
            left_abduction = 45 + np.random.uniform(-2, 2)
        else:
            left_flexion = 100 + np.random.uniform(-2, 2)
            left_abduction = 45 + np.random.uniform(-2, 2)

        records.append({
            "timestamp": round(t, 3),
            "pelvis_quaternion": _identity_quat(),
            "left_thigh_quaternion": _thigh_quat(left_flexion, left_abduction),
            "right_thigh_quaternion": _thigh_quat(right_flexion, right_abduction),
        })
        t += interval_seconds
    return records


def sustained_right_excursion(duration_seconds=15, interval_seconds=0.15,
                               excursion_start=3.0, excursion_length=10.0):
    """
    Right hip moves outside the safe zone for LONGER than the sustained limit (8s).
    Left hip stays normal.
    Expected result: right side triggers a SUSTAINED alert.
    """
    records = []
    t = 0.0
    while t < duration_seconds:
        left_flexion = 100 + np.random.uniform(-2, 2)
        left_abduction = 45 + np.random.uniform(-2, 2)

        if excursion_start <= t < excursion_start + excursion_length:
            right_flexion = 130 + np.random.uniform(-2, 2)
            right_abduction = 45 + np.random.uniform(-2, 2)
        else:
            right_flexion = 100 + np.random.uniform(-2, 2)
            right_abduction = 45 + np.random.uniform(-2, 2)

        records.append({
            "timestamp": round(t, 3),
            "pelvis_quaternion": _identity_quat(),
            "left_thigh_quaternion": _thigh_quat(left_flexion, left_abduction),
            "right_thigh_quaternion": _thigh_quat(right_flexion, right_abduction),
        })
        t += interval_seconds
    return records


def bilateral_excursion(duration_seconds=15, interval_seconds=0.15,
                         excursion_start=3.0, excursion_length=10.0):
    """
    BOTH hips move outside the safe zone at the same time, for longer than
    the sustained limit.
    Expected result: sustained alert fires for BOTH left and right independently.
    """
    records = []
    t = 0.0
    while t < duration_seconds:
        if excursion_start <= t < excursion_start + excursion_length:
            flexion = 130 + np.random.uniform(-2, 2)
            abduction = 45 + np.random.uniform(-2, 2)
        else:
            flexion = 100 + np.random.uniform(-2, 2)
            abduction = 45 + np.random.uniform(-2, 2)

        records.append({
            "timestamp": round(t, 3),
            "pelvis_quaternion": _identity_quat(),
            "left_thigh_quaternion": _thigh_quat(flexion, abduction),
            "right_thigh_quaternion": _thigh_quat(flexion, abduction),
        })
        t += interval_seconds
    return records


def repeated_left_excursions(duration_seconds=60, interval_seconds=0.15,
                              excursion_length=2.0, num_excursions=4,
                              gap_seconds=10.0):
    """
    Left hip has several SHORT excursions (each under the brief limit),
    spaced closely together within the repeated_event_window (300s default).
    Right hip stays normal.
    Expected result: individually each excursion is 'brief', but the pattern
    triggers a REPEATED_OR_PERSISTENT_EVENT flag.
    """
    records = []
    t = 0.0

    # Build excursion windows: e.g. starts at 5, 15, 25, 35...
    excursion_windows = []
    start = 5.0
    for _ in range(num_excursions):
        excursion_windows.append((start, start + excursion_length))
        start += gap_seconds

    while t < duration_seconds:
        right_flexion = 100 + np.random.uniform(-2, 2)
        right_abduction = 45 + np.random.uniform(-2, 2)

        in_excursion = any(start <= t < end for start, end in excursion_windows)
        if in_excursion:
            left_flexion = 130 + np.random.uniform(-2, 2)
            left_abduction = 45 + np.random.uniform(-2, 2)
        else:
            left_flexion = 100 + np.random.uniform(-2, 2)
            left_abduction = 45 + np.random.uniform(-2, 2)

        records.append({
            "timestamp": round(t, 3),
            "pelvis_quaternion": _identity_quat(),
            "left_thigh_quaternion": _thigh_quat(left_flexion, left_abduction),
            "right_thigh_quaternion": _thigh_quat(right_flexion, right_abduction),
        })
        t += interval_seconds
    return records


def noisy_data(duration_seconds=10, interval_seconds=0.15, noise_level=15.0):
    """
    Both hips are actually within the safe zone, but the sensor readings
    are very noisy (large random jitter on every sample).
    Expected result: confidence drops due to excessive noise, producing a
    DATA_QUALITY_WARNING instead of a normal or alert status.
    """
    records = []
    t = 0.0
    while t < duration_seconds:
        left_flexion = 100 + np.random.uniform(-noise_level, noise_level)
        left_abduction = 45 + np.random.uniform(-noise_level, noise_level)
        right_flexion = 100 + np.random.uniform(-noise_level, noise_level)
        right_abduction = 45 + np.random.uniform(-noise_level, noise_level)

        records.append({
            "timestamp": round(t, 3),
            "pelvis_quaternion": _identity_quat(),
            "left_thigh_quaternion": _thigh_quat(left_flexion, left_abduction),
            "right_thigh_quaternion": _thigh_quat(right_flexion, right_abduction),
        })
        t += interval_seconds
    return records


def missing_data(duration_seconds=10, interval_seconds=0.15,
                  missing_start=4.0, missing_length=1.0):
    """
    A short window of records has missing (None) quaternion values,
    simulating dropped sensor packets.
    Expected result: DATA_QUALITY_WARNING during the missing window.
    """
    records = []
    t = 0.0
    while t < duration_seconds:
        if missing_start <= t < missing_start + missing_length:
            left_thigh_q = None
            right_thigh_q = None
        else:
            flexion = 100 + np.random.uniform(-2, 2)
            abduction = 45 + np.random.uniform(-2, 2)
            left_thigh_q = _thigh_quat(flexion, abduction)
            right_thigh_q = _thigh_quat(flexion, abduction)

        records.append({
            "timestamp": round(t, 3),
            "pelvis_quaternion": _identity_quat(),
            "left_thigh_quaternion": left_thigh_q,
            "right_thigh_quaternion": right_thigh_q,
        })
        t += interval_seconds
    return records


def sudden_unrealistic_jump(duration_seconds=10, interval_seconds=0.15,
                             jump_time=5.0):
    """
    Orientation suddenly jumps to a physically impossible pose for one sample
    (simulating a sensor glitch), then returns to normal immediately after.
    Expected result: confidence check flags 'sudden_orientation_jump',
    producing a DATA_QUALITY_WARNING for that sample only.
    """
    records = []
    t = 0.0
    while t < duration_seconds:
        if abs(t - jump_time) < interval_seconds / 2:
            # Impossible instantaneous change: flexion jumps to 179 degrees
            left_flexion = 179.0
            left_abduction = 89.0
        else:
            left_flexion = 100 + np.random.uniform(-2, 2)
            left_abduction = 45 + np.random.uniform(-2, 2)

        right_flexion = 100 + np.random.uniform(-2, 2)
        right_abduction = 45 + np.random.uniform(-2, 2)

        records.append({
            "timestamp": round(t, 3),
            "pelvis_quaternion": _identity_quat(),
            "left_thigh_quaternion": _thigh_quat(left_flexion, left_abduction),
            "right_thigh_quaternion": _thigh_quat(right_flexion, right_abduction),
        })
        t += interval_seconds
    return records


# Known expected results for each scenario (used later in tests/test_core.py)
EXPECTED_RESULTS = {
    "normal_movement":
        "No alert. Both hips stay inside safe zone the entire time.",

    "brief_left_excursion":
        "Left hip logs a brief excursion (~1.5s, under the 3s brief limit). "
        "No sustained alert. Right hip stays normal.",

    "brief_right_excursion":
        "Right hip logs a brief excursion (~1.5s, under the 3s brief limit). "
        "No sustained alert. Left hip stays normal.",

    "sustained_left_excursion":
        "Left hip stays outside the safe zone for 10s (over the 8s sustained "
        "limit). Triggers a SUSTAINED alert on the left side only.",

    "sustained_right_excursion":
        "Right hip stays outside the safe zone for 10s (over the 8s sustained "
        "limit). Triggers a SUSTAINED alert on the right side only.",

    "bilateral_excursion":
        "Both hips stay outside the safe zone for 10s at the same time. "
        "SUSTAINED alert triggers independently for left and right.",

    "repeated_left_excursions":
        "Left hip has 4 short excursions (2s each, under brief limit), spaced "
        "10s apart. Individually each is 'brief', but the pattern triggers a "
        "REPEATED_OR_PERSISTENT_EVENT flag. Right hip stays normal.",

    "noisy_data":
        "Both hips technically stay near the safe zone, but readings are very "
        "noisy. Confidence drops below 0.75 threshold, producing a "
        "DATA_QUALITY_WARNING instead of a normal/alert status.",

    "missing_data":
        "Left and right thigh quaternions are missing (None) for a 1s window. "
        "Produces a DATA_QUALITY_WARNING during that window.",

    "sudden_unrealistic_jump":
        "Left hip orientation jumps to an impossible pose for a single sample, "
        "then returns to normal. Confidence check flags "
        "'sudden_orientation_jump', producing a DATA_QUALITY_WARNING for that "
        "sample only.",
}
