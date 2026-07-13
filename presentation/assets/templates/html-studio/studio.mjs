#!/usr/bin/env node

import { access } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';

async function exists(file) {
  try {
    await access(file);
    return true;
  } catch {
    return false;
  }
}

const roots = [
  process.env.PRESENTATION_SKILL_DIR,
  path.join(process.env.CODEX_HOME || path.join(os.homedir(), '.codex'), 'skills', 'presentation'),
].filter(Boolean);

let tool = null;
for (const root of roots) {
  const candidate = path.join(root, 'scripts', 'studio_tool.mjs');
  if (await exists(candidate)) {
    tool = candidate;
    break;
  }
}

if (!tool) {
  console.error('Cannot locate presentation/scripts/studio_tool.mjs. Set PRESENTATION_SKILL_DIR.');
  process.exit(1);
}

const child = spawn(process.execPath, [tool, ...process.argv.slice(2)], {
  cwd: process.cwd(),
  stdio: 'inherit',
});
child.once('exit', (code, signal) => {
  if (signal) process.kill(process.pid, signal);
  else process.exit(code ?? 1);
});
