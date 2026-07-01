const fs = require("fs");
const path = require("path");
const { pathToFileURL } = require("url");
const { chromium } = require("playwright");

const projectRoot = path.resolve(__dirname, "..");
const htmlPath = path.join(projectRoot, "web_control_panel", "index.html");
const outputDir = path.join(projectRoot, "artifacts");
const theme = process.argv[2] || process.env.CONTROL_PANEL_THEME || "obsidian";
const safeThemeName = theme.replace(/[^a-z0-9_-]/gi, "");
const screenshotPath = path.join(outputDir, `control-panel-${safeThemeName || "obsidian"}.png`);

async function main() {
  fs.mkdirSync(outputDir, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    viewport: { width: 1488, height: 904 },
    deviceScaleFactor: 1,
  });

  await page.goto(pathToFileURL(htmlPath).href, { waitUntil: "load" });
  const themeButton = page.locator(`[data-theme-option="${theme}"]`);
  if (await themeButton.count()) {
    await themeButton.click();
  }
  await page.waitForTimeout(800);

  const metrics = await page.evaluate(() => {
    const rect = (selector) => {
      const element = document.querySelector(selector);
      const box = element.getBoundingClientRect();
      return {
        top: Math.round(box.top),
        bottom: Math.round(box.bottom),
        height: Math.round(box.height),
        clientHeight: element.clientHeight,
        scrollHeight: element.scrollHeight,
        overflowY: getComputedStyle(element).overflowY,
      };
    };

    return {
      materialPanel: rect(".material-panel"),
      materialList: rect(".material-list"),
      statusBar: rect(".status-bar"),
      theme: document.body.dataset.theme || "obsidian",
    };
  });

  await page.screenshot({ path: screenshotPath, fullPage: false });
  await browser.close();

  const hasOverlap = metrics.materialList.bottom > metrics.statusBar.top;
  console.log(JSON.stringify({ screenshotPath, hasOverlap, metrics }, null, 2));

  if (hasOverlap) {
    process.exitCode = 1;
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
