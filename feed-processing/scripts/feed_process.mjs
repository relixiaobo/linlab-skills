#!/usr/bin/env node
import {
  asArray,
  parseArgs,
  parseSourceList,
  readJson,
  readText,
  writeJson,
} from './lib/feed_common.mjs';
import {
  FEED_PROCESSING_SCHEMA_VERSION,
  feedProcessingCapabilities,
  processFeedRequest,
  validateProcessingResult,
} from './lib/feed_runtime.mjs';

const args = parseArgs(process.argv.slice(2));
const command = args._[0] || 'process';

if (args.help || args.h) {
  printUsage();
  process.exit(0);
}

if (command === 'capabilities') {
  await writeJson(args.out, feedProcessingCapabilities());
} else if (command === 'validate') {
  const input = await readStructuredInput(args.input);
  const report = validateProcessingResult(input);
  await writeJson(args.out, report);
  if (!report.ok) process.exitCode = 1;
} else if (command === 'process') {
  const request = await buildRequest(args);
  const result = await processFeedRequest(request);
  await writeJson(args.out, result);
  if (!result.validation.ok || (request.strictness === 'strict' && result.coverage.failedSources > 0)) process.exitCode = 1;
} else {
  console.error(`Unknown command: ${command}`);
  printUsage();
  process.exit(2);
}

async function buildRequest(cliArgs) {
  let request;
  const urls = asArray(cliArgs.url);
  if (urls.length) {
    request = { sources: urls.map((inputUrl) => ({ inputUrl })) };
  } else {
    const text = await readInputText(cliArgs.input);
    request = parseRequestText(text, cliArgs.input || 'stdin');
  }

  request.schemaVersion ||= FEED_PROCESSING_SCHEMA_VERSION;
  request.scope ||= { mode: 'all' };
  request.limits = {
    ...(request.limits || {}),
    ...(cliArgs.timeoutMs ? { timeoutMs: Number(cliArgs.timeoutMs) } : {}),
    ...(cliArgs.maxBytes ? { maxBytes: Number(cliArgs.maxBytes) } : {}),
    ...(cliArgs.maxRedirects !== undefined ? { maxRedirects: Number(cliArgs.maxRedirects) } : {}),
    ...(cliArgs.maxCandidates ? { maxCandidates: Number(cliArgs.maxCandidates) } : {}),
    ...(cliArgs.maxDiscoveryDepth !== undefined ? { maxDiscoveryDepth: Number(cliArgs.maxDiscoveryDepth) } : {}),
    ...(cliArgs.concurrency ? { concurrency: Number(cliArgs.concurrency) } : {}),
  };
  request.discovery = {
    ...(request.discovery || {}),
    ...(cliArgs['no-common'] ? { includeCommonPaths: false } : {}),
  };
  if (cliArgs.now) request.now = cliArgs.now;
  if (cliArgs.strict) request.strictness = 'strict';
  if (cliArgs.userAgent) request.userAgent = cliArgs.userAgent;
  return request;
}

async function readStructuredInput(path) {
  if (path && path !== '-') return readJson(path);
  const text = await readInputText(path);
  return JSON.parse(text);
}

async function readInputText(path) {
  if (path && path !== '-') return readText(path);
  if (process.stdin.isTTY) {
    console.error('No input provided. Use --input <file>, --input -, or --url <url>.');
    process.exit(2);
  }
  return new Promise((resolve) => {
    let data = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', (chunk) => { data += chunk; });
    process.stdin.on('end', () => resolve(data));
  });
}

function parseRequestText(text, name) {
  const trimmed = String(text || '').trim();
  if (!trimmed) return { sources: [] };
  if (/^[\[{]/.test(trimmed)) {
    const parsed = JSON.parse(trimmed);
    if (Array.isArray(parsed)) return { sources: parsed };
    if (Array.isArray(parsed.sources)) return parsed;
  }
  const parsed = parseSourceList(trimmed, name);
  return { sources: parsed.sources, warnings: parsed.warnings };
}

function printUsage() {
  console.error(`Usage:
  feed_process.mjs process --input request.json [--out result.json]
  feed_process.mjs process --input -
  feed_process.mjs process --url https://example.com/feed.xml [--url ...]
  feed_process.mjs validate --input result.json
  feed_process.mjs capabilities`);
}
