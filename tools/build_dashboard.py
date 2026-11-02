"""Build dashboards/ac_adaptive_lt2.yaml (the "AC Lantai 2" dashboard) from Python.

Offline only: it writes a file in this repo and does not touch Home Assistant.

    python tools/build_dashboard.py

The design follows the mockup "Dashboard AC Lantai 2" (dark cards, rounded corners, a ring for the
setpoint). Most cards are `custom:button-card` WITHOUT an entity: one custom field returns HTML built
by a JavaScript template that only reads `states[...]`. The 24 hour chart is two `apexcharts-card`
inside a `stack-in-card`. Nothing here can change a device: every tap, hold and double-tap action is
"none" (the activity card only navigates to the Logbook), and tools/push_dashboard.py plus the tests
refuse a dashboard that breaks this.

Edit the cards here, regenerate, run `python run.py test`, then push with tools/push_dashboard.py.
"""
from pathlib import Path

import yaml


class NoAlias(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


FULL = {"columns": "full", "rows": "auto"}
NONE = {"action": "none"}
NO_TAP = {"tap_action": NONE, "hold_action": NONE, "double_tap_action": NONE}

# ---------------------------------------------------------------------------------------------
# Shared JavaScript. Every card template starts with this. It reads entities through `states[...]`
# (button-card watches whatever a template reads) and never calls a service.
# ---------------------------------------------------------------------------------------------
PRELUDE = r"""
const ACC = '#5CC8FF';
const st = (id) => { const s = states[id]; return s ? s.state : undefined; };
const at = (id, k) => { const s = states[id]; return (s && s.attributes) ? s.attributes[k] : undefined; };
const bad = (v) => v === undefined || v === null || v === 'unknown' || v === 'unavailable';
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const pad = (n) => String(n).padStart(2, '0');
const dayKey = (d) => d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
const DOW = ['Minggu', 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu'];
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'];
const UNITS = [
  { k: 'left', short: 'Kiri', name: 'Sharp Kiri', color: '#D47A12',
    climate: 'climate.ac_sharp_lt_2_kiri', status: 'sensor.ac_lt2_left_status',
    control: 'input_boolean.ac_lt2_left_control_enabled', rec: 'sensor.ac_lt2_left_recommended_setting' },
  { k: 'middle', short: 'Tengah', name: 'Sharp Tengah', color: '#4E8CF0',
    climate: 'climate.ac_sharp_lt_2_tengah', status: 'sensor.ac_lt2_middle_status',
    control: 'input_boolean.ac_lt2_middle_control_enabled', rec: 'sensor.ac_lt2_middle_recommended_setting' },
  { k: 'right', short: 'Kanan', name: 'LG Kanan', color: '#11A37C',
    climate: 'climate.ac_lg_2_2', status: 'sensor.ac_lt2_right_status',
    control: 'input_boolean.ac_lt2_right_control_enabled', rec: 'sensor.ac_lt2_right_recommended_setting' }
];
const MODES = {
  auto: ['Auto', 'M6 19 12 5l6 14M8.5 14h7'],
  cool: ['Cool', 'M12 3v18M4.2 7.5l15.6 9M4.2 16.5l15.6-9M9.5 4.5 12 7l2.5-2.5M9.5 19.5 12 17l2.5 2.5'],
  dry: ['Dry', 'M12 3.5s-6 6.8-6 10.9a6 6 0 0 0 12 0c0-4.1-6-10.9-6-10.9z'],
  fan_only: ['Fan only', 'M3 9h11a3 3 0 1 0-3-3M3 13h15a3 3 0 1 1-3 3M3 17h6'],
  heat: ['Heat', 'M12 3c3 4 5 6 5 9a5 5 0 0 1-10 0c0-3 2-5 5-9z'],
  off: ['Off', 'M12 3v8M6.3 6.8a8 8 0 1 0 11.4 0']
};
const FANS = {
  Auto: 'M6 19 12 5l6 14M8.5 14h7', Low: 'M6 19v-3',
  Medium: 'M6 19v-3M12 19v-7', High: 'M6 19v-3M12 19v-7M18 19v-11'
};
const icon = (d, color, w) => '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="' + color +
  '" stroke-width="' + (w || 2) + '" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="' + d + '"></path></svg>';
const isOff = (v) => bad(v) || v === 'off';
const num = (v) => { const n = parseFloat(v); return isNaN(n) ? null : n; };
const dec = (n) => Number.isInteger(n) ? String(n) : n.toFixed(1).replace('.', ',');
const CARD = 'background:#141A24;border:1px solid #222B3A;border-radius:24px;box-sizing:border-box;';
"""

HEADER_JS = r"""
const counting = st('input_boolean.ac_adaptive_count_enabled') === 'on';
const hours = st('schedule.ac_adaptive_hours') === 'on';
const occupied = st('binary_sensor.ac_lt2_occupied') === 'on';
const d = new Date();
const stamp = DOW[d.getDay()] + ', ' + d.getDate() + ' ' + MON[d.getMonth()] + ' ' + d.getFullYear() +
  ' · ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
const chip = (svg, text) => '<span style="display:inline-flex;align-items:center;gap:8px;height:32px;padding:0 12px;' +
  'border-radius:999px;background:#141A24;border:1px solid #222B3A;font-size:13px;color:#C9D2DF;white-space:nowrap">' +
  svg + text + '</span>';
const people = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="' + (counting ? '#7EE2B0' : '#9AA6B8') +
  '" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3.5"></circle><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 7M18.5 14.5a6.5 6.5 0 0 1 3 5.5"></path></svg>';
const clock = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="' + (hours ? '#7EE2B0' : '#9AA6B8') +
  '" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"></circle><path d="M12 7v5l3 2"></path></svg>';
const room = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="' + (occupied ? '#7EE2B0' : '#9AA6B8') +
  '" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 11l9-7 9 7v9H3z"></path></svg>';
return '<header style="display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px;padding:4px 0 0">' +
  '<span style="font-size:30px;font-weight:600;letter-spacing:-0.02em;line-height:1.1;color:#E8EDF5">AC Lantai 2</span>' +
  '<div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center">' +
  chip(people, counting ? 'Hitung orang aktif' : 'Hitung orang mati') +
  chip(clock, hours ? 'Jam kerja 07–18' : 'Di luar jam kerja 07–18') +
  chip(room, occupied ? 'Terisi' : 'Kosong') +
  chip('', stamp) + '</div></header>';
"""

SUMMARY_JS = r"""
const occupied = st('binary_sensor.ac_lt2_occupied') === 'on';
const count = parseInt(st('sensor.ac_lt2_people'), 10) || 0;
const level = at('sensor.ac_lt2_middle_recommended_temperature', 'level_name');
const age = parseInt(at('sensor.ac_lt2_people', 'last_count_age_minutes'), 10);
const stale = st('binary_sensor.ac_lt2_count_stale') === 'on';
const LEVELS = { empty: 'Kosong', few: 'Sedikit', normal: 'Normal', busy: 'Ramai' };
const rows = UNITS.map((u) => {
  const s = states[u.climate];
  return { u: u, mode: s ? s.state : undefined, temp: num(at(u.climate, 'temperature')),
           control: st(u.control) === 'on', rec: st(u.rec) };
});
const active = rows.filter((r) => !isOff(r.mode));
const controlled = rows.filter((r) => r.control);
const tile = (border, inner) => '<div style="' + CARD.replace('border:1px solid #222B3A', 'border:1px solid ' + border) +
  'border-radius:20px;padding:18px 20px;display:flex;flex-direction:column;gap:8px">' + inner + '</div>';
const label = (t) => '<span style="font-size:13px;color:#9AA6B8">' + t + '</span>';
const big = (t, color, unit) => '<div style="display:flex;align-items:baseline;gap:6px"><span style="font-size:38px;font-weight:600;line-height:1;color:' +
  (color || '#E8EDF5') + '">' + t + '</span>' + (unit ? '<span style="font-size:18px;color:#7D8798">' + unit + '</span>' : '') + '</div>';
const sub = (t) => '<span style="font-size:13px;color:#9AA6B8">' + t + '</span>';

const peopleSub = (occupied ? '<b style="color:#C9D2DF">' + (LEVELS[level] || '-') + '</b>' : 'Tidak ada orang') +
  (isNaN(age) ? '' : ' · dihitung ' + age + ' menit lalu') +
  (stale ? ' · <span style="color:#F5C46B">data lama</span>' : '');
const peopleTile = tile('#222B3A', label('Orang di Lantai 2') + big(occupied ? count : 0, null, 'orang') + sub(peopleSub));

const names = active.map((r) => r.u.short).join(' &amp; ');
const modeSet = Array.from(new Set(active.map((r) => (MODES[r.mode] || [r.mode])[0])));
const modeText = active.length === 0 ? 'Semua AC mati' : (modeSet.length === 1 ? 'mode ' + modeSet[0] : 'mode campuran');
const onTile = tile('#222B3A', label('AC menyala') +
  '<div style="display:flex;align-items:baseline;gap:4px"><span style="font-size:38px;font-weight:600;line-height:1">' + active.length +
  '</span><span style="font-size:20px;color:#7D8798">/' + rows.length + '</span></div>' +
  sub((active.length ? names + ' · ' : '') + modeText));

const temps = active.map((r) => r.temp).filter((t) => t !== null);
const avg = temps.length ? temps.reduce((a, b) => a + b, 0) / temps.length : null;
const avgTile = tile('#222B3A', label('Setelan rata-rata') +
  big(avg === null ? '–' : dec(avg), null, avg === null ? '' : '°C') +
  sub(avg === null ? 'Tidak ada AC menyala' : 'Dari AC yang menyala'));

const pick = rows.find((r) => !isOff(r.mode) && !r.control) || rows[1];
const recParts = (pick && !bad(pick.rec) && pick.rec.indexOf('|') > 0) ? pick.rec.split('|') : null;
const warn = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#F5B544" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3 2.5 20h19L12 3zM12 10v4M12 17.2v.1"></path></svg>';
let ctrlTile;
if (controlled.length === 0) {
  ctrlTile = tile('#3A2F1A', '<span style="display:inline-flex;align-items:center;gap:6px;font-size:13px;color:#9AA6B8">' + warn + 'Kontrol otomatis</span>' +
    big('Mati', '#F5C46B') +
    sub(recParts ? 'Saran sistem: <b style="color:#E8EDF5">' + esc(recParts[0]) + ' °C · ' + esc(recParts[1]) + '</b>' : 'Belum ada saran'));
} else {
  ctrlTile = tile('#222B3A', label('Kontrol otomatis') +
    '<div style="display:flex;align-items:baseline;gap:4px"><span style="font-size:38px;font-weight:600;line-height:1;color:#7EE2B0">' + controlled.length +
    '</span><span style="font-size:20px;color:#7D8798">/' + rows.length + '</span></div>' +
    sub(controlled.map((r) => r.u.short).join(', ')));
}
return '<section style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px">' +
  peopleTile + onTile + avgTile + ctrlTile + '</section>';
"""

AC_ROW_JS = r"""
const geom = (t) => {
  const f = Math.max(0, Math.min(1, (t - 16) / 14));
  const a = (135 + 270 * f) * Math.PI / 180;
  return { dash: (433.54 * f).toFixed(1) + ' 578.05', kx: (110 + 92 * Math.cos(a)).toFixed(1), ky: (110 + 92 * Math.sin(a)).toFixed(1) };
};
const cards = UNITS.map((u) => {
  const s = states[u.climate];
  const mode = s ? s.state : undefined;
  const a = (s && s.attributes) || {};
  const note = st(u.status);
  const off = isOff(mode);
  const t = num(a.temperature);
  const g = (!off && t !== null) ? geom(t) : { dash: '0 578.05', kx: 0, ky: 0 };
  const m = MODES[mode] || [bad(mode) ? 'N/A' : mode, MODES.off[1]];
  const modeLabel = off ? 'OFF' : m[0].toUpperCase();
  const fanName = bad(a.fan_mode) ? null : a.fan_mode;
  const pill = '<span style="display:inline-flex;align-items:center;gap:6px;height:26px;padding:0 10px;border-radius:999px;font-size:11px;font-weight:700;letter-spacing:0.08em;flex:none;' +
    (off ? 'background:#1C2330;color:#9AA6B8' : 'background:rgba(92,200,255,0.12);color:#A9E4FF') + '">' + icon(m[1], off ? '#9AA6B8' : ACC, 2.2) + modeLabel + '</span>';
  const center = off
    ? '<span style="font-size:40px;font-weight:500;color:#9AA6B8;line-height:1.1">Mati</span>'
    : '<div style="display:flex;align-items:flex-start;line-height:1"><span style="font-size:50px;font-weight:500;letter-spacing:-0.03em;color:#E8EDF5">' +
      (t === null ? '–' : dec(t)) + '</span><span style="font-size:18px;font-weight:500;color:#9AA6B8;margin-top:6px">°C</span></div>';
  const knob = off ? '' : '<circle cx="' + g.kx + '" cy="' + g.ky + '" r="9" fill="#0B0F16" stroke="#E8EDF5" stroke-width="3"></circle>';
  const glow = off ? '' : '<circle cx="110" cy="110" r="92" fill="none" stroke="' + ACC + '" stroke-width="14" stroke-linecap="round" stroke-dasharray="' +
    g.dash + '" transform="rotate(135 110 110)" style="filter:drop-shadow(0 0 10px rgba(92,200,255,0.55))"></circle>';
  const showNote = !bad(note) && note !== 'ok';
  return '<article style="' + CARD + 'padding:16px 18px;display:flex;flex-direction:column;gap:10px;white-space:normal">' +
    '<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:10px">' +
    '<div style="display:flex;align-items:center;gap:10px;min-width:0">' +
    '<svg width="10" height="10" viewBox="0 0 10 10" style="flex:none"><circle cx="5" cy="5" r="5" fill="' + u.color + '"></circle></svg>' +
    '<div style="display:flex;flex-direction:column;gap:2px;min-width:0"><span style="font-size:16px;font-weight:600;color:#E8EDF5">' + u.name + '</span>' +
    '<span style="font-size:10px;color:#8E9AAD;word-break:break-all">' + u.climate + '</span></div></div>' + pill + '</div>' +
    '<div style="position:relative;width:170px;height:170px;align-self:center">' +
    '<svg width="170" height="170" viewBox="0 0 220 220" style="overflow:visible">' +
    '<circle cx="110" cy="110" r="92" fill="none" stroke="#222B3A" stroke-width="14" stroke-linecap="round" stroke-dasharray="433.54 578.05" transform="rotate(135 110 110)"></circle>' +
    glow + knob +
    '<text x="46" y="205" fill="#7D8798" font-size="13" text-anchor="middle">16°</text>' +
    '<text x="174" y="205" fill="#7D8798" font-size="13" text-anchor="middle">30°</text></svg>' +
    '<div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px">' +
    '<span style="font-size:10px;font-weight:700;letter-spacing:0.16em;color:#8E9AAD">' + modeLabel + '</span>' + center +
    (fanName ? '<span style="font-size:12px;color:#9AA6B8">Fan ' + esc(fanName) + '</span>' : '') + '</div></div>' +
    (showNote ? '<div style="display:flex;align-items:flex-start;gap:8px;padding:8px 10px;border-radius:12px;background:#1A1710;border:1px solid #3A2F1A;font-size:12px;line-height:1.4;color:#E8D9B8">' +
      '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#F5B544" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex:none;margin-top:1px"><path d="M7 3h10M7 21h10M8 3c0 5 8 5 8 9s-8 4-8 9M16 3c0 5-8 5-8 9s8 4 8 9"></path></svg>' +
      '<span style="min-width:0">' + esc(note) + '</span></div>' : '') +
    '</article>';
});
return '<section style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;white-space:normal">' + cards.join('') + '</section>';
"""

CHART_HEAD_JS = r"""
const legend = UNITS.map((u) => '<span style="display:inline-flex;align-items:center;gap:6px"><svg width="14" height="4" viewBox="0 0 14 4"><rect width="14" height="4" rx="2" fill="' +
  u.color + '"></rect></svg>' + u.short + '</span>').join('');
return '<div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:6px">' +
  '<div style="display:flex;flex-direction:column;gap:4px"><span style="font-size:17px;font-weight:600;color:#E8EDF5">Suhu setelan AC &amp; jumlah orang</span>' +
  '<span style="font-size:12px;color:#8E9AAD">24 jam terakhir · perintah terakhir lewat IR</span></div>' +
  '<div style="display:flex;flex-wrap:wrap;gap:8px;font-size:12px;color:#C9D2DF">' + legend +
  '<span style="display:inline-flex;align-items:center;gap:6px"><svg width="10" height="10" viewBox="0 0 10 10"><rect width="10" height="10" rx="2" fill="#8B95A7"></rect></svg>Orang</span></div></div>';
"""

ACTIVITY_JS = r"""
const events = at('sensor.ac_lt2_activity', 'events') || [];
const MONTHS = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'];
const todayKey = dayKey(new Date());
// An event without a stored day (older data) counts as today.
const dayLabel = (key) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(key);
  if (!m) { return key; }
  const x = new Date(parseInt(m[1], 10), parseInt(m[2], 10) - 1, parseInt(m[3], 10));
  const date = x.getDate() + ' ' + MONTHS[x.getMonth()] + ' ' + x.getFullYear();
  return (key === todayKey ? 'Hari ini' : DOW[x.getDay()]) + ' · ' + date;
};
const U = {};
UNITS.forEach((u) => { U[u.k] = u; });
const describe = (e) => {
  if (e.kind === 'sent') {
    const p = String(e.value).split('|');
    return ['Perintah dikirim', p[0] + '° · ' + (p[1] || '')];
  }
  if (e.kind === 'manual') { return ['Perubahan manual', 'Manual']; }
  return ['Kontrol otomatis', e.value === 'on' ? 'On' : 'Off'];
};
const item = (e) => {
  const u = U[e.unit] || { short: e.unit, color: '#8B95A7' };
  const x = describe(e);
  return '<li style="display:flex;gap:12px"><div style="display:flex;flex-direction:column;align-items:center;width:12px">' +
    '<svg width="12" height="12" viewBox="0 0 12 12" style="margin-top:4px"><circle cx="6" cy="6" r="4.5" fill="#141A24" stroke="' + u.color + '" stroke-width="3"></circle></svg>' +
    '<div style="flex:1;width:2px;background:#222B3A;margin-top:4px"></div></div>' +
    '<div style="flex:1;display:flex;justify-content:space-between;gap:10px;padding-bottom:14px">' +
    '<div style="display:flex;flex-direction:column;gap:2px"><span style="font-size:14px;font-weight:600;color:#E8EDF5">AC LT2 ' + esc(u.short) + '</span>' +
    '<span style="font-size:12px;color:#8E9AAD">' + x[0] + '</span></div>' +
    '<div style="display:flex;flex-direction:column;align-items:flex-end;gap:2px"><span style="font-size:14px;font-weight:600;color:#E8EDF5">' + esc(x[1]) + '</span>' +
    '<span style="font-size:11px;color:#7D8798">' + esc(e.time) + '</span></div></div></li>';
};
const groups = [];
events.slice(0, 6).forEach((e) => {
  const key = e.day || todayKey;
  const last = groups[groups.length - 1];
  if (last && last.key === key) { last.items.push(item(e)); } else { groups.push({ key: key, items: [item(e)] }); }
});
const sections = groups.map((g) => '<div style="display:flex;flex-direction:column;gap:10px">' +
  '<div style="font-size:11px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:#8E9AAD">' + esc(dayLabel(g.key)) + '</div>' +
  '<ol style="list-style:none;margin:0;padding:0;display:flex;flex-direction:column">' + g.items.join('') + '</ol></div>');
return '<div style="' + CARD + 'padding:20px;display:flex;flex-direction:column;gap:14px;height:100%">' +
  '<div style="display:flex;justify-content:space-between;align-items:center;gap:10px"><div style="display:flex;flex-direction:column;gap:2px">' +
  '<span style="font-size:17px;font-weight:600;color:#E8EDF5">Aktivitas perubahan setelan</span>' +
  '<span style="font-size:12px;color:#8E9AAD">Perubahan terbaru</span></div>' +
  '<span style="display:inline-flex;align-items:center;justify-content:center;width:36px;height:36px;border-radius:12px;background:#1C2330;color:#C9D2DF">' +
  '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"></path></svg></span></div>' +
  (sections.length ? sections.join('')
    : '<span style="font-size:13px;color:#8E9AAD;line-height:1.5">Belum ada perubahan tercatat.</span>') +
  '</div>';
"""

WEEK_JS = r"""
const peaks = at('sensor.ac_lt2_activity', 'people_peak_by_day') || {};
const sent = at('sensor.ac_lt2_activity', 'sent_by_day') || {};
const now = new Date();
const days = [];
for (let i = 6; i >= 0; i--) {
  const x = new Date(now.getFullYear(), now.getMonth(), now.getDate() - i);
  days.push({ key: dayKey(x), dow: DOW[x.getDay()], short: DOW[x.getDay()].slice(0, 3), date: x.getDate(), mon: MON[x.getMonth()],
              n: parseInt(peaks[dayKey(x)], 10) || 0, today: i === 0 });
}
const maxN = Math.max.apply(null, days.map((x) => x.n));
const scale = Math.max(5, maxN);
const best = days.slice().sort((a, b) => b.n - a.n)[0];
const bars = days.map((x) => '<div style="display:flex;flex-direction:column;align-items:center;justify-content:flex-end;gap:6px;height:100%">' +
  '<span style="font-size:12px;font-weight:600;color:' + (x.n ? '#E8EDF5' : '#8E9AAD') + '">' + x.n + '</span>' +
  '<div style="width:100%;max-width:34px;height:' + Math.max(3, Math.round(x.n / scale * 130)) + 'px;background:' +
  (x.n === 0 ? '#2A3444' : (x.today ? '#C3CBD8' : '#8B95A7')) + ';border-radius:6px 6px 0 0"></div></div>').join('');
const labels = days.map((x) => '<div style="display:flex;flex-direction:column;align-items:center;gap:1px;font-size:11px;color:#7D8798"><span>' +
  x.short + '</span><span style="color:#9AA6B8;font-weight:600">' + x.date + '</span></div>').join('');
const totals = { left: 0, middle: 0, right: 0 };
Object.keys(sent).forEach((k) => { ['left', 'middle', 'right'].forEach((u) => { totals[u] += parseInt((sent[k] || {})[u], 10) || 0; }); });
const total = totals.left + totals.middle + totals.right;
const box = (cardStyle, inner) => '<div style="' + CARD + 'padding:20px;display:flex;flex-direction:column;gap:14px;' + cardStyle + '">' + inner + '</div>';
const head = (t, s) => '<div style="display:flex;flex-direction:column;gap:4px"><span style="font-size:17px;font-weight:600;color:#E8EDF5">' + t +
  '</span><span style="font-size:12px;color:#8E9AAD">' + s + '</span></div>';
const peopleCard = box('', head('Orang terbanyak per hari', '7 hari · ' + (maxN > 0 ? 'puncak <b style="color:#E8EDF5">' + best.n + ' orang</b> pada ' + best.dow + ', ' + best.date + ' ' + best.mon : 'belum ada data')) +
  '<div style="display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:6px;align-items:end;height:170px;border-bottom:1px solid #3A4558">' + bars + '</div>' +
  '<div style="display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:6px;margin-top:-6px">' + labels + '</div>');
const unitBox = UNITS.map((u) => '<div style="background:#10151E;border:1px solid #222B3A;border-radius:16px;padding:14px;display:flex;flex-direction:column;align-items:center;text-align:center;gap:6px">' +
  '<span style="display:inline-flex;align-items:center;gap:6px;font-size:12px;color:#9AA6B8"><svg width="8" height="8" viewBox="0 0 8 8"><circle cx="4" cy="4" r="4" fill="' + u.color + '"></circle></svg>' + u.short + '</span>' +
  '<span style="font-size:32px;font-weight:600;line-height:1;color:#E8EDF5">' + totals[u.k] + '</span></div>').join('');
const changeCard = box('', head('Perubahan setelan', 'Total 7 hari, per AC') +
  '<div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px">' + unitBox + '</div>' +
  '<span style="font-size:13px;color:#8E9AAD;line-height:1.5">' + (total === 0 ? 'Tidak ada perubahan setelan dalam 7 hari terakhir.' : total + ' setelan terkirim dalam 7 hari.') + '</span>');
const aboutCard = '<div style="background:#10151E;border:1px dashed #2A3444;border-radius:24px;padding:20px;display:flex;gap:12px;align-items:flex-start;box-sizing:border-box">' +
  '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="' + ACC + '" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex:none;margin-top:2px"><circle cx="12" cy="12" r="9"></circle><path d="M12 11v5.5M12 7.6v.1"></path></svg>' +
  '<div style="display:flex;flex-direction:column;gap:6px"><span style="font-size:15px;font-weight:600;color:#E8EDF5">Tentang data ini</span>' +
  '<p style="margin:0;font-size:13px;line-height:1.6;color:#B4BFCE">Angka suhu dan fan adalah perintah terakhir yang dikirim Home Assistant ke AC lewat IR. Dashboard ini hanya untuk dilihat; tidak ada tombol untuk mengubah AC. Remote fisik tidak terbaca oleh sistem.</p></div></div>';
return '<section style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px">' + peopleCard + changeCard + aboutCard + '</section>';
"""


def html_card(js, update_timer=None, tap=None, grid=None):
    """A button-card with no entity whose single field returns the HTML built by `js`."""
    code = "[[[\n" + (PRELUDE + js).strip() + "\n]]]"
    card = {
        "type": "custom:button-card",
        # A section is a 12-column grid per column_span; a card that does not say how wide it is gets 12
        # of those columns (one section column). "full" makes it fill the whole section.
        "grid_options": grid or FULL,
        "show_name": False,
        "show_icon": False,
        "show_state": False,
        "show_label": False,
        "show_ripple": False,
        "custom_fields": {"body": code},
        "styles": {
            "card": [{"background": "transparent"}, {"border": "none"}, {"box-shadow": "none"},
                     {"padding": "0"}, {"border-radius": "0"}, {"overflow": "visible"}],
            "grid": [{"grid-template-areas": '"body"'}, {"grid-template-columns": "1fr"},
                     {"grid-template-rows": "1fr"}],
            "custom_fields": {"body": [{"width": "100%"}, {"text-align": "left"}, {"font-family": "inherit"},
                                       {"white-space": "normal"}, {"overflow": "visible"},
                                       {"text-overflow": "clip"}, {"line-height": "1.35"}]},
        },
    }
    if tap:
        card["tap_action"] = tap
        card["hold_action"] = NONE
        card["double_tap_action"] = NONE
        card["styles"]["card"].append({"cursor": "pointer"})
    else:
        card.update(NO_TAP)
    if update_timer:
        card["update_timer"] = update_timer
    return card


def apex(series, yaxis, height, show_x):
    config = {
        "type": "custom:apexcharts-card",
        "graph_span": "24h",
        "update_delay": "3s",
        "header": {"show": False},
        "hours_12": False,
        "show": {"loading": False},
        "all_series_config": {"stroke_width": 2},
        "apex_config": {
            "chart": {"height": height, "background": "transparent", "foreColor": "#7D8798",
                      "toolbar": {"show": False}, "parentHeightOffset": 0},
            "legend": {"show": False},
            "grid": {"borderColor": "#222B3A", "strokeDashArray": 0,
                     "padding": {"left": 4, "right": 8, "top": 0, "bottom": 0}},
            "xaxis": {"labels": {"show": show_x}, "axisBorder": {"show": False}, "axisTicks": {"show": False}},
            "tooltip": {"theme": "dark"},
        },
        "series": series,
        # The outer stack is the only bordered card. ApexCharts' own ha-card would otherwise
        # draw two square frames inside it (one around each plot).
        "card_mod": {"style": "ha-card { background: transparent !important; border: 0 !important; "
                              "--ha-card-border-width: 0px; box-shadow: none !important; padding: 0 !important; }"},
    }
    if yaxis is not None:
        config["yaxis"] = yaxis
    return config


def temperature_chart():
    # No end-of-line value labels: they reserved space on the left of the plot and the current
    # values are already shown on the AC cards and the summary tiles above.
    series = []
    for entity, name, color in (("climate.ac_sharp_lt_2_kiri", "Kiri", "#D47A12"),
                                ("climate.ac_sharp_lt_2_tengah", "Tengah", "#4E8CF0"),
                                ("climate.ac_lg_2_2", "Kanan", "#11A37C")):
        series.append({"entity": entity, "attribute": "temperature", "name": name,
                       "curve": "stepline", "color": color})
    chart = apex(series, None, 176, show_x=False)
    # apexcharts-card creates one Y axis PER series when `yaxis:` is set (even when every series
    # uses the same yaxis_id). The extra hidden axes still consume horizontal space. Configure
    # a single shared ApexCharts axis instead, so this plot aligns with the one-series people plot.
    chart["apex_config"]["yaxis"] = {
        "min": 16, "max": 30, "tickAmount": 7, "decimalsInFloat": 0,
        "labels": {"minWidth": 36, "maxWidth": 36,
                   "formatter": "EVAL:function(v) { return [16,20,24,28].includes(Math.round(v)) ? Math.round(v) + '°' : ''; }"},
    }
    return chart


def people_chart():
    series = [{"entity": "sensor.ac_lt2_people", "name": "Orang", "type": "column", "color": "#8B95A7",
               "yaxis_id": "people", "group_by": {"func": "max", "duration": "1h"}}]
    yaxis = [{"id": "people", "min": 0, "max": "~6", "decimals": 0,
              "apex_config": {"tickAmount": 2, "labels": {"minWidth": 36, "maxWidth": 36}}}]
    chart = apex(series, yaxis, 150, show_x=True)
    chart["apex_config"]["plotOptions"] = {"bar": {"columnWidth": "65%", "borderRadius": 3}}
    # One shared time axis below both plots. Reserve space below the bars for readable labels.
    chart["apex_config"]["xaxis"]["labels"].update({
        "style": {"fontSize": "12px", "colors": "#A9B8CC"}, "offsetY": 3,
        "hideOverlappingLabels": True,
    })
    chart["apex_config"]["grid"]["padding"]["bottom"] = 9
    # ApexCharts chooses datetime tick positions itself. A JS formatter that required minutes == 0
    # returned empty strings for ticks at e.g. 11:20, hiding the entire time axis. Its native
    # datetime format always draws the tick, including at midnight, in 24-hour time.
    chart["apex_config"]["xaxis"]["labels"]["format"] = "HH:mm"
    return chart


def chart_card():
    return {
        "type": "custom:stack-in-card",
        "mode": "vertical",
        "cards": [html_card(CHART_HEAD_JS), temperature_chart(), people_chart()],
        "card_mod": {"style": ":host { height: 100%; display: block; } "
                              "ha-card { background: #141A24 !important; border: 1px solid #222B3A !important; "
                              "border-radius: 24px !important; box-shadow: none !important; "
                              "padding: 14px 14px 18px !important; height: 100%; box-sizing: border-box; }"},
    }


def chart_and_activity():
    """One full-width card: two columns on desktop, two full-width rows after zoom/mobile."""
    activity = html_card(ACTIVITY_JS, tap={"action": "navigate", "navigation_path": "/logbook"})
    activity["styles"]["card"].extend([{"height": "100%"}, {"box-sizing": "border-box"}])
    activity["styles"]["grid"].append({"height": "100%"})
    activity["styles"]["custom_fields"]["body"].append({"height": "100%"})
    activity["extra_styles"] = ":host { display: block; height: 100%; }"
    # Nested button-card templates use one additional pair of brackets: the outer card must
    # leave the inner JavaScript for the inner card to evaluate.
    activity["custom_fields"]["body"] = activity["custom_fields"]["body"].replace("[[[", "[[[[", 1)
    activity["custom_fields"]["body"] = activity["custom_fields"]["body"][:-3] + "]]]]"
    return {
        "type": "custom:button-card",
        "grid_options": FULL,
        "show_name": False, "show_icon": False, "show_state": False, "show_ripple": False,
        **NO_TAP,
        "styles": {
            "card": [{"background": "transparent"}, {"border": "0"}, {"box-shadow": "none"},
                     {"padding": "0"}, {"overflow": "visible"}],
            "grid": [{"grid-template-areas": '"chart activity"'},
                     {"grid-template-columns": "minmax(0, 2fr) minmax(0, 1fr)"},
                     {"grid-template-rows": "auto"}, {"gap": "12px"}, {"align-items": "stretch"}],
            "custom_fields": {"chart": [{"min-width": "0"}, {"height": "100%"}],
                              "activity": [{"min-width": "0"}, {"height": "100%"}]},
        },
        # Container queries follow the actual dashboard width, including HA's sidebar and browser zoom.
        "extra_styles": "ha-card { container-type: inline-size; } "
                        "@container (max-width: 900px) { #container { "
                        "grid-template-areas: 'chart' 'activity' !important; "
                        "grid-template-columns: minmax(0, 1fr) !important; } }",
        "custom_fields": {"chart": {"card": chart_card()}, "activity": {"card": activity}},
    }


def build():
    sections = [
        {"type": "grid", "column_span": 3, "cards": [html_card(HEADER_JS, update_timer=60000)]},
        {"type": "grid", "column_span": 3, "cards": [html_card(SUMMARY_JS)]},
        {"type": "grid", "column_span": 3, "cards": [html_card(AC_ROW_JS)]},
        {"type": "grid", "column_span": 3, "cards": [chart_and_activity()]},
        {"type": "grid", "column_span": 3, "cards": [html_card(WEEK_JS, update_timer=300000)]},
    ]
    return {
        "title": "AC Adaptive",
        # The tab label is the view title (HA shows an icon instead when one is set), so no icon here.
        "views": [{
            "title": "LT2",
            "path": "lantai-2",
            "type": "sections",
            "max_columns": 3,
            "sections": sections,
        }, {
            "title": "LT1",
            "path": "lantai-1",
            "type": "sections",
            "max_columns": 3,
            "sections": [],
        }],
    }


def main():
    out = Path(__file__).resolve().parent.parent / "dashboards" / "ac_adaptive_lt2.yaml"
    out.parent.mkdir(exist_ok=True)
    header = (
        "# Dashboard 'AC Adaptive' (storage dashboard url_path: ac-adaptive-lt2). GENERATED by\n"
        "# tools/build_dashboard.py: edit the builder, not this file or the dashboard in the HA UI.\n"
        "# Read-only on purpose: every tap, hold and double-tap action is 'none' (the activity card only\n"
        "# navigates to the Logbook) and there is no thermostat, climate or entity button card, so nothing\n"
        "# on this page can change an AC. Pushed to HA by tools/push_dashboard.py (needs --confirm).\n"
    )
    out.write_text(header + yaml.dump(build(), Dumper=NoAlias, sort_keys=False, allow_unicode=True,
                                       width=1000, default_flow_style=False), encoding="utf-8")
    print("written", out)


if __name__ == "__main__":
    main()
