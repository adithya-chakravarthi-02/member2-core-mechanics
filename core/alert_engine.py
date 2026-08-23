"""
alert_engine.py
State-based alert logic for the Pavlik-harness monitoring prototype.

States:
    NORMAL
    OUTSIDE_ZONE
    BRIEF_EXCURSION
    SUSTAINED_EXCURSION
    REPEATED_OR_PERSISTENT_EVENT
    DATA_QUALITY_WARNING

Priority order (checked top to bottom, first match wins):
    1. If confidence is low            -> DATA_QUALITY_WARNING
    2. Else if inside safe zone        -> NORMAL
    3. Else if outside < brief limit   -> BRIEF_EXCURSION (or OUTSIDE_ZONE if
                                           still ramping up, see note below)
    4. Else if outside >= sustained    -> SUSTAINED_EXCURSION
    5. Else if repeated/severe pattern -> REPEATED_OR_PERSISTENT_EVENT

This module tracks state PER HIP (left and right run independently) using
an `alert_state` dict that the caller keeps and passes back in on every
call, since this system processes one record at a time in real time.

LIMITATION:
This is a software research prototype only. It does not diagnose DDH,
confirm hip reduction, replace ultrasound, or recommend treatment changes.
"""


def _new_hip_state():
    """Initial empty alert-tracking state for one hip."""
    return {
        "status": "normal",
        "excursion_start_time": None,
        "excursion_max_deviation": 0.0,
        "excursion_deviation_sum": 0.0,
        "excursion_sample_count": 0,
        "event_history": [],   # list of completed event dicts
    }


def init_alert_state():
    """
    Create a fresh alert_state dict for a new session, covering both hips.
    Pass this into process_hip_alert() on the first call, then keep
    reusing the returned state on every subsequent call.
    """
    return {
        "left_hip": _new_hip_state(),
        "right_hip": _new_hip_state(),
    }


def _close_excursion(hip_state, timestamp, patient_profile):
    """
    Called when a hip returns to normal after being outside the zone.
    Logs the completed event into event_history and resets excursion
    tracking fields.
    """
    if hip_state["excursion_start_time"] is not None:
        duration = timestamp - hip_state["excursion_start_time"]
        avg_deviation = (
            hip_state["excursion_deviation_sum"] / hip_state["excursion_sample_count"]
            if hip_state["excursion_sample_count"] > 0 else 0.0
        )
        hip_state["event_history"].append({
            "start_time": hip_state["excursion_start_time"],
            "end_time": timestamp,
            "duration_seconds": duration,
            "max_deviation": hip_state["excursion_max_deviation"],
            "avg_deviation": avg_deviation,
        })

    hip_state["excursion_start_time"] = None
    hip_state["excursion_max_deviation"] = 0.0
    hip_state["excursion_deviation_sum"] = 0.0
    hip_state["excursion_sample_count"] = 0


def _count_recent_events(event_history, timestamp, window_seconds):
    """Count how many completed events ended within the repeated-event window."""
    return sum(
        1 for event in event_history
        if (timestamp - event["end_time"]) <= window_seconds
    )


def process_hip_alert(side, timestamp, confidence, zone_result,
                       patient_profile, alert_state):
    """
    Run the alert state machine for a single hip (left or right) for one
    incoming record. Mutates and returns the shared alert_state dict.

    Parameters
    ----------
    side : str
        "left" or "right" - selects which hip's state to update.
    timestamp : float
        Current record's timestamp in seconds.
    confidence : float
        Confidence score (0-1) for this hip's reading, from confidence.py.
    zone_result : dict
        Output of safe_zone.check_hip_safe_zone() for this hip:
        {"inside": bool, "deviation_deg": float, "boundary_distance": float}
    patient_profile : dict
        The patient profile JSON, containing brief_event_limit_seconds,
        sustained_event_limit_seconds, repeated_event_window_seconds,
        and minimum_confidence.
    alert_state : dict
        The shared state dict returned by init_alert_state() (or a prior
        call to this function). Must contain "left_hip" and "right_hip".

    Returns
    -------
    dict
        {
            "status": str,           # one of the 6 defined states
            "side": str,
            "duration_seconds": float,
            "deviation": float,
            "severity": str,         # "none" | "low" | "medium" | "high"
            "message": str,
        }
    """
    hip_key = f"{side}_hip"
    hip_state = alert_state[hip_key]

    min_confidence = patient_profile["minimum_confidence"]
    brief_limit = patient_profile["brief_event_limit_seconds"]
    sustained_limit = patient_profile["sustained_event_limit_seconds"]
    repeated_window = patient_profile["repeated_event_window_seconds"]

    # ---- Priority 1: low confidence overrides everything else ----
    if confidence < min_confidence:
        hip_state["status"] = "data_quality_warning"
        return {
            "status": "data_quality_warning",
            "side": side,
            "duration_seconds": 0.0,
            "deviation": zone_result.get("deviation_deg", 0.0),
            "severity": "none",
            "message": "Low-confidence data; alert suppressed pending reliable signal.",
        }

    # ---- Priority 2: inside safe zone ----
    if zone_result["inside"]:
        was_in_excursion = hip_state["excursion_start_time"] is not None
        if was_in_excursion:
            _close_excursion(hip_state, timestamp, patient_profile)
        hip_state["status"] = "normal"
        return {
            "status": "normal",
            "side": side,
            "duration_seconds": 0.0,
            "deviation": 0.0,
            "severity": "none",
            "message": "Within safe zone.",
        }

    # ---- Outside the zone: track / start excursion timing ----
    deviation = zone_result["deviation_deg"]

    if hip_state["excursion_start_time"] is None:
        hip_state["excursion_start_time"] = timestamp

    hip_state["excursion_max_deviation"] = max(
        hip_state["excursion_max_deviation"], deviation
    )
    hip_state["excursion_deviation_sum"] += deviation
    hip_state["excursion_sample_count"] += 1

    duration = timestamp - hip_state["excursion_start_time"]

    # ---- Priority 5: repeated/persistent pattern check ----
    # Count prior completed events within the repeated-event window, plus
    # this ongoing excursion counts as one more if it becomes sustained.
    recent_event_count = _count_recent_events(
        hip_state["event_history"], timestamp, repeated_window
    )

    if recent_event_count >= 2 and duration < sustained_limit:
        # Multiple prior brief events already happened recently, and now
        # another excursion is happening -> escalate to repeated/persistent,
        # even though this individual excursion hasn't hit "sustained" yet.
        hip_state["status"] = "repeated_or_persistent_event"
        return {
            "status": "repeated_or_persistent_event",
            "side": side,
            "duration_seconds": duration,
            "deviation": deviation,
            "severity": "high",
            "message": (
                f"Repeated excursions detected: {recent_event_count} prior "
                f"events within the last {repeated_window}s window."
            ),
        }

    # ---- Priority 4: sustained excursion ----
    if duration >= sustained_limit:
        hip_state["status"] = "sustained_excursion"
        return {
            "status": "sustained_excursion",
            "side": side,
            "duration_seconds": duration,
            "deviation": deviation,
            "severity": "medium" if duration < sustained_limit * 2 else "high",
            "message": "Sustained out-of-zone event.",
        }

    # ---- Priority 3: brief excursion (still under brief limit) ----
    if duration < brief_limit:
        hip_state["status"] = "brief_excursion"
        return {
            "status": "brief_excursion",
            "side": side,
            "duration_seconds": duration,
            "deviation": deviation,
            "severity": "low",
            "message": "Brief out-of-zone movement; logged, no alert.",
        }

    # ---- In between brief and sustained limits ----
    hip_state["status"] = "outside_zone"
    return {
        "status": "outside_zone",
        "side": side,
        "duration_seconds": duration,
        "deviation": deviation,
        "severity": "low",
        "message": "Outside safe zone; monitoring duration.",
    }
