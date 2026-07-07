#!/usr/bin/env node
import { parseArgs, asArray, readText, writeJson, parseFeedContent } from './lib/feed_common.mjs';

const args = parseArgs(process.argv.slice(2));
const inputs = asArray(args.input);
if (!inputs.length) {
  console.error('Usage: feed_parse.mjs --input feed.xml [--url https://example.com/feed.xml] [--out out.json]');
  process.exit(2);
}

const sources = [];
let items = [];
const warnings = [];
const errors = [];
let sawFetchOutput = false;
let requested = 0;
let fetched = 0;
let notModified = 0;

for (const [index, input] of inputs.entries()) {
  const feedUrl = asArray(args.url)[index] || `file://${input}`;
  const text = await readText(input);
  const fetchOutput = maybeFetchOutput(text);
  if (fetchOutput) {
    sawFetchOutput = true;
    requested += fetchOutput.coverage?.requested ?? fetchOutput.responses.length;
    fetched += fetchOutput.coverage?.fetched ?? fetchOutput.responses.filter((response) => response.ok && !response.notModified).length;
    notModified += fetchOutput.coverage?.notModified ?? fetchOutput.responses.filter((response) => response.notModified).length;
    for (const response of fetchOutput.responses) parseFetchedResponse(response);
    continue;
  }
  try {
    recordParsed(parseFeedContent(text, feedUrl));
  } catch (error) {
    errors.push({
      url: feedUrl,
      code: 'parse_error',
      severity: 'error',
      retryable: false,
      message: error.message,
    });
  }
}

await writeJson(args.out, {
  generatedAt: new Date().toISOString(),
  sources,
  items,
  warnings,
  errors,
  coverage: {
    requested: sawFetchOutput ? requested : undefined,
    fetched: sawFetchOutput ? fetched : undefined,
    notModified: sawFetchOutput ? notModified : undefined,
    sourceCount: sources.length,
    parsedItems: items.length,
    erroredSources: errors.length,
  },
});

function maybeFetchOutput(text) {
  const trimmed = text.trim();
  if (!trimmed.startsWith('{')) return null;
  try {
    const parsed = JSON.parse(trimmed);
    return Array.isArray(parsed.responses) ? parsed : null;
  } catch {
    return null;
  }
}

function parseFetchedResponse(response) {
  if (!response.ok) {
    errors.push({
      sourceId: response.sourceId,
      url: response.url,
      finalUrl: response.finalUrl,
      code: response.error?.code || 'fetch_error',
      severity: 'error',
      retryable: response.error?.code !== 'http_error',
      message: response.error?.message || `HTTP ${response.status || 'error'}`,
    });
    return;
  }
  if (response.notModified) return;
  try {
    const feedUrl = response.finalUrl || response.url;
    const parsed = parseFeedContent(response.body || '', feedUrl);
    recordParsed(parsed, {
      sourceId: response.sourceId,
      originalUrl: response.url,
      finalUrl: feedUrl,
    });
  } catch (error) {
    errors.push({
      sourceId: response.sourceId,
      url: response.url,
      finalUrl: response.finalUrl,
      code: 'parse_error',
      severity: 'error',
      retryable: false,
      message: error.message,
    });
  }
}

function recordParsed(parsed, provenance = {}) {
  const sourceId = provenance.sourceId || parsed.source.sourceId;
  const source = {
    ...parsed.source,
    sourceId,
    originalUrl: provenance.originalUrl,
    finalUrl: provenance.finalUrl,
  };
  sources.push(source);
  items = items.concat(parsed.items.map((item) => ({
    ...item,
    sourceId,
    feedUrl: source.feedUrl,
  })));
  warnings.push(...parsed.warnings.map((warning) => ({ ...warning, sourceId })));
}
