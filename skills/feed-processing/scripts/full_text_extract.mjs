#!/usr/bin/env node
import { parseArgs, asArray, readJson, readText, writeJson, stableHash, extractArticleText, contentStats } from './lib/feed_common.mjs';

const args = parseArgs(process.argv.slice(2));
if (!args.input) {
  console.error('Usage: full_text_extract.mjs --input selected.json [--article itemId=article.html] [--out out.json]');
  process.exit(2);
}

const input = await readJson(args.input);
const items = input.items || input.selectedItems || [];
const articleMap = new Map();
for (const pair of asArray(args.article)) {
  const [id, path] = String(pair).split('=');
  if (id && path) articleMap.set(id, path);
}

const selectedItems = [];
for (const item of items) {
  selectedItems.push({ ...item, fullText: await extractForItem(item) });
}

await writeJson(args.out, {
  generatedAt: new Date().toISOString(),
  scope: input.scope,
  sources: input.sources || [],
  items: selectedItems,
  skipped: input.skipped || [],
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
    skippedItems: input.coverage?.skippedItems ?? (input.skipped || []).reduce((sum, row) => sum + (row.count || 0), 0),
    erroredSources: input.coverage?.erroredSources ?? (input.errors || []).length,
    complete: selectedItems.filter((item) => item.fullText.status === 'complete').length,
    partial: selectedItems.filter((item) => item.fullText.status === 'partial').length,
    failed: selectedItems.filter((item) => item.fullText.status === 'failed').length,
  },
});

async function extractForItem(item) {
  const attempts = [];
  const feedText = item.contentText || '';
  const summaryText = item.summaryText || '';
  if (feedText.length >= 500 || (feedText.length >= 150 && feedText.length > summaryText.length * 1.8)) {
    attempts.push({ strategy: 'feed_content', status: 'success', ...contentStats(feedText), confidence: 'high' });
    return result('complete', 'feed_content', feedText, attempts, 'high', 'low');
  }
  attempts.push({
    strategy: 'feed_content',
    status: feedText ? 'partial' : 'failed',
    reason: feedText ? 'feed_summary_only' : 'extractor_empty',
    ...contentStats(feedText),
    confidence: 'low',
  });

  const articlePath = articleMap.get(item.itemId) || articleMap.get(item.rawId) || articleMap.get(stableHash(item.url || ''));
  if (!articlePath) {
    attempts.push({ strategy: 'static_readability', status: 'skipped', reason: 'no_article_url' });
    return result(feedText ? 'partial' : 'failed', feedText ? 'feed_content' : 'static_readability', feedText, attempts, 'low', 'medium');
  }

  const html = await readText(articlePath);
  const extracted = extractArticleText(html);
  if (extracted.articleText.length >= 200) {
    attempts.push({ strategy: 'static_readability', status: 'success', ...contentStats(extracted.articleText), confidence: extracted.boilerplateRisk === 'high' ? 'medium' : 'high' });
    return result('complete', 'static_readability', extracted.articleText, attempts, extracted.boilerplateRisk === 'high' ? 'medium' : 'high', extracted.boilerplateRisk);
  }
  attempts.push({ strategy: 'static_readability', status: 'failed', reason: 'extractor_too_short', ...contentStats(extracted.articleText), confidence: 'low' });
  if (extracted.bodyText.length >= 200) {
    attempts.push({ strategy: 'static_defuddle', status: 'partial', ...contentStats(extracted.bodyText), confidence: 'medium' });
    return result('partial', 'static_defuddle', extracted.bodyText, attempts, 'medium', 'high');
  }
  attempts.push({ strategy: 'static_defuddle', status: 'failed', reason: html.includes('<script') ? 'client_rendered' : 'extractor_empty', ...contentStats(extracted.bodyText), confidence: 'low' });
  return result(feedText ? 'partial' : 'failed', feedText ? 'feed_content' : 'static_defuddle', feedText || extracted.bodyText, attempts, 'low', 'high');
}

function result(status, selectedStrategy, text, attempts, confidence, boilerplateRisk) {
  const stats = contentStats(text);
  return {
    status,
    selectedStrategy,
    textPreview: text.slice(0, 1000),
    confidence,
    quality: {
      ...stats,
      titleMatched: true,
      authorMatched: null,
      dateMatched: null,
      contentToSummaryRatio: null,
      boilerplateRisk,
    },
    attempts,
  };
}
