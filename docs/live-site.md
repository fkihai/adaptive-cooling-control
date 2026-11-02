# Live site facts for ac-adaptive (read on 2026-10-28, read-only)

Home Assistant `https://aj9.iotera.cc`, version 2026.7.1, time zone Asia/Jakarta. This file holds only the facts this project uses.

## Floor 2 cameras and people sensors

* Frigate camera `camera.2nd_floor`; detect stream 640x360 at 1 fps.
* `binary_sensor.2nd_floor_person_occupancy`, `sensor.2nd_floor_person_count`, `sensor.2nd_floor_person_active_count` (people who move), `binary_sensor.2nd_floor_motion`, `sensor.2nd_floor_camera_fps`.
* Floor 2 has **one physical camera** (user, 2026-10-29). `camera.2nd_floor` is Frigate's feed of it (Frigate reads the RTSP stream `imou_lt2` from the HA host, detect stream 640x360). Generic cameras `camera.cctv_lt1` and `camera.cctv_lt2` share an IP-based name suffix (probably two channels of one recorder). The user confirmed `camera.cctv_lt2` shows floor 2, so it is presumably the same view as `camera.2nd_floor` through another path; resolution never checked. This project uses `camera.2nd_floor`.
* No physical presence sensor on floor 2. The sensors `Zemismart presence` (`0xa4c13857f235f01c`), `tes` (`0xa4c138ebc51e03ba`) and `Presence-Sensor-FP2-818F` exist, but their rooms are unknown.
* Observed 2026-10-28 around 11:20 WIB and again on 2026-10-29 about 09:52 to 09:57 WIB: Frigate counted 1 person while 4 were present. Gemini on `camera.2nd_floor` counted 4 in 5 of 6 answers (one answer was 0).
* An HTTP 404 comes back from `/api/error_log` on the REST API; the HA log is not readable that way.

## Floor 2 air conditioners (all Broadlink IR)

| AC | Climate entity | Power sensor | On threshold used by the old automations |
|----|----------------|--------------|------------------------------------------|
| Sharp LT2 kiri | `climate.ac_sharp_lt_2_kiri` | `sensor.0x60b763fffe1e451c_power` | above 50 W (this project; the old automation used 5 W) |
| Sharp LT2 tengah | `climate.ac_sharp_lt_2_tengah` | `sensor.0x60b763fffe1f48ee_power` | above 50 W |
| LG LT2 | `climate.ac_lg_2_2` | `sensor.0x60b763fffe1e67ae_power` | above 50 W |

* The mapping comes from the existing `automation.ac_lt2_*_on_by_power` and `_off_by_power` automations. Verify before relying on it.
* `climate.ac_lg_2_2` may duplicate `climate.ac_lg` (SmartIR). Confirm which one is used.
* Every climate entity reports `current_temperature` equal to its target, so it is not a room temperature. The only real temperature sensor found is `sensor.0x84b4dbfffee9c73e_temperature` (26.3 C), an Imou ZTM1 in the area 2nd Floor Workspace (checked 2026-11-02). **It last reported on 2026-10-28 15:04 WIB and its battery sensor reads 0**, so the dashboard tile shows its value as "data lama" until the battery is replaced.
* Modes and fan names differ per AC. Sharp LT2 kiri and tengah: fan `Auto`, `Low`, `Medium`, `High` (capitalised), 18 to 30 C, step 1. Use each entity's own `fan_modes` list.
* Existing automations `automation.ac_*_on_by_power` / `_off_by_power` keep helper booleans and selects in sync with the power sensors. Do not change them.
* Many old `script.ac_*` entries are `unavailable`; ignore them.

## Floor 2 AC positions (read 2026-10-29, confirmed by the user)

The three ACs are left (kiri), middle (tengah) and right (kanan) along one wall.

| Position | AC | Climate entity | Power sensor |
|----------|----|----------------|--------------|
| Left | Sharp | `climate.ac_sharp_lt_2_kiri` | `sensor.0x60b763fffe1e451c_power` |
| Middle | Sharp | `climate.ac_sharp_lt_2_tengah` | `sensor.0x60b763fffe1f48ee_power` |
| Right | LG | `climate.ac_lg_2_2` (not `climate.ac_lg`) | `sensor.0x60b763fffe1e67ae_power` |

* LG LT2 is `climate.ac_lg_2_2`: changing it ran `script.ac_lg_2_send_cool_code` in the logbook, and the dashboard pop-up "AC LG Kanan" shows its modes (Cool, Fan only, Off) and fan modes. `climate.ac_lg` is a separate SmartIR entity with other fan names.
* **The dashboard icons send real IR commands.** At about 10:21 to 10:22 WIB on 2026-10-29 the logbook shows mode changes on the Sharp kiri (auto, off) and the LG kanan (cool, then fan_only), made from the dashboard by a user. The user then reported the state: kiri off, tengah 18 C, kanan 16 C, all read from the dashboard, not from the units. Only open a pop-up to look; do not press its buttons.
* Related but not extra ACs: `binary_sensor.ac_lt2_kiri/tengah/kanan` (on/off from power), the `input_select` and `input_number` helpers of the old automations, and `climate.ac_sharp_lt_2_2`, `remote.ac_lt2`, `remote.ac_lg_lt_2` (unavailable leftovers). IR blasters: `text.0xf0fd45fffe5f9734_ir_code_to_send` (kiri), `text.0xbc8d7efffeff810a_ir_code_to_send` (tengah), `text.0xbc8d7efffeff73c6_ir_code_to_send` (LG).

## Floor 2 AC survey (phase 3, read-only, 2026-10-29 about 10:15 WIB, last 7 days)

Entity attributes now:

| Entity | State | HA setpoint / fan | Range | Fan modes | HVAC modes |
|--------|-------|-------------------|-------|-----------|------------|
| `climate.ac_sharp_lt_2_kiri` | off | 18 / Auto | 18 to 30, step 1 | Auto, Low, Medium, High | off, cool, dry, fan_only, auto |
| `climate.ac_sharp_lt_2_tengah` | cool | 18 / Auto | 18 to 30, step 1 | Auto, Low, Medium, High | off, cool, dry, fan_only, auto |
| `climate.ac_lg_2_2` | off | 16 / High | **16** to 30, step 1 | Auto, Low, Medium, High | off, cool, fan_only (no dry/auto) |
| `climate.ac_lg` (not floor 2 as far as known) | off | 18 / highest | 18 to 30 | lowest, low, mid, high, highest, auto | off, cool, dry, fan_only |

Findings:

* **The setpoint and fan in HA are not the real settings.** Over 7 days `climate.ac_sharp_lt_2_tengah` always showed 18 C (fan Auto or High) and `climate.ac_lg_2_2` always 16 C / High, while only the on/off state changed. Broadlink IR is one-way; HA shows the last commanded or assumed value. Before the pilot, ask the user what the AC is really set to.
* **The HA on/off state follows the power sensor.** The old `ac_*_on_by_power` automations set it. About 12 power readings of Sharp tengah (above 900 W) and 4 of LG were recorded while HA said `off`, so the HA state can lag the real state.
* **Power only tells on/off, not fan or setpoint.** Sharp tengah: about 900 to 1100 W whenever on, standby 18 to 21 W. LG: about 440 to 830 W (median 588 W) on, standby 27 to 28 W. HA recorded the same setpoint all week, so the power per fan speed cannot be separated from this data. The 50 W on-threshold works for both. Sharp kiri has reported 0 W continuously since 2026-10-28 (only standby-level readings before that), so the unit is off or unplugged; its control switch stays off until the plug reports power again.
* **The power sensors report about every 10 minutes** (median gap between readings 10 min). A check 2 minutes after a command cannot see a change that quickly. Settled in the pilot: the control script checks power state 15 minutes after a command, and treats a reading as fresh when `last_reported` is younger than 20 minutes (`last_changed` is wrong for this, because an unchanged wattage keeps its old `last_changed`).
* **Usage (power above 50 W, time-weighted):** Sharp tengah was on 44 h inside Mon-Fri 08:00-17:00 (the work hours at that time) and 32 h outside it, about 15 to 16 h a day on 2026-10-26 to 28, so it is left on into the evening. LG was on 25 h inside work hours and 32 h outside, on 4 of the 6 weekdays in the window (2026-10-22, 23, 26, 27; no power on 28). On 2026-10-29 it was switched on before the live pilot and has been cooling since. Neither ran on the weekend of 2026-10-24 and 25.
* **Which LG entity is floor 2:** settled on 2026-10-29, it is `climate.ac_lg_2_2` (see the positions table above). The first pilot AC was Sharp tengah; middle and right are both live since 2026-10-29, left stays off.
* The only room temperature sensor, `sensor.0x84b4dbfffee9c73e_temperature`, is in 2nd Floor Workspace (area name, 2026-11-02) and is silent since 2026-10-28 with battery 0.

## Areas and floors (read 2026-10-29, read-only)

HA has the floors `lantai_1` and `lantai_2`, but no Area is attached to a floor. Areas: `ruang_meeting_besar`, `2nd_floor_workspace`, `ruang_meeting_kecil`, `front_office`, `1st_floor_workspace`, `outdoor`. Most entities this project uses are in no Area: `camera.2nd_floor`, `binary_sensor.2nd_floor_person_occupancy`, `climate.ac_sharp_lt_2_kiri`, `climate.ac_sharp_lt_2_tengah` and the three AC power plugs. `climate.ac_lg_2_2` is in `2nd_floor_workspace`, together with the leftover `climate.ac_sharp_lt_2` (state `unknown`) and an unrelated plug (`sensor.0xa4c13813795610e2_power`, Almo Smart Socket 3). The three AC plugs have device names "AC Sharp Kiri LT 2", "AC Sharp Tengah LT 2" and "AC LG LT 2". HA has 11 `climate` entities in total, including floor 1 and meeting-room ACs. Why this matters: [plan-and-test.md](plan-and-test.md) phase 8.

## SSH access

* Terminal & SSH add-on (`core_ssh`), host alias `ha-lt2` (address, user and port only in the gitignored `credentials/ssh_config`), office network only. This repo has its own key: `credentials/ha_ssh_key` with the host key pinned in `credentials/ha_known_hosts`. Verified working 2026-10-29.
* Config root on the site is `/homeassistant`; the packages live in `/homeassistant/packages/` and `packages: !include_dir_named packages` is active in `configuration.yaml`.
* Never use another project's key and never expose this port through the tunnel.

## AI

`ai_task.google_ai_task` is the primary AI Task (`models/gemini-3.1-flash-lite`). Quota is shared with other automations on the site. Use `ai_task.generate_data` with `structure` for a typed answer.

## Energy

`sensor.energy_meter_daily_energy`, `sensor.energy_meter_monthly_energy`, `sensor.0x6ce4a4fffe5c4d9c_power` (whole-site meter). Per-AC power sensors above are the useful ones for checking commands.
