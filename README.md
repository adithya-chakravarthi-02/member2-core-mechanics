# member2-core-mechanics

This is the **processing and decision-making core** for the Pavlik-harness
monitoring software prototype. It was built by Member 2 (Python Processing
and Decision-Core Lead). This README is written for **Member 3**, so you
can wire this into the Streamlit dashboard without needing to reverse-
engineer anything.

> ⚠️ **Important:** This is a **software research prototype only**. It does
> NOT diagnose Developmental Dysplasia of the Hip (DDH), confirm hip
> reduction, replace ultrasound, or recommend treatment changes. All data
> is simulated, not from real patients or real sensors.

---

## Table of Contents

1. What this module does, in plain terms
2. Folder structure — what lives where
3. The one function you need: `process_record()`
4. What goes IN — the raw record format
5. What comes OUT — the result you'll display
6. A full minimal working example
7. Trying it with realistic fake data (before real sensors exist)
8. The patient profile — what's configurable
9. Running the tests yourself
10. Rules of the integration (please respect these)
11. Questions?
12. **Appendix — full internal function reference** (you don't need this to
    integrate; it's here so nothing is a black box if you're curious or
    need to debug something)

---

## 1. What this module does, in plain terms

Imagine a patient wearing a Pavlik harness with sensors on their pelvis and
both thighs. Every ~0.1 seconds, those sensors report their orientation
(as quaternions — explained below). This module:

1. Takes that raw orientation data
2. Works out how bent (**flexion**) and how spread apart (**abduction**)
   each hip currently is, in degrees
3. Checks whether those angles are inside the "safe zone" set for that
   specific patient
4. Decides whether anything needs an alert — and if so, how serious
   (a quick 1-second wobble is very different from being out of position
   for 10 seconds straight)
5. Also checks whether the sensor data itself looks trustworthy (missing
   packets, sudden impossible jumps, noisy readings) — and if it doesn't,
   it says so instead of raising a false alarm

**You (Member 3) don't need to do any of that math yourself.** You just
call one function, and it hands you a clean, ready-to-display result.

---

## 2. Folder structure — what lives where

```
core/
├── __init__.py         (empty — makes this folder importable)
├── schema.py            <- YOU ONLY NEED THIS ONE. Contains process_record()
├── calibration.py        internal - calibration math
├── kinematics.py         internal - angle calculation math
├── safe_zone.py          internal - safe zone checking math
├── alert_engine.py       internal - alert state machine
└── confidence.py         internal - data quality checking

simulator/
├── __init__.py
├── scenarios.py          10 pre-built fake data scenarios for testing
├── stream_generator.py   turns a scenario into a live-feeling stream
└── export_sample_csv.py  exports scenario data to CSV

data/
└── profiles/
    └── sample_patient.json   example patient profile (safe zone limits etc.)

tests/
└── test_core.py          21 automated tests proving everything works

docs/
├── data_contract.md                        full input format spec
└── sample_outputs/
    └── process_record_sample.json          example of what you'll receive
```

**You will realistically only ever need to import from `core/schema.py`.**
Everything else is internal machinery you don't need to touch — but it's
all explained in the Appendix (Section 12) if you're curious.

---

## 3. The one function you need: `process_record()`

This is the entire interface. One function call per incoming data record.

```python
from core import calibration, alert_engine, schema
```

### Step A — Do this ONCE, when a monitoring session starts

```python
# 1. Load the patient's profile (their specific safe-zone limits)
import json
with open("data/profiles/sample_patient.json") as f:
    patient_profile = json.load(f)

# 2. Calibrate — this needs one "reference pose" snapshot, usually taken
#    when the patient is resting still at the very start of the session
calibration_parameters = calibration.calibrate(
    pelvis_reference=[1.0, 0.0, 0.0, 0.0],       # example: identity/resting pose
    left_thigh_reference=[1.0, 0.0, 0.0, 0.0],
    right_thigh_reference=[1.0, 0.0, 0.0, 0.0],
)

# 3. Create the alert state — this is memory that tracks excursions,
#    events, and confidence history across the whole session
alert_state = alert_engine.init_alert_state()
```

**Do NOT recreate `alert_state` or `calibration_parameters` on every
record.** They need to persist across the whole session — create them
once, then keep reusing the same objects.

### Step B — Do this for EVERY incoming record

```python
output = schema.process_record(
    raw_record,              # one record: timestamp + 3 quaternions
    patient_profile,         # loaded once in Step A
    calibration_parameters,  # created once in Step A
    alert_state,              # created once in Step A, reused every time
)
```

That's it. `output` now contains everything your dashboard needs to
display — angles, confidence, zone status, alert status, and any newly
completed events.

---

## 4. What goes IN — the raw record format

Every record you feed into `process_record()` must look exactly like this:

```python
{
    "timestamp": 12.4,
    "pelvis_quaternion": [1.0, 0.0, 0.0, 0.0],
    "left_thigh_quaternion": [0.98, 0.1, 0.05, -0.02],
    "right_thigh_quaternion": [0.97, 0.11, 0.04, -0.03]
}
```

| Field | Meaning |
|---|---|
| `timestamp` | Time in seconds since the session started |
| `pelvis_quaternion` | Orientation of the pelvis sensor |
| `left_thigh_quaternion` | Orientation of the left thigh sensor |
| `right_thigh_quaternion` | Orientation of the right thigh sensor |

**Quaternion order is `[w, x, y, z]`** — this is important, it's NOT the
scipy default order. Don't rearrange these numbers.

Any thigh quaternion can also be `None` (this simulates a dropped sensor
packet) — `process_record()` handles this gracefully and will flag it as
a data-quality issue automatically. You don't need to filter these out
yourself.

Full details: see `docs/data_contract.md`.

---

## 5. What comes OUT — the result you'll display

```python
{
    "timestamp": 12.4,

    "left_flexion_deg": 98.2,
    "left_abduction_deg": 42.7,
    "right_flexion_deg": 101.4,
    "right_abduction_deg": 48.0,

    "left_confidence": 0.94,
    "right_confidence": 0.91,

    "left_zone_status": "inside",
    "right_zone_status": "inside",

    "left_alert_status": "normal",
    "right_alert_status": "normal",

    "events": []
}
```

### Field-by-field explanation

| Field | Type | What it means |
|---|---|---|
| `timestamp` | float | Same timestamp you sent in |
| `left/right_flexion_deg` | float or `None` | How bent that hip is, in degrees. `None` only if data was unusable |
| `left/right_abduction_deg` | float or `None` | How spread apart that hip is, in degrees |
| `left/right_confidence` | float 0–1 | How trustworthy this reading is. Below the patient's `minimum_confidence` threshold, alerts get suppressed automatically |
| `left/right_zone_status` | `"inside"` / `"outside"` / `"unknown"` | Whether that hip is within its safe-zone limits |
| `left/right_alert_status` | string | See the 6 possible values below |
| `events` | list | Any excursion that just **completed** on this exact call (usually empty — only populates the moment a hip returns to normal after being out of zone) |

### The 6 possible alert statuses

| Status | What it means for your UI |
|---|---|
| `"normal"` | Everything's fine. Green / no alert. |
| `"outside_zone"` | Just left the safe zone, still figuring out how long it'll last. Low-key warning. |
| `"brief_excursion"` | Was outside briefly (under the patient's brief-event limit), then came back. Log it, don't alarm. |
| `"sustained_excursion"` | Been outside the zone for longer than the sustained limit. **This should show a real alert.** |
| `"repeated_or_persistent_event"` | Multiple excursions have happened close together in time. **This should show a real alert.** |
| `"data_quality_warning"` | The sensor data itself is unreliable right now (missing, noisy, or jumped impossibly). **Show this as a data-quality notice, NOT a movement alert** — the hip might actually be totally fine, we just can't trust the reading. |

**Display tip:** Treat `data_quality_warning` very differently from the
movement-related alerts. It's not telling you "the hip moved badly" — it's
telling you "we're not sure what's happening right now, ignore this
reading."

### What's inside an `events` entry

```python
{
    "side": "left",
    "duration_seconds": 9.4,
    "max_deviation": 12.3,
    "avg_deviation": 8.7
}
```

This appears in the `events` list only on the exact record where an
excursion just ended (hip returned to "normal"). Use this to build your
event history table — append each one you see to a running log.

---

## 6. A full minimal working example

```python
import json
from core import calibration, alert_engine, schema

# --- Setup (once per session) ---
with open("data/profiles/sample_patient.json") as f:
    patient_profile = json.load(f)

calib = calibration.calibrate(
    pelvis_reference=[1.0, 0.0, 0.0, 0.0],
    left_thigh_reference=[1.0, 0.0, 0.0, 0.0],
    right_thigh_reference=[1.0, 0.0, 0.0, 0.0],
)

alert_state = alert_engine.init_alert_state()

# --- Simulate receiving 3 records ---
records = [
    {"timestamp": 0.0, "pelvis_quaternion": [1.0,0,0,0],
     "left_thigh_quaternion": [1.0,0,0,0], "right_thigh_quaternion": [1.0,0,0,0]},
    {"timestamp": 0.15, "pelvis_quaternion": [1.0,0,0,0],
     "left_thigh_quaternion": [1.0,0,0,0], "right_thigh_quaternion": [1.0,0,0,0]},
    {"timestamp": 0.30, "pelvis_quaternion": [1.0,0,0,0],
     "left_thigh_quaternion": [1.0,0,0,0], "right_thigh_quaternion": [1.0,0,0,0]},
]

for record in records:
    result = schema.process_record(record, patient_profile, calib, alert_state)
    print(result["left_alert_status"], result["left_flexion_deg"])
```

---

## 7. Trying it with realistic fake data (before real sensors exist)

You don't need to wait for real sensor data to build your dashboard.
Use the simulator:

```python
from simulator import scenarios

records = scenarios.normal_movement()          # calm, everything fine
records = scenarios.sustained_left_excursion()  # left hip alert-worthy
records = scenarios.repeated_left_excursions()  # repeated pattern
records = scenarios.missing_data()              # dropped sensor packets
records = scenarios.noisy_data()                # unreliable readings
# ...10 total scenarios available, see simulator/scenarios.py
```

Each one returns a list of records in the exact format described in
Section 4 — feed them straight into `process_record()` in a loop, exactly
like the example above, to test your dashboard against every situation
before real data exists.

For a live-feeling stream (records arriving with realistic timing delays
instead of all at once):

```python
from simulator.stream_generator import stream_records

for record in stream_records(records):
    result = schema.process_record(record, patient_profile, calib, alert_state)
    # update your dashboard here
```

`stream_records()` yields one record at a time, sleeping a randomized
100–250ms between each — it simulates what a real live sensor feed would
feel like. There's also `collect_stream()` in the same file, which returns
everything instantly with no delay (useful for automated testing where you
don't want to wait).

### All 10 scenario functions

| Function | What it simulates |
|---|---|
| `normal_movement()` | Both hips stay comfortably in the safe zone |
| `brief_left_excursion()` | Left hip briefly out of zone (~1.5s), then back — no real alert |
| `brief_right_excursion()` | Same, but on the right hip |
| `sustained_left_excursion()` | Left hip out of zone for 10s — triggers a real sustained alert |
| `sustained_right_excursion()` | Same, but on the right hip |
| `bilateral_excursion()` | Both hips out of zone at the same time |
| `repeated_left_excursions()` | Left hip has 4 short excursions spaced 10s apart — triggers the repeated-pattern alert |
| `noisy_data()` | Both hips technically fine, but sensor readings are jittery — triggers a data-quality warning |
| `missing_data()` | Sensor packets drop out for 1 second — triggers a data-quality warning |
| `sudden_unrealistic_jump()` | One single impossible orientation spike — triggers a brief data-quality warning |

---

## 8. The patient profile — what's configurable

`data/profiles/sample_patient.json` contains the safe-zone thresholds.
These are **demo values only, not real clinical limits**:

```json
{
  "left_hip": {"flexion_min": 90, "flexion_max": 110, "abduction_min": 30, "abduction_max": 60},
  "right_hip": {"flexion_min": 90, "flexion_max": 110, "abduction_min": 30, "abduction_max": 60},
  "brief_event_limit_seconds": 3,
  "sustained_event_limit_seconds": 8,
  "repeated_event_window_seconds": 300,
  "minimum_confidence": 0.75
}
```

If your dashboard has a "patient selector" or "treatment stage selector,"
you can load a different profile JSON (following this same shape) and
pass that into `process_record()` instead. Everything downstream — safe
zones, alert timing, confidence threshold — will automatically respect
the new profile.

---

## 9. Running the tests yourself

If you want to confirm the core works before wiring it in:

```cmd
pip install scipy numpy pytest --break-system-packages
pytest tests/test_core.py -v
```

You should see `21 passed`. If anything fails, that's a bug in the core
(Member 2's responsibility to fix), not something in your dashboard code.

---

## 10. Rules of the integration (please respect these)

- ✅ **Do** call `process_record()` for every incoming record
- ✅ **Do** create `alert_state` and `calibration_parameters` once per
  session, then reuse them
- ✅ **Do** display exactly what `process_record()` returns
- ❌ **Don't** recalculate angles, zone status, or alerts yourself in the
  dashboard — this duplicates logic and risks the two systems disagreeing
- ❌ **Don't** rename any of the output field names in your own code in a
  way that hides the original meaning — keep it traceable back to this
  contract
- ❌ **Don't** create a new `alert_state` per record — you'll lose all
  excursion timing and event history if you do

---

## 11. Questions?

If any output doesn't make sense, or a scenario behaves unexpectedly,
ping Member 2 directly rather than guessing — the internal math has some
genuine geometric limitations that are documented in each file's
docstring (also summarized below in the Appendix), and it's faster to ask
than to reverse-engineer.

---

## 12. Appendix — full internal function reference

**You do not need any of this to build the dashboard.** `process_record()`
already calls everything below internally and hands you the combined
result. This section exists purely so nothing is hidden — read it if
you're curious, debugging something odd, or want to understand *why* a
number came out the way it did.

### 12.1 `core/calibration.py`

#### `calibrate(pelvis_reference, left_thigh_reference, right_thigh_reference)`

Takes three quaternions (a single "reference pose" snapshot, usually
captured while the patient is resting still at the start of a session)
and works out the rotational offset between the pelvis and each thigh at
that moment.

```python
calibration.calibrate(
    pelvis_reference=[1.0, 0.0, 0.0, 0.0],
    left_thigh_reference=[1.0, 0.0, 0.0, 0.0],
    right_thigh_reference=[1.0, 0.0, 0.0, 0.0],
)
# Returns:
{
    "left_hip": {"offset_quaternion": [1.0, 0.0, 0.0, 0.0]},
    "right_hip": {"offset_quaternion": [1.0, 0.0, 0.0, 0.0]},
    "note": "..."
}
```

This offset is later subtracted out by `kinematics.py`, so that the
calibration pose reads as "zero flexion, zero abduction" — everything
reported afterward is movement *relative to* that starting pose, not the
sensor's raw zero point.

**Limitation:** this estimates external pelvis-thigh sensor orientation
only. It does not represent true anatomical femoral-head position.

---

### 12.2 `core/kinematics.py`

#### `estimate_hip_angles(pelvis_quaternion, left_thigh_quaternion, right_thigh_quaternion, calibration_parameters)`

The core angle math. Takes the live quaternions plus the calibration
offsets from `calibrate()`, and returns both hips' current flexion and
abduction in degrees.

```python
kinematics.estimate_hip_angles(
    pelvis_quaternion, left_thigh_quaternion, right_thigh_quaternion,
    calibration_parameters,
)
# Returns:
{
    "left_flexion_deg": 98.2,
    "left_abduction_deg": 42.7,
    "right_flexion_deg": 101.4,
    "right_abduction_deg": 48.0,
}
```

**How it works internally:** computes the thigh's orientation relative to
the pelvis (`R_relative = R_pelvis⁻¹ × R_thigh`), removes the calibration
offset, then decomposes what's left into flexion (rotation about X) and
abduction (rotation about Y) using `scipy.spatial.transform.Rotation`.

**Known limitation (documented in the file):** flexion and abduction
rotations don't perfectly "add" and "subtract" independently — if
abduction changes while flexion is already non-zero, a small cross-axis
error (typically a few degrees) can appear. This is expected behavior of
how 3D rotations combine, not a bug, and has acceptable margin given the
safe-zone thresholds used.

---

### 12.3 `core/safe_zone.py`

#### `is_inside_rectangular_zone(flexion, abduction, flexion_min, flexion_max, abduction_min, abduction_max)`

Simple box check — is the point inside a min/max rectangle?

```python
safe_zone.is_inside_rectangular_zone(100, 45, 90, 110, 30, 60)
# Returns:
{"inside": True, "deviation_deg": 0.0, "boundary_distance": 10.0}
```
- `deviation_deg`: 0 if inside; otherwise how far outside, in degrees
- `boundary_distance`: how much "room to spare" if inside (positive), or
  negative if outside

#### `is_inside_polygon_zone(flexion, abduction, polygon_points)`

Same idea, but the safe zone is a custom-shaped polygon instead of a
rectangle (X = flexion, Y = abduction). Useful later if the safe zone
needs to be a more realistic non-rectangular shape.

#### `check_hip_safe_zone(flexion, abduction, hip_profile, zone_type="rectangular")`

A convenience wrapper around the two functions above — this is the one
`process_record()` actually calls. Picks rectangular or polygon logic
based on `zone_type`, and reads limits straight from a hip's profile dict.

---

### 12.4 `core/confidence.py`

#### `assess_confidence(current_quaternion, previous_quaternion=None, dt_seconds=0.15, recent_quaternions=None)`

Looks at one hip's incoming quaternion and decides how much to trust it.

```python
confidence.assess_confidence(current_quaternion, previous_quaternion, dt_seconds=0.15)
# Returns:
{"confidence": 0.94, "quality_status": "high", "reason": "none"}
```

Checks performed, in order:
1. **Missing data** — if the quaternion is `None` or malformed, confidence
   drops to 0.0 immediately, reason = `"missing_data"`
2. **Sudden orientation jump** — if the angle changed impossibly fast
   between this sample and the last one (>500°/s), confidence drops
   heavily, reason = `"sudden_orientation_jump"`
3. **Unrealistic angular velocity** — a lesser version of the above
   (>250°/s but under the "impossible" threshold), a smaller penalty,
   reason = `"unrealistic_angular_velocity"`
4. **Excessive noise** — if you supply `recent_quaternions` (a short
   rolling window of the last few samples), it checks whether the average
   step-to-step jitter across that window is too high, indicating jittery
   / unreliable sensor readings, reason = `"excessive_noise"`

Multiple reasons can combine (joined with `+`, e.g.
`"sudden_orientation_jump+excessive_noise"`).

`quality_status` is just a simplified bucket: `"high"` (≥0.85),
`"medium"` (≥0.6), or `"low"` (below that).

**Where this connects to alerts:** `process_record()` feeds this
confidence score into `alert_engine.py`, which suppresses the normal
zone/duration alert logic whenever confidence drops below the patient
profile's `minimum_confidence` — that's what produces
`"data_quality_warning"` in the output you see.

---

### 12.5 `core/alert_engine.py`

#### `init_alert_state()`

Creates a fresh, empty tracking state for a new session — one sub-dict
for the left hip, one for the right. You call this once per session (see
Section 3, Step A).

#### `process_hip_alert(side, timestamp, confidence, zone_result, patient_profile, alert_state)`

The actual state machine. Runs for one hip, one record at a time. Decides
the alert status using this priority order (first match wins):

1. Confidence too low → `data_quality_warning`
2. Inside the safe zone → `normal`
3. Outside, but multiple recent events already happened nearby in time →
   `repeated_or_persistent_event`
4. Outside, and has been for longer than the sustained limit →
   `sustained_excursion`
5. Outside, but still under the brief limit → `brief_excursion`
6. Outside, in between the brief and sustained limits → `outside_zone`

It also tracks, per hip, a running `event_history` — every time a hip
returns to `normal` after being outside, a completed event (duration, max
deviation, average deviation) gets appended to that list. This is what
powers the `events` field you see in `process_record()`'s output.

#### `get_exposure_summary(hip_state)`

Not currently surfaced in `process_record()`'s output, but available if
your dashboard wants a cumulative severity picture for a hip over the
whole session:

```python
alert_engine.get_exposure_summary(alert_state["left_hip"])
# Returns:
{
    "event_count": 3,
    "total_duration_seconds": 6.0,
    "max_deviation": 10.0,
    "average_deviation": 10.0,
    "average_time_between_events": 8.0,
    "cumulative_exposure": 60.0,   # sum of (duration × deviation) per event
}
```

`cumulative_exposure` weights longer AND more severe excursions more
heavily — three brief mild taps produce a much lower score than three
long near-sustained excursions. Could be useful for an end-of-session
summary report or export.

---

### 12.6 `core/schema.py` (the file you actually use)

Besides `process_record()` itself (already covered in Section 3), this
file has two small internal helpers you likely won't need directly, but
are worth knowing about:

#### `validate_record(raw_record)`

Checks that an incoming record has all four required fields
(`timestamp`, `pelvis_quaternion`, `left_thigh_quaternion`,
`right_thigh_quaternion`). Raises `ValueError` if something's missing.
`process_record()` calls this automatically on every record — you don't
need to call it yourself.

#### `RECORD_FIELDS`

Just a tuple of the four required field names, kept as a single source of
truth so the schema can't silently drift.

---

That's everything. If you've read this far, you now know exactly as much
about this module as Member 2 does.
