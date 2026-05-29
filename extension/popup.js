async function getApiBase() {
  const { apiBase } = await chrome.storage.sync.get({
    apiBase: "http://localhost:8001",
  });
  return apiBase.replace(/\/$/, "");
}

async function getFrontendBase() {
  const { frontendBase } = await chrome.storage.sync.get({
    frontendBase: "http://localhost:3000",
  });
  return frontendBase.replace(/\/$/, "");
}

document.getElementById("opts").addEventListener("click", (e) => {
  e.preventDefault();
  chrome.runtime.openOptionsPage();
});

const claim = document.getElementById("claim");
const go = document.getElementById("go");
const status = document.getElementById("status");
const result = document.getElementById("result");
const openApp = document.getElementById("openApp");

// Pre-fill from any selected text on the active tab.
chrome.tabs.query({ active: true, currentWindow: true }).then(async ([tab]) => {
  if (!tab?.id) return;
  try {
    const [{ result: sel }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => window.getSelection()?.toString() ?? "",
    });
    if (sel && sel.length > 4 && sel.length < 280) claim.value = sel.trim();
  } catch {
    // Selection API failed (chrome:// pages, e.g.). No-op.
  }
});

getFrontendBase().then((b) => {
  openApp.href = b;
});

const GRADE_LABEL = {
  strong: "Strong",
  moderate: "Moderate",
  weak: "Weak",
  insufficient: "Insufficient",
  contradicted: "Contradicted",
};

go.addEventListener("click", async () => {
  const text = claim.value.trim();
  if (!text) return;
  go.disabled = true;
  status.hidden = false;
  status.textContent = "Searching the literature...";
  result.hidden = true;

  try {
    const api = await getApiBase();
    const r = await fetch(`${api}/api/check-claim`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!r.ok) throw new Error(`API ${r.status}`);
    const data = await r.json();
    await pollAndRender(api, data);
  } catch (e) {
    status.textContent = `Error: ${e.message}. Is the API running at ${
      await getApiBase()
    }?`;
  } finally {
    go.disabled = false;
  }
});

async function pollAndRender(api, data) {
  const jobId = data.job.job_id;
  const subject = data.subject;
  const fe = await getFrontendBase();

  if (jobId === "cached") {
    const v = await fetch(`${api}/api/products/${data.job.slug}`).then((r) =>
      r.json(),
    );
    renderVerdict(v, subject, fe);
    return;
  }

  for (let i = 0; i < 60; i++) {
    const j = await fetch(`${api}/api/jobs/${jobId}`).then((r) => r.json());
    status.textContent = j.message ?? "Working...";
    if (j.state === "complete" && j.slug) {
      const v = await fetch(`${api}/api/products/${j.slug}`).then((r) =>
        r.json(),
      );
      renderVerdict(v, subject, fe);
      return;
    }
    if (j.state === "error") {
      status.textContent = `Error: ${j.message ?? "pipeline failed"}`;
      return;
    }
    await new Promise((r) => setTimeout(r, 800));
  }
  status.textContent = "Timed out waiting for the analysis.";
}

function renderVerdict(verdict, subject, frontendBase) {
  status.hidden = true;
  result.hidden = false;
  // Pick the matching claim if any, else the first.
  const match =
    verdict.claims.find((c) =>
      c.claim.toLowerCase().includes(subject.toLowerCase()),
    ) ?? verdict.claims[0];
  const grade = match?.grade ?? verdict.overall_grade;
  result.innerHTML = "";
  const pill = document.createElement("span");
  pill.className = `grade grade-${grade}`;
  pill.textContent = GRADE_LABEL[grade] ?? grade;
  result.appendChild(pill);
  const subj = document.createElement("div");
  subj.className = "subject";
  subj.textContent = verdict.product;
  result.appendChild(subj);
  if (match) {
    const p = document.createElement("div");
    p.className = "notes";
    p.textContent = match.plain_language ?? match.claim;
    result.appendChild(p);
  }
  const link = document.createElement("a");
  link.href = `${frontendBase}/product/${verdict.slug}`;
  link.target = "_blank";
  link.style.cssText = "display:block;margin-top:8px;font-size:12px;";
  link.textContent = "Open full verdict →";
  result.appendChild(link);
}
