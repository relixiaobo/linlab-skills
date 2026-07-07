#!/usr/bin/env node
import { parseArgs, readJson, writeJson } from './lib/feed_common.mjs';

const args = parseArgs(process.argv.slice(2));
if (!args.input) {
  console.error('Usage: feed_profile.mjs --input parsed-or-pack.json [--out profile.json]');
  process.exit(2);
}

const input = await readJson(args.input);
const items = input.items || input.selectedItems || [];
const sources = input.sources || [];
const statsBySource = new Map();

for (const item of items) {
  const stats = statsFor(item.sourceId);
  stats.itemCount += 1;
  const rawDate = item.publishedAt || item.updatedAt;
  if (!item.publishedAt && !item.updatedAt) stats.missingDateCount += 1;
  if (rawDate) {
    const time = new Date(rawDate).getTime();
    if (Number.isFinite(time)) {
      stats.newestMs = stats.newestMs === null ? time : Math.max(stats.newestMs, time);
      stats.oldestMs = stats.oldestMs === null ? time : Math.min(stats.oldestMs, time);
    }
  }
  if (!item.url) stats.missingUrlCount += 1;
  const key = `${item.title}|${rawDate || ''}`;
  if (stats.titleDates.has(key)) stats.duplicateTitleDateCount += 1;
  stats.titleDates.add(key);
  if ((item.summaryText || '').length > 0 && (item.contentText || '').length <= (item.summaryText || '').length + 20) {
    stats.truncationLikelyCount += 1;
  }
}

const profile = sources.map((source) => {
  const stats = statsBySource.get(source.sourceId) || emptyStats();
  return {
    sourceId: source.sourceId,
    feedUrl: source.feedUrl,
    title: source.title,
    itemCount: stats.itemCount,
    newestAt: stats.newestMs === null ? null : new Date(stats.newestMs).toISOString(),
    oldestAt: stats.oldestMs === null ? null : new Date(stats.oldestMs).toISOString(),
    missingDateCount: stats.missingDateCount,
    missingUrlCount: stats.missingUrlCount,
    duplicateTitleDateCount: stats.duplicateTitleDateCount,
    truncationLikelyCount: stats.truncationLikelyCount,
    warnings: source.warnings || [],
  };
});

await writeJson(args.out, {
  generatedAt: new Date().toISOString(),
  profile,
  coverage: {
    sourceCount: sources.length,
    itemCount: items.length,
  },
});

function statsFor(sourceId) {
  if (!statsBySource.has(sourceId)) statsBySource.set(sourceId, emptyStats());
  return statsBySource.get(sourceId);
}

function emptyStats() {
  return {
    itemCount: 0,
    newestMs: null,
    oldestMs: null,
    missingDateCount: 0,
    missingUrlCount: 0,
    duplicateTitleDateCount: 0,
    truncationLikelyCount: 0,
    titleDates: new Set(),
  };
}
