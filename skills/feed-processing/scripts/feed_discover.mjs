#!/usr/bin/env node
import { parseArgs, readText, writeJson, parseAttributes, absoluteUrl } from './lib/feed_common.mjs';

const args = parseArgs(process.argv.slice(2));
if (!args.html && !args.url) {
  console.error('Usage: feed_discover.mjs --html page.html --url https://example.com/page [--out out.json]');
  process.exit(2);
}

const pageUrl = args.url || 'https://example.com/';
let html = '';
if (args.html) html = await readText(args.html);
else {
  const response = await fetch(pageUrl);
  html = await response.text();
}

const candidates = [];
const warnings = [];
const linkRe = /<link\b([^>]*?)>/gi;
let match;
while ((match = linkRe.exec(html))) {
  const attrs = parseAttributes(match[1]);
  const rel = String(attrs.rel || '').toLowerCase();
  const type = String(attrs.type || '').toLowerCase();
  if (!rel.includes('alternate')) continue;
  const feedType = type.includes('rss') ? 'rss'
    : type.includes('atom') ? 'atom'
      : type.includes('json') || type.includes('feed+json') ? 'jsonfeed'
        : null;
  if (!feedType || !attrs.href) continue;
  candidates.push({
    url: absoluteUrl(attrs.href, pageUrl),
    type: feedType,
    title: attrs.title || undefined,
    source: 'html_alternate',
    confidence: 'high',
  });
}

if (!candidates.length) {
  warnings.push({ code: 'no_alternate_feed_links', severity: 'warning', message: 'No RSS/Atom/JSON alternate links found in HTML.' });
  if (!args['no-common']) {
    const base = new URL(pageUrl);
    for (const path of ['/feed', '/rss', '/atom.xml', '/feed.xml', '/index.xml', '/rss.xml']) {
      candidates.push({
        url: new URL(path, `${base.origin}/`).toString(),
        type: path.includes('atom') ? 'atom' : 'rss',
        source: 'common_path',
        confidence: 'low',
      });
    }
  }
}

await writeJson(args.out, {
  pageUrl,
  candidates,
  warnings,
});
