#!/usr/bin/env node
import { access, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

const PLACEHOLDER_RE = /\b(lorem|ipsum|todo|placeholder|sample|dummy|xxxx)\b/gi;
const IMAGE_RE = /!\[[^\]]*\]\(([^)]+)\)/g;
const LINK_RE = /(?<!!)\[[^\]]+\]\(([^)]+)\)/g;
const TABLE_ROW_RE = /^\s*\|(.+)\|\s*$/;
const BARE_URL_RE = /(^|[\s(])(https?:\/\/[^\s)]+)(?=$|[\s)])/g;

function usage() {
  console.error('Usage: node scripts/markdown_tool.mjs inspect draft.md [--out report.json]');
}

function localReferences(markdown) {
  const refs = [];
  for (const match of markdown.matchAll(IMAGE_RE)) refs.push(match[1]);
  for (const match of markdown.matchAll(LINK_RE)) refs.push(match[1]);
  return refs.filter((value) => {
    const clean = value.trim();
    if (!clean || clean.startsWith('#')) return false;
    if (/^(https?:|data:|mailto:|tel:)/i.test(clean)) return false;
    return true;
  });
}

function externalReferences(markdown) {
  const refs = [];
  for (const match of markdown.matchAll(IMAGE_RE)) refs.push(match[1]);
  for (const match of markdown.matchAll(LINK_RE)) refs.push(match[1]);
  return refs.filter((value) => /^https?:/i.test(value.trim()));
}

function remoteImageReferences(markdown) {
  const refs = [];
  for (const match of markdown.matchAll(IMAGE_RE)) refs.push(match[1]);
  return refs.filter((value) => /^https?:/i.test(value.trim()));
}

async function existingLocalReference(filePath, ref) {
  const cleanRef = ref.split('#')[0].split('?')[0].replace(/^<|>$/g, '');
  if (!cleanRef) return true;
  try {
    await access(path.resolve(path.dirname(filePath), cleanRef));
    return true;
  } catch {
    return false;
  }
}

async function inspectMarkdown(filePath, markdown) {
  const { frontMatter, body } = parseFrontMatter(markdown);
  const proseMarkdown = stripFencedCodeBlocks(body);
  const headings = [...proseMarkdown.matchAll(/^(#{1,6})(?:[ \t]+(.*))?$/gm)].map((match) => ({
    level: match[1].length,
    text: (match[2] ?? '').trim(),
  }));
  const emptyHeadings = headings
    .map((heading, index) => ({ heading_index: index + 1, level: heading.level, text: heading.text }))
    .filter((heading) => heading.text.length === 0 || /^\[?(?:todo|placeholder|tbd|to be written)\]?$/i.test(heading.text));
  const headingTextCounts = new Map();
  for (const heading of headings) {
    const key = heading.text.toLowerCase();
    headingTextCounts.set(key, (headingTextCounts.get(key) ?? 0) + 1);
  }
  const duplicateHeadings = [...headingTextCounts.entries()]
    .filter(([, count]) => count > 1)
    .map(([text, count]) => ({ text, count }));
  const headingLevelJumps = [];
  let previousLevel = 0;
  headings.forEach((heading, index) => {
    if (heading.level > previousLevel + 1) {
      headingLevelJumps.push({ heading_index: index + 1, level: heading.level, previous_level: previousLevel });
    }
    previousLevel = heading.level;
  });

  const paragraphs = proseMarkdown
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter((block) => {
      if (!block) return false;
      if (/^#{1,6}\s+/m.test(block)) return false;
      if (/^```/.test(block)) return false;
      if (/^\s*[-*+]\s+/m.test(block)) return false;
      if (TABLE_ROW_RE.test(block.split('\n')[0] ?? '')) return false;
      return true;
    });
  const longParagraphs = paragraphs
    .map((text, index) => ({ index: index + 1, word_count: text.split(/\s+/).filter(Boolean).length }))
    .filter((item) => item.word_count > 120);

  const tableRows = body.split('\n').filter((line) => TABLE_ROW_RE.test(line));
  const tableCount = countMarkdownTables(body);
  const wideTableRows = tableRows
    .map((line, index) => ({ row_index: index + 1, column_count: line.split('|').length - 2 }))
    .filter((row) => row.column_count > 6);
  const refs = localReferences(body);
  const externalRefs = externalReferences(body);
  const remoteImageRefs = remoteImageReferences(body);
  const bareUrls = sortedUnique([...body.matchAll(BARE_URL_RE)].map((match) => match[2]));
  const brokenLocalReferences = [];
  for (const ref of refs) {
    if (!(await existingLocalReference(filePath, ref))) brokenLocalReferences.push(ref);
  }
  const placeholders = sortedUnique([...body.matchAll(PLACEHOLDER_RE)].map((match) => match[0].toLowerCase()));
  const errors = [];
  const warnings = [];
  if (headings.length === 0) warnings.push('no_headings_found');
  if (headings[0] && headings[0].level !== 1) warnings.push('first_heading_not_h1');
  if (headingLevelJumps.length > 0) warnings.push('heading_level_jump_found');
  if (emptyHeadings.length > 0) warnings.push('empty_or_placeholder_heading_found');
  if (duplicateHeadings.length > 0) warnings.push('duplicate_heading_found');
  if (longParagraphs.length > 0) warnings.push('long_paragraph_found');
  if (wideTableRows.length > 0) warnings.push('wide_table_found');
  if (placeholders.length > 0) warnings.push('placeholder_text_found');
  if (brokenLocalReferences.length > 0) errors.push('broken_local_asset_reference_found');
  if (remoteImageRefs.length > 0) warnings.push('remote_image_reference_found');
  if (bareUrls.length > 0) warnings.push('bare_url_found');
  if (frontMatter.present && frontMatter.fields.convert === false) warnings.push('front_matter_convert_false');
  if (!frontMatter.present && /\b(docx|word|client|deliverable|classification|version)\b/i.test(body)) {
    warnings.push('front_matter_missing_for_deliverable');
  }
  if (!/\b(source|citation|evidence|reference|出处|来源)\b/i.test(body) && body.split(/\s+/).filter(Boolean).length > 500) {
    warnings.push('source_coverage_not_obvious');
  }

  return {
    file: filePath,
    ok: errors.length === 0,
    errors,
    word_count: body.split(/\s+/).filter(Boolean).length,
    front_matter: frontMatter,
    paragraph_count: paragraphs.length,
    long_paragraphs: longParagraphs,
    heading_count: headings.length,
    headings,
    heading_level_jumps: headingLevelJumps,
    empty_headings: emptyHeadings,
    duplicate_headings: duplicateHeadings,
    table_count: tableCount,
    wide_table_rows: wideTableRows,
    local_references: sortedUnique(refs),
    external_references: sortedUnique(externalRefs),
    remote_image_references: sortedUnique(remoteImageRefs),
    bare_urls: bareUrls,
    broken_local_references: sortedUnique(brokenLocalReferences),
    placeholder_hits: placeholders,
    warnings,
  };
}

function parseFrontMatter(markdown) {
  const empty = { present: false, fields: {}, raw: '' };
  const match = markdown.match(/^---\r?\n([\s\S]*?)\r?\n---[ \t]*(?:\r?\n|$)/);
  if (!match) {
    return {
      frontMatter: markdown.startsWith('---\n') || markdown.startsWith('---\r\n')
        ? { ...empty, malformed: true }
        : empty,
      body: markdown,
    };
  }
  const raw = match[1].trim();
  const fields = {};
  for (const line of raw.split('\n')) {
    const match = line.match(/^\s*([A-Za-z0-9_-]+)\s*:\s*(.*?)\s*$/);
    if (!match) continue;
    const value = match[2].replace(/^["']|["']$/g, '');
    fields[match[1]] = value === 'true' ? true : value === 'false' ? false : value;
  }
  return {
    frontMatter: { present: true, fields, raw },
    body: markdown.slice(match[0].length),
  };
}

function stripFencedCodeBlocks(markdown) {
  return markdown.replace(/^```[\s\S]*?^```/gm, '');
}

function sortedUnique(values) {
  return [...new Set(values)].sort((a, b) => a.localeCompare(b));
}

function countMarkdownTables(markdown) {
  const lines = markdown.split('\n');
  let count = 0;
  let inTable = false;
  for (const line of lines) {
    const isRow = TABLE_ROW_RE.test(line);
    if (isRow && !inTable) {
      count += 1;
      inTable = true;
    } else if (!isRow) {
      inTable = false;
    }
  }
  return count;
}

const [command, input, ...rest] = process.argv.slice(2);
if (command !== 'inspect' || !input) {
  usage();
  process.exit(2);
}

let out = '-';
for (let index = 0; index < rest.length; index += 1) {
  if (rest[index] === '--out') {
    out = rest[index + 1] ?? '-';
    index += 1;
  }
}

const inputPath = path.resolve(input);
const markdown = await readFile(inputPath, 'utf8');
const report = await inspectMarkdown(inputPath, markdown);
const json = `${JSON.stringify(report, null, 2)}\n`;
if (out === '-') {
  process.stdout.write(json);
} else {
  await writeFile(path.resolve(out), json, 'utf8');
}
process.exit(report.ok ? 0 : 1);
