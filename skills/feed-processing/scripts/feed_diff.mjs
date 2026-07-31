#!/usr/bin/env node
import { parseArgs, readJson, writeJson, itemIdentity, stableHash } from './lib/feed_common.mjs';

const args = parseArgs(process.argv.slice(2));
if (!args.prior || !args.current) {
  console.error('Usage: feed_diff.mjs --prior prior.json --current current.json [--out diff.json]');
  process.exit(2);
}

const priorInput = await readJson(args.prior);
const priorItems = priorInput.items || priorInput.selectedItems || [];
const currentInput = await readJson(args.current);
const currentItems = currentInput.items || currentInput.selectedItems || [];
const priorById = new Map(priorItems.map((item) => [itemIdentity(item), item]));
const currentById = new Map();
const newItems = [];
const changedItems = [];
const duplicateItems = [];

for (const item of currentItems) {
  const id = itemIdentity(item);
  if (currentById.has(id)) {
    duplicateItems.push(item);
    continue;
  }
  currentById.set(id, item);
  const prior = priorById.get(id);
  if (!prior) newItems.push(item);
  else if (contentMarker(prior) !== contentMarker(item)) changedItems.push(item);
}

const staleItems = priorItems.filter((item) => !currentById.has(itemIdentity(item)));
const weakDuplicates = findWeakDuplicates(currentItems);

await writeJson(args.out, {
  generatedAt: new Date().toISOString(),
  newItems,
  changedItems,
  duplicateItems,
  weakDuplicates,
  staleItems,
  coverage: {
    priorItems: priorItems.length,
    currentItems: currentItems.length,
    newItems: newItems.length,
    changedItems: changedItems.length,
    duplicateItems: duplicateItems.length,
    weakDuplicateGroups: weakDuplicates.length,
    staleItems: staleItems.length,
  },
});

function contentMarker(item) {
  return stableHash(`${item.title}|${item.updatedAt || item.publishedAt || ''}|${item.url || ''}|${item.contentText || item.summaryText || ''}`);
}

function findWeakDuplicates(items) {
  const groups = new Map();
  for (const item of items) {
    const key = `${String(item.title || '').toLowerCase()}|${item.publishedAt || item.updatedAt || ''}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
  }
  return [...groups.values()].filter((group) => group.length > 1).map((group) => ({
    reason: 'same_title_and_date',
    count: group.length,
    items: group.map((item) => ({ itemId: item.itemId, title: item.title, sourceId: item.sourceId })),
  }));
}
