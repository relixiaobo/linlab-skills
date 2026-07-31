#!/usr/bin/env node
import { parseArgs, readJson, writeJson } from './lib/feed_common.mjs';

const args = parseArgs(process.argv.slice(2));
if (!args.input || !args.rules) {
  console.error('Usage: feed_rules.mjs --input items.json --rules rules.json [--out out.json]');
  process.exit(2);
}

const input = await readJson(args.input);
const rules = await readJson(args.rules);
const items = input.items || input.selectedItems || [];
const selectedItems = [];
const rejected = [];
const existingSkipped = input.skipped || [];

for (const item of items) {
  const text = `${item.title || ''}\n${item.summaryText || ''}\n${item.contentText || ''}`.toLowerCase();
  const reasons = [];
  const failures = [];
  for (const word of rules.includeKeywords || []) {
    if (text.includes(String(word).toLowerCase())) reasons.push(`include keyword: ${word}`);
  }
  for (const word of rules.excludeKeywords || []) {
    if (text.includes(String(word).toLowerCase())) failures.push(`exclude keyword: ${word}`);
  }
  if (rules.requiredDomains?.length && !rules.requiredDomains.some((domain) => (item.url || '').includes(domain))) failures.push('required domain missing');
  if (rules.blockedDomains?.some((domain) => (item.url || '').includes(domain))) failures.push('blocked domain');
  if (rules.minContentLength && String(item.contentText || item.summaryText || '').length < rules.minContentLength) failures.push('content too short');
  if (rules.maxContentLength && String(item.contentText || item.summaryText || '').length > rules.maxContentLength) failures.push('content too long');
  if (failures.length) rejected.push({ item, reasons: failures });
  else selectedItems.push({ ...item, matchedRules: reasons.length ? reasons : ['default include'] });
}

await writeJson(args.out, {
  generatedAt: new Date().toISOString(),
  scope: input.scope,
  sources: input.sources || [],
  items: selectedItems,
  rejected: rejected.map((row) => ({ reasons: row.reasons, itemId: row.item.itemId, title: row.item.title })),
  skipped: [
    ...existingSkipped,
    ...summarizeRejected(rejected),
  ],
  errors: input.errors || [],
  warnings: input.warnings || [],
  coverage: {
    requested: input.coverage?.requested,
    fetched: input.coverage?.fetched,
    notModified: input.coverage?.notModified,
    sourceCount: input.coverage?.sourceCount ?? (input.sources || []).length,
    parsedItems: input.coverage?.parsedItems ?? input.coverage?.inputItems ?? items.length,
    inputItems: items.length,
    selectedItems: selectedItems.length,
    rejectedItems: rejected.length,
    skippedItems: (input.coverage?.skippedItems ?? skippedCount(existingSkipped)) + rejected.length,
    erroredSources: input.coverage?.erroredSources ?? (input.errors || []).length,
  },
});

function summarizeRejected(rows) {
  if (!rows.length) return [];
  return [{
    reason: 'rule_rejected',
    count: rows.length,
    visibleItems: rows.slice(0, 5).map((row) => ({ itemId: row.item.itemId || null, title: row.item.title || null, reasons: row.reasons })),
  }];
}

function skippedCount(rows) {
  return rows.reduce((sum, row) => sum + (row.count || 0), 0);
}
