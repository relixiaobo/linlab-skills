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
const terminalStatuses = new Set(['parsed', 'empty', 'not_modified', 'failed', 'skipped']);

if (pack.schemaVersion && pack.schemaVersion !== '1.0') errors.push(`unsupported schemaVersion: ${pack.schemaVersion}`);
if (!pack.generatedAt) errors.push('missing generatedAt');
if (!pack.scope?.mode) errors.push('missing scope.mode');
if (!Array.isArray(pack.sources)) errors.push('sources must be an array');
if (!Array.isArray(pack.selectedItems)) errors.push('selectedItems must be an array');

for (const source of pack.sources || []) {
  if (!source.sourceId) errors.push(`source missing sourceId: ${source.inputUrl || source.feedUrl || source.siteUrl || 'unknown'}`);
  if (!source.inputUrl && !source.feedUrl && !source.siteUrl) errors.push(`source ${source.sourceId || 'unknown'} has no inputUrl, feedUrl, or siteUrl`);
  if (source.feedUrl && !validUrl(source.feedUrl) && !source.feedUrl.startsWith('file://')) errors.push(`invalid source feedUrl: ${source.feedUrl}`);
  if (source.status && !terminalStatuses.has(source.status)) errors.push(`source ${source.sourceId || 'unknown'} has invalid status: ${source.status}`);
  if (source.status && !Array.isArray(source.attempts)) errors.push(`source ${source.sourceId || 'unknown'} attempts must be an array`);
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
const portableSources = (pack.sources || []).filter((source) => source.status);
if (portableSources.length && portableSources.length !== (pack.sources || []).length) {
  errors.push('portable source status is missing from one or more sources');
}
if (coverage.selectedItems !== undefined && coverage.selectedItems !== (pack.selectedItems || []).length) {
  errors.push('coverage.selectedItems does not match selectedItems length');
}
if (coverage.sourceCount !== undefined && coverage.sourceCount !== (pack.sources || []).length) {
  errors.push('coverage.sourceCount does not match sources length');
}
if ((pack.errors || []).length && coverage.erroredSources === 0) {
  warnings.push('pack has errors but coverage.erroredSources is zero');
}
if (coverage.parsedItems !== undefined && coverage.parsedItems < (pack.selectedItems || []).length) {
  errors.push('coverage.parsedItems is smaller than selectedItems length');
}
if (portableSources.length) {
  const count = (status) => portableSources.filter((source) => source.status === status).length;
  const expected = {
    parsedSources: count('parsed'),
    emptySources: count('empty'),
    notModifiedSources: count('not_modified'),
    failedSources: count('failed'),
    skippedSources: count('skipped'),
  };
  for (const [key, value] of Object.entries(expected)) {
    if (coverage[key] !== undefined && Number(coverage[key]) !== value) errors.push(`coverage.${key} does not match source statuses`);
  }
  if (coverage.requestedSources !== undefined && Number(coverage.requestedSources) !== portableSources.length) {
    errors.push('coverage.requestedSources does not match portable sources length');
  }
}
if (coverage.requestedSources !== undefined) {
  const terminalTotal = ['parsedSources', 'emptySources', 'notModifiedSources', 'failedSources', 'skippedSources']
    .reduce((sum, key) => sum + Number(coverage[key] || 0), 0);
  if (terminalTotal !== Number(coverage.requestedSources)) errors.push('terminal source coverage does not reconcile');
}

const report = {
  ok: errors.length === 0,
  errors,
  warnings,
  coverage,
};

await writeJson(args.out, report);
if (!report.ok) process.exit(1);
