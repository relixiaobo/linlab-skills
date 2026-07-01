#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i++) {
    const item = argv[i];
    if (!item.startsWith("--")) continue;
    const key = item.slice(2);
    const next = argv[i + 1];
    if (!next || next.startsWith("--")) {
      args[key] = true;
    } else {
      args[key] = next;
      i++;
    }
  }
  return args;
}

function required(args, key) {
  if (!args[key]) {
    console.error(`missing --${key}`);
    process.exit(2);
  }
  return args[key];
}

const args = parseArgs(process.argv);
const url = required(args, "url");
const outDir = required(args, "out-dir");
const width = Number(args.width || 1080);
const height = Number(args.height || 1920);
const fps = Number(args.fps || 30);
const duration = Number(args.duration || 5);
const waitMs = Number(args.wait || 500);

let chromium;
try {
  ({ chromium } = await import("playwright"));
} catch (error) {
  console.error("Playwright is not installed. Run: npm install playwright && npx playwright install chromium");
  process.exit(2);
}

await fs.mkdir(outDir, { recursive: true });

const browser = await chromium.launch({
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});

try {
  const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1 });
  await page.goto(url, { waitUntil: "networkidle" });
  await page.waitForTimeout(waitMs);

  const hasSeek = await page.evaluate(() => typeof window.__seek === "function");
  const totalFrames = Math.max(1, Math.round(duration * fps));

  for (let frame = 0; frame < totalFrames; frame++) {
    const seconds = frame / fps;
    if (hasSeek) {
      await page.evaluate(async (t) => {
        await window.__seek(t);
      }, seconds);
    } else if (frame > 0) {
      await page.waitForTimeout(1000 / fps);
    }
    const filename = `${String(frame + 1).padStart(6, "0")}.png`;
    await page.screenshot({ path: path.join(outDir, filename), fullPage: false });
    if (args["progress-json"]) {
      console.error(JSON.stringify({ stage: "item", frame: frame + 1, totalFrames, pct: Math.round(((frame + 1) / totalFrames) * 100) }));
    }
  }
} finally {
  await browser.close();
}

if (args["progress-json"]) {
  console.error(JSON.stringify({ stage: "complete", pct: 100, outDir }));
}
