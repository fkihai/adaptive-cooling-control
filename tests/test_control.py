"""Structure checks for the consolidated control package (no live HA or AC calls).

Behaviour (every gate, the cooldowns, the manual pause, the power check) is tested on real
Home Assistant Core in test_control_runtime.py. These tests pin the shape of the YAML that
those runtime tests cannot see: which entity each unit may command and the order of actions.
Run with: python run.py test.
"""

from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONTROL = yaml.safe_load((ROOT / "packages/adaptive_cooling_lt2_control.yaml").read_text(encoding="utf-8"))
AUTOMATIONS = {a["id"]: a for a in CONTROL["automation"]}
SCRIPT = CONTROL["script"]["ac_lt2_apply_setting"]["sequence"]
UNITS = {
    "left": ("climate.ac_sharp_lt_2_kiri", "sensor.0x60b763fffe1e451c_power", 18, 30),
    "middle": ("climate.ac_sharp_lt_2_tengah", "sensor.0x60b763fffe1f48ee_power", 18, 30),
    "right": ("climate.ac_lg_2_2", "sensor.0x60b763fffe1e67ae_power", 16, 30),
}


def climate_actions():
    return [a for a in SCRIPT if str(a.get("action", "")).startswith("climate.")]


class ControlTests(unittest.TestCase):
    def test_script_sends_only_temperature_then_fan_to_the_unit_it_is_given(self):
        calls = climate_actions()
        self.assertEqual([a["action"] for a in calls], ["climate.set_temperature", "climate.set_fan_mode"])
        for call in calls:
            self.assertEqual(call["target"]["entity_id"], "{{ ac_climate }}")
        self.assertNotIn("set_hvac_mode", str(SCRIPT))
        self.assertNotIn("turn_on", str(SCRIPT))
        self.assertNotIn("turn_off", str(SCRIPT))

    def test_each_unit_commands_only_its_own_ac_with_its_own_limits(self):
        for unit, (climate, power, low, high) in UNITS.items():
            with self.subTest(unit=unit):
                data = AUTOMATIONS[f"ac_lt2_{unit}_apply"]["actions"][0]["data"]
                self.assertEqual(AUTOMATIONS[f"ac_lt2_{unit}_apply"]["actions"][0]["action"],
                                 "script.ac_lt2_apply_setting")
                self.assertEqual(data["ac_climate"], climate)
                self.assertEqual(data["ac_power"], power)
                self.assertEqual(data["ac_control_switch"], f"input_boolean.ac_lt2_{unit}_control_enabled")
                self.assertEqual(data["ac_last_applied"], f"input_text.ac_lt2_{unit}_last_applied")
                self.assertEqual(data["ac_setting"], f"sensor.ac_lt2_{unit}_recommended_setting")
                self.assertEqual((data["ac_min_temp"], data["ac_max_temp"]), (low, high))

    def test_switches_have_no_initial_value_so_a_restart_keeps_their_state(self):
        for unit in UNITS:
            self.assertNotIn("initial", CONTROL["input_boolean"][f"ac_lt2_{unit}_control_enabled"] or {})

    def test_the_attempt_is_recorded_before_either_ir_call(self):
        first_ir = next(i for i, a in enumerate(SCRIPT) if str(a.get("action", "")).startswith("climate."))
        stamp = next(i for i, a in enumerate(SCRIPT) if a.get("action") == "input_datetime.set_datetime")
        record = next(i for i, a in enumerate(SCRIPT) if a.get("action") == "input_text.set_value")
        self.assertLess(stamp, first_ir)
        self.assertLess(record, first_ir)

    def test_script_keeps_every_guard(self):
        text = str(SCRIPT)
        for needle in ("input_boolean.ac_adaptive_count_enabled", "schedule.ac_adaptive_hours",
                       "binary_sensor.ac_lt2_occupied", "binary_sensor.ac_lt2_count_stale",
                       "last_reported", "20 * 60", "10 * 60", "30 * 60", "ac_min_temp", "fan_modes",
                       "ac_last_applied"):
            self.assertIn(needle, text)

    def test_manual_pause_pauses_only_the_unit_that_changed_and_sends_no_ir(self):
        manual = AUTOMATIONS["ac_lt2_manual_pause"]
        condition = manual["conditions"][0]["value_template"]
        self.assertIn("context.user_id is not none", condition)
        self.assertIn("context.parent_id is none", condition)
        actions = str(manual["actions"])
        self.assertIn("input_boolean.turn_off", actions)
        self.assertIn("ac_lt2_{{ unit }}_control_enabled", actions)
        self.assertNotIn("climate.set", actions)

    def test_arming_and_power_check_send_no_ir(self):
        for key in ("ac_lt2_arm", "ac_lt2_check_power"):
            self.assertNotIn("climate.set", str(AUTOMATIONS[key]["actions"]))
        self.assertIn("armed", str(AUTOMATIONS["ac_lt2_arm"]["actions"]))
        for unit in UNITS:
            self.assertIn("armed", str(AUTOMATIONS[f"ac_lt2_{unit}_apply"]["triggers"]))
        check = AUTOMATIONS["ac_lt2_check_power"]
        self.assertEqual(check["actions"][1]["delay"]["minutes"], 15)
        self.assertIn("last_reported", str(check["actions"]))

    def test_notifications_never_touch_a_climate_entity(self):
        for key in ("ac_lt2_notify_setting_sent", "ac_lt2_daily_summary"):
            self.assertNotIn("climate.", str(AUTOMATIONS[key]["actions"]))


if __name__ == "__main__":
    unittest.main()
