# Decisions

Each entry: the decision, the evidence, and what would change it. Dates are absolute.

## 2026-10-28: Gemini counts people, Frigate only triggers

* **Decision:** the people count used for AC levels comes from a Gemini image question. Frigate's occupancy sensor decides "someone is there / the room is empty" and triggers a count.
* **Evidence:** on 2026-10-28 around 11:20 WIB Frigate's `sensor.2nd_floor_person_count` showed 1 while the user said at least 4 people were present and all of them are in the camera's view. Over 2026-10-21 to 2026-10-28 working hours the count was 4 or more for about a minute a day. Frigate detects at 640x360 and drops a person who sits still after roughly 40 to 60 seconds, so seated staff are under-counted.
* **Cost:** about 50 calls a day for one floor, on the primary AI Task only.
* **Would change it if:** the count test shows Gemini is not accurate either, or the daily quota is a problem. Alternatives then: HD frames, a radar presence sensor, or a Frigate zone and model change (not in scope here).

## 2026-10-29: camera source is `camera.2nd_floor`; ignore a 0 while Frigate sees people

* **Decision:** Gemini gets its frame from `camera.2nd_floor`, the Frigate feed that other automations on the site already use. `camera.cctv_lt2` is not used. A Gemini count of 0 is ignored while `binary_sensor.2nd_floor_person_occupancy` is on.
* **Evidence:** the user says floor 2 has one physical camera, so `camera.2nd_floor` (Frigate feed) and `camera.cctv_lt2` (recorder feed) are presumed to be the same view; this was not compared on the same frame. With 4 people present, `camera.2nd_floor` gave 0, 4, 4 and then 4, 4, 4 (Frigate read 1 every time). The single 0 came with confidence 100, so the confidence threshold does not catch it. Per-round results: [plan-and-test.md](plan-and-test.md) phase 2.
* **Pass rule for a 3-round run:** at least 2 of 3 answers within 1 of the real count. Chosen with the user because the package uses only the latest accepted answer and ignores bad frames, so one wrong answer does not change the level (the earlier `max(prev, last)` rule was dropped on 2026-10-29, see below).
* **Would change it if:** the pilot shows repeated 0 or low counts from `camera.2nd_floor`; then compare `camera.cctv_lt2` (it may be sharper; its resolution was never checked) on the same head count.

## 2026-10-29: levels and recommended settings

* **Decision (with the user):** 4 levels. Empty 27 C / Low; few (1 to 2 people) 26 C / Low; normal (3 to 5) 20 C / Medium; busy (6 or more) 18 C / High. Every AC has its own entry (`left`, `middle`, `right`) with its own ranges, temperatures, fans and temperature limits, in one `SETTINGS` block of the package; the three start with the same numbers. Names in the package are English (the user asked for it).
* **Evidence:** floor 2 usually has 4 people a day (user); Gemini answered 3 or 4 for 4 people, so the "normal" range 3 to 5 holds both. The user said the room already feels cold and chose the low values 20 and 18 C; there is no comfort data behind them.
* **Limits:** the Sharp ACs cannot go below 18 C (LG: 16 C); each recommendation is clamped to its AC's own limits. The count package sends nothing, so the numbers can still change freely. Live control needs a comfort check and the user's approval per AC.
* **Would change it if:** the pilot shows the level flipping often, or staff report the recommended setting as too cold or too warm.
* **Superseded 2026-10-29** by "normal per AC" below: normal is 3 to 4 people, not 3 to 5, and the normal temperature now differs per AC.

## 2026-10-29: normal level is 3 to 4 people at 18 C (supersedes the 20 C normal; itself superseded by "normal per AC" below)

* **Decision (user, after the first accepted counts):** normal (3 to 4 people) now asks for 18 C with fan Medium; busy (5 or more) stays 18 C with fan High. Empty 27 C / Low and few (1 to 2) 26 C / Low are unchanged.
* **Why:** floor 2 usually has 4 people, and the user wants the coldest setting at that usual occupancy. 18 C is the Sharp's lowest setpoint, so normal and busy now differ only in fan speed.
* **Would change it if:** staff report 18 C as too cold or the room overcools; then raise the normal temperature again and re-run the offline tests before installing.

## 2026-10-29: live Sharp middle pilot, no shadow week

* **Decision:** prepare a separate optional control package for `climate.ac_sharp_lt_2_tengah`. Installation requires separate approval. Both the count switch and live-control switch stay off until individually enabled; the live-control switch reset off after a restart (superseded 2026-10-29: the switches now restore their last state, see below). The user decided no shadow week is needed; offline checks and the first-command approval still apply.
* **Constraints:** only while the Sharp is cooling and its plug is above 50 W with a fresh reading, during work hours with an occupied floor and a fresh accepted count. Only set temperature and fan; never send on/off. Record attempts before sending IR; do not resend an unchanged target automatically. Pause and disable on a direct HA user change; a physical remote cannot be detected. A power check after 15 minutes can confirm only that it is still on, not that it received the temperature/fan command. No automatic IR retries.
* **Evidence:** `climate.ac_sharp_lt_2_tengah` reports `Auto/Low/Medium/High` and 18–30 C. The power sensor reports about every 10 minutes and measures only on/off, not setpoint/fan. See [live-site.md](live-site.md).
* **Would change it if:** the first command fails at the physical unit, the sensor reports stale data, the counting automation is unreliable, or staff find the chosen setpoint uncomfortable. Turn the live switch off before changing control rules.

## 2026-10-28: own presence sensor

* **Decision:** build `binary_sensor.ac_lt2_occupied` from `binary_sensor.2nd_floor_person_occupancy` with its own off-delay.
* **Why:** HA already has `binary_sensor.floor2_staff_present`, a template owned by another automation package (Frigate occupancy plus a 390 s hold) whose hold time was still being tuned. Depending on it would let a change there alter AC behaviour without notice.
* **Data:** in 2026-10-21 to 2026-10-28 working hours the held sensor was off 1 to 86 minutes a day, raw Frigate occupancy 59 to 243 minutes a day.

## 2026-10-28: no auto-off in the pilot

* **Decision:** the count package computes and shows a recommended setting but never calls a `climate` service. The pilot never turns an AC off when the room is empty; level 0 means an energy-saving setting.
* **Why:** the ACs are controlled by Broadlink IR, which is one-way. HA cannot tell whether a command arrived, and manual remote changes are invisible except through the power sensor. A wrong "off" with people seated is worse than wasted energy.

## 2026-10-28: pilot scope

* Floor 2, temperature and fan speed. Floor 2 has three ACs: Sharp LT2 kiri, Sharp LT2 tengah and LG LT2. The first live AC will be Sharp LT2 tengah.

## 2026-10-29: normal per AC (left 18 C, middle and right 20 C)

* **Decision:** normal (3 to 4 people) is 18 C on the left Sharp and 20 C on the middle Sharp and the right LG, fan Medium on all three. Empty 27 C / Low, few (1 to 2) 26 C / Low and busy (5 or more) 18 C / High stay the same for every AC. `few_max` 2 and `normal_max` 4 are the same for all three.
* **State as deployed:** `packages/adaptive_cooling_lt2.yaml:97` (left `[27, 26, 18, 18]`), `:105` and `:113` (middle and right `[27, 26, 20, 18]`), fans `[Low, Low, Medium, High]` on all three. The split was already in the file when this entry was written; the reason for it was not recorded, so treat it as unconfirmed and ask the user before relying on it.
* **Why it matters:** the level table in the guide and the plan must show per-AC values. A single "normal = 18 C" statement is wrong for middle and right.
* **Would change it if:** staff report either unit as too cold or too warm; then change that AC's `temperature` list only, keep `min_temp`/`max_temp` unchanged, and re-run the offline checks before installing.

## 2026-10-29: per-unit switches restore their last state (no `initial:`)

* **Decision:** none of the helpers created by the two packages has `initial:`, including `input_boolean.ac_lt2_left/middle/right_control_enabled` and `input_boolean.ac_adaptive_count_enabled`. After a restart HA restores the last state instead of forcing every switch off.
* **Why:** an `initial:` value is applied again on every restart and on every reload of the helper domain, so a restart during the working day would silently stop control (and an `initial: false` would look like a failure), and a reload would fight the user's choice.
* **Consequence:** the first install still starts with every switch off, because a new `input_boolean` has no saved state. Rolling back therefore means turning the switch off explicitly, not restarting HA.
* **Would change it if:** a restart is ever observed to re-enable control unexpectedly, or the user asks for a guaranteed-safe start. Then add `initial: false` to the three control switches and accept that a restart pauses control.
