// Content script: scan the page for known wellness products and annotate
// their first mention with a small inline badge that opens a verdict
// overlay on click. Conservative by default -- one badge per matched
// term per page, and we never touch <input>, <textarea>, or editable
// nodes.

(async function main() {
  const cfg = await chrome.storage.sync.get({
    enableAutodetect: true,
    enabledHosts: {},
  });
  if (!cfg.enableAutodetect) return;

  const host = location.hostname.replace(/^www\./, "");
  const allowed = Object.entries(cfg.enabledHosts).some(
    ([k, v]) => v && host.endsWith(k),
  );
  if (!allowed) return;

  let products;
  try {
    const res = await fetch(chrome.runtime.getURL("products.json"));
    products = (await res.json()).terms;
  } catch {
    return;
  }

  const pattern = buildPattern(products);
  const seen = new Set();

  // Run once at startup, then on DOM mutation (debounced) for SPAs.
  scan();
  const obs = new MutationObserver(debounce(scan, 500));
  obs.observe(document.body, { childList: true, subtree: true });

  function buildPattern(terms) {
    const esc = terms
      .map((t) => t.replace(/[-/\\^$*+?.()|[\]{}]/g, "\\$&"))
      .sort((a, b) => b.length - a.length)
      .join("|");
    return new RegExp(`\\b(${esc})\\b`, "gi");
  }

  function scan() {
    const walker = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_TEXT,
      {
        acceptNode(node) {
          if (!node.nodeValue || node.nodeValue.length < 4)
            return NodeFilter.FILTER_REJECT;
          const p = node.parentElement;
          if (!p) return NodeFilter.FILTER_REJECT;
          if (p.closest("script,style,textarea,input,.se-overlay,.se-badge"))
            return NodeFilter.FILTER_REJECT;
          if (p.isContentEditable) return NodeFilter.FILTER_REJECT;
          return NodeFilter.FILTER_ACCEPT;
        },
      },
    );
    const batch = [];
    while (walker.nextNode()) {
      batch.push(walker.currentNode);
      if (batch.length > 800) break; // cap work per scan
    }
    for (const node of batch) annotate(node);
  }

  function annotate(node) {
    const text = node.nodeValue;
    const m = pattern.exec(text);
    pattern.lastIndex = 0;
    if (!m) return;
    const term = m[1].toLowerCase();
    if (seen.has(term)) return;
    seen.add(term);

    const before = text.slice(0, m.index);
    const after = text.slice(m.index + m[0].length);
    const frag = document.createDocumentFragment();
    if (before) frag.appendChild(document.createTextNode(before));
    frag.appendChild(document.createTextNode(m[0]));
    const badge = document.createElement("span");
    badge.className = "se-badge";
    badge.textContent = "check evidence";
    badge.title = `What does the literature say about "${term}"?`;
    badge.addEventListener("click", (ev) => {
      ev.stopPropagation();
      openOverlay(term, badge);
    });
    frag.appendChild(badge);
    if (after) frag.appendChild(document.createTextNode(after));
    try {
      node.parentNode.replaceChild(frag, node);
    } catch {
      // Detached / removed during scan -- ignore.
    }
  }

  function openOverlay(term, anchor) {
    // Reuse one overlay element across clicks.
    document.querySelectorAll(".se-overlay").forEach((n) => n.remove());
    const el = document.createElement("div");
    el.className = "se-overlay";
    const rect = anchor.getBoundingClientRect();
    el.style.top = `${Math.min(rect.bottom + 6, window.innerHeight - 240)}px`;
    el.style.left = `${Math.min(rect.left, window.innerWidth - 340)}px`;
    el.innerHTML = `
      <button class="se-close" aria-label="close">×</button>
      <h3>${escapeHtml(term)}</h3>
      <p>Loading verdict…</p>
    `;
    document.body.appendChild(el);
    el.querySelector(".se-close").addEventListener("click", () => el.remove());

    chrome.runtime.sendMessage(
      { type: "STUDYEVAL_CHECK_CLAIM", text: term },
      async (resp) => {
        if (!resp?.ok) {
          el.querySelector("p").textContent =
            "Couldn't reach the StudyEvaluator API. Check the extension settings.";
          return;
        }
        await pollAndShow(el, term, resp.data);
      },
    );
  }

  async function pollAndShow(el, term, initial) {
    const jobId = initial.job.job_id;
    const slug = initial.job.slug;
    let product;
    if (jobId === "cached") {
      product = await getProduct(slug);
    } else {
      const { apiBase, frontendBase } = await chrome.storage.sync.get({
        apiBase: "http://localhost:8001",
        frontendBase: "http://localhost:3000",
      });
      const base = apiBase.replace(/\/$/, "");
      for (let i = 0; i < 60; i++) {
        const j = await fetch(`${base}/api/jobs/${jobId}`).then((r) =>
          r.json(),
        );
        if (j.state === "complete" && j.slug) {
          product = await getProduct(j.slug);
          break;
        }
        if (j.state === "error") {
          el.querySelector("p").textContent = `Error: ${j.message ?? ""}`;
          return;
        }
        await new Promise((r) => setTimeout(r, 800));
      }
      el.dataset.frontendBase = frontendBase;
    }
    if (!product) {
      el.querySelector("p").textContent = "Analysis timed out.";
      return;
    }
    renderProduct(el, term, product);
  }

  async function getProduct(slug) {
    return new Promise((res) => {
      chrome.runtime.sendMessage(
        { type: "STUDYEVAL_GET_PRODUCT", slug },
        (resp) => res(resp?.ok ? resp.data : null),
      );
    });
  }

  function renderProduct(el, term, p) {
    const match =
      p.claims.find((c) => c.claim.toLowerCase().includes(term)) ?? p.claims[0];
    const grade = match?.grade ?? p.overall_grade;
    const label = {
      strong: "Strong",
      moderate: "Moderate",
      weak: "Weak",
      insufficient: "Insufficient",
      contradicted: "Contradicted",
    }[grade] ?? grade;
    const fe = el.dataset.frontendBase ?? "http://localhost:3000";
    el.innerHTML = `
      <button class="se-close" aria-label="close">×</button>
      <span class="se-grade ${grade}">${label}</span>
      <h3>${escapeHtml(p.product)}</h3>
      <p>${escapeHtml(match?.plain_language ?? p.summary)}</p>
      <a href="${fe}/product/${p.slug}" target="_blank">Open full verdict →</a>
    `;
    el.querySelector(".se-close").addEventListener("click", () => el.remove());
  }

  function escapeHtml(s) {
    return String(s).replace(
      /[&<>"']/g,
      (c) =>
        ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[
          c
        ]),
    );
  }

  function debounce(fn, ms) {
    let t;
    return (...a) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...a), ms);
    };
  }
})();
