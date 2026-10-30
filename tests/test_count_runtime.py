"""Phase 5 cases for the counting package, on real Home Assistant Core with fakes."""

from datetime import datetime, timedelta

import pytest

from conftest import FRIGATE, LOCAL, START

COUNT_SWITCH = "ac_adaptive_count_enabled"
GOOD = {"count": 4, "confidence": 95, "observation": "Four people."}


def answer(count, confidence=95):
    return {"count": count, "confidence": confidence, "observation": f"{count} people."}


async def test_switch_off_means_no_gemini_call(site):
    site.ai.answers = [answer(4)]
    await site.after(minutes=10)
    assert site.ai.calls == 0
    assert site.state("sensor.ac_lt2_people") == "0"


async def test_accepted_count_uses_latest_answer(site):
    await site.switch(COUNT_SWITCH, True)
    site.ai.answers = [answer(4), answer(2)]
    await site.after(minutes=10)  # 10:20
    assert site.ai.calls == 1
    assert site.state("sensor.ac_lt2_people") == "4"
    assert site.state("sensor.ac_lt2_middle_level") == "2"
    await site.after(minutes=10)  # 10:30
    assert site.ai.calls == 2
    assert site.state("input_number.ac_lt2_count_last") == "2.0"
    assert site.state("input_number.ac_lt2_count_prev") == "4.0"
    assert site.state("sensor.ac_lt2_people") == "2"  # latest accepted answer
    await site.set_count(2, prev=2)
    assert site.state("sensor.ac_lt2_people") == "2"
    assert site.state("sensor.ac_lt2_middle_level") == "1"


async def test_failed_answer_keeps_last_count(site):
    await site.switch(COUNT_SWITCH, True)
    site.ai.answers = [answer(4)]
    await site.after(minutes=10)
    assert site.state("sensor.ac_lt2_people") == "4"
    # No scripted answer: the fake AI raises, like a failed Gemini call.
    await site.after(minutes=10)
    assert site.ai.calls == 2
    assert site.state("sensor.ac_lt2_people") == "4"
    assert site.state("input_number.ac_lt2_count_prev") == "0.0"


async def test_low_confidence_not_written(site):
    await site.switch(COUNT_SWITCH, True)
    site.ai.answers = [answer(7, confidence=69)]
    await site.after(minutes=10)
    assert site.ai.calls == 1
    assert site.state("input_number.ac_lt2_count_last") == "0.0"
    assert site.state("sensor.ac_lt2_people") == "0"
    site.ai.answers = [answer(3, confidence=70)]  # exactly the threshold is accepted
    await site.after(minutes=10)
    assert site.state("sensor.ac_lt2_people") == "3"


async def test_prev_write_cannot_publish_a_temporary_count(site):
    # The live 15:10 bug: writing the previous count while "last" still held an
    # old value made max(prev, last) dip to 2 and sent 26 C. Only "last" is used now.
    await site.set_count(2, prev=3)
    assert site.state("sensor.ac_lt2_people") == "2"
    assert site.state("sensor.ac_lt2_middle_recommended_setting") == "26|Low"
    await site.call("input_number", "set_value",
                    entity_id="input_number.ac_lt2_count_prev", value=2)
    assert site.state("sensor.ac_lt2_people") == "2"  # unchanged by a prev write
    await site.call("input_number", "set_value",
                    entity_id="input_number.ac_lt2_count_last", value=4)
    assert site.state("sensor.ac_lt2_people") == "4"
    assert site.state("sensor.ac_lt2_middle_recommended_setting") == "20|Medium"


async def test_zero_rejected_while_frigate_sees_people(site):
    await site.switch(COUNT_SWITCH, True)
    site.ai.answers = [answer(4)]
    await site.after(minutes=10)
    site.ai.answers = [answer(0, confidence=100)]
    await site.after(minutes=10)
    assert site.ai.calls == 2
    assert site.state("sensor.ac_lt2_people") == "4"
    assert site.state("input_number.ac_lt2_count_prev") == "0.0"


async def test_zero_accepted_when_frigate_is_off(site):
    await site.switch(COUNT_SWITCH, True)
    site.ai.answers = [answer(4)]
    await site.after(minutes=10)
    # Frigate drops the person; the 15-minute hold keeps the floor occupied.
    site.hass.states.async_set(FRIGATE, "off")
    await site.settle()
    site.ai.answers = [answer(0, confidence=90)]
    await site.after(minutes=10)
    assert site.state("binary_sensor.ac_lt2_occupied") == "on"
    assert site.ai.calls == 2
    assert site.state("input_number.ac_lt2_count_last") == "0.0"
    assert site.state("input_number.ac_lt2_count_prev") == "4.0"
    # An accepted zero is the latest answer, even while the 15-minute hold remains on.
    assert site.state("sensor.ac_lt2_people") == "0"


async def test_count_above_50_never_exceeds_50(site):
    await site.switch(COUNT_SWITCH, True)
    site.ai.answers = [answer(60)]
    await site.after(minutes=10)
    assert float(site.state("input_number.ac_lt2_count_last")) <= 50
    assert int(site.state("sensor.ac_lt2_people")) <= 50


async def test_room_empty_for_15_minutes_is_level_0(site):
    await site.set_count(4)
    assert site.state("binary_sensor.ac_lt2_occupied") == "on"
    site.hass.states.async_set(FRIGATE, "off")
    await site.after(minutes=14)
    assert site.state("binary_sensor.ac_lt2_occupied") == "on"  # dip shorter than 15 min
    assert site.state("sensor.ac_lt2_people") == "4"
    await site.after(minutes=2)
    assert site.state("binary_sensor.ac_lt2_occupied") == "off"
    assert site.state("sensor.ac_lt2_people") == "0"
    for ac in ("left", "middle", "right"):
        assert site.state(f"sensor.ac_lt2_{ac}_level") == "0"
        assert site.state(f"sensor.ac_lt2_{ac}_recommended_temperature") == "27"
        assert site.state(f"sensor.ac_lt2_{ac}_recommended_fan") == "Low"


async def test_short_dip_returns_without_going_empty(site):
    await site.set_count(4)
    site.hass.states.async_set(FRIGATE, "off")
    await site.after(minutes=8)
    site.hass.states.async_set(FRIGATE, "on")
    await site.after(minutes=20)
    assert site.state("binary_sensor.ac_lt2_occupied") == "on"
    assert site.state("sensor.ac_lt2_people") == "4"


async def test_stale_count_uses_safe_level(site):
    await site.set_count(1, age_minutes=31)
    await site.after(minutes=1)
    assert site.state("binary_sensor.ac_lt2_count_stale") == "on"
    for ac in ("left", "middle", "right"):
        assert site.state(f"sensor.ac_lt2_{ac}_level") == "2"
        assert site.state(f"sensor.ac_lt2_{ac}_recommended_temperature") == ("18" if ac == "left" else "20")
    await site.set_count(1)
    assert site.state("binary_sensor.ac_lt2_count_stale") == "off"
    assert site.state("sensor.ac_lt2_middle_level") == "1"


async def test_two_triggers_within_4_minutes_make_one_call(site):
    await site.switch(COUNT_SWITCH, True)
    site.ai.answers = [answer(4), answer(4)]
    await site.after(minutes=10)  # 10:20, scheduled call
    assert site.ai.calls == 1
    await site.after(minutes=2)  # 10:22, a second trigger with conditions evaluated
    await site.call("automation", "trigger",
                    entity_id="automation.ac_adaptive_count_people_floor_2",
                    skip_condition=False)
    assert site.ai.calls == 1
    await site.after(minutes=3)  # 10:25, gap is now 5 minutes
    await site.call("automation", "trigger",
                    entity_id="automation.ac_adaptive_count_people_floor_2",
                    skip_condition=False)
    assert site.ai.calls == 2


@pytest.mark.parametrize("people, level, left_temp, other_temp, fan", [
    (1, 1, "26", "26", "Low"),
    (2, 1, "26", "26", "Low"),
    (3, 2, "18", "20", "Medium"),
    (4, 2, "18", "20", "Medium"),
    (5, 3, "18", "18", "High"),
    (6, 3, "18", "18", "High"),
    (50, 3, "18", "18", "High"),
])
async def test_level_mapping_for_every_ac(site, people, level, left_temp, other_temp, fan):
    await site.set_count(people)
    for ac in ("left", "middle", "right"):
        assert site.state(f"sensor.ac_lt2_{ac}_level") == str(level)
        assert site.state(f"sensor.ac_lt2_{ac}_recommended_temperature") == (left_temp if ac == "left" else other_temp)
        assert site.state(f"sensor.ac_lt2_{ac}_recommended_fan") == fan


@pytest.mark.parametrize("when, label", [
    (datetime(2026, 10, 29, 18, 10, tzinfo=LOCAL), "after 18:00 on a weekday"),
    (datetime(2026, 10, 30, 6, 50, tzinfo=LOCAL), "before 07:00 on a weekday"),
    (datetime(2026, 10, 31, 10, 10, tzinfo=LOCAL), "Saturday"),
])
async def test_outside_working_hours_no_gemini_call(site, when, label):
    await site.switch(COUNT_SWITCH, True)
    site.ai.answers = [answer(4)] * 3
    # Let the schedule helper catch up with the new time first, then use a fresh
    # ten-minute mark.
    await site.at(when - timedelta(minutes=9))
    calls_before = site.ai.calls
    await site.at(when)
    assert site.state("schedule.ac_adaptive_hours") == "off", label
    assert site.ai.calls == calls_before, label
