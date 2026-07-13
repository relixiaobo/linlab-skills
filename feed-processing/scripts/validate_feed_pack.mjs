#!/usr/bin/env node
import { parseArgs, readJson, writeJson, itemIdentity, validUrl } from './lib/feed_common.mjs';

const args = parseArgs(process.argv.slice(2));
if (!args.input) {
  console.error('Usage: validate_feed_pack.mjs --input feed-pack.json [--out report.json]');
  process.exit(2);
}

const pack = await readJson(args.input);
const errors = [];
const warnings = [];

if (!pack.generatedAt) errors.push('missing generatedAt');
if (!pack.scope?.mode) errors.push('missing scope.mode');
if (!Array.isArray(pack.sources)) errors.push('sources must be an array');
if (!Array.isArray(pack.selectedItems)) errors.push('selectedItems must be an array');

for (const source of pack.sources || []) {
  if (!source.sourceId) errors.push(`source missing sourceId: ${source.feedUrl || source.siteUrl || 'unknown'}`);
  if (!source.feedUrl && !source.siteUrl) errors.push(`source ${source.sourceId || 'unknown'} has no feedUrl or siteUrl`);
  if (source.feedUrl && !validUrl(source.feedUrl) && !source.feedUrl.startsWith('file://')) errors.push(`invalid source feedUrl: ${source.feedUrl}`);
}

const identities = new Set();
for (const item of pack.selectedItems || []) {
  if (!item.title) errors.push(`item missing title: ${item.itemId || item.url || 'unknown'}`);
  if (!item.sourceId) errors.push(`item ${item.title || item.itemId || 'unknown'} missing sourceId`);
  if (!item.feedUrl) errors.push(`item ${item.title || item.itemId || 'unknown'} missing feedUrl`);
  if (!item.itemId && !item.rawId && !item.url) errors.push(`item ${item.title || 'unknown'} missing identity`);
  const identity = itemIdentity(item);
  if (identities.has(identity)) errors.push(`duplicate item identity: ${identity}`);
  identities.add(identity);
  if (item.url && !validUrl(item.url) && !item.url.startsWith('file://')) errors.push(`invalid item url: ${item.url}`);
  if (item.fullText && item.fullText.status !== 'not_requested') {
    if (!item.fullText.selectedStrategy) errors.push(`item ${item.title} fullText missing selectedStrategy`);
    if (!item.fullText.quality) errors.push(`item ${item.title} fullText missing quality`);
    if (!Array.isArray(item.fullText.attempts) || !item.fullText.attempts.length) errors.push(`item ${item.title} fullText missing attempt ledger`);
    if ((item.fullText.textPreview || '').length > 2000) errors.push(`item ${item.title} fullText preview oversized`);
  }
}

const coverage = pack.coverage || {};
if (coverage.selectedItems !== undefined && coverage.selectedItems !== (pack.selectedItems || []).length) {
  errors.push('coverage.selectedItems does not match selectedItems length');
}
if (coverage.sourceCount !== undefined && coverage.sourceCount !== (pack.sources || []).length) {
  errors.push('coverage.sourceCount does not match sources length');
}
if ((pack.errors || []).length && coverage.erroredSources === 0) {
  warnings.push('pack has errors but coverage.erroredSources is zero');
}

const report = {
  ok: errors.length === 0,
  errors,
  warnings,
  coverage,
};

await writeJson(args.out, report);
if (!report.ok) process.exit(1);
