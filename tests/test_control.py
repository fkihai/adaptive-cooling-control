"""Offline contract checks for the Sharp middle pilot (no live HA or AC calls).

Run with: python run.py test. Needs PyYAML and Jinja2 (installed with Home Assistant);
this does not replace the HA config check (python run.py check).
"""

import datetime as dt
from pathlib import Path
import unittest

import yaml
from jinja2 import Environment


ROOT = Path(__file__).resolve().parents[1]
COUNT = yaml.safe_load((ROOT / "packages/adaptive_cooling_lt2.yaml").read_text(encoding="utf-8"))
CONTROL = yaml.safe_load((ROOT / "packages/adaptive_cooling_lt2_control.yaml").read_text(encoding="utf-8"))
AUTOMATIONS = {a["id"]: a for a in CONTROL["automation"]}
APPLY = AUTOMATIONS["ac_lt2_middle_apply"]
POWER = "sensor.0x60b763fffe1f48ee_power"
CLIMATE = "climate.ac_sharp_lt_2_tengah"


class Clock:
    def __init__(self, timestamp=1_800_000_000):
        self.ts = timestamp

    def timestamp(self):
        return self.ts


class State:
    def __init__(self, last_updated):
        self.last_changed = last_updated
        self.last_reported = last_updated


class ClimateDomain(dict):
    pass


class FakeHA:
    def __init__(self):
        self.clock = Clock()
        self.values = {
            "input_boolean.ac_lt2_middle_control_enabled": "on",
            "input_boolean.ac_adaptive_count_enabled": "on",
            "schedule.ac_adaptive_hours": "on",
            "binary_sensor.ac_lt2_occupied": "on",
            "binary_sensor.ac_lt2_count_stale": "off",
            CLIMATE: "cool",
            POWER: "1000",
            "input_text.ac_lt2_middle_last_applied": "unknown",
            "input_datetime.ac_lt2_middle_last_command": "unknown",
            "input_datetime.ac_lt2_middle_last_manual": "unknown",
            "sensor.ac_lt2_middle_recommended_temperature": "20",
            "sensor.ac_lt2_middle_recommended_fan": "Medium",
            "sensor.ac_lt2_middle_recommended_setting": "20|Medium",
        }
        self.timestamps = {}
        self.updated = self.clock.timestamp() - 60

    def render(self, template, **extra):
        env = Environment()

        def number(value, default, convert):
            try:
                return convert(value)
            except (ValueError, TypeError):
                return default

        env.filters["int"] = lambda x, d=0: number(x, d, int)
        env.filters["float"] = lambda x, d=0.0: number(x, d, float)
        ns = type("States", (), {})()
        ns.sensor = ClimateDomain({POWER.removeprefix("sensor."): State(dt.datetime.fromtimestamp(self.updated, dt.timezone.utc))})
        vars_ = {
            "now": lambda: self.clock,
            "is_state": lambda entity, value: self.values.get(entity) == value,
            "state_attr": lambda entity, attr: (
                self.timestamps.get(entity) if attr == "timestamp" else
                ["Auto", "Low", "Medium", "High"] if attr == "fan_modes" and entity == CLIMATE else None
            ),
            "has_value": lambda entity: self.values.get(entity, "unknown") not in ("unknown", "unavailable"),
            "as_timestamp": lambda value, d=0: value.timestamp() if hasattr(value, "timestamp") else d,
            "target_temperature": int(self.values["sensor.ac_lt2_middle_recommended_temperature"]),
            "target_fan": self.values["sensor.ac_lt2_middle_recommended_fan"],
            "target_setting": self.values["sensor.ac_lt2_middle_recommended_temperature"] + "|" + self.values["sensor.ac_lt2_middle_recommended_fan"],
        }
        # HA's states() function also exposes states.sensor in templates.
        class States:
            sensor = ns.sensor

            def __call__(self, entity):
                return self_values.get(entity, "unknown")

        self_values = self.values
        vars_["states"] = States()
        vars_.update(extra)
        return env.from_string(template).render(**vars_).strip()

    def eligible(self):
        for cond in APPLY["conditions"]:
            if cond["condition"] == "state":
                if self.values[cond["entity_id"]] != cond["state"]:
                    return False
            elif cond["condition"] == "numeric_state":
                if float(self.values[cond["entity_id"]]) <= cond["above"]:
                    return False
            elif cond["condition"] == "template":
                if self.render(cond["value_template"]).lower() != "true":
                    return False
            else:
                raise AssertionError(cond)
        return True


class ControlTests(unittest.TestCase):
    def test_only_middle_ac_receives_commands(self):
        actions = APPLY["actions"]
        calls = [a for a in actions if a.get("action", "").startswith("climate.")]
        self.assertEqual([a["action"] for a in calls], ["climate.set_temperature", "climate.set_fan_mode"])
        self.assertTrue(all(a["target"]["entity_id"] == CLIMATE for a in calls))
        self.assertTrue(all(a["target"]["entity_id"] not in ("climate.ac_sharp_lt_2_kiri", "climate.ac_lg_2_2") for a in calls))
        self.assertFalse(CONTROL["input_boolean"]["ac_lt2_middle_control_enabled"]["initial"])
        # Record the attempt before either IR service (including a failed service).
        self.assertLess(next(i for i, a in enumerate(actions) if a.get("action") == "input_datetime.set_datetime"),
                        next(i for i, a in enumerate(actions) if a.get("action", "").startswith("climate.")))
        self.assertLess(next(i for i, a in enumerate(actions) if a.get("action") == "input_text.set_value"),
                        next(i for i, a in enumerate(actions) if a.get("action", "").startswith("climate.")))

    def test_controls_block_on_missing_preconditions(self):
        h = FakeHA()
        self.assertTrue(h.eligible())
        for entity, value in (("input_boolean.ac_lt2_middle_control_enabled", "off"),
                              ("input_boolean.ac_adaptive_count_enabled", "off"),
                              ("schedule.ac_adaptive_hours", "off"),
                              ("binary_sensor.ac_lt2_occupied", "off"),
                              ("binary_sensor.ac_lt2_count_stale", "on"),
                              (CLIMATE, "off"), (POWER, "0"),
                              ("sensor.ac_lt2_middle_recommended_temperature", "17"),
                              ("sensor.ac_lt2_middle_recommended_fan", "invalid"),
                               ("input_text.ac_lt2_middle_last_applied", "20|Medium")):
            with self.subTest(entity=entity, value=value):
                other = FakeHA()
                other.values[entity] = value
                self.assertFalse(other.eligible())

    def test_power_freshness_and_command_cooldowns(self):
        h = FakeHA()
        h.updated = h.clock.ts - 20 * 60
        self.assertFalse(h.eligible())
        h.updated = h.clock.ts - 19 * 60
        self.assertTrue(h.eligible())
        h.timestamps["input_datetime.ac_lt2_middle_last_command"] = h.clock.ts - 9 * 60
        self.assertFalse(h.eligible())
        h.timestamps["input_datetime.ac_lt2_middle_last_command"] = h.clock.ts - 10 * 60
        self.assertTrue(h.eligible())
        h.timestamps["input_datetime.ac_lt2_middle_last_manual"] = h.clock.ts - 29 * 60
        self.assertFalse(h.eligible())
        h.timestamps["input_datetime.ac_lt2_middle_last_manual"] = h.clock.ts - 30 * 60
        self.assertTrue(h.eligible())

    def test_manual_pause_and_power_check_do_not_send_ir(self):
        manual = AUTOMATIONS["ac_lt2_middle_manual_pause"]
        check = AUTOMATIONS["ac_lt2_middle_check_power"]
        arm = AUTOMATIONS["ac_lt2_middle_arm"]
        self.assertIn("context.user_id is not none", manual["conditions"][0]["value_template"])
        self.assertIn("context.parent_id is none", manual["conditions"][0]["value_template"])
        self.assertEqual(manual["actions"][1]["target"]["entity_id"],
                         "input_boolean.ac_lt2_middle_control_enabled")
        self.assertEqual(arm["actions"][0]["data"]["value"], "armed")
        self.assertIn("armed", str(APPLY["triggers"]))
        self.assertEqual(check["actions"][0]["delay"]["minutes"], 15)
        self.assertIn("last_reported", str(check["actions"][1]))
        for a in (arm, manual, check):
            self.assertNotIn("climate.", str(a["actions"]))


if __name__ == "__main__":
    unittest.main()
