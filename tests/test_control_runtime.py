"""Phase 5 cases for the Sharp-middle control package, on real HA Core with fakes.

Every climate service is a fake that records the call. Nothing reaches a real AC.
"""

from datetime import datetime, timedelta

import pytest

from conftest import CLIMATE, LOCAL, POWER

COUNT = "ac_adaptive_count_enabled"
CONTROL = "ac_lt2_middle_control_enabled"
APPLIED = "input_text.ac_lt2_middle_last_applied"


def services(site):
    return [s for s, _ in site.calls]


def temperatures(site):
    return [d["temperature"] for s, d in site.calls if s == "set_temperature"]


async def live(site, people=4):
    """Count switch on, a fresh count, then the control switch on."""
    await site.switch(COUNT, True)
    await site.set_count(people)
    await site.switch(CONTROL, True)


async def test_control_off_sends_nothing(site):
    await site.switch(COUNT, True)
    await site.set_count(4)
    await site.after(minutes=10)
    assert site.calls == []


async def test_first_command_is_temperature_then_fan_only(site):
    await live(site)
    assert services(site) == ["set_temperature", "set_fan_mode"]
    assert site.calls[0][1]["temperature"] == 20
    assert site.calls[1][1]["fan_mode"] == "Medium"
    assert site.state(APPLIED) == "20|Medium"


async def test_never_sends_power_or_hvac_mode(site):
    await live(site)
    await site.tick(minutes=10)
    await site.set_count(8)
    await site.tick(minutes=10)
    assert set(services(site)) <= {"set_temperature", "set_fan_mode"}


@pytest.mark.parametrize("name, prepare", [
    ("count switch off", lambda s: s.switch(COUNT, False)),
    ("power at or below 50 W", lambda s: s.power(50)),
    ("AC in standby (20 W)", lambda s: s.power(20)),
    ("floor not occupied", None),
    ("count stale", None),
    ("AC not in cool mode", None),
])
async def test_gate_blocks_the_command(site, name, prepare):
    await site.switch(COUNT, True)
    await site.set_count(4)
    if name == "floor not occupied":
        from conftest import FRIGATE
        site.hass.states.async_set(FRIGATE, "off")
        await site.after(minutes=16)
        await site.power()
        assert site.state("binary_sensor.ac_lt2_occupied") == "off"
    elif name == "count stale":
        await site.set_count(4, age_minutes=40)
    elif name == "AC not in cool mode":
        site.hass.states.async_set(CLIMATE, "fan_only",
                                   {"fan_modes": ["Auto", "Low", "Medium", "High"]})
        await site.settle()
    else:
        await prepare(site)
    await site.switch(CONTROL, True)
    assert site.calls == [], name


async def test_stale_power_reading_blocks_the_command(site):
    await site.switch(COUNT, True)
    await site.set_count(4)
    # The plug last reported 21 minutes ago. Keep the count fresh meanwhile.
    await site.after(minutes=21)
    await site.set_count(4)
    assert site.state("binary_sensor.ac_lt2_count_stale") == "off"
    await site.switch(CONTROL, True)
    assert site.calls == []
    # A fresh reading lets the next evaluation through.
    await site.power()
    await site.after(minutes=10)
    assert services(site) == ["set_temperature", "set_fan_mode"]


async def test_unchanged_watts_but_fresh_report_keeps_control_on(site):
    await live(site)
    await site.after(minutes=12)
    # Real HA keeps last_changed but advances last_reported for identical watts.
    before = site.hass.states.get(POWER)
    last_changed, last_reported = before.last_changed, before.last_reported
    await site.power(1000)
    after = site.hass.states.get(POWER)
    assert after.last_changed == last_changed
    assert after.last_reported > last_reported
    await site.after(minutes=9)
    assert site.state(f"input_boolean.{CONTROL}") == "on"
    assert site.notifications == []


async def test_power_report_recovery_sends_pending_latest_target(site):
    await live(site)
    await site.after(minutes=21)
    await site.set_count(1, prev=1)
    assert site.state("sensor.ac_lt2_middle_recommended_setting") == "26|Low"
    assert temperatures(site) == [20]
    await site.power(1000)  # same wattage, new report
    await site.after(minutes=1)
    assert temperatures(site) == [20, 26]
    assert site.state(f"input_boolean.{CONTROL}") == "on"


async def test_right_control_is_separate_and_off_until_enabled(site):
    await site.switch(COUNT, True)
    await site.set_count(4)
    assert site.state("input_boolean.ac_lt2_right_control_enabled") == "off"
    assert site.state("sensor.ac_lt2_right_recommended_setting") == "20|Medium"
    assert site.calls == []
    await site.switch("ac_lt2_right_control_enabled", True)
    assert services(site) == ["set_temperature", "set_fan_mode"]
    assert all(d["entity_id"] == ["climate.ac_lg_2_2"] for _, d in site.calls)
    assert site.calls[0][1]["temperature"] == 20
    assert site.calls[1][1]["fan_mode"] == "Medium"
    assert site.state("input_boolean.ac_lt2_middle_control_enabled") == "off"


async def test_outside_working_hours_blocks_the_command(site):
    await site.switch(COUNT, True)
    evening = datetime(2026, 10, 29, 17, 5, tzinfo=LOCAL)
    await site.at(evening - timedelta(minutes=1))
    await site.set_count(4)
    await site.power()
    await site.at(evening)
    assert site.state("schedule.ac_adaptive_hours") == "off"
    await site.switch(CONTROL, True)
    assert site.calls == []


async def test_fan_missing_from_ac_modes_blocks_the_command(site):
    site.hass.states.async_set(CLIMATE, "cool", {"fan_modes": ["Auto", "Low", "High"]})
    await live(site)  # target fan is Medium
    assert site.calls == []


async def test_unchanged_target_is_not_resent(site):
    await live(site)
    assert len(site.calls) == 2
    for _ in range(4):
        await site.tick(minutes=10)
    assert len(site.calls) == 2
    assert site.state(f"input_boolean.{CONTROL}") == "on"


async def test_rate_limit_delays_a_new_target_by_10_minutes(site):
    await live(site)  # 10:10, sends 20|Medium
    assert temperatures(site) == [20]
    await site.after(minutes=3)
    await site.power()
    await site.set_count(8)  # 10:13, the recommendation changes to 18|High
    assert site.state("sensor.ac_lt2_middle_recommended_fan") == "High"
    assert len(site.calls) == 2  # blocked: last attempt was 3 minutes ago
    await site.tick(minutes=6)  # 10:19
    assert len(site.calls) == 2
    await site.tick(minutes=1)  # 10:20, ten minutes since the last attempt
    assert len(site.calls) == 4
    assert site.calls[-1][0] == "set_fan_mode" and site.calls[-1][1]["fan_mode"] == "High"
    assert site.state(APPLIED) == "18|High"


async def test_new_target_after_the_gap_is_sent(site):
    await live(site)
    await site.tick(minutes=11)
    await site.set_count(1, prev=1)
    assert site.state("sensor.ac_lt2_middle_recommended_temperature") == "26"
    assert temperatures(site) == [20, 26]
    assert site.calls[-1][1]["fan_mode"] == "Low"


async def test_user_change_in_ha_pauses_and_switches_control_off(site):
    await live(site)
    assert len(site.calls) == 2
    await site.after(minutes=1)
    await site.manual_change(25, fan="High")
    assert site.state(f"input_boolean.{CONTROL}") == "off"
    assert site.state(APPLIED) == "manual change"
    assert site.state("input_datetime.ac_lt2_middle_last_manual") != "1970-01-01 00:00:00"
    # Even if someone switches control back on, nothing is sent for 30 minutes.
    await site.set_count(8)
    await site.switch(CONTROL, True)
    for _ in range(2):
        await site.tick(minutes=10)
    assert len(site.calls) == 2
    # 30 minutes after the manual change the pause is over.
    await site.tick(minutes=10)
    await site.set_count(8)
    assert site.state(APPLIED) == "18|High"
    assert len(site.calls) == 4


async def test_change_without_a_user_does_not_pause(site):
    await live(site)
    site.hass.states.async_set(
        CLIMATE, "cool",
        {"fan_modes": ["Auto", "Low", "Medium", "High"], "temperature": 20, "fan_mode": "Medium"})
    await site.settle()
    assert site.state(f"input_boolean.{CONTROL}") == "on"


async def test_reenabling_resends_the_current_setting_once(site):
    await live(site)
    assert len(site.calls) == 2
    await site.tick(minutes=11)
    await site.switch(CONTROL, False)
    await site.switch(CONTROL, True)  # arm: the current setting is sent again
    assert len(site.calls) == 4
    await site.tick(minutes=10)
    assert len(site.calls) == 4


async def test_failed_command_is_recorded_and_not_retried(site):
    site.flags["fail_temperature"] = True
    await live(site)
    assert services(site) == ["set_temperature"]  # the fan command never follows
    assert site.state(APPLIED) == "20|Medium"
    for _ in range(3):
        await site.tick(minutes=10)
    assert services(site) == ["set_temperature"]


async def test_power_check_keeps_control_on_while_the_ac_draws_power(site):
    await live(site)
    await site.after(minutes=7)
    await site.power(1010)
    await site.after(minutes=8)  # 15 minutes after the command
    assert site.state(f"input_boolean.{CONTROL}") == "on"
    assert site.notifications == []


async def test_power_check_pauses_control_when_power_drops(site):
    await live(site)
    await site.after(minutes=7)
    await site.power(5)
    await site.after(minutes=8)
    assert site.state(f"input_boolean.{CONTROL}") == "off"
    assert len(site.notifications) == 1
    assert "paused" in site.notifications[0]["title"]
    assert len(site.calls) == 2  # and no retry was sent


async def test_power_check_pauses_control_when_the_sensor_goes_silent(site):
    await live(site)
    await site.after(minutes=21)  # no new reading at all since the command
    assert site.state(f"input_boolean.{CONTROL}") == "on"
    assert site.notifications == []
    await site.set_count(1)
    assert len(site.calls) == 2  # stale power holds the next command


async def test_power_check_pauses_control_when_the_sensor_is_unavailable(site):
    await live(site)
    await site.after(minutes=5)
    site.hass.states.async_set(POWER, "unavailable")
    await site.settle()
    await site.after(minutes=10)
    assert site.state(f"input_boolean.{CONTROL}") == "on"
    assert site.notifications == []


async def test_restart_leaves_control_off(site):
    # The helper has "initial: false", so a restart restores it to off.
    st = site.hass.states.get(f"input_boolean.{CONTROL}")
    assert st.state == "off"
