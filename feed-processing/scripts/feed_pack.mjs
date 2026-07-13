#!/usr/bin/env node
import { parseArgs, readJson, writeJson } from './lib/feed_common.mjs';

const args = parseArgs(process.argv.slice(2));
if (!args.input) {
  console.error('Usage: feed_pack.mjs --input selected.json [--out feed-pack.json]');
  process.exit(2);
}

const input = await readJson(args.input);
const selectedItems = input.items || input.selectedItems || [];
const errors = input.errors || [];
const skipped = input.skipped || [];
const sources = input.sources || [];

await writeJson(args.out, {
  generatedAt: new Date().toISOString(),
  scope: input.scope || { mode: 'all' },
  sources,
  selectedItems,
  skipped,
  errors,
  warnings: input.warnings || [],
  coverage: {
    sourceCount: sources.length,
    fetched: input.coverage?.fetched ?? sources.length,
    notModified: input.coverage?.notModified ?? 0,
    parsedItems: input.coverage?.parsedItems ?? input.coverage?.inputItems ?? selectedItems.length,
    selectedItems: selectedItems.length,
    skippedItems: input.coverage?.skippedItems ?? skipped.reduce((sum, row) => sum + (row.count || 0), 0),
    erroredSources: errors.length,
  },
});
