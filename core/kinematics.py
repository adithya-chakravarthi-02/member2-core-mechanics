"""
kinematics.py
Bilateral hip angle estimation for the Pavlik-harness monitoring prototype.

Purpose:
Given live pelvis and thigh orientation quaternions, plus calibration
parameters from calibration.py, compute flexion and abduction angles for
both hips.

Method:
    R_relative = R_pelvis^-1 * R_thigh

This gives the thigh's orientation relative to the pelvis. The calibration
offset (captured at rest) is then removed, so that the reported angles
represent movement AWAY from the calibrated reference pose, not raw sensor
values.

Angles are extracted using an XY Euler decomposition:
    - Flexion  = rotation about X axis (sagittal plane movement)
    - Abduction = rotation about Y axis (frontal plane movement)

This matches the simplified simulator convention in simulator/scenarios.py
(_thigh_quat uses R.from_euler('xy', [flexion, abduction])).

LIMITATION:
This is a simplified geometric model for a software prototype. It does not
represent true anatomical hip-joint kinematics or replace clinical
measurement tools.

KNOWN GEOMETRIC LIMITATION (Euler axis coupling):
Because flexion (X) and abduction (Y) rotations do not commute, subtracting
a calibration offset from a live reading gives clean, intuitive results only
when a single axis moves at a time from a near-zero baseline. When abduction
changes while flexion is already non-zero (or vice versa), the two axes
couple slightly and introduce a small cross-axis error (typically a few
degrees at the ranges used in this prototype). This is expected behavior of
Euler-angle composition, not a bug, and has acceptable margin given the
safe-zone thresholds used in patient profiles.
"""

from scipy.spatial.transform import Rotation as R


def _to_rotation(quat_wxyz):
    """Convert schema quaternion [w, x, y, z] to a scipy Rotation."""
    w, x, y, z = quat_wxyz
    return R.from_quat([x, y, z, w])


def _extract_flexion_abduction(relative_rotation: R):
    """
    Decompose a relative rotation into flexion (X) and abduction (Y)
    angles in degrees, matching the simulator's 'xy' Euler convention.

    Note: scipy's as_euler() requires a 3-axis sequence even though the
    simulator only rotates about 2 axes when building poses (from_euler
    accepts 2 axes for construction, but decomposition always needs 3).
    We use 'xyz' and discard the third (z) component, which is expected
    to be ~0 for poses built the same way the simulator builds them.
    """
    flexion_deg, abduction_deg, _unused_z = relative_rotation.as_euler('xyz', degrees=True)
    return float(flexion_deg), float(abduction_deg)


def estimate_hip_angles(pelvis_quaternion, left_thigh_quaternion,
                         right_thigh_quaternion, calibration_parameters):
    """
    Estimate bilateral hip flexion and abduction angles.

    Parameters
    ----------
    pelvis_quaternion : list[float]
        Live pelvis orientation [w, x, y, z].
    left_thigh_quaternion : list[float]
        Live left thigh orientation [w, x, y, z].
    right_thigh_quaternion : list[float]
        Live right thigh orientation [w, x, y, z].
    calibration_parameters : dict
        Output of calibration.calibrate(), containing "left_hip" and
        "right_hip" offset quaternions.

    Returns
    -------
    dict
        {
            "left_flexion_deg": float,
            "left_abduction_deg": float,
            "right_flexion_deg": float,
            "right_abduction_deg": float
        }
    """
    pelvis_rot = _to_rotation(pelvis_quaternion)
    left_thigh_rot = _to_rotation(left_thigh_quaternion)
    right_thigh_rot = _to_rotation(right_thigh_quaternion)

    left_offset_rot = _to_rotation(calibration_parameters["left_hip"]["offset_quaternion"])
    right_offset_rot = _to_rotation(calibration_parameters["right_hip"]["offset_quaternion"])

    # Relative orientation: R_relative = R_pelvis^-1 * R_thigh
    left_relative = pelvis_rot.inv() * left_thigh_rot
    right_relative = pelvis_rot.inv() * right_thigh_rot

    # Remove the calibration offset captured at rest
    left_corrected = left_offset_rot.inv() * left_relative
    right_corrected = right_offset_rot.inv() * right_relative

    left_flexion, left_abduction = _extract_flexion_abduction(left_corrected)
    right_flexion, right_abduction = _extract_flexion_abduction(right_corrected)

    return {
        "left_flexion_deg": left_flexion,
        "left_abduction_deg": left_abduction,
        "right_flexion_deg": right_flexion,
        "right_abduction_deg": right_abduction,
    }
