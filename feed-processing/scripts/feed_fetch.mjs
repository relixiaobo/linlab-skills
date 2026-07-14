#!/usr/bin/env node
import { parseArgs, asArray, readJson, writeJson } from './lib/feed_common.mjs';
import { fetchResource, makeFeedError, normalizeLimits } from './lib/feed_runtime.mjs';

const args = parseArgs(process.argv.slice(2));
const urls = asArray(args.url);
if (args.help || args.h) {
  console.error('Usage: feed_fetch.mjs --url https://example.com/feed.xml [--sources sources.json] [--out out.json]');
  process.exit(0);
}
if (!urls.length && !args.sources) {
  console.error('Usage: feed_fetch.mjs --url https://example.com/feed.xml [--sources sources.json] [--out out.json]');
  process.exit(2);
}

const sources = args.sources ? (await readJson(args.sources)).sources : urls.map((url) => ({ inputUrl: url, feedUrl: url }));
const limits = normalizeLimits({
  timeoutMs: args.timeoutMs,
  maxBytes: args.maxBytes,
  maxRedirects: args.maxRedirects,
  concurrency: args.concurrency,
});
const responses = new Array(sources.length);
let nextIndex = 0;

await Promise.all(Array.from({ length: Math.min(limits.concurrency, sources.length) }, worker));

async function worker() {
  while (nextIndex < sources.length) {
    const index = nextIndex;
    nextIndex += 1;
    responses[index] = await fetchSource(sources[index]);
  }
}

async function fetchSource(source) {
  const url = source.feedUrl || source.inputUrl || source.url;
  if (!url) {
    return {
      sourceId: source.sourceId,
      url,
      ok: false,
      transportOk: false,
      error: makeFeedError('invalid_url', { stage: 'fetch', message: 'Source has no feed URL.' }),
    };
  }
  const response = await fetchResource(url, {
    limits,
    userAgent: args.userAgent,
    etag: source.etag,
    lastModified: source.lastModified,
  });
  return { sourceId: source.sourceId, ...response };
}

await writeJson(args.out, {
  generatedAt: new Date().toISOString(),
  responses,
  coverage: {
    requested: sources.length,
    fetched: responses.filter((response) => response.transportOk && !response.notModified).length,
    notModified: responses.filter((response) => response.notModified).length,
    errored: responses.filter((response) => !response.transportOk).length,
  },
});
