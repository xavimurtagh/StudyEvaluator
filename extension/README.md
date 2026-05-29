# StudyEvaluator Chrome extension

Closes the loop on wellness misinformation: instead of leaving TikTok /
Instagram / Reddit / YouTube to fact-check a claim, the extension does
it inline.

## Two ways in

1. **Auto-detect.** The content script scans the page for mentions of
   common wellness ingredients (see `products.json`) and adds a small
   "check evidence" badge after the first hit. Click it to see the
   grade right there, with a link to the full verdict.
2. **Popup.** Click the toolbar icon, paste (or pre-fill from the
   selection) the claim you want checked, and hit "Fact-check."

## Install (unpacked)

1. Start the API and frontend locally
   (`scripts/run_api.py` + `cd web && npm run dev`).
2. Chrome → `chrome://extensions` → enable **Developer mode**.
3. **Load unpacked** → pick the `extension/` directory.
4. Optional: open the extension's options page to point it at a
   non-default API URL, or to disable auto-detect per site.

## Privacy

The extension only ever sends a short snippet — the highlighted product
term, or what you type into the popup — to the API. Full page content,
selections, browsing history: never transmitted, never stored.

## Files

- `manifest.json` — MV3 manifest, declares the content script's host
  matches.
- `popup.{html,js,css}` — toolbar popup.
- `content.{js,css}` — page scan + inline badge + overlay.
- `background.js` — service worker, proxies API calls to dodge strict
  page CSP.
- `options.{html,js}` — settings page.
- `products.json` — curated wellness-ingredient match list. Edit to
  expand coverage.
- `icons/` — generated placeholder icons.
