#!/usr/bin/env node
import { parseArgs, asArray, readJson, writeJson } from './lib/feed_common.mjs';

const args = parseArgs(process.argv.slice(2));
const urls = asArray(args.url);
if (!urls.length && !args.sources) {
  console.error('Usage: feed_fetch.mjs --url https://example.com/feed.xml [--sources sources.json] [--out out.json]');
  process.exit(2);
}

const sources = args.sources ? (await readJson(args.sources)).sources : urls.map((url) => ({ feedUrl: url }));
const timeoutMs = Number(args.timeoutMs || 15000);
const maxBytes = Number(args.maxBytes || 2_000_000);
const concurrency = Math.max(1, Math.floor(Number(args.concurrency || 8)));
const responses = new Array(sources.length);
let nextIndex = 0;

await Promise.all(Array.from({ length: Math.min(concurrency, sources.length) }, worker));

async function worker() {
  while (nextIndex < sources.length) {
    const index = nextIndex;
    nextIndex += 1;
    responses[index] = await fetchSource(sources[index]);
  }
}

async function fetchSource(source) {
  const url = source.feedUrl || source.url;
  const started = Date.now();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {
      signal: controller.signal,
      headers: {
        'User-Agent': args.userAgent || 'Linlab Feed Processing Skill/0.1 (+https://github.com/relixiaobo/linlab-skills)',
        Accept: 'application/rss+xml, application/atom+xml, application/feed+json, application/json, text/xml, application/xml;q=0.9, */*;q=0.5',
        ...(source.etag ? { 'If-None-Match': source.etag } : {}),
        ...(source.lastModified ? { 'If-Modified-Since': source.lastModified } : {}),
      },
      redirect: 'follow',
    });
    const text = response.status === 304 ? '' : await readResponseText(response, maxBytes);
    return {
      sourceId: source.sourceId,
      url,
      finalUrl: response.url,
      status: response.status,
      ok: response.ok || response.status === 304,
      notModified: response.status === 304,
      contentType: response.headers.get('content-type'),
      etag: response.headers.get('etag'),
      lastModified: response.headers.get('last-modified'),
      durationMs: Date.now() - started,
      body: text,
      error: response.ok || response.status === 304 ? undefined : { code: 'http_error', message: `HTTP ${response.status}` },
    };
  } catch (error) {
    return {
      sourceId: source.sourceId,
      url,
      ok: false,
      durationMs: Date.now() - started,
      error: { code: errorCode(error), message: error.message },
    };
  } finally {
    clearTimeout(timer);
  }
}

await writeJson(args.out, {
  generatedAt: new Date().toISOString(),
  responses,
  coverage: {
    requested: sources.length,
    fetched: responses.filter((r) => r.ok && !r.notModified).length,
    notModified: responses.filter((r) => r.notModified).length,
    errored: responses.filter((r) => !r.ok).length,
  },
});

async function readResponseText(response, maxBytes) {
  const contentLength = Number(response.headers.get('content-length') || 0);
  if (contentLength > maxBytes) throw responseTooLarge(maxBytes);
  if (!response.body) return '';

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let bytesRead = 0;
  let text = '';
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      bytesRead += value.byteLength;
      if (bytesRead > maxBytes) {
        await reader.cancel();
        throw responseTooLarge(maxBytes);
      }
      text += decoder.decode(value, { stream: true });
    }
    text += decoder.decode();
    return text;
  } finally {
    reader.releaseLock();
  }
}

function responseTooLarge(maxBytes) {
  const error = new Error(`response exceeds maxBytes (${maxBytes})`);
  error.code = 'response_too_large';
  return error;
}

function errorCode(error) {
  if (error.name === 'AbortError') return 'timeout';
  if (error.code === 'response_too_large') return 'response_too_large';
  return 'network_error';
}
