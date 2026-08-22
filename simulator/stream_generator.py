"""
stream_generator.py
Turns a pre-built scenario (list of records) into a live, continuous stream,
emitting one record every ~100-250 ms, like a real-time sensor feed.
"""

import time
import random

def stream_records(records, min_interval_ms=100, max_interval_ms=250, speed_multiplier=1.0):
    """
    Generator that yields one record at a time, waiting a randomized
    interval between each to simulate real-time sensor delivery.

    speed_multiplier: >1.0 speeds up playback, <1.0 slows it down.
    Useful for the dashboard's speed control later.
    """
    for record in records:
        yield record
        delay_ms = random.uniform(min_interval_ms, max_interval_ms) / speed_multiplier
        time.sleep(delay_ms / 1000.0)


def collect_stream(records):
    """
    Non-blocking version: returns all records instantly (no sleep).
    Useful for tests and CSV export where waiting isn't needed.
    """
    return list(records)
