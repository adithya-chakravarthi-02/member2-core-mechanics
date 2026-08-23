"""
test_core.py
Test suite for the Pavlik-harness monitoring prototype's processing core.

Covers every row from the expected-results table built during simulator
development (scenarios.py EXPECTED_RESULTS), plus targeted unit tests for
each individual module (calibration, kinematics, safe_zone, confidence,
alert_engine).

Run with: pytest tests/test_core.py -v
"""

import json
import os
import sys

import pytest
from scipy.spatial.transform import Rotation as R

# Make project root importable regardless of where pytest is invoked from
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from core import calibration, kinematics, safe_zone, confidence, alert_engine
from simulator import scenarios


# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def patient_profile():
    profile_path = os.path.join(PROJECT_ROOT, "data", "profiles", "sample_patient.json")
    with open(profile_path) as f:
        return json.load(f)


@pytest.fixture
def identity_calibration():
    """Calibration where pelvis and both thighs start perfectly aligned."""
    return calibration.calibrate(
        pelvis_reference=[1.0, 0.0, 0.0, 0.0],
        left_thigh_reference=[1.0, 0.0, 0.0, 0.0],
        right_thigh_reference=[1.0, 0.0, 0.0, 0.0],
    )


def run_scenario(records, patient_profile, calib_params, dt=0.15):
    """
    Push an entire scenario's records through the full pipeline:
    kinematics -> safe_zone -> confidence -> alert_engine, for both hips.

    Returns a dict: {"left": [status, status, ...], "right": [...]}
    plus the final alert_state for inspecting event_history afterward.
    """
    alert_state = alert_engine.init_alert_state()
    statuses = {"left": [], "right": []}
    recent_quats = {"left": [], "right": []}
    previous_quats = {"left": None, "right": None}

    for record in records:
        for side in ("left", "right"):
            thigh_quat = record[f"{side}_thigh_quaternion"]

            conf_result = confidence.assess_confidence(
                current_quaternion=thigh_quat,
                previous_quaternion=previous_quats[side],
                dt_seconds=dt,
                recent_quaternions=recent_quats[side][-6:] if recent_quats[side] else None,
            )

            if thigh_quat is not None:
                angles = kinematics.estimate_hip_angles(
                    record["pelvis_quaternion"],
                    thigh_quat if side == "left" else previous_quats["left"] or thigh_quat,
                    thigh_quat if side == "right" else previous_quats["right"] or thigh_quat,
                    calib_params,
                )
                flexion = angles[f"{side}_flexion_deg"]
                abduction = angles[f"{side}_abduction_deg"]
                zone_result = safe_zone.check_hip_safe_zone(
                    flexion, abduction, patient_profile[f"{side}_hip"]
                )
            else:
                # Missing data: zone check is meaningless, feed a neutral
                # placeholder since confidence will already flag it.
                zone_result = {"inside": True, "deviation_deg": 0.0, "boundary_distance": 0.0}

            alert_result = alert_engine.process_hip_alert(
                side, record["timestamp"], conf_result["confidence"],
                zone_result, patient_profile, alert_state,
            )
            statuses[side].append(alert_result["status"])

            if thigh_quat is not None:
                recent_quats[side].append(thigh_quat)
                previous_quats[side] = thigh_quat

    return statuses, alert_state


# ---------------------------------------------------------------------------
# 1. Correct quaternion input / schema sanity
# ---------------------------------------------------------------------------

def test_normal_movement_record_shape():
    records = scenarios.normal_movement(duration_seconds=1)
    record = records[0]
    assert set(record.keys()) == {
        "timestamp", "pelvis_quaternion",
        "left_thigh_quaternion", "right_thigh_quaternion",
    }
    assert len(record["pelvis_quaternion"]) == 4
    assert len(record["left_thigh_quaternion"]) == 4
    assert len(record["right_thigh_quaternion"]) == 4


# ---------------------------------------------------------------------------
# 2. Calibration
# ---------------------------------------------------------------------------

def test_calibration_identity_pose():
    result = calibration.calibrate(
        pelvis_reference=[1.0, 0.0, 0.0, 0.0],
        left_thigh_reference=[1.0, 0.0, 0.0, 0.0],
        right_thigh_reference=[1.0, 0.0, 0.0, 0.0],
    )
    assert result["left_hip"]["offset_quaternion"] == pytest.approx([1.0, 0.0, 0.0, 0.0])
    assert result["right_hip"]["offset_quaternion"] == pytest.approx([1.0, 0.0, 0.0, 0.0])


def test_calibration_output_is_json_serializable():
    result = calibration.calibrate(
        pelvis_reference=[1.0, 0.0, 0.0, 0.0],
        left_thigh_reference=[1.0, 0.0, 0.0, 0.0],
        right_thigh_reference=[1.0, 0.0, 0.0, 0.0],
    )
    json.dumps(result)  # raises if any value isn't a native type


# ---------------------------------------------------------------------------
# 3. Kinematics: known flexion / abduction movements
# ---------------------------------------------------------------------------

def test_known_flexion_movement(identity_calibration):
    pose = R.from_euler('xy', [15, 0], degrees=True)
    x, y, z, w = pose.as_quat()
    quat = [float(w), float(x), float(y), float(z)]

    angles = kinematics.estimate_hip_angles(
        [1.0, 0.0, 0.0, 0.0], quat, quat, identity_calibration
    )
    assert angles["left_flexion_deg"] == pytest.approx(15.0, abs=0.5)
    assert angles["left_abduction_deg"] == pytest.approx(0.0, abs=0.5)


def test_known_abduction_movement(identity_calibration):
    pose = R.from_euler('xy', [0, 20], degrees=True)
    x, y, z, w = pose.as_quat()
    quat = [float(w), float(x), float(y), float(z)]

    angles = kinematics.estimate_hip_angles(
        [1.0, 0.0, 0.0, 0.0], quat, quat, identity_calibration
    )
    assert angles["left_abduction_deg"] == pytest.approx(20.0, abs=0.5)
    assert angles["left_flexion_deg"] == pytest.approx(0.0, abs=0.5)


def test_left_right_independent(identity_calibration):
    left_pose = R.from_euler('xy', [30, 0], degrees=True)
    lx, ly, lz, lw = left_pose.as_quat()
    left_quat = [float(lw), float(lx), float(ly), float(lz)]
    right_quat = [1.0, 0.0, 0.0, 0.0]

    angles = kinematics.estimate_hip_angles(
        [1.0, 0.0, 0.0, 0.0], left_quat, right_quat, identity_calibration
    )
    assert angles["left_flexion_deg"] == pytest.approx(30.0, abs=0.5)
    assert angles["right_flexion_deg"] == pytest.approx(0.0, abs=0.5)


# ---------------------------------------------------------------------------
# 4. Safe zone: inside / outside
# ---------------------------------------------------------------------------

def test_safe_zone_inside(patient_profile):
    result = safe_zone.check_hip_safe_zone(100, 45, patient_profile["left_hip"])
    assert result["inside"] is True
    assert result["deviation_deg"] == 0.0


def test_safe_zone_outside(patient_profile):
    result = safe_zone.check_hip_safe_zone(130, 45, patient_profile["left_hip"])
    assert result["inside"] is False
    assert result["deviation_deg"] > 0.0


# ---------------------------------------------------------------------------
# 5. Confidence: missing data / low confidence
# ---------------------------------------------------------------------------

def test_missing_quaternion_flags_low_confidence():
    result = confidence.assess_confidence(current_quaternion=None)
    assert result["confidence"] == 0.0
    assert result["quality_status"] == "low"
    assert result["reason"] == "missing_data"


def test_low_confidence_data_reason_present():
    prev = [1.0, 0.0, 0.0, 0.0]
    pose = R.from_euler('xy', [179, 89], degrees=True)
    x, y, z, w = pose.as_quat()
    jump_quat = [float(w), float(x), float(y), float(z)]

    result = confidence.assess_confidence(jump_quat, prev, dt_seconds=0.15)
    assert result["confidence"] < 0.75  # below patient profile's minimum_confidence
    assert "sudden_orientation_jump" in result["reason"]


# ---------------------------------------------------------------------------
# 6. Full-scenario integration tests (one per EXPECTED_RESULTS row)
# ---------------------------------------------------------------------------

def test_normal_scenario_no_alert(patient_profile, identity_calibration):
    records = scenarios.normal_movement()
    statuses, _ = run_scenario(records, patient_profile, identity_calibration)
    assert all(s == "normal" for s in statuses["left"])
    assert all(s == "normal" for s in statuses["right"])


def test_brief_left_excursion_logged_not_sustained(patient_profile, identity_calibration):
    records = scenarios.brief_left_excursion()
    statuses, state = run_scenario(records, patient_profile, identity_calibration)

    assert "brief_excursion" in statuses["left"]
    assert "sustained_excursion" not in statuses["left"]
    assert all(s == "normal" for s in statuses["right"])
    assert len(state["left_hip"]["event_history"]) == 1


def test_brief_right_excursion_logged_not_sustained(patient_profile, identity_calibration):
    records = scenarios.brief_right_excursion()
    statuses, _ = run_scenario(records, patient_profile, identity_calibration)

    assert "brief_excursion" in statuses["right"]
    assert "sustained_excursion" not in statuses["right"]
    assert all(s == "normal" for s in statuses["left"])


def test_sustained_left_excursion_triggers_alert(patient_profile, identity_calibration):
    records = scenarios.sustained_left_excursion()
    statuses, _ = run_scenario(records, patient_profile, identity_calibration)

    assert "sustained_excursion" in statuses["left"]
    assert all(s == "normal" for s in statuses["right"])


def test_sustained_right_excursion_triggers_alert(patient_profile, identity_calibration):
    records = scenarios.sustained_right_excursion()
    statuses, _ = run_scenario(records, patient_profile, identity_calibration)

    assert "sustained_excursion" in statuses["right"]
    assert all(s == "normal" for s in statuses["left"])


def test_bilateral_excursion_triggers_both_sides(patient_profile, identity_calibration):
    records = scenarios.bilateral_excursion()
    statuses, _ = run_scenario(records, patient_profile, identity_calibration)

    assert "sustained_excursion" in statuses["left"]
    assert "sustained_excursion" in statuses["right"]


def test_repeated_excursions_flag_pattern(patient_profile, identity_calibration):
    records = scenarios.repeated_left_excursions()
    statuses, state = run_scenario(records, patient_profile, identity_calibration)

    assert "repeated_or_persistent_event" in statuses["left"]
    assert len(state["left_hip"]["event_history"]) >= 2


def test_missing_data_scenario_produces_quality_warning(patient_profile, identity_calibration):
    records = scenarios.missing_data()
    statuses, _ = run_scenario(records, patient_profile, identity_calibration)

    assert "data_quality_warning" in statuses["left"]
    assert "data_quality_warning" in statuses["right"]


def test_sudden_jump_scenario_produces_quality_warning(patient_profile, identity_calibration):
    records = scenarios.sudden_unrealistic_jump()
    statuses, _ = run_scenario(records, patient_profile, identity_calibration)

    assert "data_quality_warning" in statuses["left"]


def test_noisy_data_scenario_produces_quality_warning(patient_profile, identity_calibration):
    records = scenarios.noisy_data()
    statuses, _ = run_scenario(records, patient_profile, identity_calibration)

    assert "data_quality_warning" in statuses["left"]
    assert "data_quality_warning" in statuses["right"]


# ---------------------------------------------------------------------------
# 7. Patient profile changes affect safe-zone results
# ---------------------------------------------------------------------------

def test_profile_change_affects_zone_result(patient_profile):
    flexion, abduction = 115, 45

    original_result = safe_zone.check_hip_safe_zone(
        flexion, abduction, patient_profile["left_hip"]
    )
    assert original_result["inside"] is False

    widened_profile = dict(patient_profile["left_hip"])
    widened_profile["flexion_max"] = 120

    widened_result = safe_zone.check_hip_safe_zone(
        flexion, abduction, widened_profile
    )
    assert widened_result["inside"] is True
