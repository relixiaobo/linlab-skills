#!/usr/bin/env node
import { parseArgs, readText, writeJson } from './lib/feed_common.mjs';
import {
  discoverFeedCandidates,
  fetchResource,
  isFeedPayloadKind,
  makeFeedError,
  normalizeLimits,
} from './lib/feed_runtime.mjs';

const args = parseArgs(process.argv.slice(2));
if (args.help || args.h) {
  console.error('Usage: feed_discover.mjs --html page.html --url https://example.com/page [--out out.json]');
  process.exit(0);
}
if (!args.html && !args.url) {
  console.error('Usage: feed_discover.mjs --html page.html --url https://example.com/page [--out out.json]');
  process.exit(2);
}

const limits = normalizeLimits({
  timeoutMs: args.timeoutMs,
  maxBytes: args.maxBytes,
  maxRedirects: args.maxRedirects,
});
const requestedUrl = args.url || 'https://example.com/';
let pageUrl = requestedUrl;
let html = '';
let linkHeader;
const errors = [];

if (args.html) {
  html = await readText(args.html);
} else {
  const response = await fetchResource(requestedUrl, { limits, userAgent: args.userAgent });
  pageUrl = response.finalUrl || requestedUrl;
  linkHeader = response.linkHeader;
  if (!response.transportOk) {
    errors.push(response.error);
  } else if (isFeedPayloadKind(response.contentKind)) {
    await writeJson(args.out, {
      pageUrl,
      requestedUrl,
      candidates: [{
        url: pageUrl,
        type: response.contentKind,
        source: 'direct_feed',
        confidence: 'high',
      }],
      warnings: [],
      errors: [],
    });
    process.exit(0);
  } else if (response.contentKind === 'html') {
    html = response.body;
  } else {
    errors.push(makeFeedError('unsupported_content_type', {
      stage: 'discover',
      url: requestedUrl,
      finalUrl: pageUrl,
      message: `Cannot discover feeds from ${response.contentKind} content.`,
      details: { contentType: response.contentType, contentKind: response.contentKind },
    }));
  }
}

const discovered = html
  ? discoverFeedCandidates(html, pageUrl, {
    includeCommonPaths: !args['no-common'],
    linkHeader,
  })
  : { pageUrl, candidates: [], warnings: [] };

await writeJson(args.out, {
  requestedUrl,
  pageUrl: discovered.pageUrl,
  candidates: discovered.candidates,
  warnings: discovered.warnings,
  errors,
});
