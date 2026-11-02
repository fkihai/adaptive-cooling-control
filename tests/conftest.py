"""Shared harness: both packages on real Home Assistant Core with local fakes.

Nothing here touches a live Home Assistant, Gemini or a real AC.
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import shutil
from zoneinfo import ZoneInfo

import pytest

from homeassistant import config as conf_util
from homeassistant.components.ai_task.const import DATA_COMPONENT as AI_COMPONENT
from homeassistant.components.camera.const import DATA_COMPONENT as CAM_COMPONENT
from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from fakes import FakeAI, FakeCamera

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ZoneInfo("Asia/Jakarta")
CLIMATE = "climate.ac_sharp_lt_2_tengah"
POWER = "sensor.0x60b763fffe1f48ee_power"
FRIGATE = "binary_sensor.2nd_floor_person_occupancy"
# Thursday, inside working hours.
START = datetime(2026, 10, 29, 10, 10, tzinfo=LOCAL)


@pytest.fixture
def expected_lingering_timers() -> bool:
    return True


class Site:
    """A fake floor 2 with helpers to move time and read results."""

    def __init__(self, hass, freezer, ai, calls, flags, notifications, pushes=None, bell=None):
        self.hass = hass
        self.freezer = freezer
        self.ai = ai
        self.calls = calls  # (service, data) for every fake climate call
        self.flags = flags  # flags["fail_temperature"]: make set_temperature raise
        self.notifications = notifications  # persistent_notification.create data, except the bell entry below
        self.bell = bell if bell is not None else []  # notification ids ac_lt2_left/_middle/_right: one entry per setting sent
        self.pushes = pushes if pushes is not None else []  # notify.mobile_app_cph2457 data
        self.now = START
        self._tick = 0

    # ---- time -------------------------------------------------------------------
    def _delay_pending(self):
        """True while the power-check automation sits in its 15-minute delay."""
        for st in self.hass.states.async_all("automation"):
            if "check_power" in st.entity_id and st.attributes.get("current", 0) > 0:
                return True
        return False

    async def settle(self, rounds=6):
        # The clock is frozen, so asyncio timeouts never fire, and block_till_done
        # would wait forever for an automation that is inside a delay. Use it only
        # when no delay is pending; otherwise just spin the event loop.
        for _ in range(rounds):
            if self._delay_pending():
                break
            await self.hass.async_block_till_done(wait_background_tasks=True)
        for _ in range(60):
            await asyncio.sleep(0)

    async def at(self, when: datetime):
        """Move the clock to `when` and let every due timer and trigger run."""
        self.now = when
        self.freezer.move_to(when)
        async_fire_time_changed(self.hass, when)
        await self.settle()

    async def after(self, **delta):
        await self.at(self.now + timedelta(**delta))

    # ---- state helpers ----------------------------------------------------------
    def state(self, entity_id):
        st = self.hass.states.get(entity_id)
        assert st is not None, entity_id
        return st.state

    async def call(self, domain, service, **data):
        await self.hass.services.async_call(domain, service, data, blocking=True)
        await self.settle()

    async def switch(self, name, on):
        await self.call("input_boolean", "turn_on" if on else "turn_off",
                        entity_id=f"input_boolean.{name}")

    async def set_count(self, last, prev=None, age_minutes=0, floor="lt2"):
        """Write an accepted count straight into the helpers (no Gemini call)."""
        await self.call("input_number", "set_value",
                        entity_id=f"input_number.ac_{floor}_count_last", value=last)
        await self.call("input_number", "set_value",
                        entity_id=f"input_number.ac_{floor}_count_prev",
                        value=last if prev is None else prev)
        await self.call("input_datetime", "set_datetime",
                        entity_id=f"input_datetime.ac_{floor}_count_time",
                        timestamp=int((self.now - timedelta(minutes=age_minutes)).timestamp()))

    async def power(self, watts=None):
        """Publish a fresh power report, even if the watts stay unchanged."""
        if watts is None:
            self._tick += 1
            watts = 1000 + self._tick % 2
        self.hass.states.async_set(POWER, str(watts))
        await self.settle()

    async def tick(self, **delta):
        """Move time forward with a fresh power reading just before it (the real
        sensor reports about every 10 minutes)."""
        await self.power()
        await self.after(**delta)

    async def manual_change(self, temperature, fan="Low"):
        """A user changes the HA climate entity (what the dashboard does)."""
        self.hass.states.async_set(
            CLIMATE, "cool",
            {"fan_modes": ["Auto", "Low", "Medium", "High"],
             "temperature": temperature, "fan_mode": fan},
            context=Context(user_id="user-1"))
        await self.settle()

    def climate_calls(self):
        return [(s, d) for s, d in self.calls]


@pytest.fixture
async def site(hass: HomeAssistant, freezer, tmp_path):
    return await setup_site(hass, freezer, tmp_path)


@pytest.fixture
async def site_lt1(hass: HomeAssistant, freezer, tmp_path):
    return await setup_site(hass, freezer, tmp_path, floor="lt1")


async def setup_site(hass: HomeAssistant, freezer, tmp_path, floor="lt2"):
    freezer.move_to(START)
    await hass.config.async_set_time_zone("Asia/Jakarta")
    cfg = tmp_path / "config"
    pkgs = cfg / "packages"
    pkgs.mkdir(parents=True)
    shutil.copy(ROOT / "tests/fixtures/configuration.yaml", cfg / "configuration.yaml")
    for name in (f"adaptive_cooling_{floor}.yaml", f"adaptive_cooling_{floor}_control.yaml"):
        shutil.copy(ROOT / "packages" / name, pkgs / name)
    hass.config.config_dir = str(cfg)

    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "camera", {})
    await hass.data[CAM_COMPONENT].async_add_entities([FakeCamera("1st" if floor == "lt1" else "2nd")])
    assert await async_setup_component(hass, "ai_task", {})
    ai = FakeAI()
    await hass.data[AI_COMPONENT].async_add_entities([ai])

    calls = []
    flags = {"fail_temperature": False}
    notifications = []
    pushes = []
    bell = []

    async def fake_climate(call: ServiceCall):
        calls.append((call.service, dict(call.data)))
        if flags["fail_temperature"] and call.service == "set_temperature":
            raise HomeAssistantError("fake IR failure")

    async def fake_notification(call: ServiceCall):
        # The setting-sent entry in the bell has its own list, so the power-pause tests keep counting only
        # their own notification.
        if call.data.get("notification_id") in ("ac_lt2_left", "ac_lt2_middle", "ac_lt2_right",
                                                "ac_lt1_left", "ac_lt1_right"):
            bell.append(dict(call.data))
        else:
            notifications.append(dict(call.data))

    async def fake_push(call: ServiceCall):
        pushes.append(dict(call.data))

    hass.services.async_register("notify", "mobile_app_cph2457", fake_push)
    hass.services.async_register("climate", "set_temperature", fake_climate)
    hass.services.async_register("climate", "set_fan_mode", fake_climate)
    hass.services.async_register("climate", "set_hvac_mode", fake_climate)
    hass.services.async_register("climate", "turn_off", fake_climate)
    hass.services.async_register("climate", "turn_on", fake_climate)
    if floor == "lt1":
        hass.states.async_set("climate.ac_lg_lt_1_kiri", "cool",
                              {"fan_modes": ["Auto", "Low", "Medium", "High"],
                               "temperature": 16, "fan_mode": "High"})
        hass.states.async_set("sensor.0x60b763fffe1e5fc6_power", "700")
        hass.states.async_set("climate.ac_lg_lt_1_kanan", "off",
                              {"fan_modes": ["auto", "low", "medium", "high"],
                               "temperature": 16, "fan_mode": "high"})
        hass.states.async_set("sensor.0x60b763fffe1e380d_power", "0")
        hass.states.async_set("binary_sensor.1st_floor_person_occupancy", "on")
    else:
        hass.states.async_set(CLIMATE, "cool", {"fan_modes": ["Auto", "Low", "Medium", "High"]})
        hass.states.async_set(POWER, "1000")
        hass.states.async_set("climate.ac_lg_2_2", "cool",
                              {"fan_modes": ["Auto", "Low", "Medium", "High"]})
        hass.states.async_set("sensor.0x60b763fffe1e67ae_power", "600")
        hass.states.async_set(FRIGATE, "on")

    config = await conf_util.async_hass_config_yaml(hass)
    for domain in ("input_boolean", "input_number", "input_datetime", "input_text",
                   "schedule", "template", "persistent_notification", "script",
                   "automation"):
        assert await async_setup_component(hass, domain, config), domain
    hass.services.async_register("persistent_notification", "create", fake_notification)
    s = Site(hass, freezer, ai, calls, flags, notifications, pushes, bell)
    if floor == "lt1":
        from functools import partial
        s.set_count = partial(s.set_count, floor="lt1")
    await s.settle(8)
    return s
