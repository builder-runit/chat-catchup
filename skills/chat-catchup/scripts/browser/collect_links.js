// Chat Catch-up: list every link in the page that is open, with its REAL address.
//
// WHY: reading page text drops the addresses behind link text ("here's the sheet" -> no URL).
// Run this in the browser's JavaScript tool on the open Google Chat conversation, right after
// reading its text, and put the result in each message's "links" list.
//
// It only reads. It skips Google's own navigation (account menu, help, policies) and unwraps
// google.com/url?q=... redirect wrappers.

const links = (() => {
  const SKIP_HOSTS = /^(accounts|support|myaccount|policies|workspace|contacts|ogs)\.google\.com$|^www\.google\.com$/i;
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
    const href = unwrap(a.href);
    if (!/^https?:\/\//i.test(href) || seen.has(href)) continue;
    let host; try { host = new URL(href).hostname; } catch (e) { continue; }
    if (SKIP_HOSTS.test(host) || /^chat\.google\.com$/i.test(host)) continue;   // navigation, not content
    seen.add(href);
    out.push({href, text: (a.textContent || '').trim().slice(0, 80)});
  }
  return out;
})();
links;
