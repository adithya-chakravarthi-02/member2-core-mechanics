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


# Known expected results for each scenario (used later in tests/test_core.py)
EXPECTED_RESULTS = {
    "normal_movement": "No alert. Both hips stay inside safe zone the entire time.",
    "brief_left_excursion": "Left hip logs a brief excursion (~1.5s, under the 3s brief "
                             "limit). No sustained alert. Right hip stays normal.",
}
