"""Checks on dashboards/ac_adaptive_lt2.yaml: read-only, entities exist, templates render.

Two kinds of template live in the dashboard:
* Jinja (`{{ }}`) in a few card options: rendered by real Home Assistant Core here.
* JavaScript (`[[[ ]]]`) in every `custom:button-card`: run with Node against fake states, the same
  way button-card runs it (`new Function(...)`), with a hass object that throws if it is touched.
"""

import html as htmllib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import push_dashboard  # noqa: E402

DASHBOARD = yaml.safe_load((ROOT / "dashboards/ac_adaptive_lt2.yaml").read_text(encoding="utf-8"))
RUNNER = ROOT / "tests/js_runner.js"
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")

ENTITY_RE = re.compile(r"\b(?:climate|sensor|binary_sensor|input_boolean|input_text|input_number|"
                       r"input_datetime|schedule)\.[a-z0-9_]+")
# Real devices the test harness does not create (the three ACs and the room temperature/humidity sensor).
SITE_ENTITIES = {"climate.ac_sharp_lt_2_kiri", "climate.ac_sharp_lt_2_tengah", "climate.ac_lg_2_2",
                 "sensor.0x84b4dbfffee9c73e_temperature", "sensor.0x84b4dbfffee9c73e_humidity"}
ENV_T = "sensor.0x84b4dbfffee9c73e_temperature"
ENV_H = "sensor.0x84b4dbfffee9c73e_humidity"
FAN_MODES = ["Auto", "Low", "Medium", "High"]
NOW = "2026-10-30T11:05:00+07:00"


def cards():
    """Every card, including cards nested in a stack or a custom field."""
    out = []

    def add(card):
        out.append(card)
        for sub in card.get("cards", []):
            add(sub)
        for field in card.get("custom_fields", {}).values():
            if isinstance(field, dict) and isinstance(field.get("card"), dict):
                add(field["card"])

    for view in DASHBOARD["views"]:
        for card in view.get("cards", []):
            add(card)
        for section in view.get("sections", []):
            for card in section.get("cards", []):
                add(card)
    return out


def body(card):
    return card["custom_fields"]["body"]


def button_cards():
    return [c for c in cards() if c["type"] == "custom:button-card" and "body" in c.get("custom_fields", {})]


def js(card):
    code = body(card)
    if code.startswith("[[[[") and code.rstrip().endswith("]]]]"):
        code = code.strip()[1:-1]  # nested button-card template
    assert code.startswith("[[[") and code.rstrip().endswith("]]]")
    return code.strip()[3:-3]


def by_marker(marker):
    found = [c for c in button_cards() if marker in body(c)]
    assert len(found) == 1, marker
    return found[0]


def run(card, states, now=NOW):
    assert NODE, "node missing"
    proc = subprocess.run([NODE, str(RUNNER)], input=json.dumps({"code": js(card), "states": states, "now": now}),
                          capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert "error" not in result, result["error"]
    return result["html"]


def s(state, **attributes):
    return {"state": state, "attributes": attributes}


def reading(state, reported):
    """A sensor state as button-card sees it: timestamps are top-level fields, not attributes."""
    return {"state": state, "attributes": {}, "last_reported": reported, "last_updated": reported}


def site_states(**over):
    """A believable floor 2: middle and right cooling, left off, 3 people."""
    states = {
        "input_boolean.ac_adaptive_count_enabled": s("on"),
        "schedule.ac_adaptive_hours": s("on"),
        "binary_sensor.ac_lt2_occupied": s("on"),
        "binary_sensor.ac_lt2_count_stale": s("off"),
        "sensor.ac_lt2_people": s("3", last_count_age_minutes=0),
        "sensor.ac_lt2_middle_recommended_temperature": s("20", level_name="normal"),
        "climate.ac_sharp_lt_2_kiri": s("off", temperature=18, fan_mode="Auto", fan_modes=FAN_MODES),
        "climate.ac_sharp_lt_2_tengah": s("cool", temperature=20, fan_mode="Medium", fan_modes=FAN_MODES),
        "climate.ac_lg_2_2": s("cool", temperature=19, fan_mode="Medium", fan_modes=FAN_MODES),
        "sensor.ac_lt2_left_status": s("AC mati, tidak diatur otomasi"),
        "sensor.ac_lt2_middle_status": s("ok"),
        "sensor.ac_lt2_right_status": s("Otomasi mati · saran 20 °C · Medium"),
        "input_boolean.ac_lt2_left_control_enabled": s("off"),
        "input_boolean.ac_lt2_middle_control_enabled": s("off"),
        "input_boolean.ac_lt2_right_control_enabled": s("off"),
        "sensor.ac_lt2_left_recommended_setting": s("20|Medium"),
        "sensor.ac_lt2_middle_recommended_setting": s("20|Medium"),
        "sensor.ac_lt2_right_recommended_setting": s("20|Medium"),
        "sensor.ac_lt2_activity": s("0", events=[], sent_by_day={}, people_peak_by_day={}),
        ENV_T: reading("26.3", "2026-10-30T10:30:00+07:00"),   # 35 minutes before NOW
        ENV_H: reading("54.53", "2026-10-30T10:30:00+07:00"),
    }
    states.update(over)
    return states


def text(fragment):
    """Visible text of a rendered fragment, as a browser would show it."""
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


# ---- read-only ------------------------------------------------------------------------------


def test_dashboard_is_read_only():
    assert push_dashboard.read_only_problems(DASHBOARD) == []


def test_every_button_card_has_no_entity_and_only_inert_actions():
    assert button_cards()
    for card in button_cards():
        assert "entity" not in card
        for key in ("tap_action", "hold_action", "double_tap_action"):
            assert card[key]["action"] in {"none", "navigate"}, key
        if card["tap_action"]["action"] == "navigate":
            assert card["tap_action"]["navigation_path"] == "/logbook"


def test_the_read_only_check_catches_dangerous_cards():
    cases = [
        {"type": "thermostat", "entity": "climate.ac_lg_2_2"},
        {"type": "custom:button-card", "entity": "climate.ac_lg_2_2", "tap_action": {"action": "none"},
         "hold_action": {"action": "none"}, "double_tap_action": {"action": "none"}},
        {"type": "custom:button-card", "tap_action": {"action": "none"}},
        {"type": "custom:button-card", "tap_action": {"action": "call-service"}, "hold_action": {"action": "none"},
         "double_tap_action": {"action": "none"}},
        {"type": "custom:button-card", "tap_action": {"action": "none"}, "hold_action": {"action": "none"},
         "double_tap_action": {"action": "none"},
         "custom_fields": {"body": "[[[ hass.callService('climate', 'turn_off', {}) ]]]"}},
    ]
    for card in cases:
        assert push_dashboard.read_only_problems({"views": [{"cards": [card]}]}), card


def test_no_javascript_template_can_reach_a_service():
    for card in button_cards():
        for forbidden in push_dashboard.FORBIDDEN_JS:
            assert forbidden not in body(card), forbidden


def test_dashboard_has_the_widgets_that_were_asked_for():
    kinds = [c["type"] for c in cards()]
    assert kinds.count("custom:button-card") == 6     # outer layout plus five content cards
    assert kinds.count("custom:stack-in-card") == 1   # 24 h chart
    assert kinds.count("custom:apexcharts-card") == 2  # temperature lines and people bars
    assert DASHBOARD["views"][0]["type"] == "sections"


def test_dashboard_has_an_empty_floor_one_tab_and_keeps_floor_two_first():
    assert DASHBOARD["title"] == push_dashboard.TITLE == "AC Adaptive"
    # The tab label is the view title; an icon would replace the text in the tab.
    assert [view["title"] for view in DASHBOARD["views"]] == ["LT2", "LT1"]
    assert [view["path"] for view in DASHBOARD["views"]] == ["lantai-2", "lantai-1"]
    assert all("icon" not in view for view in DASHBOARD["views"])
    assert DASHBOARD["views"][1]["sections"] == []


# ---- entities --------------------------------------------------------------------------------


async def test_every_entity_in_the_dashboard_exists(site):
    texts = list(push_dashboard.strings(DASHBOARD))
    names = {m for t in texts for m in ENTITY_RE.findall(t)}
    for card in cards():
        if card["type"] == "custom:apexcharts-card":
            names |= {x["entity"] for x in card["series"]}
    assert "sensor.ac_lt2_activity" in names and "sensor.ac_lt2_people" in names
    missing = sorted(n for n in names if site.hass.states.get(n) is None and n not in SITE_ENTITIES)
    assert missing == []


# ---- JavaScript templates, run with Node ---------------------------------------------------------


@needs_node
def test_header_shows_status_and_the_page_title():
    html = run(by_marker("Hitung orang aktif"), site_states())
    t = text(html)
    assert "AC Lantai 2" in t and "HOME ASSISTANT" not in t
    assert "Hitung orang aktif" in t and "Jam kerja 07–18" in t and "Terisi" in t
    assert "Jumat, 30 Okt 2026" in t and "11:05" in t


@needs_node
def test_header_when_counting_is_off_and_outside_hours():
    t = text(run(by_marker("Hitung orang aktif"), site_states(**{
        "input_boolean.ac_adaptive_count_enabled": s("off"),
        "schedule.ac_adaptive_hours": s("off"),
        "binary_sensor.ac_lt2_occupied": s("off")})))
    assert "Hitung orang mati" in t and "Di luar jam kerja" in t and "Kosong" in t


@needs_node
def test_summary_matches_the_mockup_numbers():
    t = text(run(by_marker("Orang di Lantai 2"), site_states()))
    assert "Orang di Lantai 2 3 orang" in t
    assert "Normal" in t and "dihitung 0 menit lalu" in t
    assert "AC menyala" not in t   # replaced by the room temperature and humidity tile
    assert "Setelan rata-rata 19,5 °C" in t
    assert "Kontrol otomatis Mati" in t and "Saran sistem: 20 °C · Medium" in t


@needs_node
def test_summary_when_every_ac_is_off_and_nobody_is_there():
    states = site_states(**{
        "binary_sensor.ac_lt2_occupied": s("off"),
        "climate.ac_sharp_lt_2_tengah": s("off", temperature=20, fan_mode="Low"),
        "climate.ac_lg_2_2": s("off", temperature=19, fan_mode="Low")})
    t = text(run(by_marker("Orang di Lantai 2"), states))
    assert "0 orang" in t and "Tidak ada orang" in t
    assert "Setelan rata-rata – " in t and "Tidak ada AC menyala" in t


@needs_node
def test_summary_counts_units_with_automatic_control_on():
    states = site_states(**{"input_boolean.ac_lt2_middle_control_enabled": s("on"),
                            "input_boolean.ac_lt2_right_control_enabled": s("on")})
    t = text(run(by_marker("Orang di Lantai 2"), states))
    assert "Kontrol otomatis 2 /3" in t and "Tengah, Kanan" in t


@needs_node
def test_summary_flags_an_old_count():
    t = text(run(by_marker("Orang di Lantai 2"), site_states(**{"binary_sensor.ac_lt2_count_stale": s("on")})))
    assert "data lama" in t


AC_MARKER = "climate.ac_sharp_lt_2_kiri"  # only the AC card mentions the entity id as visible text


def ac_cards(states):
    html = run(by_marker("'<article style="), states)
    return html.split("<article")[1:]


def one_ac(states, name):
    return next(c for c in ac_cards(states) if name in c)


@needs_node
@pytest.mark.parametrize("name, temperature, fan", [("Sharp Tengah", "20", "Medium"), ("LG Kanan", "19", "Medium")])
def test_ac_card_shows_the_current_mode_and_fan_once(name, temperature, fan):
    t = text(one_ac(site_states(), name))
    assert f"{temperature} °C" in t
    assert t.count("COOL") == 2                      # the pill and the label inside the ring
    assert t.count(f"Fan {fan}") == 1
    # No list of choices: none of the other modes or fan speeds appears.
    for other in ("Dry", "Fan only", "Auto", "Low", "High", "Heat"):
        assert other not in t, other


@needs_node
def test_ac_card_has_no_row_of_mode_or_fan_chips():
    html = run(by_marker("'<article style="), site_states())
    assert "height:30px;padding:0 12px" not in html   # the old chip style
    assert "MODE" not in text(html) and "KIPAS" not in text(html)


@needs_node
def test_off_ac_shows_mati_and_its_status_note_but_no_temperature():
    t = text(one_ac(site_states(), "Sharp Kiri"))
    assert "Mati" in t and t.count("OFF") == 2 and "Fan Auto" in t
    assert "AC mati, tidak diatur otomasi" in t
    assert "°C" not in t.replace("16°", "").replace("30°", "")


@needs_node
def test_status_note_is_hidden_when_the_ac_matches_the_target():
    middle = one_ac(site_states(), "Sharp Tengah")
    right = one_ac(site_states(), "LG Kanan")
    assert "background:#1A1710" not in middle      # status is "ok": no amber note
    assert "Otomasi mati · saran 20 °C · Medium" in text(right)


@needs_node
def test_status_notes_are_short():
    for note in ("Otomasi mati · saran 26 °C · Low", "AC mati, tidak diatur otomasi", "Di luar jam kerja",
                 "Menunggu hitungan orang", "Menunggu data daya AC", "Dijeda manual s/d 10:15",
                 "Akan ke 18 °C · High (± 4 mnt)", "Terkirim, belum sesuai"):
        assert len(note) <= 40, note


@needs_node
def test_ac_card_survives_missing_entities():
    cards = ac_cards({})
    assert len(cards) == 3
    assert all("Mati" in text(c) for c in cards)  # an unknown state is shown as off, never as a number


@needs_node
def test_text_in_the_cards_can_wrap():
    """button-card marks the field `ellipsis` (nowrap, overflow hidden), which cut long sentences."""
    for card in button_cards():
        style = card["styles"]["custom_fields"]["body"]
        assert {"white-space": "normal"} in style and {"overflow": "visible"} in style


@needs_node
def test_activity_timeline_renders_events():
    events = [
        {"unit": "middle", "kind": "sent", "value": "22|Medium", "time": "10:52:10", "ts": 1},
        {"unit": "right", "kind": "manual", "value": "manual change", "time": "09:52:54", "ts": 0},
        {"unit": "right", "kind": "control", "value": "off", "time": "09:52:54", "ts": 0},
    ]
    html = run(by_marker("Aktivitas perubahan setelan"),
               site_states(**{"sensor.ac_lt2_activity": s("1", events=events)}))
    t = text(html)
    assert "AC LT2 Tengah Perintah dikirim 22° · Medium 10:52:10" in t
    assert "Perubahan manual Manual" in t and "Kontrol otomatis Off" in t
    assert "Hari ini · 30 Oktober 2026" in t


@needs_node
def test_activity_timeline_groups_events_by_day():
    events = [
        {"unit": "middle", "kind": "sent", "value": "24|Medium", "time": "10:05:12", "ts": 3, "day": "2026-10-30"},
        {"unit": "right", "kind": "sent", "value": "26|Low", "time": "17:20:06", "ts": 2, "day": "2026-10-27"},
        {"unit": "left", "kind": "sent", "value": "26|Low", "time": "16:01:02", "ts": 1, "day": "2026-10-27"},
    ]
    html = run(by_marker("Aktivitas perubahan setelan"),
               site_states(**{"sensor.ac_lt2_activity": s("3", events=events)}))
    t = text(html)
    assert t.index("Hari ini · 30 Oktober 2026") < t.index("10:05:12") < t.index("Selasa · 27 Oktober 2026")
    assert t.index("Selasa · 27 Oktober 2026") < t.index("17:20:06") < t.index("16:01:02")
    assert t.count("Selasa · 27 Oktober 2026") == 1


@needs_node
def test_activity_timeline_does_not_call_old_events_today():
    """An event from an earlier day must never sit under a "Hari ini" header (Monday morning case)."""
    events = [{"unit": "right", "kind": "sent", "value": "26|Low", "time": "17:20:06", "ts": 1, "day": "2026-10-27"}]
    html = run(by_marker("Aktivitas perubahan setelan"),
               site_states(**{"sensor.ac_lt2_activity": s("1", events=events)}))
    t = text(html)
    assert "Hari ini" not in t
    assert "Selasa · 27 Oktober 2026" in t and "17:20:06" in t


@needs_node
def test_activity_timeline_when_empty():
    t = text(run(by_marker("Aktivitas perubahan setelan"), site_states()))
    assert "Belum ada perubahan tercatat" in t


@needs_node
def test_activity_timeline_shows_only_six_newest_events():
    events = [{"unit": "middle", "kind": "sent", "value": "20|Medium",
               "time": f"14:{minute:02d}:00", "ts": 8 - minute} for minute in range(8)]
    html = run(by_marker("Aktivitas perubahan setelan"),
               site_states(**{"sensor.ac_lt2_activity": s("8", events=events)}))
    assert html.count("<li ") == 6
    assert "14:05:00" in html and "14:06:00" not in html and "14:07:00" not in html


@needs_node
def test_summary_row_order_has_the_room_climate_tile_on_the_far_right():
    t = text(run(by_marker("Orang di Lantai 2"), site_states()))
    order = [t.index(x) for x in ("Orang di Lantai 2", "Setelan rata-rata", "Kontrol otomatis", "Suhu & kelembapan")]
    assert order == sorted(order)


@needs_node
def test_room_climate_tile_shows_temperature_and_humidity():
    t = text(run(by_marker("Orang di Lantai 2"), site_states()))
    assert "Suhu & kelembapan 26,3 °C 54,5 % 35 menit yang lalu" in t
    tile = t.split("Suhu & kelembapan")[1]
    assert "2nd Floor Workspace" not in tile and "dilaporkan" not in tile and "data lama" not in tile


@needs_node
def test_room_climate_tile_flags_an_old_reading_with_its_age():
    old = "2026-10-26T11:05:00+07:00"   # 4 days before NOW; the real sensor last reported on 2026-10-28
    states = site_states(**{ENV_T: reading("26.3", old), ENV_H: reading("54.53", old)})
    t = text(run(by_marker("Orang di Lantai 2"), states))
    tile = t.split("Suhu & kelembapan")[1]
    assert "26,3 °C" in tile and "54,5 %" in tile      # the old value is still shown, but labelled
    assert "4 hari yang lalu" in tile and "data lama" not in tile and "2nd Floor Workspace" not in tile


@needs_node
def test_room_climate_tile_prefers_last_reported_over_last_updated():
    """An unchanged value keeps an old last_updated but still reports; it must not look old."""
    fresh = {"state": "26.3", "attributes": {}, "last_updated": "2026-10-28T15:04:20+07:00",
             "last_reported": "2026-10-30T11:00:00+07:00"}
    t = text(run(by_marker("Orang di Lantai 2"), site_states(**{ENV_T: fresh, ENV_H: fresh})))
    assert "5 menit yang lalu" in t and "hari yang lalu" not in t


@needs_node
def test_room_climate_tile_colours_only_an_old_age_yellow():
    old = "2026-10-26T11:05:00+07:00"
    old_html = run(by_marker("Orang di Lantai 2"), site_states(**{ENV_T: reading("26.3", old), ENV_H: reading("54.5", old)}))
    fresh_html = run(by_marker("Orang di Lantai 2"), site_states())
    assert '<span style="color:#F5C46B">4 hari yang lalu</span>' in old_html
    assert "#F5C46B" not in fresh_html.split("Suhu &amp; kelembapan")[1]


@needs_node
def test_room_climate_values_sit_on_one_row_in_smaller_type():
    html = run(by_marker("Orang di Lantai 2"), site_states())
    tile = html.split("Suhu &amp; kelembapan")[1]
    assert "flex-wrap:nowrap" in tile and "font-size:38px" not in tile
    assert tile.count("font-size:30px") == 2 and tile.count("font-size:16px") == 2


@needs_node
def test_room_climate_tile_when_the_sensor_is_unavailable_or_missing():
    for states in (site_states(**{ENV_T: s("unavailable"), ENV_H: s("unavailable")}),
                   {k: v for k, v in site_states().items() if k not in (ENV_T, ENV_H)}):
        t = text(run(by_marker("Orang di Lantai 2"), states))
        tile = t.split("Suhu & kelembapan")[1]
        assert "Sensor tidak tersedia" in tile and "–" in tile
        assert "26" not in tile and "54" not in tile


def test_the_weekly_cards_are_not_on_the_dashboard_but_the_data_is_still_recorded():
    """User removed 'Orang terbanyak per hari', 'Perubahan setelan' and 'Tentang data ini' from the UI
    (2026-11-02). Only the UI: sensor.ac_lt2_activity keeps people_peak_by_day and sent_by_day."""
    everything = " ".join(body(c) for c in button_cards())
    for gone in ("Orang terbanyak per hari", "Perubahan setelan", "Tentang data ini"):
        assert gone not in everything, gone
    assert "label('AC menyala')" not in everything   # the removed summary tile
    package = (ROOT / "packages/adaptive_cooling_lt2_control.yaml").read_text(encoding="utf-8")
    assert "people_peak_by_day" in package and "sent_by_day" in package


@needs_node
def test_chart_legend_shows_names_without_values():
    t = text(run(by_marker("Suhu setelan AC"), site_states()))
    assert "Kiri Tengah Kanan Orang" in t
    for value in ("mati", "20°", "19°", "Orang 3", "Orang 2"):
        assert value not in t, value


@needs_node
def test_a_template_that_touches_hass_would_fail():
    evil = {"type": "custom:button-card", "custom_fields": {"body": "[[[ return hass.callService('a','b'); ]]]"}}
    proc = subprocess.run([NODE, str(RUNNER)], input=json.dumps({"code": js(evil), "states": {}}),
                          capture_output=True, text=True, encoding="utf-8")
    assert "touched hass" in json.loads(proc.stdout)["error"]


@needs_node
def test_text_in_the_cards_is_not_oversized():
    """The first version used huge text. Keep every font size in the cards at 52px or below."""
    sizes = []
    for card in button_cards():
        sizes += [int(x) for x in re.findall(r"font-size:\s*(\d+)px", body(card))]
    assert sizes and max(sizes) <= 52


def test_every_top_level_card_says_how_wide_it_is():
    """Without grid_options a card gets one column of the section, so the page looked like a phone
    on a wide desktop screen (2026-10-30). The responsive wrapper occupies the whole section."""
    sections = [sec for view in DASHBOARD["views"] for sec in view.get("sections", [])]
    assert sections
    for section in sections:
        assert section["cards"], section
        widths = [card["grid_options"]["columns"] for card in section["cards"]]
        assert widths == ["full"], widths


def test_chart_and_activity_share_one_responsive_section():
    view = DASHBOARD["views"][0]
    assert view["max_columns"] == 3
    assert [sec["column_span"] for sec in view["sections"]] == [3, 3, 3, 3]
    shared = view["sections"][3]["cards"]
    assert len(shared) == 1
    wrapper = shared[0]
    assert wrapper["custom_fields"]["chart"]["card"]["type"] == "custom:stack-in-card"
    activity = wrapper["custom_fields"]["activity"]["card"]
    assert activity["tap_action"] == {"action": "navigate", "navigation_path": "/logbook"}
    grid = wrapper["styles"]["grid"]
    assert {"grid-template-columns": "minmax(0, 2fr) minmax(0, 1fr)"} in grid
    assert {"align-items": "stretch"} in grid
    for field in ("chart", "activity"):
        assert {"height": "100%"} in wrapper["styles"]["custom_fields"][field]
    assert "height: 100%" in wrapper["custom_fields"]["chart"]["card"]["card_mod"]["style"]
    css = wrapper["extra_styles"]
    assert "container-type: inline-size" in css
    assert "@container (max-width: 900px)" in css
    assert "grid-template-areas: 'chart' 'activity'" in css


def test_chart_has_one_outer_border_and_unframed_inner_plots():
    chart = next(c for c in cards() if c["type"] == "custom:stack-in-card")
    assert "border: 1px solid #222B3A" in chart["card_mod"]["style"]
    plots = [c for c in chart["cards"] if c["type"] == "custom:apexcharts-card"]
    assert len(plots) == 2
    for plot in plots:
        style = plot["card_mod"]["style"]
        assert "border: 0 !important" in style and "padding: 0 !important" in style
        assert plot["hours_12"] is False
    temperature, people = plots
    assert "yaxis" not in temperature
    assert all("yaxis_id" not in series for series in temperature["series"])
    assert temperature["apex_config"]["yaxis"]["tickAmount"] == 7
    assert people["yaxis"][0]["apex_config"]["tickAmount"] == 2
    assert temperature["apex_config"]["yaxis"]["labels"]["minWidth"] == people["yaxis"][0]["apex_config"]["labels"]["minWidth"]
    assert [p["apex_config"]["grid"]["padding"]["left"] for p in plots] == [4, 4]
    assert [p["apex_config"]["grid"]["padding"]["right"] for p in plots] == [8, 8]
    assert "padding: 14px 14px 18px" in chart["card_mod"]["style"]
    assert plots[0]["apex_config"]["xaxis"]["labels"]["show"] is False
    time_labels = plots[1]["apex_config"]["xaxis"]["labels"]
    assert time_labels["show"] is True
    assert time_labels["style"]["fontSize"] == "12px"
    assert plots[1]["apex_config"]["grid"]["padding"]["bottom"] == 9
    # No end-of-line value labels: they reserved space and pushed the plot to the right.
    assert "dataLabels" not in plots[0]["apex_config"]
    assert [p["apex_config"]["grid"]["padding"]["right"] for p in plots] == [8, 8]
    bars = plots[1]["apex_config"]["plotOptions"]["bar"]
    assert bars["columnWidth"] == "65%" and bars["borderRadius"] == 3
    time_labels = plots[1]["apex_config"]["xaxis"]["labels"]
    assert time_labels["format"] == "HH:mm"
    assert "formatter" not in time_labels  # A tick may land at 11:20, not exactly on the hour.


def test_charts_are_short():
    chart = next(c for c in cards() if c["type"] == "custom:stack-in-card")
    heights = [c["apex_config"]["chart"]["height"] for c in chart["cards"] if c["type"] == "custom:apexcharts-card"]
    assert heights == [176, 150]
