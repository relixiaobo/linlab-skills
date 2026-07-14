#!/usr/bin/env node
import { parseArgs, asArray, readText, writeJson, parseFeedContent } from './lib/feed_common.mjs';
import { classifyPayload, makeFeedError } from './lib/feed_runtime.mjs';

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
let parsedSources = 0;
let emptySources = 0;

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
    errors.push(makeFeedError('parse_error', {
      stage: 'parse',
      url: feedUrl,
      message: error.message,
    }));
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
    requestedSources: sawFetchOutput ? requested : sources.length + errors.length,
    fetched: sawFetchOutput ? fetched : undefined,
    notModified: sawFetchOutput ? notModified : undefined,
    sourceCount: sources.length,
    parsedSources,
    emptySources,
    failedSources: errors.length,
    notModifiedSources: notModified,
    skippedSources: 0,
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
    errors.push({ sourceId: response.sourceId, ...normalizeResponseError(response) });
    return;
  }
  if (response.notModified) return;
  const contentKind = response.contentKind || classifyPayload(response.body || '', response.contentType);
  if (contentKind === 'html') {
    errors.push({
      sourceId: response.sourceId,
      ...makeFeedError('unsupported_content_type', {
        stage: 'parse',
        url: response.url,
        finalUrl: response.finalUrl,
        message: 'The response is HTML, not a feed. Run feed discovery against the final URL or fetched HTML.',
        nextAction: 'discover_feed',
        details: { contentType: response.contentType, contentKind },
      }),
    });
    return;
  }
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
      ...makeFeedError('parse_error', {
        stage: 'parse',
        url: response.url,
        finalUrl: response.finalUrl,
        message: error.message,
      }),
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
  if (parsed.items.length) parsedSources += 1;
  else emptySources += 1;
  items = items.concat(parsed.items.map((item) => ({
    ...item,
    sourceId,
    feedUrl: source.feedUrl,
  })));
  warnings.push(...parsed.warnings.map((warning) => ({ ...warning, sourceId })));
}

function normalizeResponseError(response) {
  if (response.error?.stage && response.error?.nextAction) return response.error;
  return makeFeedError(response.error?.code || 'network_error', {
    stage: 'fetch',
    url: response.url,
    finalUrl: response.finalUrl,
    status: response.status,
    retryable: response.error?.retryable,
    severity: response.error?.severity,
    message: response.error?.message || `HTTP ${response.status || 'error'}`,
    nextAction: response.error?.nextAction,
  });
}
