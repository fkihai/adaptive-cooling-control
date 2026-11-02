"""LT1 on real Home Assistant Core with fake camera, Gemini and IR services."""

from datetime import datetime

import pytest

from conftest import LOCAL


COUNT = "ac_adaptive_count_lt1_enabled"
LEFT = "ac_lt1_left_control_enabled"
RIGHT = "ac_lt1_right_control_enabled"


@pytest.mark.parametrize("people,level,temp", [(0, 1, "22"), (1, 1, "22"), (2, 2, "20"),
                                           (3, 2, "20"), (4, 3, "18"), (6, 3, "18")])
async def test_lt1_recommendations_match_lt2_rules(site_lt1, people, level, temp):
    site = site_lt1
    await site.set_count(people)
    for unit, fan in (("left", "High"), ("right", "high")):
        assert site.state(f"sensor.ac_lt1_{unit}_level") == str(level)
        assert site.state(f"sensor.ac_lt1_{unit}_recommended_setting") == f"{temp}|{fan}"


async def test_lt1_controls_start_off_and_right_ac_is_off(site_lt1):
    site = site_lt1
    assert site.state(f"input_boolean.{LEFT}") == "off"
    assert site.state(f"input_boolean.{RIGHT}") == "off"
    assert site.state("sensor.ac_lt1_right_status") == "AC mati, tidak diatur otomasi"
    await site.switch(COUNT, True)
    await site.set_count(4)
    assert site.calls == []


async def test_right_off_still_gets_no_ir_even_if_control_is_enabled(site_lt1):
    site = site_lt1
    await site.switch(COUNT, True)
    await site.set_count(4)
    await site.switch(RIGHT, True)
    await site.after(minutes=11)
    assert site.calls == []
    assert site.state("sensor.ac_lt1_right_status") == "AC mati, tidak diatur otomasi"


async def test_left_first_ir_is_temperature_then_high_fan(site_lt1):
    site = site_lt1
    await site.switch(COUNT, True)
    await site.set_count(3)
    await site.switch(LEFT, True)
    assert [s for s, _ in site.calls] == ["set_temperature", "set_fan_mode"]
    assert all(c["entity_id"] == ["climate.ac_lg_lt_1_kiri"] for _, c in site.calls)
    assert site.calls[0][1]["temperature"] == 20
    assert site.calls[1][1]["fan_mode"] == "High"
    assert site.state("input_text.ac_lt1_left_last_applied") == "20|High"
    assert site.pushes[0]["data"]["tag"] == "ac_lt1_left"
    assert site.pushes[0]["data"]["url"] == "/ac-adaptive-lt2/lantai-1"
    assert "Lantai 1" in site.pushes[0]["message"]
    assert site.bell[0]["notification_id"] == "ac_lt1_left"
    assert site.bell[0]["title"] == site.pushes[0]["title"]


async def test_right_lowercase_fan_when_it_is_cooling_with_fresh_power(site_lt1):
    site = site_lt1
    await site.switch(COUNT, True)
    await site.set_count(2)
    site.hass.states.async_set("climate.ac_lg_lt_1_kanan", "cool",
                               {"fan_modes": ["auto", "low", "medium", "high"],
                                "temperature": 16, "fan_mode": "high"})
    site.hass.states.async_set("sensor.0x60b763fffe1e380d_power", "700")
    await site.settle()
    await site.switch(RIGHT, True)
    assert site.state("input_text.ac_lt1_right_last_applied") == "20|high"
    assert site.calls[-1][1]["fan_mode"] == "high"
    assert site.bell[-1]["notification_id"] == "ac_lt1_right"


async def test_no_gemini_or_ir_outside_the_separate_lt1_schedule(site_lt1):
    site = site_lt1
    # Let the schedule catch up before enabling the count switch; a large jump to
    # a scheduled minute otherwise fires the timer while the schedule still says on.
    await site.at(datetime(2026, 10, 31, 10, 4, tzinfo=LOCAL))
    assert site.state("schedule.ac_lt1_hours") == "off"
    await site.switch(COUNT, True)
    await site.at(datetime(2026, 10, 31, 10, 5, tzinfo=LOCAL))
    await site.switch(LEFT, True)
    assert site.state("schedule.ac_lt1_hours") == "off"
    assert site.ai.calls == 0 and site.calls == []


async def test_empty_room_suggests_27_but_does_not_send_to_lt1(site_lt1):
    site = site_lt1
    await site.switch(COUNT, True)
    await site.set_count(2)
    await site.switch(LEFT, True)
    sent = len(site.calls)
    site.hass.states.async_set("binary_sensor.1st_floor_person_occupancy", "off")
    await site.after(minutes=16)
    assert site.state("binary_sensor.ac_lt1_occupied") == "off"
    assert site.state("sensor.ac_lt1_left_recommended_setting") == "27|High"
    await site.tick(minutes=11)
    assert len(site.calls) == sent


async def test_count_schedule_staggered_from_lt2(site_lt1):
    site = site_lt1
    await site.switch(COUNT, True)
    site.ai.answers = [{"count": 3, "confidence": 95, "observation": "Three people."}]
    await site.at(datetime(2026, 10, 29, 10, 15, tzinfo=LOCAL))
    assert site.ai.calls == 1 and site.state("sensor.ac_lt1_people") == "3"


async def test_floor1_manual_change_pauses_only_its_own_ac(site_lt1):
    site = site_lt1
    await site.switch(COUNT, True)
    await site.set_count(2)
    await site.switch(LEFT, True)
    from homeassistant.core import Context
    site.hass.states.async_set("climate.ac_lg_lt_1_kiri", "cool",
                               {"fan_modes": ["Auto", "Low", "Medium", "High"],
                                "temperature": 24, "fan_mode": "Low"},
                               context=Context(user_id="user-1"))
    await site.settle()
    assert site.state(f"input_boolean.{LEFT}") == "off"
    assert site.state("input_text.ac_lt1_left_last_applied") == "manual change"
    assert site.state(f"input_boolean.{RIGHT}") == "off"
    assert len(site.bell) == 1  # no new setting notification for a manual change
