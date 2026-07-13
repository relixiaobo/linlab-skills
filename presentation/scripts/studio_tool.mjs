#!/usr/bin/env node

import { spawn } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import {
  access,
  cp,
  mkdir,
  mkdtemp,
  readFile,
  readdir,
  rename,
  rm,
  stat,
  writeFile,
} from 'node:fs/promises';
import http from 'node:http';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const SKILL_ROOT = path.dirname(SCRIPT_DIR);
const TEMPLATE_ROOT = path.join(SKILL_ROOT, 'assets', 'templates', 'html-studio');
const THEMES_ROOT = path.join(SKILL_ROOT, 'assets', 'themes');
const THEME_INDEX = path.join(THEMES_ROOT, 'index.json');
const ARCHETYPES_ROOT = path.join(SKILL_ROOT, 'assets', 'archetypes');
const ARCHETYPE_INDEX = path.join(ARCHETYPES_ROOT, 'index.json');
const LAYOUTS_ROOT = path.join(SKILL_ROOT, 'assets', 'layouts');
const LAYOUT_INDEX = path.join(LAYOUTS_ROOT, 'index.json');
const HTML_TOOL = path.join(SCRIPT_DIR, 'html_tool.mjs');
const EVIDENCE_TOOL = path.join(SCRIPT_DIR, 'evidence_tool.py');
const PPTX_TOOL = path.join(SCRIPT_DIR, 'pptx_tool.py');
const RENDER_SLIDES = path.join(SCRIPT_DIR, 'render_slides.py');
const DEFAULT_CONFIG = 'studio.config.json';

function usage() {
  console.error(`Presentation Studio

Usage:
  studio_tool.mjs init <project-dir> [--theme <id>] [--archetype <id>] [--force]
  studio_tool.mjs themes
  studio_tool.mjs archetypes
  studio_tool.mjs layouts
  studio_tool.mjs doctor [project-dir] [--out <report.json>]
  studio_tool.mjs check [project-dir] [--out-dir <qa-dir>]
  studio_tool.mjs evidence-check [project-dir] [--out <report.json>]
  studio_tool.mjs render-html [project-dir] [--out-dir <renders/html>]
  studio_tool.mjs compile [project-dir] [--out <deck.pptx>] [--no-notes]
  studio_tool.mjs compare [project-dir] [--pptx <deck.pptx>] [--out <report.json>]

Every command except init/themes/archetypes/layouts reads studio.config.json from the project root.
`);
}

function parseArgs(argv) {
  const positional = [];
  const options = {};
  const booleanOptions = new Set(['force', 'no-notes', 'skip-evidence', 'skip-html-check']);
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (!value.startsWith('--')) {
      positional.push(value);
      continue;
    }
    const key = value.slice(2);
    if (booleanOptions.has(key)) {
      options[key] = true;
      continue;
    }
    const next = argv[index + 1];
    if (!next || next.startsWith('--')) throw new Error(`Missing value for --${key}`);
    options[key] = next;
    index += 1;
  }
  return { positional, options };
}

function asProject(value) {
  return path.resolve(value || '.');
}

async function pathExists(filePath) {
  try {
    await access(filePath);
    return true;
  } catch {
    return false;
  }
}

async function readJson(filePath, label = filePath) {
  let source;
  try {
    source = await readFile(filePath, 'utf8');
  } catch (error) {
    throw new Error(`Cannot read ${label}: ${error.message}`);
  }
  try {
    return JSON.parse(source);
  } catch (error) {
    throw new Error(`Invalid JSON in ${label}: ${error.message}`);
  }
}

async function writeJson(filePath, value) {
  await mkdir(path.dirname(filePath), { recursive: true });
  const temporary = `${filePath}.${randomUUID()}.tmp`;
  await writeFile(temporary, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
  await rename(temporary, filePath);
}

function requiredString(value, label) {
  if (typeof value !== 'string' || value.trim() === '') throw new Error(`${label} must be a non-empty string`);
  return value;
}

function requiredNumber(value, label) {
  if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) {
    throw new Error(`${label} must be a positive number`);
  }
  return value;
}

async function loadProject(project, explicitConfig) {
  const configPath = path.resolve(project, explicitConfig || DEFAULT_CONFIG);
  const config = await readJson(configPath, DEFAULT_CONFIG);
  if (config.schemaVersion !== '1.0') throw new Error('studio.config.json schemaVersion must be "1.0"');
  requiredString(config.entry, 'config.entry');
  requiredString(config.slideSelector, 'config.slideSelector');
  requiredString(config.notesSelector, 'config.notesSelector');
  requiredString(config.exportQuery, 'config.exportQuery');
  requiredString(config.themeId, 'config.themeId');
  requiredString(config.archetypeId, 'config.archetypeId');
  requiredString(config.archetype, 'config.archetype');
  requiredString(config.layoutLibrary, 'config.layoutLibrary');
  requiredNumber(config.canvas?.widthPx, 'config.canvas.widthPx');
  requiredNumber(config.canvas?.heightPx, 'config.canvas.heightPx');
  requiredNumber(config.canvas?.widthIn, 'config.canvas.widthIn');
  requiredNumber(config.canvas?.heightIn, 'config.canvas.heightIn');
  if (config.compiler?.package !== 'dom-to-pptx') {
    throw new Error('config.compiler.package must be "dom-to-pptx"');
  }
  requiredString(config.compiler?.version, 'config.compiler.version');

  const entry = path.resolve(project, config.entry);
  if (!(await pathExists(entry))) throw new Error(`Configured HTML entry does not exist: ${entry}`);
  const archetypePath = path.resolve(project, config.archetype);
  const layoutLibraryPath = path.resolve(project, config.layoutLibrary);
  const archetype = await readJson(archetypePath, 'configured narrative archetype');
  if (archetype.schemaVersion !== '1.0' || archetype.id !== config.archetypeId) {
    throw new Error('Configured narrative archetype does not match config.archetypeId');
  }
  const layoutLibrary = await readJson(layoutLibraryPath, 'configured layout library');
  if (layoutLibrary.schemaVersion !== '1.0' || !Array.isArray(layoutLibrary.layouts) || layoutLibrary.layouts.length === 0) {
    throw new Error('Configured layout library must contain a non-empty layouts array');
  }
  return { project, configPath, config, entry, archetypePath, archetype, layoutLibraryPath, layoutLibrary };
}

function projectOutput(projectInfo, key, fallback) {
  const configured = projectInfo.config.output?.[key] || fallback;
  return path.resolve(projectInfo.project, configured);
}

function projectRequire(project) {
  return createRequire(path.join(project, 'package.json'));
}

function findPackageJson(resolvedModule) {
  let current = path.dirname(resolvedModule);
  while (current !== path.dirname(current)) {
    const candidate = path.join(current, 'package.json');
    try {
      return createRequire(import.meta.url)(candidate);
    } catch {
      current = path.dirname(current);
    }
  }
  return null;
}

function resolveRuntime(project) {
  const requireFromProject = projectRequire(project);
  const compilerModule = requireFromProject.resolve('dom-to-pptx');
  const compilerPackage = findPackageJson(compilerModule);
  if (!compilerPackage) throw new Error('Could not locate dom-to-pptx/package.json');
  const bundle = path.join(path.dirname(compilerModule), 'dom-to-pptx.bundle.js');
  const puppeteer = requireFromProject('puppeteer');
  const JSZip = requireFromProject('jszip');
  return { requireFromProject, compilerModule, compilerPackage, bundle, puppeteer, JSZip };
}

function executableCandidates() {
  if (process.platform === 'darwin') {
    return [
      '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
      '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
      '/Applications/Chromium.app/Contents/MacOS/Chromium',
    ];
  }
  if (process.platform === 'win32') {
    const roots = [process.env.PROGRAMFILES, process.env['PROGRAMFILES(X86)'], process.env.LOCALAPPDATA].filter(Boolean);
    return roots.flatMap((root) => [
      path.join(root, 'Google', 'Chrome', 'Application', 'chrome.exe'),
      path.join(root, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
    ]);
  }
  return ['/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser', '/snap/bin/chromium'];
}

async function launchBrowser(puppeteer) {
  const base = { headless: true, args: ['--no-sandbox', '--disable-setuid-sandbox'] };
  try {
    return await puppeteer.launch(base);
  } catch (firstError) {
    for (const executablePath of executableCandidates()) {
      if (!(await pathExists(executablePath))) continue;
      try {
        return await puppeteer.launch({ ...base, executablePath });
      } catch {
        // Try the next locally installed browser.
      }
    }
    throw new Error(`Unable to launch a browser for Studio: ${firstError.message}`);
  }
}

function mimeType(filePath) {
  const extension = path.extname(filePath).toLowerCase();
  return {
    '.css': 'text/css; charset=utf-8',
    '.gif': 'image/gif',
    '.html': 'text/html; charset=utf-8',
    '.jpeg': 'image/jpeg',
    '.jpg': 'image/jpeg',
    '.js': 'text/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.mjs': 'text/javascript; charset=utf-8',
    '.png': 'image/png',
    '.svg': 'image/svg+xml',
    '.webp': 'image/webp',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
  }[extension] || 'application/octet-stream';
}

async function staticResponse(root, request, response) {
  try {
    const requestUrl = new URL(request.url || '/', 'http://127.0.0.1');
    if (requestUrl.pathname === '/favicon.ico') {
      response.writeHead(204).end();
      return;
    }
    const decoded = decodeURIComponent(requestUrl.pathname);
    const target = path.resolve(root, `.${decoded}`);
    if (target !== root && !target.startsWith(`${root}${path.sep}`)) {
      response.writeHead(403).end('Forbidden');
      return;
    }
    let source = target;
    if ((await stat(source)).isDirectory()) source = path.join(source, 'index.html');
    const body = await readFile(source);
    response.writeHead(200, { 'Content-Type': mimeType(source), 'Cache-Control': 'no-store' });
    response.end(body);
  } catch {
    response.writeHead(404).end('Not found');
  }
}

async function withStaticServer(root, callback) {
  const server = http.createServer((request, response) => {
    staticResponse(root, request, response).catch((error) => {
      response.writeHead(500).end(error.message);
    });
  });
  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  });
  try {
    const address = server.address();
    return await callback(`http://127.0.0.1:${address.port}`);
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
}

function entryUrl(baseUrl, projectInfo) {
  const relative = path.relative(projectInfo.project, projectInfo.entry).split(path.sep).map(encodeURIComponent).join('/');
  const query = projectInfo.config.exportQuery || '';
  return `${baseUrl}/${relative}${query}`;
}

async function waitForDeck(page, timeoutMs = 30000) {
  await page.evaluate(async (timeout) => {
    const deadline = Date.now() + timeout;
    if (document.fonts?.ready) await document.fonts.ready;
    await Promise.all([...document.images].map((image) => {
      if (image.complete) return Promise.resolve();
      return new Promise((resolve) => {
        image.addEventListener('load', resolve, { once: true });
        image.addEventListener('error', resolve, { once: true });
      });
    }));
    const ready = window.__PRESENTATION_READY__;
    if (ready && typeof ready.then === 'function') {
      await Promise.race([
        ready,
        new Promise((_, reject) => setTimeout(() => reject(new Error('window.__PRESENTATION_READY__ timed out')), Math.max(1, deadline - Date.now()))),
      ]);
    }
  }, timeoutMs);
}

async function inspectDeckDom(page, projectInfo) {
  return page.evaluate(({ slideSelector, notesSelector }) => {
    const slides = [...document.querySelectorAll(slideSelector)];
    return slides.map((slide, index) => ({
      index: index + 1,
      id: slide.id || slide.getAttribute('data-slide') || String(index + 1),
      notes: slide.querySelector(notesSelector)?.innerText?.trim() || '',
      dom: {
        canvas: slide.querySelectorAll('canvas').length,
        images: slide.querySelectorAll('img').length,
        svg: slide.querySelectorAll('svg').length,
        tables: slide.querySelectorAll('table').length,
      },
    }));
  }, {
    slideSelector: projectInfo.config.slideSelector,
    notesSelector: projectInfo.config.notesSelector,
  });
}

async function openDeckPage(browser, baseUrl, projectInfo) {
  const page = await browser.newPage();
  await page.setViewport({
    width: projectInfo.config.canvas.widthPx,
    height: projectInfo.config.canvas.heightPx,
    deviceScaleFactor: 1,
  });
  const consoleErrors = [];
  const requestFailures = [];
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });
  page.on('requestfailed', (request) => {
    requestFailures.push({ url: request.url(), error: request.failure()?.errorText || 'request failed' });
  });
  await page.goto(entryUrl(baseUrl, projectInfo), { waitUntil: 'networkidle0', timeout: 60000 });
  await waitForDeck(page, projectInfo.config.render?.timeoutMs || 30000);
  return { page, consoleErrors, requestFailures };
}

async function runProcess(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: options.cwd,
      env: { ...process.env, ...(options.env || {}) },
      stdio: options.inherit ? 'inherit' : ['ignore', 'pipe', 'pipe'],
    });
    let stdout = '';
    let stderr = '';
    if (!options.inherit) {
      child.stdout.on('data', (chunk) => { stdout += chunk; });
      child.stderr.on('data', (chunk) => { stderr += chunk; });
    }
    child.once('error', reject);
    child.once('close', (code) => resolve({ code, stdout, stderr }));
  });
}

async function runHtmlCheck(projectInfo, output) {
  await mkdir(path.dirname(output), { recursive: true });
  const result = await runProcess(process.execPath, [HTML_TOOL, 'inspect', projectInfo.entry, '--out', output], {
    cwd: projectInfo.project,
  });
  if (result.code !== 0) throw new Error(`HTML inspection failed. See ${output}${result.stderr ? `\n${result.stderr.trim()}` : ''}`);
  return readJson(output);
}

async function runEvidenceCheck(projectInfo, output) {
  const ledger = path.resolve(projectInfo.project, projectInfo.config.evidenceLedger || 'evidence-ledger.json');
  if (!(await pathExists(ledger))) throw new Error(`Configured evidence ledger does not exist: ${ledger}`);
  await mkdir(path.dirname(output), { recursive: true });
  const result = await runProcess('python3', [EVIDENCE_TOOL, 'check', ledger, '--html', projectInfo.entry, '--out', output], {
    cwd: projectInfo.project,
  });
  if (result.code !== 0) throw new Error(`Evidence check failed. See ${output}${result.stderr ? `\n${result.stderr.trim()}` : ''}`);
  return readJson(output);
}

async function commandCheck(projectInfo, options) {
  const qaDir = path.resolve(projectInfo.project, options['out-dir'] || projectInfo.config.output?.qaDir || 'qa');
  const htmlReport = path.join(qaDir, 'html-report.json');
  const evidenceReport = path.join(qaDir, 'evidence-report.json');
  const report = { schemaVersion: '1.0', ok: true, html: null, evidence: null };
  if (!options['skip-html-check']) report.html = await runHtmlCheck(projectInfo, htmlReport);
  if (!options['skip-evidence']) report.evidence = await runEvidenceCheck(projectInfo, evidenceReport);
  await writeJson(path.join(qaDir, 'studio-check.json'), report);
  return report;
}

function xmlEscape(value) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&apos;');
}

function replaceNotesText(xml, notes, slideNumber) {
  const pattern = /(<p:cNvPr\b[^>]*name="Notes Placeholder[^"]*"[\s\S]*?<p:txBody>[\s\S]*?<a:t(?:\s[^>]*)?>)([\s\S]*?)(<\/a:t>)/;
  if (!pattern.test(xml)) throw new Error(`PPTX notes placeholder is missing on slide ${slideNumber}`);
  return xml.replace(pattern, (_match, before, _current, after) => `${before}${xmlEscape(notes)}${after}`);
}

function naturalSlideNumber(name) {
  return Number(name.match(/slide(\d+)\.xml$/)?.[1] || 0);
}

async function patchSpeakerNotes(buffer, slides, JSZip) {
  const zip = await JSZip.loadAsync(buffer);
  const noteFiles = Object.keys(zip.files)
    .filter((name) => /^ppt\/notesSlides\/notesSlide\d+\.xml$/.test(name))
    .sort((left, right) => naturalSlideNumber(left) - naturalSlideNumber(right));
  if (noteFiles.length !== slides.length) {
    throw new Error(`PPTX contains ${noteFiles.length} notes slides for ${slides.length} HTML slides`);
  }
  for (let index = 0; index < slides.length; index += 1) {
    const name = noteFiles[index];
    const xml = await zip.file(name).async('string');
    zip.file(name, replaceNotesText(xml, slides[index].notes, index + 1));
  }
  const patched = await zip.generateAsync({ type: 'nodebuffer', compression: 'DEFLATE' });
  return { zip, patched };
}

function countMatches(value, pattern) {
  return [...value.matchAll(pattern)].length;
}

function relationshipMap(xml) {
  const values = new Map();
  const pattern = /<Relationship\b([^>]*)\/>/g;
  for (const match of xml.matchAll(pattern)) {
    const attrs = match[1];
    const id = attrs.match(/\bId="([^"]+)"/)?.[1];
    const target = attrs.match(/\bTarget="([^"]+)"/)?.[1];
    const type = attrs.match(/\bType="([^"]+)"/)?.[1];
    if (id) values.set(id, { target: target || '', type: type || '' });
  }
  return values;
}

function pictureRelationshipIds(slideXml) {
  const ids = [];
  for (const block of slideXml.matchAll(/<p:pic\b[\s\S]*?<\/p:pic>/g)) {
    const id = block[0].match(/<a:blip\b[^>]*\br:embed="([^"]+)"/)?.[1];
    ids.push({ id: id || '', block: block[0] });
  }
  return ids;
}

function percentage(value, total) {
  return total === 0 ? 0 : Math.round((value / total) * 1000) / 10;
}

async function editabilityReport(zip, slides, projectInfo, outputFile) {
  const presentationXml = await zip.file('ppt/presentation.xml').async('string');
  const slideSize = {
    cx: Number(presentationXml.match(/<p:sldSz\b[^>]*\bcx="(\d+)"/)?.[1] || 0),
    cy: Number(presentationXml.match(/<p:sldSz\b[^>]*\bcy="(\d+)"/)?.[1] || 0),
  };
  const slideFiles = Object.keys(zip.files)
    .filter((name) => /^ppt\/slides\/slide\d+\.xml$/.test(name))
    .sort((left, right) => naturalSlideNumber(left) - naturalSlideNumber(right));
  const totals = {
    nativeTextObjects: 0,
    nativeTextRuns: 0,
    nativeShapeObjects: 0,
    nativeTableObjects: 0,
    nativeChartObjects: 0,
    svgObjects: 0,
    rasterObjects: 0,
    fullSlideRasterCount: 0,
    hyperlinks: 0,
  };
  const perSlide = [];
  for (let index = 0; index < slideFiles.length; index += 1) {
    const slideName = slideFiles[index];
    const slideXml = await zip.file(slideName).async('string');
    const relName = `ppt/slides/_rels/slide${index + 1}.xml.rels`;
    const relXml = zip.file(relName) ? await zip.file(relName).async('string') : '';
    const relationships = relationshipMap(relXml);
    const shapes = [...slideXml.matchAll(/<p:sp\b[\s\S]*?<\/p:sp>/g)].map((match) => match[0]);
    const nativeTextObjects = shapes.filter((shape) => /<a:t\b/.test(shape)).length;
    const nativeTextRuns = countMatches(slideXml, /<a:t\b/g);
    const nativeShapeObjects = shapes.length + countMatches(slideXml, /<p:cxnSp\b/g);
    const nativeTableObjects = countMatches(slideXml, /<a:tbl\b/g);
    const nativeChartObjects = [...relationships.values()].filter((item) => item.type.endsWith('/chart')).length;
    let svgObjects = 0;
    let rasterObjects = 0;
    let fullSlideRasterCount = 0;
    for (const picture of pictureRelationshipIds(slideXml)) {
      const relation = relationships.get(picture.id);
      const target = relation?.target || '';
      const isSvg = target.toLowerCase().endsWith('.svg');
      if (isSvg) svgObjects += 1;
      else rasterObjects += 1;
      if (!isSvg && slideSize.cx && slideSize.cy) {
        const x = Number(picture.block.match(/<a:off\b[^>]*\bx="(-?\d+)"/)?.[1] || 0);
        const y = Number(picture.block.match(/<a:off\b[^>]*\by="(-?\d+)"/)?.[1] || 0);
        const cx = Number(picture.block.match(/<a:ext\b[^>]*\bcx="(\d+)"/)?.[1] || 0);
        const cy = Number(picture.block.match(/<a:ext\b[^>]*\bcy="(\d+)"/)?.[1] || 0);
        if (Math.abs(x) <= slideSize.cx * 0.02 && Math.abs(y) <= slideSize.cy * 0.02
          && cx >= slideSize.cx * 0.96 && cy >= slideSize.cy * 0.96) fullSlideRasterCount += 1;
      }
    }
    const hyperlinks = [...relationships.values()].filter((item) => item.type.endsWith('/hyperlink')).length;
    const values = {
      slide: index + 1,
      nativeTextObjects,
      nativeTextRuns,
      nativeShapeObjects,
      nativeTableObjects,
      nativeChartObjects,
      svgObjects,
      rasterObjects,
      fullSlideRasterCount,
      hyperlinks,
      htmlDom: slides[index]?.dom || {},
      notesInjected: Boolean(slides[index]?.notes),
    };
    perSlide.push(values);
    for (const key of Object.keys(totals)) totals[key] += values[key];
  }

  const nativeObjects = totals.nativeShapeObjects + totals.nativeTableObjects + totals.nativeChartObjects;
  const classifiedObjects = nativeObjects + totals.svgObjects + totals.rasterObjects;
  const requestedNotes = slides.filter((slide) => slide.notes).length;
  const limitations = [];
  const htmlTables = slides.reduce((sum, slide) => sum + slide.dom.tables, 0);
  const htmlCanvases = slides.reduce((sum, slide) => sum + slide.dom.canvas, 0);
  const htmlSvgs = slides.reduce((sum, slide) => sum + slide.dom.svg, 0);
  if (htmlTables > 0 && totals.nativeTableObjects === 0) {
    limitations.push('HTML tables are editable drawing/text objects, not semantic PowerPoint table objects.');
  }
  if (htmlCanvases > 0) limitations.push('Canvas regions compile as raster content unless replaced with SVG or native shapes.');
  if (htmlSvgs > totals.svgObjects) {
    limitations.push(`${htmlSvgs - totals.svgObjects} HTML SVG region(s) did not remain SVG objects in the PPTX.`);
  }
  if (totals.svgObjects > 0) limitations.push('SVG objects remain vector containers; they are not semantic PowerPoint charts.');
  if (totals.fullSlideRasterCount > 0) limitations.push('One or more slides contain a full-slide raster object.');

  const report = {
    schemaVersion: '1.0',
    artifact: path.relative(projectInfo.project, outputFile),
    compiler: {
      package: projectInfo.config.compiler.package,
      version: projectInfo.config.compiler.version,
      svgAsVector: projectInfo.config.compiler.svgAsVector,
    },
    slideCount: slideFiles.length,
    coverage: {
      basis: 'top-level PowerPoint object count; percentages are not visual-area coverage',
      nativePowerPoint: { objects: nativeObjects, percent: percentage(nativeObjects, classifiedObjects) },
      svgVector: { objects: totals.svgObjects, percent: percentage(totals.svgObjects, classifiedObjects) },
      raster: { objects: totals.rasterObjects, percent: percentage(totals.rasterObjects, classifiedObjects) },
    },
    objects: totals,
    notes: {
      htmlSlidesWithNotes: requestedNotes,
      pptxSlidesWithInjectedNotes: requestedNotes,
      status: requestedNotes === 0 ? 'not-requested' : 'passed',
    },
    limitations,
    status: limitations.length > 0 ? 'warning' : 'passed',
    perSlide,
  };
  return report;
}

async function compileDeck(projectInfo, options) {
  await commandCheck(projectInfo, options);
  const runtime = resolveRuntime(projectInfo.project);
  if (runtime.compilerPackage.version !== projectInfo.config.compiler.version) {
    throw new Error(`dom-to-pptx ${runtime.compilerPackage.version} is installed; config pins ${projectInfo.config.compiler.version}`);
  }
  if (!(await pathExists(runtime.bundle))) throw new Error(`dom-to-pptx browser bundle is missing: ${runtime.bundle}`);
  const output = path.resolve(projectInfo.project, options.out || projectInfo.config.output?.pptx || 'output/deck.pptx');
  await mkdir(path.dirname(output), { recursive: true });

  const compiled = await withStaticServer(projectInfo.project, async (baseUrl) => {
    const browser = await launchBrowser(runtime.puppeteer);
    try {
      const { page, consoleErrors, requestFailures } = await openDeckPage(browser, baseUrl, projectInfo);
      const slides = await inspectDeckDom(page, projectInfo);
      if (slides.length === 0) throw new Error(`No slides match ${projectInfo.config.slideSelector}`);
      if (requestFailures.length > 0 || consoleErrors.length > 0) {
        const details = [
          ...requestFailures.map((item) => `${item.error}: ${item.url}`),
          ...consoleErrors,
        ].slice(0, 8).join('\n');
        throw new Error(`The HTML deck has browser runtime errors:\n${details}`);
      }
      await page.addScriptTag({ path: runtime.bundle });
      const dataUrl = await page.evaluate(async ({ selector, pptxOptions }) => {
        const targets = [...document.querySelectorAll(selector)];
        const blob = await window.domToPptx.exportToPptx(targets, {
          ...pptxOptions,
          skipDownload: true,
        });
        return new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onloadend = () => resolve(reader.result);
          reader.onerror = reject;
          reader.readAsDataURL(blob);
        });
      }, {
        selector: projectInfo.config.slideSelector,
        pptxOptions: {
          title: projectInfo.config.metadata?.title || path.basename(projectInfo.project),
          author: projectInfo.config.metadata?.author || '',
          width: projectInfo.config.canvas.widthIn,
          height: projectInfo.config.canvas.heightIn,
          svgAsVector: projectInfo.config.compiler.svgAsVector,
        },
      });
      return {
        buffer: Buffer.from(String(dataUrl).split(',')[1], 'base64'),
        slides,
        consoleErrors,
        requestFailures,
      };
    } finally {
      await browser.close();
    }
  });

  const notesSlides = options['no-notes']
    ? compiled.slides.map((slide) => ({ ...slide, notes: '' }))
    : compiled.slides;
  const { zip, patched } = await patchSpeakerNotes(compiled.buffer, notesSlides, runtime.JSZip);
  const temporary = `${output}.${randomUUID()}.tmp`;
  await writeFile(temporary, patched);
  await rename(temporary, output);

  const editabilityPath = projectOutput(projectInfo, 'editability', 'qa/pptx-editability.json');
  const editability = await editabilityReport(zip, notesSlides, projectInfo, output);
  await writeJson(editabilityPath, editability);

  const gatePath = projectOutput(projectInfo, 'pptxGate', 'qa/pptx-gate.json');
  const gate = await runProcess('python3', [PPTX_TOOL, 'gate', output, '--out', gatePath], {
    cwd: projectInfo.project,
  });
  if (gate.code !== 0) throw new Error(`Compiled PPTX failed the technical gate. See ${gatePath}`);

  const report = {
    schemaVersion: '1.0',
    ok: true,
    artifact: output,
    slides: compiled.slides.length,
    notes: editability.notes,
    editability: editabilityPath,
    technicalGate: gatePath,
    browserConsoleErrors: compiled.consoleErrors,
    requestFailures: compiled.requestFailures,
  };
  await writeJson(projectOutput(projectInfo, 'compileReport', 'qa/compile-report.json'), report);
  return report;
}

async function renderOwnership(outputDir) {
  if (!(await pathExists(outputDir))) return { exists: false, unowned: [] };
  const entries = await readdir(outputDir);
  if (entries.length === 0) return { exists: true, unowned: [] };
  const manifestPath = path.join(outputDir, 'render-manifest.json');
  if (!(await pathExists(manifestPath))) {
    throw new Error(`Refusing to replace non-empty render directory without render-manifest.json: ${outputDir}`);
  }
  const manifest = await readJson(manifestPath, 'existing render manifest');
  if (manifest.schemaVersion !== '1.0' || !Array.isArray(manifest.slides)) {
    throw new Error(`Existing render manifest is not owned by Presentation Studio: ${manifestPath}`);
  }
  const owned = new Set(['render-manifest.json']);
  for (const slide of manifest.slides) {
    if (typeof slide.file !== 'string' || path.basename(slide.file) !== slide.file) {
      throw new Error(`Existing render manifest contains an unsafe slide filename: ${slide.file}`);
    }
    owned.add(slide.file);
  }
  if (typeof manifest.contact_sheet === 'string') owned.add(manifest.contact_sheet);
  return { exists: true, unowned: entries.filter((entry) => !owned.has(entry)) };
}

async function preserveUnownedFiles(outputDir, staging, unowned) {
  const stagedNames = new Set(await readdir(staging));
  for (const name of unowned) {
    if (stagedNames.has(name)) {
      throw new Error(`Generated render would overwrite an unowned file: ${path.join(outputDir, name)}`);
    }
    await cp(path.join(outputDir, name), path.join(staging, name), { recursive: true, force: false });
  }
}

async function publishDirectory(staging, outputDir, outputExists) {
  if (!outputExists) {
    await rename(staging, outputDir);
    return;
  }
  const backup = `${outputDir}.backup-${randomUUID()}`;
  await rename(outputDir, backup);
  try {
    await rename(staging, outputDir);
  } catch (error) {
    await rename(backup, outputDir);
    throw error;
  }
  await rm(backup, { recursive: true, force: true });
}

async function diffOwnership(outputDir) {
  if (!(await pathExists(outputDir))) return { exists: false, unowned: [] };
  const entries = await readdir(outputDir);
  if (entries.length === 0) return { exists: true, unowned: [] };
  const manifestPath = path.join(outputDir, 'diff-manifest.json');
  if (!(await pathExists(manifestPath))) {
    throw new Error(`Refusing to replace non-empty diff directory without diff-manifest.json: ${outputDir}`);
  }
  const manifest = await readJson(manifestPath, 'existing diff manifest');
  if (manifest.schemaVersion !== '1.0' || !Array.isArray(manifest.files)) {
    throw new Error(`Existing diff manifest is not owned by Presentation Studio: ${manifestPath}`);
  }
  const owned = new Set(['diff-manifest.json']);
  for (const file of manifest.files) {
    if (typeof file !== 'string' || path.basename(file) !== file) {
      throw new Error(`Existing diff manifest contains an unsafe filename: ${file}`);
    }
    owned.add(file);
  }
  return { exists: true, unowned: entries.filter((entry) => !owned.has(entry)) };
}

async function makeContactSheet(browser, slideFiles, output) {
  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 900, deviceScaleFactor: 1 });
  const images = [];
  for (const file of slideFiles) {
    const data = await readFile(file);
    images.push(`data:image/png;base64,${data.toString('base64')}`);
  }
  const cards = images.map((source, index) => `<figure><img src="${source}"><figcaption>${index + 1}</figcaption></figure>`).join('');
  await page.setContent(`<!doctype html><style>
    *{box-sizing:border-box}body{margin:0;padding:32px;background:#16181b;color:white;font:16px Arial,sans-serif}
    main{display:grid;grid-template-columns:repeat(4,1fr);gap:24px}figure{margin:0}img{display:block;width:100%;aspect-ratio:16/9;object-fit:contain;background:white;box-shadow:0 8px 24px #0008}figcaption{padding-top:8px;color:#bfc4ca}
  </style><main>${cards}</main>`, { waitUntil: 'load' });
  await page.screenshot({ path: output, type: 'webp', quality: 88, fullPage: true });
  await page.close();
}

async function renderHtml(projectInfo, options) {
  const runtime = resolveRuntime(projectInfo.project);
  const outputDir = path.resolve(projectInfo.project, options['out-dir'] || projectInfo.config.output?.htmlRenders || 'renders/html');
  const ownership = await renderOwnership(outputDir);
  await mkdir(path.dirname(outputDir), { recursive: true });
  const staging = await mkdtemp(path.join(path.dirname(outputDir), `.${path.basename(outputDir)}-`));
  let completed = false;
  try {
    const result = await withStaticServer(projectInfo.project, async (baseUrl) => {
      const browser = await launchBrowser(runtime.puppeteer);
      try {
        const { page, consoleErrors, requestFailures } = await openDeckPage(browser, baseUrl, projectInfo);
        await page.addStyleTag({ content: `${projectInfo.config.controlsSelector || '.deck-controls'}{display:none!important}` });
        const handles = await page.$$(projectInfo.config.slideSelector);
        if (handles.length === 0) throw new Error(`No slides match ${projectInfo.config.slideSelector}`);
        const files = [];
        for (let index = 0; index < handles.length; index += 1) {
          const file = `slide-${String(index + 1).padStart(3, '0')}.png`;
          const target = path.join(staging, file);
          await handles[index].screenshot({ path: target, type: 'png' });
          files.push(target);
        }
        await makeContactSheet(browser, files, path.join(staging, 'contact-sheet.webp'));
        return { files, consoleErrors, requestFailures };
      } finally {
        await browser.close();
      }
    });
    const manifest = {
      schemaVersion: '1.0',
      source: path.relative(projectInfo.project, projectInfo.entry),
      slide_count: result.files.length,
      width: projectInfo.config.canvas.widthPx,
      height: projectInfo.config.canvas.heightPx,
      slides: result.files.map((file, index) => ({ page: index + 1, file: path.basename(file) })),
      contact_sheet: 'contact-sheet.webp',
      browser_console_errors: result.consoleErrors,
      request_failures: result.requestFailures,
    };
    await writeJson(path.join(staging, 'render-manifest.json'), manifest);
    await preserveUnownedFiles(outputDir, staging, ownership.unowned);
    await publishDirectory(staging, outputDir, ownership.exists);
    completed = true;
    return { ...manifest, outputDir };
  } finally {
    if (!completed) await rm(staging, { recursive: true, force: true });
  }
}

async function renderPptx(projectInfo, pptx, outputDir, dpi) {
  const result = await runProcess('python3', [RENDER_SLIDES, pptx, '--out-dir', outputDir, '--dpi', String(dpi || 144)], {
    cwd: projectInfo.project,
  });
  if (result.code !== 0) throw new Error(`PPTX rendering failed: ${(result.stderr || result.stdout).trim()}`);
  return readJson(path.join(outputDir, 'render-manifest.json'));
}

async function comparePair(page, left, right, diffPath) {
  const leftData = `data:image/png;base64,${(await readFile(left)).toString('base64')}`;
  const rightData = `data:image/png;base64,${(await readFile(right)).toString('base64')}`;
  const result = await page.evaluate(async ({ leftDataUrl, rightDataUrl }) => {
    const load = (source) => new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = reject;
      image.src = source;
    });
    const [leftImage, rightImage] = await Promise.all([load(leftDataUrl), load(rightDataUrl)]);
    const width = 480;
    const height = 270;
    const canvas = document.createElement('canvas');
    const other = document.createElement('canvas');
    const diff = document.createElement('canvas');
    for (const item of [canvas, other, diff]) { item.width = width; item.height = height; }
    const leftContext = canvas.getContext('2d', { willReadFrequently: true });
    const rightContext = other.getContext('2d', { willReadFrequently: true });
    const diffContext = diff.getContext('2d');
    leftContext.drawImage(leftImage, 0, 0, width, height);
    rightContext.drawImage(rightImage, 0, 0, width, height);
    const leftPixels = leftContext.getImageData(0, 0, width, height);
    const rightPixels = rightContext.getImageData(0, 0, width, height);
    const output = diffContext.createImageData(width, height);
    let absolute = 0;
    let mismatched = 0;
    for (let index = 0; index < leftPixels.data.length; index += 4) {
      const red = Math.abs(leftPixels.data[index] - rightPixels.data[index]);
      const green = Math.abs(leftPixels.data[index + 1] - rightPixels.data[index + 1]);
      const blue = Math.abs(leftPixels.data[index + 2] - rightPixels.data[index + 2]);
      const delta = (red + green + blue) / 3;
      absolute += delta;
      if (Math.max(red, green, blue) > 32) mismatched += 1;
      output.data[index] = Math.min(255, delta * 3);
      output.data[index + 1] = 24;
      output.data[index + 2] = Math.min(255, delta * 2.2);
      output.data[index + 3] = 255;
    }
    diffContext.putImageData(output, 0, 0);
    return {
      meanAbsoluteDelta: absolute / (width * height * 255),
      mismatchRatio: mismatched / (width * height),
      diffDataUrl: diff.toDataURL('image/png'),
    };
  }, { leftDataUrl: leftData, rightDataUrl: rightData });
  await writeFile(diffPath, Buffer.from(result.diffDataUrl.split(',')[1], 'base64'));
  delete result.diffDataUrl;
  return result;
}

async function compareDeck(projectInfo, options) {
  const pptx = path.resolve(projectInfo.project, options.pptx || projectInfo.config.output?.pptx || 'output/deck.pptx');
  if (!(await pathExists(pptx))) throw new Error(`PPTX does not exist: ${pptx}`);
  const htmlDir = projectOutput(projectInfo, 'htmlRenders', 'renders/html');
  const pptxDir = projectOutput(projectInfo, 'pptxRenders', 'renders/pptx');
  const diffDir = projectOutput(projectInfo, 'diffRenders', 'renders/diff');
  const htmlManifest = await renderHtml(projectInfo, { 'out-dir': htmlDir });
  const pptxManifest = await renderPptx(projectInfo, pptx, pptxDir, Number(options.dpi || 144));
  const htmlSlides = htmlManifest.slides || [];
  const pptxSlides = pptxManifest.slides || [];
  if (htmlSlides.length !== pptxSlides.length) {
    throw new Error(`Render count mismatch: HTML ${htmlSlides.length}, PPTX ${pptxSlides.length}`);
  }
  const ownership = await diffOwnership(diffDir);
  await mkdir(path.dirname(diffDir), { recursive: true });
  const diffStaging = await mkdtemp(path.join(path.dirname(diffDir), `.${path.basename(diffDir)}-`));
  const runtime = resolveRuntime(projectInfo.project);
  const browser = await launchBrowser(runtime.puppeteer);
  const page = await browser.newPage();
  const slides = [];
  let diffPublished = false;
  try {
    for (let index = 0; index < htmlSlides.length; index += 1) {
      const left = path.join(htmlDir, htmlSlides[index].file);
      const right = path.join(pptxDir, pptxSlides[index].file);
      const diffFile = `diff-${String(index + 1).padStart(3, '0')}.png`;
      const metrics = await comparePair(page, left, right, path.join(diffStaging, diffFile));
      let status = 'passed';
      if (metrics.meanAbsoluteDelta > 0.18 || metrics.mismatchRatio > 0.55) status = 'failed';
      else if (metrics.meanAbsoluteDelta > 0.08 || metrics.mismatchRatio > 0.25) status = 'review';
      slides.push({ slide: index + 1, ...metrics, status, diff: path.relative(projectInfo.project, path.join(diffDir, diffFile)) });
    }
  } catch (error) {
    await rm(diffStaging, { recursive: true, force: true });
    throw error;
  } finally {
    await page.close();
    await browser.close();
  }
  try {
    const diffFiles = slides.map((slide) => path.basename(slide.diff));
    await writeJson(path.join(diffStaging, 'diff-manifest.json'), {
      schemaVersion: '1.0',
      files: diffFiles,
    });
    await preserveUnownedFiles(diffDir, diffStaging, ownership.unowned);
    await publishDirectory(diffStaging, diffDir, ownership.exists);
    diffPublished = true;
  } finally {
    if (!diffPublished) await rm(diffStaging, { recursive: true, force: true });
  }
  const failed = slides.filter((slide) => slide.status === 'failed').map((slide) => slide.slide);
  const review = slides.filter((slide) => slide.status === 'review').map((slide) => slide.slide);
  const report = {
    schemaVersion: '1.0',
    basis: '480x270 normalized pixel comparison; browser and office font rasterization differences still require human review',
    htmlManifest: path.relative(projectInfo.project, path.join(htmlDir, 'render-manifest.json')),
    pptxManifest: path.relative(projectInfo.project, path.join(pptxDir, 'render-manifest.json')),
    slideCount: slides.length,
    status: failed.length > 0 ? 'failed' : review.length > 0 ? 'review' : 'passed',
    failedSlides: failed,
    reviewSlides: review,
    slides,
  };
  const output = path.resolve(projectInfo.project, options.out || projectInfo.config.output?.comparison || 'qa/visual-comparison.json');
  await writeJson(output, report);
  if (failed.length > 0) throw new Error(`Visual comparison found blocking differences on slides: ${failed.join(', ')}. See ${output}`);
  return { ...report, output };
}

async function which(command) {
  const result = await runProcess(process.platform === 'win32' ? 'where' : 'which', [command]);
  return result.code === 0 ? result.stdout.trim().split(/\r?\n/)[0] : null;
}

async function doctor(projectInfo, options) {
  const checks = [];
  const add = (name, required, status, detail) => checks.push({ name, required, status, detail });
  const [nodeMajor, nodeMinor] = process.versions.node.split('.').map(Number);
  const supportedNode = nodeMajor > 22 || (nodeMajor === 22 && nodeMinor >= 12);
  add('node', true, supportedNode ? 'passed' : 'failed', `${process.version}; requires >=22.12.0`);
  try {
    const runtime = resolveRuntime(projectInfo.project);
    add('dom-to-pptx', true, runtime.compilerPackage.version === projectInfo.config.compiler.version ? 'passed' : 'failed', runtime.compilerPackage.version);
    add('dom-to-pptx bundle', true, await pathExists(runtime.bundle) ? 'passed' : 'failed', runtime.bundle);
    add('puppeteer', true, runtime.puppeteer ? 'passed' : 'failed', runtime.requireFromProject.resolve('puppeteer'));
    add('jszip', true, runtime.JSZip ? 'passed' : 'failed', runtime.requireFromProject.resolve('jszip'));
    let browserPath = null;
    try { browserPath = runtime.puppeteer.executablePath(); } catch { /* reported below */ }
    if (browserPath && await pathExists(browserPath)) add('browser', true, 'passed', browserPath);
    else {
      const local = (await Promise.all(executableCandidates().map(async (candidate) => await pathExists(candidate) ? candidate : null))).find(Boolean);
      add('browser', true, local ? 'passed' : 'failed', local || 'No Puppeteer or system browser found');
    }
  } catch (error) {
    add('studio node dependencies', true, 'failed', error.message);
  }
  const python = await which('python3');
  add('python3', true, python ? 'passed' : 'failed', python || 'not found');
  const libreOfficeCandidates = [
    await which('soffice'),
    await which('libreoffice'),
    '/Applications/LibreOffice.app/Contents/MacOS/soffice',
  ];
  const libreOffice = (await Promise.all(libreOfficeCandidates.filter(Boolean).map(async (candidate) => await pathExists(candidate) ? candidate : null))).find(Boolean);
  add('LibreOffice', false, libreOffice ? 'passed' : 'warning', libreOffice || 'required for PPTX rendering');
  const pptxRasterizer = await which('pdftoppm');
  add('PPTX visual renderer', false, pptxRasterizer ? 'passed' : 'warning', pptxRasterizer || 'LibreOffice and Poppler are required for PPTX visual comparison');
  const report = {
    schemaVersion: '1.0',
    project: projectInfo.project,
    ok: !checks.some((check) => check.required && check.status === 'failed'),
    checks,
  };
  const output = options.out ? path.resolve(projectInfo.project, options.out) : null;
  if (output) await writeJson(output, report);
  return report;
}

async function listThemes() {
  const index = await readJson(THEME_INDEX, 'theme index');
  return index.themes;
}

async function listArchetypes() {
  const index = await readJson(ARCHETYPE_INDEX, 'archetype index');
  return index.archetypes;
}

async function listLayouts() {
  const index = await readJson(LAYOUT_INDEX, 'layout index');
  return index.layouts;
}

function packageName(directory) {
  const value = path.basename(directory).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  return value || 'presentation-studio-project';
}

async function initProject(target, options) {
  const themes = await listThemes();
  const archetypes = await listArchetypes();
  const themeId = options.theme || 'analytical-ledger';
  const archetypeId = options.archetype || 'research-report';
  const theme = themes.find((item) => item.id === themeId);
  const archetype = archetypes.find((item) => item.id === archetypeId);
  if (!theme) throw new Error(`Unknown theme ${themeId}. Run themes to list valid ids.`);
  if (!archetype) throw new Error(`Unknown archetype ${archetypeId}. Run archetypes to list valid ids.`);
  await mkdir(target, { recursive: true });
  const existing = await readdir(target);
  if (existing.length > 0 && !options.force) {
    throw new Error(`Project directory is not empty: ${target}. Use --force to overwrite scaffold files without deleting other files.`);
  }
  await cp(TEMPLATE_ROOT, target, { recursive: true, force: Boolean(options.force) });
  const themeTarget = path.join(target, 'theme');
  await mkdir(themeTarget, { recursive: true });
  await cp(path.join(THEMES_ROOT, themeId, 'tokens.css'), path.join(themeTarget, 'tokens.css'), { force: true });
  await cp(path.join(THEMES_ROOT, themeId, 'design.md'), path.join(themeTarget, 'design.md'), { force: true });
  const narrativeTarget = path.join(target, 'narrative');
  await mkdir(narrativeTarget, { recursive: true });
  await writeJson(path.join(narrativeTarget, 'archetype.json'), {
    schemaVersion: '1.0',
    ...archetype,
  });
  await cp(LAYOUT_INDEX, path.join(target, 'layout-library.json'), { force: true });
  const configPath = path.join(target, DEFAULT_CONFIG);
  const config = await readJson(configPath);
  config.themeId = themeId;
  config.archetypeId = archetypeId;
  config.archetype = 'narrative/archetype.json';
  config.layoutLibrary = 'layout-library.json';
  await writeJson(configPath, config);
  const packagePath = path.join(target, 'package.json');
  const packageJson = await readJson(packagePath);
  packageJson.name = packageName(target);
  await writeJson(packagePath, packageJson);
  const lockPath = path.join(target, 'package-lock.json');
  if (await pathExists(lockPath)) {
    const lock = await readJson(lockPath);
    lock.name = packageJson.name;
    if (lock.packages?.['']) lock.packages[''].name = packageJson.name;
    await writeJson(lockPath, lock);
  }
  return { project: target, theme: themeId, archetype: archetypeId, files: await readdir(target) };
}

function printResult(value) {
  process.stdout.write(`${JSON.stringify(value, null, 2)}\n`);
}

async function main() {
  const [command, ...argv] = process.argv.slice(2);
  if (!command || command === '--help' || command === '-h') {
    usage();
    return command ? 0 : 2;
  }
  const { positional, options } = parseArgs(argv);
  if (command === 'themes') {
    printResult(await listThemes());
    return 0;
  }
  if (command === 'archetypes') {
    printResult(await listArchetypes());
    return 0;
  }
  if (command === 'layouts') {
    printResult(await listLayouts());
    return 0;
  }
  if (command === 'init') {
    if (!positional[0]) throw new Error('init requires a project directory');
    printResult(await initProject(path.resolve(positional[0]), options));
    return 0;
  }

  const project = asProject(positional[0]);
  const projectInfo = await loadProject(project, options.config);
  if (command === 'doctor') {
    const result = await doctor(projectInfo, options);
    printResult(result);
    return result.ok ? 0 : 1;
  }
  if (command === 'check') {
    printResult(await commandCheck(projectInfo, options));
    return 0;
  }
  if (command === 'evidence-check') {
    const output = path.resolve(project, options.out || projectInfo.config.output?.evidenceReport || 'qa/evidence-report.json');
    printResult(await runEvidenceCheck(projectInfo, output));
    return 0;
  }
  if (command === 'render-html') {
    printResult(await renderHtml(projectInfo, options));
    return 0;
  }
  if (command === 'compile') {
    printResult(await compileDeck(projectInfo, options));
    return 0;
  }
  if (command === 'compare') {
    printResult(await compareDeck(projectInfo, options));
    return 0;
  }
  usage();
  return 2;
}

main().then((code) => {
  process.exitCode = code;
}).catch((error) => {
  console.error(`presentation-studio: ${error.message}`);
  process.exitCode = 1;
});
