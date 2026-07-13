#!/usr/bin/env node
import { parseArgs, readJson, writeJson, itemIdentity } from './lib/feed_common.mjs';

const args = parseArgs(process.argv.slice(2));
if (!args.input) {
  console.error('Usage: feed_window.mjs --input parsed.json --mode last_n_days --days 7 [--now 2026-07-07T00:00:00Z] [--out out.json]');
  process.exit(2);
}

const input = await readJson(args.input);
const items = input.items || input.selectedItems || [];
const mode = args.mode || 'all';
const now = args.now ? new Date(args.now) : new Date();
let included = [];
const skipped = [];
const warnings = [];
const inputWarnings = input.warnings || [];
const errors = input.errors || [];

function itemDate(item) {
  const raw = item.publishedAt || item.updatedAt;
  if (!raw) return null;
  const date = new Date(raw);
  return Number.isNaN(date.getTime()) ? null : date;
}

if (mode === 'all') {
  included = items;
} else if (mode === 'last_n_days') {
  const days = Number(args.days || 7);
  const start = new Date(now.getTime() - days * 24 * 60 * 60 * 1000);
  for (const item of items) {
    const date = itemDate(item);
    if (!date) {
      skipped.push({ reason: 'date_ambiguous', item });
      continue;
    }
    if (date >= start && date <= now) included.push(item);
    else skipped.push({ reason: 'outside_window', item });
  }
} else if (mode === 'date_range') {
  const start = new Date(args.start);
  const end = new Date(args.end);
  for (const item of items) {
    const date = itemDate(item);
    if (!date) skipped.push({ reason: 'date_ambiguous', item });
    else if (date >= start && date <= end) included.push(item);
    else skipped.push({ reason: 'outside_window', item });
  }
} else if (mode === 'newest_n') {
  const count = Number(args.count || 10);
  const sorted = [...items].sort((a, b) => (itemDate(b)?.getTime() || 0) - (itemDate(a)?.getTime() || 0));
  included = sorted.slice(0, count);
  skipped.push(...sorted.slice(count).map((item) => ({ reason: 'outside_newest_n', item })));
} else if (mode === 'since_cursor') {
  const cursor = args.cursor ? await readJson(args.cursor) : {};
  const seen = new Map(Object.entries(cursor.items || cursor.seen || {}));
  for (const item of items) {
    const id = itemIdentity(item);
    const prior = seen.get(id);
    const marker = item.updatedAt || item.publishedAt || item.title || '';
    if (!prior || prior !== marker) included.push(item);
    else skipped.push({ reason: 'unchanged_since_cursor', item });
  }
} else {
  warnings.push({ code: 'unsupported_scope', severity: 'error', message: `Unsupported mode: ${mode}` });
}

await writeJson(args.out, {
  generatedAt: new Date().toISOString(),
  scope: { mode, days: args.days ? Number(args.days) : undefined, count: args.count ? Number(args.count) : undefined, start: args.start, end: args.end },
  sources: input.sources || [],
  items: included,
  skipped: summarizeSkipped(skipped),
  errors,
  warnings: [...inputWarnings, ...warnings],
  coverage: {
    requested: input.coverage?.requested,
    fetched: input.coverage?.fetched,
    notModified: input.coverage?.notModified,
    sourceCount: input.coverage?.sourceCount ?? (input.sources || []).length,
    parsedItems: input.coverage?.parsedItems ?? input.coverage?.inputItems ?? items.length,
    inputItems: items.length,
    selectedItems: included.length,
    skippedItems: skipped.length,
    erroredSources: input.coverage?.erroredSources ?? errors.length,
  },
});

function summarizeSkipped(rows) {
  const byReason = new Map();
  for (const row of rows) {
    if (!byReason.has(row.reason)) byReason.set(row.reason, []);
    byReason.get(row.reason).push(row.item);
  }
  return [...byReason.entries()].map(([reason, reasonItems]) => ({
    reason,
    count: reasonItems.length,
    visibleItems: reasonItems.slice(0, 5).map((item) => ({ sourceId: item.sourceId, itemId: item.itemId || null, title: item.title || null })),
  }));
}
