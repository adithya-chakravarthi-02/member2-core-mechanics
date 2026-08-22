# Data Contract — Pavlik Harness Monitoring Prototype

This document defines the fixed input/output data format used between the simulator,
the processing core (Member 2), and the dashboard (Member 3). These field names and
units must not change without agreement from all members.

---

## 1. Input Record Format

Each record represents one sample of simulated orientation data.

```python
{
    "timestamp": 0.0,
    "pelvis_quaternion": [1.0, 0.0, 0.0, 0.0],
    "left_thigh_quaternion": [1.0, 0.0, 0.0, 0.0],
    "right_thigh_quaternion": [1.0, 0.0, 0.0, 0.0]
}
```

### Field Descriptions

| Field | Type | Description |
|---|---|---|
| `timestamp` | float | Time in seconds since the start of the session |
| `pelvis_quaternion` | list[float] (4) | Orientation of the pelvis reference frame |
| `left_thigh_quaternion` | list[float] (4) | Orientation of the left thigh reference frame |
| `right_thigh_quaternion` | list[float] (4) | Orientation of the right thigh reference frame |

---

## 2. Units and Conventions

| Quantity | Unit / Format |
|---|---|
| Time | Seconds |
| Angles (flexion, abduction) | Degrees |
| Quaternion order | `[w, x, y, z]` |
| Confidence | Range 0.0 to 1.0 |
| Sampling interval | Approximately 0.1 seconds (100–250 ms per record) |

**Important:** Quaternion order is `[w, x, y, z]`. This must be respected exactly
when converting to/from `scipy.spatial.transform.Rotation`, since scipy expects
`[x, y, z, w]` by default — a conversion step is required internally.

---

## 3. Scope and Limitations

- This system is a **software research prototype only**.
- It does **not** diagnose Developmental Dysplasia of the Hip (DDH).
- It does **not** confirm hip reduction.
- It does **not** replace ultrasound or clinical imaging.
- It does **not** recommend treatment changes.
- All orientation data is **simulated**, not collected from real sensors or patients.
- The model estimates **external pelvis–thigh orientation**, not direct anatomical
  femoral-head position.

---

## 4. Field Naming Rule

Once this schema is agreed upon with Member 3, field names must **not** be changed.
Any required changes must be communicated to all members before implementation.

---

## 5. Change Log

| Version | Date | Change |
|---|---|---|
| 1.0 | — | Initial schema freeze |
