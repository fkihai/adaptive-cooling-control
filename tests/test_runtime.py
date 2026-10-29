"""End-to-end path on real Home Assistant Core with local fakes (see conftest.py):
one Gemini count of 4 leads to one fake Sharp-middle command, 20 C then Medium."""

from conftest import CLIMATE, LOCAL, START

from datetime import datetime


async def test_count_of_4_leads_to_one_fake_command(site):
    assert site.state("input_boolean.ac_adaptive_count_enabled") == "off"
    assert site.state("input_boolean.ac_lt2_middle_control_enabled") == "off"
    assert site.state("binary_sensor.ac_lt2_occupied") == "on"
    assert site.calls == [] and site.ai.calls == 0

    # Count switch on: a scheduled count runs, but no command while control is off.
    site.ai.answers = [{"count": 4, "confidence": 95, "observation": "Four people."}]
    await site.switch("ac_adaptive_count_enabled", True)
    await site.after(minutes=10)
    assert site.ai.calls == 1
    assert site.state("sensor.ac_lt2_people") == "4"
    assert site.state("sensor.ac_lt2_middle_recommended_temperature") == "20"
    assert site.calls == []

    # Control switch on: temperature, then fan, to the one allowed AC.
    await site.switch("ac_lt2_middle_control_enabled", True)
    assert [s for s, _ in site.calls] == ["set_temperature", "set_fan_mode"]
    assert site.calls[0][1]["entity_id"] == [CLIMATE]
    assert site.calls[0][1]["temperature"] == 20
    assert site.calls[1][1]["fan_mode"] == "Medium"
    assert site.state("input_text.ac_lt2_middle_last_applied") == "20|Medium"
    assert site.ai.calls == 1

    # The next scheduled evaluation with the same target sends nothing more.
    await site.tick(minutes=10)
    assert len(site.calls) == 2
