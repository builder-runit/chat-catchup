// Chat Catch-up: list every link in the page that is open, with its REAL address.
//
// WHY: reading page text drops the addresses behind link text ("here's the sheet" -> no URL).
// Run this in the browser's JavaScript tool on the open Google Chat conversation, right after
// reading its text, and put the result in each message's "links" list.
//
// It only reads. It skips Google's own navigation (account menu, help, policies) and image
// hosts (profile pictures), and unwraps google.com/url?q=... redirect wrappers.
//
// The query string and #fragment are REMOVED from every address. Claude in Chrome refuses to
// return text that contains query strings ("[BLOCKED: Cookie/query string data]"), which would
// make the whole result unreadable. Sheets, Docs and Forms are identified by the id in the path,
// so nothing is lost; a Sheets tab id (#gid=123) is kept in the separate "gid" field.

const links = (() => {
  const SKIP_HOSTS = /^(accounts|support|myaccount|policies|workspace|contacts|ogs)\.google\.com$|^www\.google\.com$|googleusercontent\.com$|gstatic\.com$/i;
  const unwrap = href => {
    try {
      const u = new URL(href);
      if (/(^|\.)google\.com$/i.test(u.hostname) && u.pathname === '/url') return u.searchParams.get('q') || u.searchParams.get('url') || href;
      return u.href;
    } catch (e) { return href; }
  };
  const seen = new Set(), out = [];
  for (const a of document.querySelectorAll('a[href]')) {
    if (a.closest('header, nav, [role="navigation"], [role="banner"]')) continue;
    let u; try { u = new URL(unwrap(a.href)); } catch (e) { continue; }
    if (!/^https?:$/i.test(u.protocol)) continue;
    if (SKIP_HOSTS.test(u.hostname) || /^chat\.google\.com$/i.test(u.hostname)) continue;   // navigation, not content
    const gid = (u.hash.match(/gid=(-?\d+)/) || u.search.match(/[?&]gid=(-?\d+)/) || [])[1] || null;
    const href = u.origin + u.pathname;                      // no query string, no fragment
    const key = href + '|' + (gid || '');
    if (seen.has(key)) continue;
    seen.add(key);
    const item = {href, text: (a.textContent || '').trim().slice(0, 80)};
    if (gid) item.gid = gid;
    out.push(item);
  }
  return out;
})();
links;
