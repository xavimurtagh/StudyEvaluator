// MV3 service worker. Lightweight: just installs sensible defaults and
// proxies cross-origin API calls for content scripts (some sites have
// strict CSP that blocks fetch from page context).

chrome.runtime.onInstalled.addListener(async () => {
  const current = await chrome.storage.sync.get({
    apiBase: "http://localhost:8001",
    frontendBase: "http://localhost:3000",
    enableAutodetect: true,
    enabledHosts: {
      "tiktok.com": true,
      "instagram.com": true,
      "reddit.com": true,
      "twitter.com": true,
      "x.com": true,
      "youtube.com": true,
    },
  });
  await chrome.storage.sync.set(current);
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg?.type === "STUDYEVAL_CHECK_CLAIM") {
    (async () => {
      const { apiBase } = await chrome.storage.sync.get({
        apiBase: "http://localhost:8001",
      });
      const base = apiBase.replace(/\/$/, "");
      try {
        const r = await fetch(`${base}/api/check-claim`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: msg.text }),
        });
        sendResponse({ ok: r.ok, status: r.status, data: await r.json() });
      } catch (e) {
        sendResponse({ ok: false, error: String(e) });
      }
    })();
    return true; // async
  }
  if (msg?.type === "STUDYEVAL_GET_PRODUCT") {
    (async () => {
      const { apiBase } = await chrome.storage.sync.get({
        apiBase: "http://localhost:8001",
      });
      const base = apiBase.replace(/\/$/, "");
      try {
        const r = await fetch(`${base}/api/products/${msg.slug}`);
        sendResponse({ ok: r.ok, data: r.ok ? await r.json() : null });
      } catch (e) {
        sendResponse({ ok: false, error: String(e) });
      }
    })();
    return true;
  }
});
