// Chat Catch-up: read one Google Sheet from inside a signed-in browser tab.
//
// HOW TO USE (Claude does this with the browser's JavaScript tool):
//   1. Open any page on https://docs.google.com/ in the tab (the sheet itself is ideal).
//   2. Paste this whole file, after editing SHEET_ID / TAB below. The last line is the result.
//
// WHY THIS WAY: Google Sheets draws its grid on a canvas, so reading the page text returns
// nothing. Fetching the sheet's "htmlview" pages from inside the page uses the user's own
// sign-in (no API keys, no downloads) and gives real row numbers and column letters, which is
// what makes it safe to write into the right cell later.
//
// Notes learned the hard way:
//   - /export?format=csv is blocked (cross-origin redirect), so it is not used.
//   - DOMParser/innerHTML are blocked on docs.google.com (Trusted Types), so the HTML is parsed
//     with plain string matching.
//   - Reading uses only fetch() GET requests. It changes nothing in the sheet.

const SHEET_ID = 'PASTE_SHEET_ID_HERE';   // the part after /spreadsheets/d/ in the link
const TAB = null;                         // null = first tab, or a tab name ('Sign-ups'), or a gid ('123456')
const MAX_ROWS = 500;                     // keeps the answer small; result.truncated tells you if it was cut
const FORCE_GVIZ = false;                 // true = skip htmlview and use the CSV fallback (for testing)

const result = await (async () => {
  const base = `/spreadsheets/d/${SHEET_ID}`;
  const unescJs = s => s
    .replace(/\\x([0-9a-fA-F]{2})/g, (_, h) => String.fromCharCode(parseInt(h, 16)))
    .replace(/\\u([0-9a-fA-F]{4})/g, (_, h) => String.fromCharCode(parseInt(h, 16)))
    .replace(/\\(.)/g, '$1');
  const NAMED = {amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' '};
  const decode = s => s.replace(/&(#x?[0-9a-fA-F]+|[a-z]+);/gi, (m, e) => {
    if (e[0] === '#') return String.fromCodePoint(e[1].toLowerCase() === 'x' ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10));
    return NAMED[e.toLowerCase()] ?? m;
  });
  const unwrap = href => {
    try {
      const u = new URL(href, location.origin);
      if (/(^|\.)google\.com$/.test(u.hostname) && u.pathname === '/url') return u.searchParams.get('q') || u.searchParams.get('url') || href;
      return u.href;
    } catch (e) { return href; }
  };
  const colLetters = i => { let s = '', n = i + 1; while (n) { const r = (n - 1) % 26; s = String.fromCharCode(65 + r) + s; n = Math.floor((n - 1) / 26); } return s; };
  const get = async url => {
    try { const r = await fetch(url, {credentials: 'include'}); return {status: r.status, type: r.headers.get('content-type') || '', text: await r.text()}; }
    catch (e) { return {status: 0, type: '', text: '', error: String(e)}; }
  };
  const clean = s => s.replace(/\t/g, ' ').replace(/\r?\n/g, ' ⏎ ').trim();
  const pick = (tabs) => {
    if (TAB === null) return tabs[0];
    return tabs.find(t => t.gid === String(TAB)) || tabs.find(t => t.name.toLowerCase() === String(TAB).toLowerCase());
  };

  // ---- Path A: htmlview (tab list + table with real row numbers and column letters) ----
  let tabs = [];
  if (!FORCE_GVIZ) {
    const page = await get(`${base}/htmlview`);
    tabs = [...page.text.matchAll(/items\.push\(\{name:\s*"((?:[^"\\]|\\.)*)",\s*pageUrl:\s*"((?:[^"\\]|\\.)*)",\s*gid:\s*"(-?\d+)"/g)]
      .map(m => ({name: unescJs(m[1]), url: unescJs(m[2]), gid: m[3]}));
  }
  if (tabs.length) {
    const tab = pick(tabs);
    if (!tab) return {ok: false, error: 'tab_not_found', tabs: tabs.map(({name, gid}) => ({name, gid}))};
    const res = await get(tab.url);
    const at = res.text.indexOf('<table');
    if (res.status !== 200 || at < 0) return {ok: false, error: 'tab_unreadable', status: res.status, tabs: tabs.map(({name, gid}) => ({name, gid}))};
    const table = res.text.slice(at, res.text.indexOf('</table>', at));
    const head = (table.match(/<thead>[\s\S]*?<\/thead>/) || [''])[0];
    const letters = [...head.matchAll(/<th id="[^"]*C\d+"[^>]*>([^<]*)<\/th>/g)].map(m => m[1].trim());
    const rows = [], links = [];
    for (const tr of table.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)) {
      const num = /<th[^>]*id="[^"]*R\d+"[^>]*>\s*<div[^>]*>(\d+)<\/div>/.exec(tr[1]);
      if (!num) continue;                                   // skips the frozen-row spacer lines
      let col = 0; const cells = [];
      for (const td of tr[1].matchAll(/<td\b([^>]*)>([\s\S]*?)<\/td>/g)) {
        let inner = td[2];
        inner = inner.replace(/<a\b[^>]*href="([^"]*)"[^>]*>/gi, (_, h) => {
          links.push({cell: `${letters[col] || colLetters(col)}${num[1]}`, href: unwrap(decode(h))}); return '';
        });
        cells[col] = decode(inner.replace(/<br\s*\/?>/gi, '\n').replace(/<[^>]+>/g, '')).trim();
        col += Number((/colspan="(\d+)"/.exec(td[1]) || [0, 1])[1]);
      }
      if (cells.some(c => c)) rows.push([Number(num[1]), cells]);
    }
    const width = Math.max(letters.length, ...rows.map(r => r[1].length), 0);
    while (letters.length < width) letters.push(colLetters(letters.length));
    const shown = rows.slice(0, MAX_ROWS);
    return {
      ok: true, id: SHEET_ID, source: 'htmlview',
      tabs: tabs.map(({name, gid}) => ({name, gid})), tab: {name: tab.name, gid: tab.gid},
      rows: rows.length, truncated: rows.length > shown.length,
      grid: ['#\t' + letters.join('\t'), ...shown.map(([n, c]) => n + '\t' + Array.from({length: width}, (_, i) => clean(c[i] || '')).join('\t'))].join('\n'),
      links,
    };
  }

  // ---- Path B: gviz CSV fallback (needs an explicit range so row 1 really is row 1) ----
  const param = TAB === null ? '' : (/^\d+$/.test(String(TAB)) ? `&gid=${TAB}` : `&sheet=${encodeURIComponent(TAB)}`);
  const res = await get(`${base}/gviz/tq?tqx=out:csv${param}&range=A1:AZ${MAX_ROWS}`);
  if (res.status !== 200 || !res.type.includes('csv')) {
    return {ok: false, error: 'no_access_or_not_found', status: res.status, hint: 'The signed-in account may not have access. Do not click "Request access" without asking the user.'};
  }
  const rows = []; let row = [], cell = '', quoted = false;
  for (let i = 0; i < res.text.length; i++) {
    const ch = res.text[i];
    if (quoted) { if (ch === '"' && res.text[i + 1] === '"') { cell += '"'; i++; } else if (ch === '"') quoted = false; else cell += ch; }
    else if (ch === '"') quoted = true;
    else if (ch === ',') { row.push(cell); cell = ''; }
    else if (ch === '\n') { row.push(cell); rows.push(row); row = []; cell = ''; }
    else if (ch !== '\r') cell += ch;
  }
  if (cell || row.length) { row.push(cell); rows.push(row); }
  const usedWidth = r => { let n = r.length; while (n && !r[n - 1].trim()) n--; return n; };
  const width = Math.max(0, ...rows.map(usedWidth));          // drop the empty columns the CSV pads on
  const letters = Array.from({length: width}, (_, i) => colLetters(i));
  const body = rows.map((r, i) => [i + 1, r]).filter(([, r]) => r.some(c => c.trim()));
  const domTabs = [...document.querySelectorAll('.docs-sheet-tab-name')].map(e => ({name: e.textContent.trim(), gid: null}));
  return {
    ok: true, id: SHEET_ID, source: 'gviz-csv', tabs: domTabs, tab: {name: TAB, gid: null},
    note: 'Fallback path: values come from a CSV view, so a text cell inside a mostly-numeric column can read as empty. Double-check anything important on screen.',
    rows: body.length, truncated: rows.length >= MAX_ROWS,
    grid: ['#\t' + letters.join('\t'), ...body.map(([n, r]) => n + '\t' + letters.map((_, i) => clean(r[i] || '')).join('\t'))].join('\n'),
    links: [],
  };
})();
result;
