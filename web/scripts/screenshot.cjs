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

  async function shot(url, out, fn) {
    await page.goto(url, { waitUntil: "networkidle0", timeout: 30000 });
    await new Promise((r) => setTimeout(r, 500));
    if (fn) {
      await fn(page);
      await new Promise((r) => setTimeout(r, 400));
    }
    await page.screenshot({ path: path.join(outDir, out), fullPage: false });
    console.log("wrote", out);
  }

  await shot("http://127.0.0.1:3000/", "home.png");
  await shot(
    "http://127.0.0.1:3000/product/collagen-peptides",
    "product_top.png",
  );
  await shot(
    "http://127.0.0.1:3000/product/collagen-peptides",
    "product_claim_expanded.png",
    async (p) => {
      await p.evaluate(() => {
        const b = Array.from(document.querySelectorAll("button")).find((b) =>
          (b.textContent || "").startsWith("Show the studies behind"),
        );
        b && b.click();
      });
    },
  );
  await shot(
    "http://127.0.0.1:3000/product/collagen-peptides",
    "product_study_expanded.png",
    async (p) => {
      await p.evaluate(() => {
        // Scroll past claims to the studies section.
        const h2 = Array.from(document.querySelectorAll("h2")).find((h) =>
          (h.textContent || "").startsWith("All studies"),
        );
        h2 && h2.scrollIntoView({ behavior: "instant", block: "start" });
      });
      await new Promise((r) => setTimeout(r, 200));
      await p.evaluate(() => {
        const b = Array.from(document.querySelectorAll("button")).find((b) =>
          (b.textContent || "").startsWith("Show quality breakdown"),
        );
        b && b.click();
      });
    },
  );
  await shot("http://127.0.0.1:3000/about", "about.png");

  await browser.close();
})();
