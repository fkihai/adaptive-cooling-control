"""Build LT1 packages from the proven LT2 configuration, without contacting HA.

    python tools/build_floor1_packages.py
"""

from pathlib import Path
import re

import yaml


PACKAGES = Path(__file__).resolve().parent.parent / "packages"
COUNT = "adaptive_cooling_lt1.yaml"
CONTROL = "adaptive_cooling_lt1_control.yaml"


def rename(value: str) -> str:
    for old, new in (
        ("ac_adaptive_count_people_lt2", "ac_adaptive_count_people_lt1"),
        ("ac_adaptive_count_lt2", "ac_adaptive_count_lt1"),
        ("ac_adaptive_count_enabled", "ac_adaptive_count_lt1_enabled"),
        ("ac_adaptive_hours", "ac_lt1_hours"),
        ("ac_lt2", "ac_lt1"), ("AC LT2", "AC LT1"),
        ("floor 2", "floor 1"), ("Lantai 2", "Lantai 1"),
        ("2nd_floor", "1st_floor"),
        ("climate.ac_sharp_lt_2_kiri", "climate.ac_lg_lt_1_kiri"),
        ("climate.ac_sharp_lt_2_tengah", "climate.ac_lg_lt_1_kiri"),
        ("climate.ac_lg_2_2", "climate.ac_lg_lt_1_kanan"),
        ("sensor.0x60b763fffe1e451c_power", "sensor.0x60b763fffe1e5fc6_power"),
        ("sensor.0x60b763fffe1f48ee_power", "sensor.0x60b763fffe1e5fc6_power"),
        ("sensor.0x60b763fffe1e67ae_power", "sensor.0x60b763fffe1e380d_power"),
        ("Sharp Kiri", "LG Kiri"), ("Sharp Tengah", "LG Kiri"),
    ):
        value = value.replace(old, new)
    # Multiline Jinja dictionaries: remove the middle entry, not the entire expression.
    value = "\n".join(line for line in value.split("\n") if "middle" not in line.lower())
    return value


def adapt(value):
    if isinstance(value, str):
        return rename(value)
    if isinstance(value, dict):
        return {rename(k) if isinstance(k, str) else k: adapt(v) for k, v in value.items()
                if not (isinstance(k, str) and "middle" in k.lower())}
    if isinstance(value, list):
        return [adapt(v) for v in value if not (
            isinstance(v, str) and "middle" in v.lower()
            or isinstance(v, dict) and (
                "middle" in str(v.get("id", "")).lower()
                or "middle" in str(v.get("name", "")).lower()
                or ("conditions" in v and "middle" in str(v["conditions"]).lower())
                or ("if" in v and "middle" in str(v["if"]).lower()))) ]
    return value


def generate() -> dict[str, dict]:
    count = adapt(yaml.safe_load((PACKAGES / "adaptive_cooling_lt2.yaml").read_text(encoding="utf-8")))
    control = adapt(yaml.safe_load((PACKAGES / "adaptive_cooling_lt2_control.yaml").read_text(encoding="utf-8")))
    settings = count["template"][1]["variables"]["ac_settings"]
    assert set(settings) == {"left", "right"}
    settings["left"].update(entity_id="climate.ac_lg_lt_1_kiri", min_temp=16)
    settings["right"].update(entity_id="climate.ac_lg_lt_1_kanan", min_temp=16,
                             fan=["high"] * 4)
    count["automation"][0]["triggers"][:1] = [
        {"trigger": "time_pattern", "minutes": minute}
        for minute in (5, 15, 25, 35, 45, 55)
    ]
    count["automation"][0]["variables"]["camera_entity"] = "camera.1st_floor"
    count["automation"][0]["variables"]["ai_task_entity"] = "ai_task.google_ai_task"

    for action in control["automation"]:
        if action["id"] == "ac_lt1_arm":
            action["alias"] = "AC floor 1 - arm the two units"
        if action["id"] == "ac_lt1_notify_setting_sent":
            for step in action["actions"]:
                if "variables" in step:
                    step["variables"]["ac_name"] = "{{ {'left': 'LG Kiri', 'right': 'LG Kanan'}[unit] }}"
        if action["id"] == "ac_lt1_daily_summary":
            action["actions"][0]["data"]["message"] = (
                "Setelan dikirim: Kiri {{ states('input_number.ac_lt1_left_changes') | int(0) }}x, "
                "Kanan {{ states('input_number.ac_lt1_right_changes') | int(0) }}x. "
                "Hitungan orang terakhir: {{ states('input_number.ac_lt1_count_last') | int(0) }} "
                "(pukul {{ (state_attr('input_datetime.ac_lt1_count_time', 'timestamp') | float(0)) | timestamp_custom('%H:%M') }})."
            )
    for action in control["automation"]:
        if action["id"] == "ac_lt1_left_apply":
            action["actions"][0]["data"]["ac_min_temp"] = 16
        if action["id"] == "ac_lt1_manual_pause":
            action["triggers"][0]["entity_id"] = ["climate.ac_lg_lt_1_kiri", "climate.ac_lg_lt_1_kanan"]
        if action["id"] in ("ac_lt1_notify_setting_sent", "ac_lt1_daily_summary"):
            action["variables"]["dashboard_path"] = "/ac-adaptive-lt2/lantai-1"
    control["template"][0]["variables"]["units"]["left"]["climate"] = "climate.ac_lg_lt_1_kiri"
    control["template"][0]["variables"]["units"]["right"]["climate"] = "climate.ac_lg_lt_1_kanan"
    # Both ACs are LG, and fan names differ in case. The shared apply script checks the
    # chosen name against each unit's fan_modes before attempting either IR call.
    assert len([a for a in control["automation"] if a["id"].endswith("_apply")]) == 2
    return {COUNT: count, CONTROL: control}


def build() -> None:
    for filename, data in generate().items():
        text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=100)
        assert not re.search(r"\bac_lt2\b|ac_adaptive_hours|ac_adaptive_count_enabled|2nd_floor|\bmiddle\b", text, re.I), filename
        (PACKAGES / filename).write_text("# Generated by tools/build_floor1_packages.py; edit LT2 rules or this builder.\n" + text, encoding="utf-8")
        print("written", filename)


if __name__ == "__main__":
    build()
