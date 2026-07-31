#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { dirname } from 'node:path';

export function parseArgs(argv) {
  const args = { _: [] };
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith('--')) {
      args._.push(token);
      continue;
    }
    const key = token.slice(2);
    const next = argv[i + 1];
    if (!next || next.startsWith('--')) {
      args[key] = true;
      continue;
    }
    if (args[key] === undefined) args[key] = next;
    else if (Array.isArray(args[key])) args[key].push(next);
    else args[key] = [args[key], next];
    i += 1;
  }
  return args;
}

export function asArray(value) {
  if (value === undefined || value === null) return [];
  return Array.isArray(value) ? value : [value];
}

export async function readText(path) {
  return readFile(path, 'utf8');
}

export async function readJson(path) {
  return JSON.parse(await readText(path));
}

export async function writeJson(path, value) {
  if (path) {
    await mkdir(dirname(path), { recursive: true });
    await writeFile(path, `${JSON.stringify(value, null, 2)}\n`);
  } else {
    process.stdout.write(`${JSON.stringify(value, null, 2)}\n`);
  }
}

export function stableHash(value, length = 16) {
  return createHash('sha256').update(String(value ?? '')).digest('hex').slice(0, length);
}

export function normalizeWhitespace(value) {
  return String(value ?? '').replace(/\s+/g, ' ').trim();
}

export function decodeEntities(value) {
  return String(value ?? '')
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");
}

export function stripHtml(value) {
  return normalizeWhitespace(
    decodeEntities(String(value ?? '')
      .replace(/<script[\s\S]*?<\/script>/gi, ' ')
      .replace(/<style[\s\S]*?<\/style>/gi, ' ')
      .replace(/<[^>]+>/g, ' '))
  );
}

export function validUrl(value) {
  try {
    return Boolean(new URL(value));
  } catch {
    return false;
  }
}

export function absoluteUrl(value, baseUrl) {
  try {
    return new URL(value, baseUrl).toString();
  } catch {
    return null;
  }
}

export function canonicalUrl(value) {
  try {
    const url = new URL(value);
    url.hash = '';
    if (url.pathname !== '/') url.pathname = url.pathname.replace(/\/+$/, '');
    return url.toString();
  } catch {
    return String(value ?? '').trim();
  }
}

export function parseAttributes(fragment) {
  const attrs = {};
  const re = /([A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*(?:"([^"]*)"|'([^']*)')/g;
  let match;
  while ((match = re.exec(fragment))) {
    attrs[match[1]] = decodeEntities(match[2] ?? match[3] ?? '');
  }
  return attrs;
}

export function firstTag(xml, tag) {
  const re = new RegExp(`<${tag}(?:\\s[^>]*)?>([\\s\\S]*?)<\\/${tag}>`, 'i');
  const match = xml.match(re);
  return match ? normalizeWhitespace(stripHtml(match[1])) : undefined;
}

export function firstTagRaw(xml, tag) {
  const re = new RegExp(`<${tag}(?:\\s[^>]*)?>([\\s\\S]*?)<\\/${tag}>`, 'i');
  const match = xml.match(re);
  return match ? decodeEntities(match[1]).trim() : undefined;
}

export function tagBlocks(xml, tag) {
  const blocks = [];
  const re = new RegExp(`<${tag}(?:\\s[^>]*)?>[\\s\\S]*?<\\/${tag}>`, 'gi');
  let match;
  while ((match = re.exec(xml))) blocks.push(match[0]);
  return blocks;
}

export function parseDateToIso(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString();
}

export function parseCsv(text, delimiter = ',') {
  return text.trim().split(/\r?\n/).filter(Boolean).map((line) => {
    const cells = [];
    let cell = '';
    let quoted = false;
    for (let i = 0; i < line.length; i += 1) {
      const ch = line[i];
      if (ch === '"' && line[i + 1] === '"') {
        cell += '"';
        i += 1;
      } else if (ch === '"') {
        quoted = !quoted;
      } else if (ch === delimiter && !quoted) {
        cells.push(cell.trim());
        cell = '';
      } else {
        cell += ch;
      }
    }
    cells.push(cell.trim());
    return cells;
  });
}

export function tableRowsFromDelimited(text) {
  const trimmed = text.trim();
  if (!trimmed) return [];
  const delimiter = trimmed.includes('\t') ? '\t' : ',';
  const rows = parseCsv(trimmed, delimiter);
  const headers = rows.shift()?.map((h) => h.trim()) ?? [];
  return rows.map((cells, index) => Object.fromEntries(headers.map((h, i) => [h, cells[i] ?? '']))).map((row, index) => ({ ...row, _row: index + 2 }));
}

export function tableRowsFromMarkdown(text) {
  const lines = text.split(/\r?\n/).filter((line) => /^\s*\|.*\|\s*$/.test(line));
  if (lines.length < 2) return [];
  const header = lines[0].split('|').slice(1, -1).map((cell) => cell.trim());
  const body = lines.slice(2);
  return body.map((line, index) => {
    const cells = line.split('|').slice(1, -1).map((cell) => cell.trim());
    return { ...Object.fromEntries(header.map((h, i) => [h, cells[i] ?? ''])), _row: index + 3 };
  });
}

export function parseOpmlSources(text) {
  const sources = [];
  const stack = [];
  const outlineRe = /<(\/?)outline\b([^>]*?)(\/?)>/gi;
  let match;
  while ((match = outlineRe.exec(text))) {
    const closing = match[1] === '/';
    const selfClosing = match[3] === '/';
    if (closing) {
      stack.pop();
      continue;
    }
    const attrs = parseAttributes(match[2]);
    const label = attrs.title || attrs.text;
    const isFeed = attrs.xmlUrl || attrs.type === 'rss';
    if (isFeed) {
      sources.push({
        sourceId: stableHash(attrs.xmlUrl || attrs.htmlUrl || label),
        feedUrl: attrs.xmlUrl,
        siteUrl: attrs.htmlUrl,
        title: label,
        folders: stack.filter(Boolean),
        tags: stack.filter(Boolean),
        sourceType: 'opml',
      });
    }
    if (!selfClosing) stack.push(label);
  }
  return sources;
}

export function sourceFromRow(row, ref = {}) {
  const feedUrl = row.xmlUrl || row.feedUrl || row.rssUrl || row.atomUrl || row.feed || '';
  const siteUrl = row.url || row.siteUrl || row.htmlUrl || row.homepage || '';
  const url = feedUrl || siteUrl;
  if (!url) return { error: { code: 'missing_url', row: ref, message: 'Row has no feed or site URL.' } };
  const looksFeed = Boolean(feedUrl || /\.(xml|rss|atom|json)$/i.test(url) || /\/(feed|rss|atom)(\/|$)/i.test(url));
  const source = {
    sourceId: stableHash(canonicalUrl(url)),
    feedUrl: looksFeed ? url : undefined,
    siteUrl: looksFeed ? (siteUrl || undefined) : url,
    title: row.title || row.text || row.name || row.label || undefined,
    author: row.author || undefined,
    folders: splitList(row.folder || row.category || row.group),
    tags: splitList(row.tags || row.tag),
    status: row.status || undefined,
    notes: row.notes || row.note || undefined,
    sourceType: ref.kind,
    rowRefs: [ref],
  };
  return { source };
}

export function splitList(value) {
  if (!value) return [];
  return String(value).split(/[;,]/).map((item) => item.trim()).filter(Boolean);
}

export function dedupeSources(sources) {
  const byKey = new Map();
  const warnings = [];
  for (const source of sources) {
    const key = canonicalUrl(source.feedUrl || source.siteUrl);
    if (byKey.has(key)) {
      const existing = byKey.get(key);
      existing.rowRefs = [...(existing.rowRefs ?? []), ...(source.rowRefs ?? [])];
      warnings.push({ code: 'duplicate_source', severity: 'warning', message: `Duplicate source ${key}`, sourceId: existing.sourceId });
      continue;
    }
    byKey.set(key, source);
  }
  return { sources: [...byKey.values()], warnings };
}

export function parseSourceList(text, name = 'stdin') {
  const trimmed = text.trim();
  const warnings = [];
  if (!trimmed) return { sources: [], warnings: [{ code: 'empty_input', severity: 'warning', message: `${name} is empty.` }] };
  if (/^\s*</.test(trimmed) && /<opml\b/i.test(trimmed)) {
    return { sources: parseOpmlSources(trimmed), warnings };
  }
  if (/^\s*[\[{]/.test(trimmed)) {
    const parsed = JSON.parse(trimmed);
    if (Array.isArray(parsed)) return { sources: parsed, warnings };
    if (Array.isArray(parsed.sources)) return { sources: parsed.sources, warnings };
    if (Array.isArray(parsed.selectedItems)) {
      const sources = parsed.selectedItems.map((item) => ({ sourceId: item.sourceId, feedUrl: item.feedUrl, title: item.sourceTitle })).filter((s) => s.feedUrl);
      return dedupeSources(sources);
    }
  }
  const firstLine = trimmed.split(/\r?\n/, 1)[0] || '';
  const mayBeTable = /^\s*\|.*\|\s*$/.test(firstLine) || firstLine.includes(',') || firstLine.includes('\t');
  const rows = mayBeTable ? (trimmed.includes('|') ? tableRowsFromMarkdown(trimmed) : tableRowsFromDelimited(trimmed)) : [];
  if (rows.length && Object.keys(rows[0]).some((key) => /^(xmlUrl|feedUrl|rssUrl|atomUrl|feed|url|siteUrl|htmlUrl|homepage|title|text|name|label)$/i.test(key))) {
    const sources = [];
    for (const row of rows) {
      const result = sourceFromRow(row, { kind: name, row: row._row });
      if (result.source) sources.push(result.source);
      if (result.error) warnings.push({ ...result.error, severity: 'warning' });
    }
    const deduped = dedupeSources(sources);
    return { ...deduped, warnings: [...warnings, ...deduped.warnings] };
  }
  const urls = trimmed.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const sources = [];
  for (const [index, url] of urls.entries()) {
    if (!validUrl(url)) {
      warnings.push({ code: 'invalid_url', severity: 'warning', message: `Invalid URL on line ${index + 1}: ${url}` });
      continue;
    }
    const result = sourceFromRow({ url }, { kind: name, line: index + 1 });
    if (result.source) sources.push(result.source);
  }
  const deduped = dedupeSources(sources);
  return { ...deduped, warnings: [...warnings, ...deduped.warnings] };
}

export function normalizeFeedItem(source, raw, index) {
  const url = raw.url || raw.link || raw.id;
  const rawId = raw.id || raw.guid || raw.url || raw.link || `${source.feedUrl}#${index}`;
  const publishedAt = parseDateToIso(raw.publishedAt || raw.pubDate || raw.date_published || raw.published);
  const updatedAt = parseDateToIso(raw.updatedAt || raw.updated || raw.date_modified);
  const contentHtml = raw.contentHtml || raw.content_html || raw.content || raw.description || '';
  const summaryText = stripHtml(raw.summary || raw.description || raw.content_text || '');
  const contentText = stripHtml(raw.contentText || raw.content_text || contentHtml);
  return {
    itemId: stableHash(`${source.feedUrl || source.sourceId}:${rawId}`),
    rawId,
    sourceId: source.sourceId,
    feedUrl: source.feedUrl,
    title: normalizeWhitespace(raw.title || 'Untitled item'),
    url: url ? absoluteUrl(url, source.feedUrl || source.siteUrl) : undefined,
    author: raw.author || raw.creator || raw.byline || undefined,
    publishedAt: publishedAt ?? undefined,
    updatedAt: updatedAt ?? undefined,
    summaryText: summaryText || undefined,
    contentText: contentText || undefined,
    categories: raw.categories || raw.tags || [],
    enclosures: raw.enclosures || [],
    identityConfidence: raw.id || raw.guid || raw.url || raw.link ? 'strong' : 'weak',
    warnings: [
      ...(!publishedAt && !updatedAt ? [{ code: 'date_missing', severity: 'warning', message: 'Item has no parseable date.' }] : []),
      ...(!url ? [{ code: 'link_missing', severity: 'warning', message: 'Item has no URL.' }] : []),
    ],
  };
}

export function parseFeedContent(text, feedUrl = 'file://feed.xml') {
  const trimmed = text.trim();
  if (/^\s*\{/.test(trimmed)) return parseJsonFeed(trimmed, feedUrl);
  if (/<feed[\s>]/i.test(trimmed)) return parseAtom(trimmed, feedUrl);
  if (/<rss[\s>]/i.test(trimmed) || /<rdf:RDF[\s>]/i.test(trimmed)) return parseRss(trimmed, feedUrl);
  throw new Error('Unsupported feed format.');
}

function parseJsonFeed(text, feedUrl) {
  const feed = JSON.parse(text);
  const source = {
    sourceId: stableHash(feedUrl),
    feedUrl,
    siteUrl: feed.home_page_url,
    title: feed.title || 'Untitled JSON Feed',
    description: feed.description,
    format: 'jsonfeed',
    warnings: [],
  };
  const items = (feed.items || []).map((item, index) => normalizeFeedItem(source, item, index));
  return { source, items, warnings: [] };
}

function parseRss(xml, feedUrl) {
  const channel = firstTagRaw(xml, 'channel') || xml;
  const source = {
    sourceId: stableHash(feedUrl),
    feedUrl,
    siteUrl: firstTag(channel, 'link'),
    title: firstTag(channel, 'title') || 'Untitled RSS Feed',
    description: firstTag(channel, 'description'),
    format: /<rdf:RDF[\s>]/i.test(xml) ? 'rdf' : 'rss',
    warnings: [],
  };
  const items = tagBlocks(xml, 'item').map((block, index) => normalizeFeedItem(source, {
    title: firstTag(block, 'title'),
    link: firstTag(block, 'link'),
    guid: firstTag(block, 'guid'),
    pubDate: firstTag(block, 'pubDate') || firstTag(block, 'dc:date'),
    updated: firstTag(block, 'updated'),
    description: firstTagRaw(block, 'description'),
    content: firstTagRaw(block, 'content:encoded'),
    categories: tagBlocks(block, 'category').map((cat) => stripHtml(cat)),
    author: firstTag(block, 'author') || firstTag(block, 'dc:creator'),
  }, index));
  return { source, items, warnings: items.length ? [] : [{ code: 'no_items', severity: 'warning', message: 'Feed parsed but contained no items.' }] };
}

function parseAtom(xml, feedUrl) {
  const feedLinkMatch = xml.match(/<link\b([^>]*?)>/i);
  const feedLink = feedLinkMatch ? parseAttributes(feedLinkMatch[1]).href : undefined;
  const source = {
    sourceId: stableHash(feedUrl),
    feedUrl,
    siteUrl: feedLink ? absoluteUrl(feedLink, feedUrl) : undefined,
    title: firstTag(xml, 'title') || 'Untitled Atom Feed',
    description: firstTag(xml, 'subtitle'),
    format: 'atom',
    warnings: [],
  };
  const items = tagBlocks(xml, 'entry').map((block, index) => {
    const linkMatch = block.match(/<link\b([^>]*?)>/i);
    const link = linkMatch ? parseAttributes(linkMatch[1]).href : undefined;
    return normalizeFeedItem(source, {
      title: firstTag(block, 'title'),
      id: firstTag(block, 'id'),
      link,
      published: firstTag(block, 'published'),
      updated: firstTag(block, 'updated'),
      summary: firstTagRaw(block, 'summary'),
      content: firstTagRaw(block, 'content'),
      author: firstTag(block, 'name'),
    }, index);
  });
  return { source, items, warnings: items.length ? [] : [{ code: 'no_items', severity: 'warning', message: 'Feed parsed but contained no entries.' }] };
}

export function itemIdentity(item) {
  if (item.itemId) return `item:${item.itemId}`;
  if (item.rawId) return `raw:${item.rawId}`;
  if (item.url) return `url:${canonicalUrl(item.url)}`;
  return `weak:${stableHash(`${item.sourceId}:${item.title}:${item.publishedAt || item.updatedAt || ''}`)}`;
}

export function extractArticleText(html) {
  const article = html.match(/<article\b[^>]*>([\s\S]*?)<\/article>/i)?.[1]
    || html.match(/<main\b[^>]*>([\s\S]*?)<\/main>/i)?.[1]
    || html.match(/<body\b[^>]*>([\s\S]*?)<\/body>/i)?.[1]
    || html;
  const text = stripHtml(article);
  const bodyText = stripHtml(html);
  return {
    articleText: text,
    bodyText,
    boilerplateRisk: bodyText.length && text.length / bodyText.length < 0.35 ? 'high' : 'low',
  };
}

export function contentStats(text) {
  const normalized = normalizeWhitespace(text);
  return {
    characterCount: normalized.length,
    wordCount: normalized ? normalized.split(/\s+/).length : 0,
  };
}
