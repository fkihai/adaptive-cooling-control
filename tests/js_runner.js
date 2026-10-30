// Runs one button-card JavaScript template the way button-card does:
//   new Function("states","entity","user","hass","variables","html","helpers", "'use strict'; " + code)
// Input (stdin, JSON): {code, states}. Output (stdout, JSON): {html} or {error}.
// A Proxy makes any call to a service/connection method throw, so a template that tried to act would fail.
const chunks = [];
process.stdin.on('data', (c) => chunks.push(c));
process.stdin.on('end', () => {
  const { code, states, now } = JSON.parse(Buffer.concat(chunks).toString('utf8'));
  const RealDate = Date;
  if (now) {
    global.Date = class extends RealDate {
      constructor(...a) { if (a.length === 0) { super(now); } else { super(...a); } }
      static now() { return new RealDate(now).getTime(); }
    };
  }
  const forbidden = new Proxy({}, { get: (_, k) => { throw new Error('template touched hass.' + String(k)); } });
  try {
    const fn = new Function('states', 'entity', 'user', 'hass', 'variables', 'html', 'helpers', "'use strict'; " + code);
    const out = fn.call({}, states, undefined, {}, forbidden, {}, (s) => s, {});
    process.stdout.write(JSON.stringify({ html: String(out) }));
  } catch (e) {
    process.stdout.write(JSON.stringify({ error: String(e && e.message || e) }));
  }
});
