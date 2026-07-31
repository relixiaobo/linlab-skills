import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { chromium } from "playwright";

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, "../../../..");
const output = path.join(
  repo,
  "evals/cases/create-incident-response-launch/input/assets",
);
await mkdir(output, { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1700, height: 1700 } });
const url = pathToFileURL(path.join(here, "assets.html"));
const assets = [
  ["command-center", "signaldesk-command-center.png"],
  ["mobile-oncall", "signaldesk-mobile-oncall.png"],
  ["wordmark", "signaldesk-wordmark.png"],
  ["northstar-dashboard", "northstar-dashboard-decoy.png"],
];

for (const [asset, filename] of assets) {
  url.search = new URLSearchParams({ asset }).toString();
  await page.goto(url.href);
  await page.locator(`#${asset}`).screenshot({ path: path.join(output, filename) });
}

await browser.close();
