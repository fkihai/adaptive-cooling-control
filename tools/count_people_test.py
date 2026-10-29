"""People-count accuracy test: asks Gemini to count the people in camera frames.

NEEDS THE USER'S EXPLICIT APPROVAL BEFORE EACH RUN. Every call uses Gemini quota and sends a
camera frame to Google. Frames are not saved by this script and it never opens them.

Usage:
    python tools/count_people_test.py --confirm-approved ROUNDS REAL_COUNT [camera ...]

Example (3 rounds, user says 4 people are present, one camera = 3 calls):
    python tools/count_people_test.py --confirm-approved 3 4 camera.2nd_floor

Between rounds it waits 25 seconds. It compares each answer with REAL_COUNT and prints a
summary. It only uses ai_task.google_ai_task, never the second-account fallback (see docs/working-rules.md).

Answers the package would not accept are marked and left out of the "accepted" figures:
  * LOW CONF   confidence below 70
  * REJECTED   count 0 while Frigate still reports the floor occupied (the package ignores these)
A Frigate sensor that is unavailable or unknown is shown as n/a and does not stop the run.
If Home Assistant is down (HTTP 502/503/504/530) the whole run stops at once.

Pass rule for one run: at least 2/3 of the answers are within 1 of the real count (the
package uses the higher of the last two counts, so a single wrong answer is absorbed).
"""
from __future__ import annotations

import json
import math
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

import ha_client

AI_TASK = "ai_task.google_ai_task"
FLOOR_SENSOR = "sensor.2nd_floor_person_count"
OCCUPANCY_SENSOR = "binary_sensor.2nd_floor_person_occupancy"
MIN_CONFIDENCE = 70
TOLERANCE = 1
PASS_FRACTION = 2 / 3
QUESTION = (
    "Count every person visible in this office camera image, including people seated at desks, "
    "partly hidden by furniture or far from the camera. Do not count reflections, posters or "
    "screens. Return the count, your confidence from 0 to 100, and one short sentence saying "
    "where the people are."
)
STRUCTURE = {
    "count": {"description": "Number of people visible", "required": True,
              "selector": {"number": {"min": 0, "max": 50}}},
    "confidence": {"description": "Confidence from 0 to 100", "required": True,
                   "selector": {"number": {"min": 0, "max": 100}}},
    "observation": {"description": "One short sentence", "required": True,
                    "selector": {"text": {}}},
}


def ask(camera: str) -> dict:
    body = json.dumps({
        "entity_id": AI_TASK,
        "task_name": "ac_count_test",
        "instructions": QUESTION,
        "structure": STRUCTURE,
        "attachments": [{"media_content_id": f"media-source://camera/{camera}",
                         "media_content_type": "image/jpeg"}],
    }).encode()
    request = urllib.request.Request(
        ha_client.BASE_URL + "/api/services/ai_task/generate_data?return_response",
        data=body, method="POST",
        headers={"Authorization": "Bearer " + ha_client._token(),
                 "User-Agent": ha_client.USER_AGENT, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = json.load(response)
    except urllib.error.HTTPError as err:
        if err.code in (502, 503, 504, 530):
            raise ha_client.HAUnreachable(f"HTTP {err.code}: Home Assistant looks down") from None
        raise
    except urllib.error.URLError as err:
        raise ha_client.HAUnreachable(f"connection error: {err.reason}") from None
    return data.get("service_response", data).get("data", data)


def frigate_reading() -> tuple[int | None, bool | None]:
    """Return (Frigate people count or None, floor occupied or None). None means n/a."""
    count: int | None = None
    occupied: bool | None = None
    try:
        raw = ha_client.state(FLOOR_SENSOR)["state"]
        if raw not in ("unavailable", "unknown", "none", ""):
            count = int(float(raw))
    except (ValueError, KeyError, TypeError):
        count = None
    except urllib.error.HTTPError:
        count = None
    try:
        raw = ha_client.state(OCCUPANCY_SENSOR)["state"]
        if raw in ("on", "off"):
            occupied = raw == "on"
    except (KeyError, TypeError, urllib.error.HTTPError):
        occupied = None
    return count, occupied


def classify(count: int, confidence: float, occupied: bool | None) -> str:
    """Return 'ok', 'low_conf' or 'rejected' using the package's acceptance rules."""
    if confidence < MIN_CONFIDENCE:
        return "low_conf"
    if count == 0 and occupied:
        return "rejected"
    return "ok"


def summarise(real: int, results: dict[str, list[tuple[int, str]]],
              frigate_counts: list[int | None], rounds: int) -> list[str]:
    lines = ["--- summary vs real count"]
    known = [abs(c - real) for c in frigate_counts if c is not None]
    lines.append(f"  frigate: {sum(known) / len(known):.2f} mean abs error over {len(known)} readings"
                 if known else "  frigate: n/a (sensor unavailable)")
    for camera, answers in results.items():
        if not answers:
            lines.append(f"  {camera}: no answers")
            continue
        errors = [abs(count - real) for count, _ in answers]
        accepted = [abs(count - real) for count, status in answers if status == "ok"]
        within = sum(1 for e in errors if e <= TOLERANCE)
        need = math.ceil(rounds * PASS_FRACTION)  # failed calls count against the camera
        lines.append(f"  {camera}: {len(answers)} answers of {rounds} rounds, "
                     f"mean abs error {sum(errors) / len(errors):.2f}"
                     f" | within {TOLERANCE} of real: {within}/{rounds}"
                     f" | accepted by package rules: {len(accepted)}/{rounds}")
        lines.append(f"    verdict: {'PASS' if within >= need else 'FAIL'}"
                     f" (needs {need}/{rounds} within {TOLERANCE}; a failed call counts as a miss)")
    return lines


def main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[0] != "--confirm-approved":
        print(__doc__)
        return 1
    rounds, real = int(argv[1]), int(argv[2])
    cameras = argv[3:] or ["camera.2nd_floor"]
    zone = ZoneInfo("Asia/Jakarta")
    results: dict[str, list[tuple[int, str]]] = {c: [] for c in cameras}
    frigate_counts: list[int | None] = []
    try:
        for n in range(1, rounds + 1):
            frigate, occupied = frigate_reading()
            frigate_counts.append(frigate)
            shown = "n/a" if frigate is None else frigate
            print(f"--- round {n} {datetime.now(zone):%H:%M:%S} WIB | real={real} frigate={shown}")
            for camera in cameras:
                started = time.time()
                try:
                    answer = ask(camera)
                    count = int(answer["count"])
                    confidence = float(answer.get("confidence", 0))
                    status = classify(count, confidence, occupied)
                    results[camera].append((count, status))
                    flag = {"ok": "", "low_conf": "  [LOW CONF]",
                            "rejected": "  [REJECTED: 0 while Frigate sees the floor occupied]"}[status]
                    print(f"  {camera}: count={count} confidence={answer.get('confidence')} "
                          f"({time.time() - started:.1f}s) {answer.get('observation', '')}{flag}")
                except ha_client.HAUnreachable:
                    raise  # HA is down: stop the whole run
                except Exception as err:  # keep going; report the failure
                    print(f"  {camera}: ERROR {type(err).__name__}: {str(err)[:160]}")
            if n < rounds:
                time.sleep(25)
    except ha_client.HAUnreachable as err:
        print("UNREACHABLE:", err)
        print("Stopped. Do not retry in a loop; wait for the server.")
        return 2
    print("\n".join(summarise(real, results, frigate_counts, rounds)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
