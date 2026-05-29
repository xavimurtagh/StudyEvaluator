const DEFAULTS = {
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
};

async function load() {
  const cfg = await chrome.storage.sync.get(DEFAULTS);
  document.getElementById("api").value = cfg.apiBase;
  document.getElementById("fe").value = cfg.frontendBase;
  document.getElementById("enable").checked = cfg.enableAutodetect;
  document.querySelectorAll("input[data-host]").forEach((el) => {
    el.checked = !!cfg.enabledHosts[el.dataset.host];
  });
}

async function save() {
  const enabledHosts = {};
  document.querySelectorAll("input[data-host]").forEach((el) => {
    enabledHosts[el.dataset.host] = el.checked;
  });
  await chrome.storage.sync.set({
    apiBase: document.getElementById("api").value.trim() || DEFAULTS.apiBase,
    frontendBase:
      document.getElementById("fe").value.trim() || DEFAULTS.frontendBase,
    enableAutodetect: document.getElementById("enable").checked,
    enabledHosts,
  });
  const saved = document.getElementById("saved");
  saved.hidden = false;
  setTimeout(() => (saved.hidden = true), 1500);
}

document.getElementById("save").addEventListener("click", save);
load();
