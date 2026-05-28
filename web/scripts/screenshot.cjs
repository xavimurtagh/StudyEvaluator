const puppeteer = require("puppeteer");
const path = require("path");

(async () => {
  const browser = await puppeteer.launch({
    headless: "new",
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 1100, deviceScaleFactor: 2 });
  const outDir = path.resolve(__dirname, "../../screens");

  // Pre-seed the client_id in localStorage so existing watches show up.
  await page.goto("http://127.0.0.1:3000/", { waitUntil: "domcontentloaded" });
  await page.evaluate(() => {
    localStorage.setItem("studyeval:client_id", "demo-id");
  });

  async function shot(url, out, fn) {
    await page.goto(url, { waitUntil: "networkidle0", timeout: 30000 });
    await new Promise((r) => setTimeout(r, 1000));
    if (fn) {
      await fn(page);
      await new Promise((r) => setTimeout(r, 500));
    }
    await page.screenshot({ path: path.join(outDir, out), fullPage: false });
    console.log("wrote", out);
  }

  await shot("http://127.0.0.1:3000/", "home_with_bell.png");
  await shot("http://127.0.0.1:3000/watches", "watches.png");
  await shot(
    "http://127.0.0.1:3000/product/collagen-peptides",
    "product_with_watch.png",
  );

  await browser.close();
})();
