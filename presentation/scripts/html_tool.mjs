#!/usr/bin/env node
import { access, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const PLACEHOLDER_RE = /\b(lorem|ipsum|todo|placeholder|sample|dummy|xxxx)\b|\[(?:\u5fc5\u586b|todo|placeholder)[^\]]*\]|replace\s+(?:this|with)\b/gi;
const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const LAYOUT_INDEX_PATH = path.join(path.dirname(SCRIPT_DIR), 'assets', 'layouts', 'index.json');
const LAYOUT_INDEX = JSON.parse(await readFile(LAYOUT_INDEX_PATH, 'utf8'));
const REGISTERED_LAYOUTS = new Set(LAYOUT_INDEX.layouts.map((layout) => layout.id));
const TEXT_ONLY_LAYOUTS = new Set(['section', 'statement', 'quote', 'close']);
const VISUAL_MARKER_RE = /<(img|svg|canvas|video|figure|table)\b|class\s*=\s*["'][^"']*\b(metric|stage-visual|device-frame|feature-grid|visual-frame|timeline|quote|gallery|compare|diagram|signal|panel|number|chart|map|callout|table|evidence-wall)\b/i;
const TINY_FONT_RE = /font-size\s*:\s*((?:[0-9](?:\.\d+)?)|(?:1[0-3](?:\.\d+)?))px\b/gi;
const ASSET_POSTURES = new Set(['visual', 'mixed', 'analytical']);
const IMAGE_FITS = new Set(['cover', 'contain']);

function usage() {
  console.error('Usage: node scripts/html_tool.mjs inspect deck.html [--out report.json]');
}

function attrValues(html, attr) {
  const values = [];
  const re = new RegExp(`${attr}\\s*=\\s*["']([^"']+)["']`, 'gi');
  for (const match of html.matchAll(re)) values.push(match[1]);
  return values;
}

function attrValue(html, attr) {
  return attrValues(html, attr)[0];
}

function hasAttribute(tag, attr) {
  const escaped = attr.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp(`\\s${escaped}(?=\\s|=|/?>)`, 'i').test(tag);
}

function classList(tag) {
  return (attrValue(tag, 'class') ?? '').split(/\s+/).filter(Boolean);
}

function imageElements(html) {
  return [...html.matchAll(/<img\b[^>]*>/gi)].map((match) => {
    const tag = match[0];
    return {
      tag,
      src: attrValue(tag, 'src') ?? '',
      assetId: attrValue(tag, 'data-asset-id') ?? '',
      role: attrValue(tag, 'data-asset-role') ?? '',
      fit: (attrValue(tag, 'data-fit') ?? '').toLowerCase(),
      focalPoint: attrValue(tag, 'data-focal-point') ?? '',
    };
  });
}

function contentBackgroundImageRefs(html) {
  const refs = [];
  const re = /background(?:-image)?\s*:[^;{}]*url\(\s*["']?([^"')\s]+)["']?\s*\)/gi;
  for (const match of html.matchAll(re)) refs.push(match[1]);
  return sortedUnique(refs);
}

function isSpeakerNotesTag(tag) {
  return classList(tag).includes('speaker-notes');
}

function speakerNotesElements(html) {
  const elements = [];
  const rawTextRanges = [...html.matchAll(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/gi)]
    .map((match) => ({ start: match.index, end: match.index + match[0].length }));
  const openingTagRe = /<(?:aside|div)\b[^>]*>/gi;
  let coveredUntil = -1;
  for (const match of html.matchAll(openingTagRe)) {
    if (match.index < coveredUntil) continue;
    if (rawTextRanges.some((range) => match.index >= range.start && match.index < range.end)) continue;
    const openingTag = match[0];
    if (!isSpeakerNotesTag(openingTag)) continue;
    const tagName = openingTag.match(/^<([a-z0-9-]+)/i)?.[1]?.toLowerCase();
    if (!tagName) continue;
    const tagRe = new RegExp(`<\\/?${tagName}\\b[^>]*>`, 'gi');
    tagRe.lastIndex = match.index;
    let depth = 0;
    let end = match.index + openingTag.length;
    for (const tokenMatch of html.matchAll(tagRe)) {
      const token = tokenMatch[0];
      if (/^<\//.test(token)) {
        depth -= 1;
        if (depth === 0) {
          end = tokenMatch.index + token.length;
          break;
        }
      } else if (!/\/\s*>$/.test(token)) {
        depth += 1;
      }
    }
    elements.push({ openingTag, start: match.index, end });
    coveredUntil = end;
  }
  return elements;
}

function stripSpeakerNotesElements(html) {
  const elements = speakerNotesElements(html).sort((a, b) => b.start - a.start);
  let audienceHtml = html;
  for (const element of elements) {
    audienceHtml = audienceHtml.slice(0, element.start) + audienceHtml.slice(element.end);
  }
  return audienceHtml;
}

function collectSlideElements(html) {
  const slideElements = [];
  const deckStages = [];
  const stack = [];
  const structuralTags = new Set(['main', 'section', 'article', 'div']);
  const slideTags = new Set(['section', 'article', 'div']);
  const tokenRe = /<!--[\s\S]*?-->|<\/?(?:main|section|article|div|script|style)\b[^>]*>/gi;
  let rawTextTag = null;

  for (const match of html.matchAll(tokenRe)) {
    const token = match[0];
    if (token.startsWith('<!--')) continue;
    const tagName = token.match(/^<\/?\s*([a-z0-9-]+)/i)?.[1]?.toLowerCase();
    if (!tagName) continue;
    const closing = /^<\//.test(token);

    if (rawTextTag) {
      if (closing && tagName === rawTextTag) rawTextTag = null;
      continue;
    }
    if (!closing && (tagName === 'script' || tagName === 'style')) {
      if (!/\/\s*>$/.test(token)) rawTextTag = tagName;
      continue;
    }
    if (!structuralTags.has(tagName)) continue;

    if (!closing) {
      const classes = classList(token);
      const isDeckStage = classes.includes('deck-stage') || hasAttribute(token, 'data-deck');
      const slideAncestor = [...stack].reverse().find((item) => item.isSlide) ?? null;
      const deckStageAncestor = [...stack].reverse().find((item) => item.isDeckStage) ?? null;
      const entry = {
        tagName,
        start: match.index,
        tag: token,
        classes,
        layout: attrValue(token, 'data-layout') ?? '',
        assetPosture: attrValue(token, 'data-asset-posture') ?? '',
        isDeckStage,
        isSlide: !isDeckStage && slideTags.has(tagName)
          && (classes.includes('slide') || hasAttribute(token, 'data-slide')),
        slideAncestor,
        deckStage: null,
      };
      entry.deckStage = isDeckStage ? entry : deckStageAncestor;
      if (isDeckStage) deckStages.push(entry);
      if (/\/\s*>$/.test(token)) {
        if (entry.isSlide) slideElements.push({ ...entry, html: token });
      } else {
        stack.push(entry);
      }
      continue;
    }

    let openIndex = stack.length - 1;
    while (openIndex >= 0 && stack[openIndex].tagName !== tagName) openIndex -= 1;
    if (openIndex < 0) continue;
    const end = match.index + token.length;
    const closedEntries = stack.splice(openIndex);
    for (const entry of closedEntries) {
      if (entry.isSlide) slideElements.push({ ...entry, html: html.slice(entry.start, end) });
    }
  }

  for (const entry of stack) {
    if (entry.isSlide) slideElements.push({ ...entry, html: html.slice(entry.start) });
  }

  const ordered = slideElements.sort((a, b) => a.start - b.start);
  const scoped = deckStages.length > 0
    ? ordered.filter((slide) => slide.deckStage !== null)
    : ordered;
  const candidateIndex = new Map(scoped.map((slide, index) => [slide.start, index + 1]));
  const isNestedInDeck = (slide) => slide.slideAncestor !== null
    && (deckStages.length === 0 || slide.slideAncestor.deckStage === slide.deckStage);
  const nested = scoped.filter((slide) => isNestedInDeck(slide));
  const pages = scoped.filter((slide) => !isNestedInDeck(slide));

  return {
    slides: pages.map((slide, index) => ({
      index: index + 1,
      html: slide.html,
      tag: slide.tag,
      layout: slide.layout,
      classes: slide.classes,
    })),
    nestedSlideElements: nested.map((slide) => ({
      element_index: candidateIndex.get(slide.start),
      tag: slide.tagName,
      parent_element_index: candidateIndex.get(slide.slideAncestor?.start) ?? null,
    })),
    deckAssetPostures: deckStages.map((stage) => stage.assetPosture).filter(Boolean),
    deckStageCount: deckStages.length,
    ignoredSlideElementCount: ordered.length - scoped.length,
  };
}

function hasFixedStageHint(html) {
  const hasAspectRatio = /aspect-ratio\s*:\s*[0-9]+(?:\.[0-9]+)?\s*\/\s*[0-9]+(?:\.[0-9]+)?/i.test(html);
  const hasStageVariables = /--stage-width\s*:\s*[0-9]+(?:\.[0-9]+)?(?:px|pt|in|cm|mm)/i.test(html)
    && /--stage-height\s*:\s*[0-9]+(?:\.[0-9]+)?(?:px|pt|in|cm|mm)/i.test(html);
  return hasAspectRatio || hasStageVariables;
}

function hasKeyboardNavigation(html) {
  return /addEventListener\s*\(\s*['"]keydown['"]/i.test(html)
    || /onkeydown\s*=/i.test(html)
    || /keydown/i.test(html) && /(ArrowRight|ArrowLeft|PageDown|PageUp|Home|End|Space|\s['"]\s)/i.test(html);
}

function remoteDependencies(html) {
  const remoteSrcs = attrValues(html, 'src').filter((value) => /^https?:/i.test(value.trim()));
  const remoteCssUrls = [];
  const cssUrlRe = /url\(\s*["']?(https?:[^"')\s]+)["']?\s*\)/gi;
  for (const match of html.matchAll(cssUrlRe)) remoteCssUrls.push(match[1]);

  const remoteLinks = [];
  const linkRe = /<link\b[^>]*>/gi;
  for (const match of html.matchAll(linkRe)) {
    const href = attrValues(match[0], 'href')[0];
    if (href && /^https?:/i.test(href.trim())) remoteLinks.push(href);
  }
  return sortedUnique([...remoteSrcs, ...remoteCssUrls, ...remoteLinks]);
}

async function existingLocalReference(filePath, ref) {
  const cleanRef = ref.split('#')[0].split('?')[0];
  if (!cleanRef) return true;
  try {
    await access(path.resolve(path.dirname(filePath), cleanRef));
    return true;
  } catch {
    return false;
  }
}

async function inspectHtml(filePath, html) {
  const collection = collectSlideElements(html);
  const slides = collection.slides;
  const slideCount = slides.length;
  const audienceDocument = stripSpeakerNotesElements(html);
  const backgroundImageRefs = contentBackgroundImageRefs(audienceDocument);
  const localRefs = [
    ...attrValues(html, 'src'),
    ...attrValues(html, 'href'),
    ...backgroundImageRefs,
  ].filter((value) => {
    if (!value || value.startsWith('#')) return false;
    if (/^(https?:|data:|mailto:|tel:)/i.test(value)) return false;
    return true;
  });
  const placeholders = sortedUnique([...html.matchAll(PLACEHOLDER_RE)].map((match) => match[0].toLowerCase()));
  const remoteDependencyRefs = remoteDependencies(html);
  const errors = [];
  const warnings = [];
  const analyzedSlides = slides.map((slide) => ({
    ...slide,
    audienceHtml: stripSpeakerNotesElements(slide.html),
    speakerNotesTags: speakerNotesElements(slide.html).map((element) => element.openingTag),
  }));
  const imageAssets = analyzedSlides.flatMap((slide) => imageElements(slide.audienceHtml)
    .map((asset) => ({ ...asset, slide: slide.index })));
  const imageContractIssues = imageAssets.flatMap((asset) => {
    const issues = [];
    if (!asset.assetId) issues.push('missing_asset_id');
    if (!asset.role) issues.push('missing_asset_role');
    if (!asset.fit) issues.push('missing_fit');
    else if (!IMAGE_FITS.has(asset.fit)) issues.push('invalid_fit');
    if (asset.fit === 'cover' && !asset.focalPoint) issues.push('cover_missing_focal_point');
    return issues.length > 0 ? [{ ...asset, issues }] : [];
  });
  const mediaBearingSlides = analyzedSlides
    .filter((slide) => /<(img|video)\b/i.test(slide.audienceHtml))
    .map((slide) => slide.index);
  const assetPostures = sortedUnique(collection.deckAssetPostures);
  const assetPosture = assetPostures.length === 1 ? assetPostures[0] : '';
  const layouts = analyzedSlides.map((slide) => slide.layout).filter(Boolean);
  const missingLayoutSlides = analyzedSlides
    .filter((slide) => !slide.layout)
    .map((slide) => slide.index);
  const customLayouts = sortedUnique(layouts.filter((layout) => !REGISTERED_LAYOUTS.has(layout)));
  const textOnlySlides = analyzedSlides
    .filter((slide) => !TEXT_ONLY_LAYOUTS.has(slide.layout)
      && !VISUAL_MARKER_RE.test(slide.audienceHtml))
    .map((slide) => slide.index);
  const notesSlides = analyzedSlides
    .filter((slide) => slide.speakerNotesTags.length > 0)
    .map((slide) => slide.index);
  const unhiddenSpeakerNotesSlides = analyzedSlides
    .filter((slide) => slide.speakerNotesTags.some(
      (tag) => !hasAttribute(tag, 'hidden')
    ))
    .map((slide) => slide.index);
  const bulletDenseSlides = analyzedSlides
    .filter((slide) => (slide.audienceHtml.match(/<li\b/gi) ?? []).length >= 5)
    .map((slide) => slide.index);
  const tinyTextHits = sortedUnique(
    [...audienceDocument.matchAll(TINY_FONT_RE)].map((match) => `${match[1]}px`)
  );
  const slideDisplayNone = /\.slide[^{]*{[^}]*display\s*:\s*none/i.test(html);
  const visiblePresenterText = analyzedSlides
    .filter((slide) => /speaker\s*(notes?|script)|presenter\s*(notes?|view)|\u9010\u5b57\u7a3f|\u8bb2\u7a3f|\u6f14\u8bb2\u8005/i.test(
      slide.audienceHtml
    ))
    .map((slide) => slide.index);
  const brokenLocalReferences = [];
  for (const ref of localRefs) {
    if (!(await existingLocalReference(filePath, ref))) brokenLocalReferences.push(ref);
  }
  if (slideCount === 0) errors.push('no_slide_elements_found');
  if (collection.nestedSlideElements.length > 0) errors.push('nested_slide_element_found');
  if (unhiddenSpeakerNotesSlides.length > 0) errors.push('speaker_notes_not_hidden');
  if (assetPostures.length > 1) errors.push('conflicting_asset_postures');
  if (assetPosture && !ASSET_POSTURES.has(assetPosture)) errors.push('invalid_asset_posture');
  if (imageContractIssues.length > 0) errors.push('image_asset_contract_failed');
  if (['visual', 'mixed'].includes(assetPosture) && mediaBearingSlides.length === 0) {
    errors.push('required_media_missing');
  }
  if (placeholders.length > 0) warnings.push('placeholder_text_found');
  if (brokenLocalReferences.length > 0) errors.push('broken_local_asset_reference_found');
  if (remoteDependencyRefs.length > 0) warnings.push('remote_dependency_reference_found');
  if (!hasKeyboardNavigation(html)) warnings.push('keyboard_navigation_not_obvious');
  if (!hasFixedStageHint(html)) warnings.push('missing_fixed_stage_hint');
  if (!assetPosture) warnings.push('missing_asset_posture');
  if (backgroundImageRefs.length > 0) warnings.push('content_background_image_found');
  if (slideDisplayNone) warnings.push('display_none_slide_switching_risk');
  if (missingLayoutSlides.length > 0) warnings.push('missing_layout_metadata_found');
  if (slideCount >= 4 && new Set(layouts).size <= 2) warnings.push('low_layout_variety');
  if (textOnlySlides.length > 0) warnings.push('text_only_slide_found');
  if (bulletDenseSlides.length > 0) warnings.push('bullet_dump_risk');
  if (tinyTextHits.length > 0) warnings.push('tiny_text_risk');
  if (visiblePresenterText.length > 0) warnings.push('presenter_text_visible_risk');

  return {
    file: filePath,
    ok: errors.length === 0,
    layout_catalog_version: LAYOUT_INDEX.schemaVersion,
    errors,
    slide_count: slideCount,
    deck_stage_count: collection.deckStageCount,
    asset_posture: assetPosture,
    asset_postures: assetPostures,
    nested_slide_elements: collection.nestedSlideElements,
    ignored_slide_element_count: collection.ignoredSlideElementCount,
    layouts: sortedUnique(layouts),
    standard_layouts: sortedUnique(layouts.filter((layout) => REGISTERED_LAYOUTS.has(layout))),
    custom_layouts: customLayouts,
    missing_layout_slides: missingLayoutSlides,
    unknown_layouts: [],
    visual_slide_count: slideCount - textOnlySlides.length,
    media_bearing_slides: mediaBearingSlides,
    image_count: imageAssets.length,
    image_assets: imageAssets,
    image_contract_issues: imageContractIssues,
    content_background_image_references: backgroundImageRefs,
    text_only_slides: textOnlySlides,
    notes_slides: notesSlides,
    unhidden_speaker_notes_slides: unhiddenSpeakerNotesSlides,
    bullet_dense_slides: bulletDenseSlides,
    tiny_text_hits: tinyTextHits,
    visible_presenter_text_slides: visiblePresenterText,
    local_references: sortedUnique(localRefs),
    remote_dependency_references: remoteDependencyRefs,
    broken_local_references: sortedUnique(brokenLocalReferences),
    placeholder_hits: placeholders,
    warnings,
  };
}

function sortedUnique(values) {
  return [...new Set(values)].sort((a, b) => a.localeCompare(b));
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
const html = await readFile(inputPath, 'utf8');
const report = await inspectHtml(inputPath, html);
const json = `${JSON.stringify(report, null, 2)}\n`;
if (out === '-') {
  process.stdout.write(json);
} else {
  await writeFile(path.resolve(out), json, 'utf8');
}
process.exit(report.ok ? 0 : 1);
