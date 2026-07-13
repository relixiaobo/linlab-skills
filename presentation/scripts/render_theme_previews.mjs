#!/usr/bin/env node

import { spawn } from 'node:child_process';
import { access, mkdtemp, readFile, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.dirname(SCRIPT_DIR);
const THEMES_ROOT = path.join(ROOT, 'assets', 'themes');
const INDEX_PATH = path.join(THEMES_ROOT, 'index.json');
const PREVIEW_PAGE = path.join(ROOT, 'assets', 'theme-preview', 'index.html');

async function exists(file) {
  try {
    await access(file);
    return true;
  } catch {
    return false;
  }
}

function run(command, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { stdio: ['ignore', 'pipe', 'pipe'] });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (chunk) => { stdout += chunk; });
    child.stderr.on('data', (chunk) => { stderr += chunk; });
    child.once('error', reject);
    child.once('close', (code) => {
      if (code === 0) resolve({ stdout, stderr });
      else reject(new Error(`${command} exited ${code}: ${(stderr || stdout).trim()}`));
    });
  });
}

async function executable(candidates) {
  for (const candidate of candidates) {
    if (candidate.includes(path.sep)) {
      if (await exists(candidate)) return candidate;
      continue;
    }
    try {
      const result = await run(process.platform === 'win32' ? 'where' : 'which', [candidate]);
      const resolved = result.stdout.trim().split(/\r?\n/)[0];
      if (resolved) return resolved;
    } catch {
      // Try the next candidate.
    }
  }
  return null;
}

async function main() {
  const requested = process.argv.slice(2).filter((value) => !value.startsWith('-'));
  const index = JSON.parse(await readFile(INDEX_PATH, 'utf8'));
  const known = new Map(index.themes.map((theme) => [theme.id, theme]));
  const ids = requested.length > 0 ? requested : [...known.keys()];
  for (const id of ids) {
    if (!known.has(id)) throw new Error(`Unknown theme: ${id}`);
  }

  const chrome = await executable(process.platform === 'darwin'
    ? ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge']
    : ['google-chrome', 'chromium', 'chromium-browser']);
  const ffmpeg = await executable(['ffmpeg']);
  const cwebp = await executable(['cwebp']);
  const python = await executable(['python3', 'python']);
  if (!chrome) throw new Error('Chrome or Chromium is required to render theme previews');

  async function encodeWebp(png, output) {
    if (ffmpeg) {
      try {
        await run(ffmpeg, ['-y', '-loglevel', 'error', '-i', png, '-c:v', 'libwebp', '-q:v', '84', output]);
        return 'ffmpeg';
      } catch {
        // Continue to portable fallbacks when ffmpeg lacks libwebp.
      }
    }
    if (cwebp) {
      await run(cwebp, ['-quiet', '-q', '84', png, '-o', output]);
      return 'cwebp';
    }
    if (python) {
      await run(python, [
        '-c',
        'from PIL import Image; import sys; Image.open(sys.argv[1]).convert("RGB").save(sys.argv[2], "WEBP", quality=84, method=6)',
        png,
        output,
      ]);
      return 'pillow';
    }
    throw new Error('WebP encoding requires ffmpeg with libwebp, cwebp, or Python Pillow');
  }

  const temporary = await mkdtemp(path.join(os.tmpdir(), 'presentation-theme-previews-'));
  const rendered = [];
  try {
    for (const id of ids) {
      const png = path.join(temporary, `${id}.png`);
      const output = path.join(THEMES_ROOT, id, 'preview.webp');
      const url = new URL(pathToFileURL(PREVIEW_PAGE));
      url.searchParams.set('theme', id);
      await run(chrome, [
        '--headless=new',
        '--hide-scrollbars',
        '--disable-gpu',
        '--no-sandbox',
        '--force-device-scale-factor=1',
        '--window-size=1200,675',
        '--virtual-time-budget=1200',
        `--screenshot=${png}`,
        url.href,
      ]);
      const encoder = await encodeWebp(png, output);
      rendered.push({ id, output, encoder });
    }
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }

  process.stdout.write(`${JSON.stringify({ rendered }, null, 2)}\n`);
}

main().catch((error) => {
  console.error(`render-theme-previews: ${error.message}`);
  process.exitCode = 1;
});
