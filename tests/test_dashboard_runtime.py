"""Status lines and push notifications for the dashboard, on real HA Core with fakes.

The status sensor stays "ok" while the AC matches the target and otherwise says in one
sentence what the unit is waiting for. A push goes out only for a setting the automation sent.
"""

from datetime import datetime, timedelta

import pytest

from conftest import CLIMATE, FRIGATE, LOCAL, POWER

COUNT = "ac_adaptive_count_enabled"
CONTROL = "ac_lt2_middle_control_enabled"
STATUS = "sensor.ac_lt2_middle_status"
FANS = ["Auto", "Low", "Medium", "High"]


def set_ac(site, state="cool", temperature=20, fan="Medium"):
    site.hass.states.async_set(CLIMATE, state,
                               {"fan_modes": FANS, "temperature": temperature, "fan_mode": fan})


async def live(site, people=4):
    await site.switch(COUNT, True)
    await site.set_count(people)
    await site.switch(CONTROL, True)


# ---- status line ----------------------------------------------------------------------


async def test_status_is_ok_when_the_ac_matches_the_target(site):
    await site.switch(COUNT, True)
    await site.set_count(4)  # normal level: 20 C / Medium for the middle AC
    set_ac(site, temperature=20, fan="Medium")
    await site.settle()
    assert site.state(STATUS) == "ok"


async def test_status_says_the_ac_is_off(site):
    await site.set_count(4)
    set_ac(site, state="off")
    await site.settle()
    assert "AC mati" in site.state(STATUS)


async def test_status_says_control_is_off_and_shows_the_suggestion(site):
    await site.switch(COUNT, True)
    await site.set_count(4)
    set_ac(site, temperature=26, fan="Low")
    await site.settle()
    text = site.state(STATUS)
    assert "Otomasi mati" in text and "20 °C" in text and "Medium" in text


async def test_status_outside_work_hours(site):
    await site.switch(COUNT, True)
    await site.set_count(4)
    await site.switch(CONTROL, True)
    set_ac(site, temperature=26, fan="Low")
    await site.at(datetime(2026, 10, 31, 10, 10, tzinfo=LOCAL))  # Saturday
    assert "Di luar jam kerja" in site.state(STATUS)


async def test_status_waits_for_a_fresh_count(site):
    await site.switch(COUNT, True)
    await site.set_count(4, age_minutes=40)
    await site.switch(CONTROL, True)
    set_ac(site, temperature=26, fan="Low")
    await site.settle()
    assert "Menunggu hitungan orang" in site.state(STATUS)


async def test_status_waits_for_power_data(site):
    await live(site)
    set_ac(site, temperature=26, fan="Low")
    await site.power(20)  # standby
    assert "Menunggu data daya" in site.state(STATUS)


async def test_status_during_the_ten_minute_gap(site):
    await live(site)           # first command sent now
    await site.power()
    set_ac(site, temperature=26, fan="Low")
    await site.set_count(8)    # busy: 18 C / High, but the gap has not passed
    await site.power()
    text = site.state(STATUS)
    assert "Akan ke 18 °C · High" in text and "mnt" in text


async def test_status_after_a_manual_change_is_paused(site):
    await live(site)
    await site.manual_change(24, "Low")
    await site.set_count(8)
    await site.power()
    assert "Dijeda manual s/d" in site.state(STATUS)


async def test_status_is_ok_for_every_ac_when_all_match(site):
    await site.switch(COUNT, True)
    await site.set_count(8)  # busy: 18 C / High for all three
    for entity in (CLIMATE, "climate.ac_lg_2_2", "climate.ac_sharp_lt_2_kiri"):
        site.hass.states.async_set(entity, "cool",
                                   {"fan_modes": FANS, "temperature": 18, "fan_mode": "High"})
    await site.settle()
    for unit in ("left", "middle", "right"):
        assert site.state(f"sensor.ac_lt2_{unit}_status") == "ok", unit


# ---- push notification -------------------------------------------------------------------


async def test_push_for_a_setting_the_automation_sent(site):
    await live(site)
    assert len(site.pushes) == 1
    push = site.pushes[0]
    assert push["title"] == "AC Sharp Tengah: 20 °C · Fan Medium"
    assert "4 orang" in push["message"]
    assert push["data"]["tag"] == "ac_lt2_middle"
    assert float(site.state("input_number.ac_lt2_middle_changes")) == 1


async def test_no_push_for_the_armed_marker_or_the_same_target(site):
    await site.switch(COUNT, True)
    await site.set_count(4)
    await site.switch(CONTROL, True)
    await site.tick(minutes=11)  # the same target is not sent again
    assert len(site.pushes) == 1


async def test_a_new_target_sends_a_second_push(site):
    await live(site)
    await site.tick(minutes=11)
    await site.set_count(8)
    await site.tick(minutes=1)
    assert [p["title"] for p in site.pushes] == [
        "AC Sharp Tengah: 20 °C · Fan Medium",
        "AC Sharp Tengah: 18 °C · Fan High",
    ]


async def test_no_push_for_a_manual_change(site):
    await live(site)
    before = len(site.pushes)
    await site.manual_change(24, "Low")
    assert len(site.pushes) == before  # "manual change" has no "|"


async def test_no_push_when_a_user_edits_the_helper(site):
    from homeassistant.core import Context
    await site.switch(COUNT, True)
    site.hass.states.async_set("input_text.ac_lt2_middle_last_applied", "22|Low",
                               context=Context(user_id="user-1"))
    await site.settle()
    assert site.pushes == []


@pytest.mark.parametrize("unit, climate, name", [
    ("right", "climate.ac_lg_2_2", "LG Kanan"),
])
async def test_push_names_the_right_ac(site, unit, climate, name):
    await site.switch(COUNT, True)
    await site.set_count(4)
    site.hass.states.async_set("sensor.0x60b763fffe1e67ae_power", "1000")
    await site.switch(f"ac_lt2_{unit}_control_enabled", True)
    assert any(p["title"].startswith(f"AC {name}") for p in site.pushes)


# ---- daily summary ----------------------------------------------------------------------


async def test_daily_summary_after_work_hours_resets_the_counters(site):
    await live(site)
    assert float(site.state("input_number.ac_lt2_middle_changes")) == 1
    before = len(site.pushes)
    await site.at(datetime(2026, 10, 29, 18, 4, tzinfo=LOCAL))
    await site.at(datetime(2026, 10, 29, 18, 5, 5, tzinfo=LOCAL))
    summary = [p for p in site.pushes[before:] if p["data"]["tag"] == "ac_lt2_daily"]
    assert len(summary) == 1
    assert "Tengah 1x" in summary[0]["message"]
    assert float(site.state("input_number.ac_lt2_middle_changes")) == 0


# ---- activity sensor (timeline and 7-day summary) --------------------------------------------

ACTIVITY = "sensor.ac_lt2_activity"


def attrs(site):
    return site.hass.states.get(ACTIVITY).attributes


async def test_activity_records_a_sent_setting_and_the_daily_total(site):
    await live(site)
    events = attrs(site)["events"]
    assert events[0]["unit"] == "middle" and events[0]["kind"] == "sent"
    assert events[0]["value"] == "20|Medium"
    assert attrs(site)["sent_by_day"]["2026-10-29"]["middle"] == 1
    assert site.state(ACTIVITY) == "1"


async def test_activity_ignores_armed_and_unchanged_values(site):
    await site.switch(COUNT, True)
    await site.set_count(4)
    await site.switch(CONTROL, True)   # writes "armed" first, then the real setting
    await site.tick(minutes=11)        # same target again: nothing new
    assert [e["kind"] for e in attrs(site)["events"] if e["unit"] == "middle"].count("sent") == 1
    assert all(e["value"] != "armed" for e in attrs(site)["events"])


async def test_activity_records_manual_change_and_control_switch(site):
    await live(site)
    await site.manual_change(24, "Low")
    kinds = [e["kind"] for e in attrs(site)["events"]]
    assert "manual" in kinds and "control" in kinds


async def test_activity_keeps_only_the_last_eight_events(site):
    await site.switch(COUNT, True)
    for i in range(10):
        await site.call("input_text", "set_value",
                        entity_id="input_text.ac_lt2_middle_last_applied", value=f"{20 + i % 2}|Low{i}")
    events = attrs(site)["events"]
    assert len(events) == 8
    assert events[0]["value"] == "21|Low9"  # newest first


async def test_activity_tracks_the_daily_peak_of_people(site):
    await site.set_count(3)
    await site.set_count(6)
    await site.set_count(2)
    assert attrs(site)["people_peak_by_day"]["2026-10-29"] == 6


async def test_activity_drops_days_older_than_seven(site):
    await site.set_count(5)
    assert attrs(site)["people_peak_by_day"]["2026-10-29"] == 5
    await site.at(datetime(2026, 11, 6, 10, 10, tzinfo=LOCAL))  # 8 days later
    await site.set_count(2, prev=2)
    peaks = attrs(site)["people_peak_by_day"]
    assert "2026-10-29" not in peaks
    assert peaks["2026-11-06"] <= 5  # a day only keeps the highest value it saw
