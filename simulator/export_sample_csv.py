"""
export_sample_csv.py
Runs the two scenarios and exports the records to CSV for Member 3.
Run this file directly: python simulator/export_sample_csv.py
"""

import csv
from scenarios import normal_movement, brief_left_excursion, EXPECTED_RESULTS

def flatten_record(record):
    return {
        "timestamp": record["timestamp"],
        "pelvis_w": record["pelvis_quaternion"][0],
        "pelvis_x": record["pelvis_quaternion"][1],
        "pelvis_y": record["pelvis_quaternion"][2],
        "pelvis_z": record["pelvis_quaternion"][3],
        "left_thigh_w": record["left_thigh_quaternion"][0],
        "left_thigh_x": record["left_thigh_quaternion"][1],
        "left_thigh_y": record["left_thigh_quaternion"][2],
        "left_thigh_z": record["left_thigh_quaternion"][3],
        "right_thigh_w": record["right_thigh_quaternion"][0],
        "right_thigh_x": record["right_thigh_quaternion"][1],
        "right_thigh_y": record["right_thigh_quaternion"][2],
        "right_thigh_z": record["right_thigh_quaternion"][3],
    }

def export_scenario(records, filename):
    rows = [flatten_record(r) for r in records]
    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Exported {len(rows)} records to {filename}")

if __name__ == "__main__":
    export_scenario(normal_movement(), "sample_normal_movement.csv")
    export_scenario(brief_left_excursion(), "sample_brief_left_excursion.csv")

    print("\nExpected results:")
    for name, result in EXPECTED_RESULTS.items():
        print(f"- {name}: {result}")
