"""
schema.py
Data schema definitions and the final integration function for Member 3.

This file is the single entry point for the dashboard. Member 3 should
only ever need to import process_record() from this file - everything
else (calibration, kinematics, safe zones, alerts, confidence) happens
internally.

See docs/data_contract.md for the full field/unit documentation.

LIMITATION:
This is a software research prototype only. It does not diagnose DDH,
confirm hip reduction, replace ultrasound, or recommend treatment changes.
"""

from core import calibration as calibration_module
from core import kinematics
from core import safe_zone
from core import confidence as confidence_module
from core import alert_engine


# ---------------------------------------------------------------------------
# Frozen input schema (do not rename these fields without agreement from
# Member 3 - see docs/data_contract.md)
# ---------------------------------------------------------------------------

RECORD_FIELDS = (
    "timestamp",
    "pelvis_quaternion",
    "left_thigh_quaternion",
    "right_thigh_quaternion",
)

QUATERNION_ORDER = ("w", "x", "y", "z")


def validate_record(raw_record):
    """
    Basic structural check that a raw record has the expected fields.
    Does NOT check quaternion validity (missing/None quaternions are a
    legitimate, expected case handled downstream by confidence.py).

    Raises
    ------
    ValueError if a required field is absent from the record.
    """
    missing_fields = [f for f in RECORD_FIELDS if f not in raw_record]
    if missing_fields:
        raise ValueError(f"Record is missing required field(s): {missing_fields}")


# ---------------------------------------------------------------------------
# Internal helpers for process_record()
# ---------------------------------------------------------------------------

def _ensure_quaternion_history(alert_state):
    """
    process_record() needs to remember the previous quaternion and a short
    rolling window per hip, for confidence.py's jump/noise detection.
    alert_engine.py's state dict doesn't include this by default, so we
    lazily attach it here on first use without modifying alert_engine.py.
    """
    for side in ("left", "right"):
        hip_state = alert_state[f"{side}_hip"]
        if "_previous_quaternion" not in hip_state:
            hip_state["_previous_quaternion"] = None
        if "_recent_quaternions" not in hip_state:
            hip_state["_recent_quaternions"] = []


def _fallback_quaternion(current, previous):
    """
    If this sample's quaternion is missing, fall back to the last known
    valid quaternion so kinematics.py still has something to compute with.
    (The missing sample itself is still correctly flagged by confidence.py
    and will suppress the alert via DATA_QUALITY_WARNING regardless.)
    """
    return current if current is not None else previous


# ---------------------------------------------------------------------------
# The one function Member 3 calls
# ---------------------------------------------------------------------------

def process_record(raw_record, patient_profile, calibration_parameters, alert_state):
    """
    Process a single incoming record through the full pipeline:
    confidence check -> angle estimation -> safe-zone check -> alert logic.

    This is the ONLY function the dashboard (Member 3) should call.
    It returns a stable, documented output shape - Member 3 should only
    display these values, never recompute angles or alert status.

    Parameters
    ----------
    raw_record : dict
        One record following the frozen input schema:
        {"timestamp", "pelvis_quaternion",
         "left_thigh_quaternion", "right_thigh_quaternion"}
    patient_profile : dict
        The patient profile JSON (see data/profiles/sample_patient.json).
    calibration_parameters : dict
        Output of calibration.calibrate(), containing "left_hip" and
        "right_hip" offset quaternions.
    alert_state : dict
        Persistent state dict, created once via alert_engine.init_alert_state()
        at the start of a session, then passed into process_record() on
        every subsequent call. This function mutates it in place.

    Returns
    -------
    dict
        {
            "timestamp": float,

            "left_flexion_deg": float or None,
            "left_abduction_deg": float or None,
            "right_flexion_deg": float or None,
            "right_abduction_deg": float or None,

            "left_confidence": float,
            "right_confidence": float,

            "left_zone_status": "inside" | "outside" | "unknown",
            "right_zone_status": "inside" | "outside" | "unknown",

            "left_alert_status": str,   # one of the 6 defined alert states
            "right_alert_status": str,

            "events": [
                {
                    "side": "left" | "right",
                    "duration_seconds": float,
                    "max_deviation": float,
                    "avg_deviation": float,
                },
                ...
            ]
        }
    """
    validate_record(raw_record)
    _ensure_quaternion_history(alert_state)

    timestamp = raw_record["timestamp"]
    pelvis_quat = raw_record["pelvis_quaternion"]

    output = {
        "timestamp": timestamp,
        "left_flexion_deg": None,
        "left_abduction_deg": None,
        "right_flexion_deg": None,
        "right_abduction_deg": None,
        "left_confidence": None,
        "right_confidence": None,
        "left_zone_status": "unknown",
        "right_zone_status": "unknown",
        "left_alert_status": None,
        "right_alert_status": None,
        "events": [],
    }

    angle_inputs = {}  # side -> quaternion to actually feed into kinematics

    for side in ("left", "right"):
        hip_state = alert_state[f"{side}_hip"]
        raw_quat = raw_record[f"{side}_thigh_quaternion"]
        previous_quat = hip_state["_previous_quaternion"]

        # ---- Confidence check (uses the RAW quaternion, missing or not) ----
        conf_result = confidence_module.assess_confidence(
            current_quaternion=raw_quat,
            previous_quaternion=previous_quat,
            dt_seconds=0.15,
            recent_quaternions=hip_state["_recent_quaternions"][-6:] or None,
        )
        output[f"{side}_confidence"] = conf_result["confidence"]

        # ---- Determine what quaternion to actually use for angle math ----
        effective_quat = _fallback_quaternion(raw_quat, previous_quat)
        angle_inputs[side] = effective_quat

        # ---- Update rolling history (only with genuinely valid samples) ----
        if raw_quat is not None:
            hip_state["_previous_quaternion"] = raw_quat
            hip_state["_recent_quaternions"].append(raw_quat)
            if len(hip_state["_recent_quaternions"]) > 10:
                hip_state["_recent_quaternions"].pop(0)

    # ---- Angle estimation (bilateral, single call) ----
    if angle_inputs["left"] is not None and angle_inputs["right"] is not None:
        angles = kinematics.estimate_hip_angles(
            pelvis_quat, angle_inputs["left"], angle_inputs["right"],
            calibration_parameters,
        )
        output["left_flexion_deg"] = angles["left_flexion_deg"]
        output["left_abduction_deg"] = angles["left_abduction_deg"]
        output["right_flexion_deg"] = angles["right_flexion_deg"]
        output["right_abduction_deg"] = angles["right_abduction_deg"]

    # ---- Safe-zone + alert logic, per hip ----
    for side in ("left", "right"):
        hip_state = alert_state[f"{side}_hip"]
        flexion = output[f"{side}_flexion_deg"]
        abduction = output[f"{side}_abduction_deg"]

        if flexion is not None and abduction is not None:
            zone_result = safe_zone.check_hip_safe_zone(
                flexion, abduction, patient_profile[f"{side}_hip"]
            )
            output[f"{side}_zone_status"] = "inside" if zone_result["inside"] else "outside"
        else:
            # No usable angle this frame (e.g. very first sample missing) -
            # feed a neutral placeholder; confidence already flags this
            # sample and alert_engine will report data_quality_warning.
            zone_result = {"inside": True, "deviation_deg": 0.0, "boundary_distance": 0.0}

        events_before = len(hip_state["event_history"])

        alert_result = alert_engine.process_hip_alert(
            side, timestamp, output[f"{side}_confidence"],
            zone_result, patient_profile, alert_state,
        )
        output[f"{side}_alert_status"] = alert_result["status"]

        # If a new event was completed on this call, surface it in "events"
        events_after = hip_state["event_history"]
        if len(events_after) > events_before:
            new_event = events_after[-1]
            output["events"].append({
                "side": side,
                "duration_seconds": new_event["duration_seconds"],
                "max_deviation": new_event["max_deviation"],
                "avg_deviation": new_event["avg_deviation"],
            })

    return output
