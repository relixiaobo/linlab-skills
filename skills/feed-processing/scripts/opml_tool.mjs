#!/usr/bin/env node
import { parseArgs, readText, readJson, writeJson, parseOpmlSources } from './lib/feed_common.mjs';

const args = parseArgs(process.argv.slice(2));
const command = args._[0] || args.command || 'inspect';

if (!args.input) {
  console.error('Usage: opml_tool.mjs inspect|to-sources|validate|from-sources --input file [--out out.json]');
  process.exit(2);
}

if (command === 'inspect' || command === 'to-sources' || command === 'validate') {
  const sources = parseOpmlSources(await readText(args.input));
  const warnings = sources.filter((source) => !source.feedUrl).map((source) => ({ code: 'missing_xmlUrl', severity: 'warning', sourceId: source.sourceId }));
  const output = command === 'validate'
    ? { ok: warnings.length === 0, warnings, sourceCount: sources.length }
    : { sources, warnings, coverage: { sourceCount: sources.length } };
  await writeJson(args.out, output);
  if (command === 'validate' && !output.ok) process.exit(1);
} else if (command === 'from-sources') {
  const input = await readJson(args.input);
  const sources = input.sources || [];
  const outlines = sources.map((source) => `    <outline type="rss" text="${escapeXml(source.title || source.feedUrl)}" title="${escapeXml(source.title || source.feedUrl)}" xmlUrl="${escapeXml(source.feedUrl || '')}" htmlUrl="${escapeXml(source.siteUrl || '')}" />`).join('\n');
  const opml = `<?xml version="1.0" encoding="UTF-8"?>\n<opml version="2.0">\n  <head><title>Feed Processing export</title></head>\n  <body>\n${outlines}\n  </body>\n</opml>\n`;
  if (args.out) await import('node:fs/promises').then((fs) => fs.writeFile(args.out, opml));
  else process.stdout.write(opml);
} else {
  console.error(`Unknown command: ${command}`);
  process.exit(2);
}

function escapeXml(value) {
  return String(value ?? '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
