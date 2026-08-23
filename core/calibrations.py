"""
calibration.py
Calibration step for the Pavlik-harness monitoring prototype.

Purpose:
At the start of a session, the patient/limb starts in some known reference
pose (e.g. resting position). Because the pelvis and thigh sensors may not
be perfectly aligned to true anatomical axes, we record this starting pose
as a "reference" and compute an offset (calibration) so that later live
readings can be measured RELATIVE to this reference, not to the sensor's
raw zero position.

IMPORTANT LIMITATION:
This calibration estimates the relative orientation between the pelvis and
thigh reference frames as defined by the simulated sensor placement. It does
NOT represent true anatomical hip-joint axes or real femoral-head position.
It is a software/geometric calibration only, not a clinical measurement.
"""

from scipy.spatial.transform import Rotation as R


def _to_rotation(quat_wxyz):
    """
    Convert a quaternion in our schema order [w, x, y, z] into a
    scipy Rotation object (which internally expects [x, y, z, w]).
    """
    w, x, y, z = quat_wxyz
    return R.from_quat([x, y, z, w])


def _to_wxyz(rotation: R):
    """
    Convert a scipy Rotation back into our schema order [w, x, y, z].
    Values are cast to native Python floats (not np.float64) so that
    downstream JSON export (e.g. for Member 3's dashboard) works without
    needing a custom encoder.
    """
    x, y, z, w = rotation.as_quat()
    return [float(w), float(x), float(y), float(z)]


def calibrate(pelvis_reference, left_thigh_reference, right_thigh_reference):
    """
    Compute calibration parameters for both hips using a single reference
    pose captured at the start of a session (e.g. patient resting still).

    Parameters
    ----------
    pelvis_reference : list[float]
        Quaternion [w, x, y, z] representing the pelvis orientation at the
        moment of calibration.
    left_thigh_reference : list[float]
        Quaternion [w, x, y, z] representing the left thigh orientation at
        the moment of calibration.
    right_thigh_reference : list[float]
        Quaternion [w, x, y, z] representing the right thigh orientation at
        the moment of calibration.

    Returns
    -------
    dict
        {
            "left_hip": {
                "offset_quaternion": [w, x, y, z]
            },
            "right_hip": {
                "offset_quaternion": [w, x, y, z]
            },
            "note": "..."
        }

        The offset quaternion represents the relative rotation between the
        pelvis and thigh at calibration time. Later, this offset is removed
        from live readings so that the reference pose reads as "zero"
        flexion/abduction.
    """
    pelvis_rot = _to_rotation(pelvis_reference)
    left_thigh_rot = _to_rotation(left_thigh_reference)
    right_thigh_rot = _to_rotation(right_thigh_reference)

    # Relative orientation at calibration time: R_offset = R_pelvis^-1 * R_thigh
    left_offset = pelvis_rot.inv() * left_thigh_rot
    right_offset = pelvis_rot.inv() * right_thigh_rot

    return {
        "left_hip": {
            "offset_quaternion": _to_wxyz(left_offset)
        },
        "right_hip": {
            "offset_quaternion": _to_wxyz(right_offset)
        },
        "note": (
            "Calibration parameters describe external pelvis-thigh sensor "
            "orientation only. They do not represent true anatomical "
            "femoral-head position or joint axes, and must not be "
            "interpreted as a clinical measurement."
        )
    }
