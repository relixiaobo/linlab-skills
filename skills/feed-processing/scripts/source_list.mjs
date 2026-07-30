#!/usr/bin/env node
import { parseArgs, asArray, parseSourceList, readText, writeJson } from './lib/feed_common.mjs';

const args = parseArgs(process.argv.slice(2));
const inputs = asArray(args.input);
const warnings = [];
let sources = [];

if (inputs.length) {
  for (const input of inputs) {
    const result = parseSourceList(await readText(input), input);
    sources = sources.concat(result.sources);
    warnings.push(...result.warnings);
  }
} else {
  const stdin = await new Promise((resolve) => {
    let data = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', (chunk) => { data += chunk; });
    process.stdin.on('end', () => resolve(data));
  });
  const result = parseSourceList(stdin, 'stdin');
  sources = result.sources;
  warnings.push(...result.warnings);
}

await writeJson(args.out, {
  generatedAt: new Date().toISOString(),
  sources,
  warnings,
  coverage: {
    sourceCount: sources.length,
    warningCount: warnings.length,
  },
});
