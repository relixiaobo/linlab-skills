import {
  absoluteUrl,
  canonicalUrl,
  itemIdentity,
  parseAttributes,
  parseFeedContent,
  stableHash,
  validUrl,
} from './feed_common.mjs';

export const FEED_PROCESSING_SCHEMA_VERSION = '1.0';

export const DEFAULT_LIMITS = Object.freeze({
  timeoutMs: 15_000,
  maxBytes: 2_000_000,
  maxRedirects: 8,
  maxCandidates: 8,
  maxDiscoveryDepth: 2,
  concurrency: 8,
});

const REDIRECT_STATUSES = new Set([301, 302, 303, 307, 308]);
const FEED_KINDS = new Set(['rss', 'atom', 'jsonfeed']);
const TERMINAL_STATUSES = new Set(['parsed', 'empty', 'not_modified', 'failed', 'skipped']);
const DEFAULT_USER_AGENT = 'Feed Processing Skill/1.0';
const DEFAULT_ACCEPT = 'application/rss+xml, application/atom+xml, application/feed+json, application/json, text/xml, application/xml;q=0.9, text/html;q=0.5, */*;q=0.2';

const ERROR_DEFAULTS = {
  invalid_url: { retryable: false, severity: 'error', nextAction: 'provide_valid_url' },
  unsupported_url_scheme: { retryable: false, severity: 'error', nextAction: 'provide_http_url' },
  network_error: { retryable: true, severity: 'error', nextAction: 'retry' },
  timeout: { retryable: true, severity: 'error', nextAction: 'retry_with_larger_timeout' },
  http_error: { retryable: false, severity: 'error', nextAction: 'check_source_url' },
  redirect_loop: { retryable: false, severity: 'error', nextAction: 'replace_source_url' },
  too_many_redirects: { retryable: false, severity: 'error', nextAction: 'replace_source_url' },
  redirect_missing_location: { retryable: false, severity: 'error', nextAction: 'replace_source_url' },
  unsupported_content_type: { retryable: false, severity: 'error', nextAction: 'provide_alternate_feed_url' },
  oversized_response: { retryable: false, severity: 'error', nextAction: 'raise_max_bytes_or_use_alternate_feed' },
  parse_error: { retryable: false, severity: 'error', nextAction: 'provide_alternate_feed_url' },
  no_feed_discovered: { retryable: false, severity: 'error', nextAction: 'provide_alternate_feed_url' },
  auth_required: { retryable: false, severity: 'error', nextAction: 'provide_authorized_source' },
  rate_limited: { retryable: true, severity: 'error', nextAction: 'retry_after_delay' },
  capability_unavailable: { retryable: false, severity: 'error', nextAction: 'provide_required_capability' },
  unknown: { retryable: false, severity: 'error', nextAction: 'inspect_source' },
};

export function normalizeLimits(limits = {}) {
  return {
    timeoutMs: positiveNumber(limits.timeoutMs, DEFAULT_LIMITS.timeoutMs),
    maxBytes: positiveNumber(limits.maxBytes, DEFAULT_LIMITS.maxBytes),
    maxRedirects: nonNegativeInteger(limits.maxRedirects, DEFAULT_LIMITS.maxRedirects),
    maxCandidates: positiveInteger(limits.maxCandidates, DEFAULT_LIMITS.maxCandidates),
    maxDiscoveryDepth: nonNegativeInteger(limits.maxDiscoveryDepth, DEFAULT_LIMITS.maxDiscoveryDepth),
    concurrency: positiveInteger(limits.concurrency, DEFAULT_LIMITS.concurrency),
  };
}

export function makeFeedError(code, options = {}) {
  const defaults = ERROR_DEFAULTS[code] || ERROR_DEFAULTS.unknown;
  return {
    code,
    stage: options.stage || 'process',
    retryable: options.retryable ?? defaults.retryable,
    severity: options.severity || defaults.severity,
    message: options.message || code,
    nextAction: options.nextAction || defaults.nextAction,
    ...(options.url ? { url: options.url } : {}),
    ...(options.finalUrl ? { finalUrl: options.finalUrl } : {}),
    ...(options.status !== undefined ? { status: options.status } : {}),
    ...(options.details ? { details: options.details } : {}),
  };
}

export function classifyPayload(body, contentType = '') {
  const text = String(body || '');
  const trimmed = text.trim();
  const type = String(contentType || '').toLowerCase();
  if (!trimmed) return 'empty';

  const sample = trimmed.slice(0, 16_384);
  if (/<rss[\s>]/i.test(sample) || /<rdf:RDF[\s>]/i.test(sample)) return 'rss';
  if (/<feed[\s>]/i.test(sample)) return 'atom';

  if (/^\s*[\[{]/.test(sample)) {
    try {
      const parsed = JSON.parse(trimmed);
      if (
        parsed
        && !Array.isArray(parsed)
        && typeof parsed === 'object'
        && typeof parsed.version === 'string'
        && parsed.version.includes('jsonfeed.org/version')
        && Array.isArray(parsed.items)
      ) return 'jsonfeed';
      return 'json';
    } catch {
      if (type.includes('json')) return 'json';
    }
  }

  if (
    type.includes('text/html')
    || /<!doctype\s+html/i.test(sample)
    || /<html[\s>]/i.test(sample)
    || /<head[\s>]/i.test(sample)
  ) return 'html';
  if (type.includes('xml') || /^\s*<\?xml\b/i.test(sample)) return 'xml';
  if (type.includes('json')) return 'json';
  if (type.startsWith('text/')) return 'text';
  return 'unknown';
}

export function isFeedPayloadKind(kind) {
  return FEED_KINDS.has(kind);
}

export async function fetchResource(url, options = {}) {
  const limits = normalizeLimits(options.limits || options);
  const started = Date.now();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), limits.timeoutMs);
  let currentUrl = String(url || '');
  const redirectChain = [];
  const visited = new Set();

  try {
    currentUrl = normalizeHttpUrl(currentUrl);
    while (true) {
      if (visited.has(currentUrl)) {
        throw codedError('redirect_loop', `Redirect loop detected at ${currentUrl}`);
      }
      visited.add(currentUrl);

      const response = await fetch(currentUrl, {
        signal: controller.signal,
        redirect: 'manual',
        headers: {
          'User-Agent': options.userAgent || DEFAULT_USER_AGENT,
          Accept: options.accept || DEFAULT_ACCEPT,
          ...(options.etag ? { 'If-None-Match': options.etag } : {}),
          ...(options.lastModified ? { 'If-Modified-Since': options.lastModified } : {}),
          ...(options.headers || {}),
        },
      });

      if (REDIRECT_STATUSES.has(response.status)) {
        const location = response.headers.get('location');
        if (!location) throw codedError('redirect_missing_location', `HTTP ${response.status} redirect has no Location header`);
        if (redirectChain.length >= limits.maxRedirects) {
          throw codedError('too_many_redirects', `redirect count exceeds maxRedirects (${limits.maxRedirects})`);
        }
        const nextUrl = normalizeHttpUrl(new URL(location, currentUrl).toString());
        redirectChain.push({
          status: response.status,
          url: currentUrl,
          location,
          nextUrl,
        });
        currentUrl = nextUrl;
        continue;
      }

      const body = response.status === 304 ? '' : await readResponseText(response, limits.maxBytes);
      const contentType = response.headers.get('content-type');
      const transportOk = response.ok || response.status === 304;
      return {
        url: String(url),
        finalUrl: response.url || currentUrl,
        status: response.status,
        ok: transportOk,
        transportOk,
        notModified: response.status === 304,
        contentType,
        contentKind: classifyPayload(body, contentType),
        etag: response.headers.get('etag'),
        lastModified: response.headers.get('last-modified'),
        retryAfter: response.headers.get('retry-after'),
        linkHeader: response.headers.get('link'),
        redirectChain,
        durationMs: Date.now() - started,
        body,
        ...(!transportOk ? { error: errorForHttpResponse(response, String(url)) } : {}),
      };
    }
  } catch (error) {
    const code = classifyFetchError(error);
    return {
      url: String(url),
      ...(currentUrl && currentUrl !== String(url) ? { finalUrl: currentUrl } : {}),
      ok: false,
      transportOk: false,
      notModified: false,
      redirectChain,
      durationMs: Date.now() - started,
      error: makeFeedError(code, {
        stage: 'fetch',
        url: String(url),
        finalUrl: currentUrl || undefined,
        message: error.message || String(error),
      }),
    };
  } finally {
    clearTimeout(timer);
  }
}

export function discoverFeedCandidates(html, pageUrl, options = {}) {
  const candidates = [];
  const warnings = [];
  const includeCommonPaths = options.includeCommonPaths !== false;
  const linkRe = /<link\b([^>]*?)>/gi;
  let match;

  while ((match = linkRe.exec(String(html || '')))) {
    const rawAttrs = parseAttributes(match[1]);
    const attrs = Object.fromEntries(Object.entries(rawAttrs).map(([key, value]) => [key.toLowerCase(), value]));
    const rel = String(attrs.rel || '').toLowerCase().split(/\s+/);
    const type = String(attrs.type || '').toLowerCase();
    if (!rel.includes('alternate') || !attrs.href) continue;
    const feedType = feedTypeFromMime(type);
    if (!feedType) continue;
    const url = absoluteUrl(attrs.href, pageUrl);
    if (!url) continue;
    candidates.push({
      url,
      type: feedType,
      title: attrs.title || undefined,
      source: 'html_alternate',
      confidence: 'high',
    });
  }

  for (const candidate of candidatesFromLinkHeader(options.linkHeader, pageUrl)) candidates.push(candidate);

  const alternateCount = candidates.length;
  if (!alternateCount) {
    warnings.push({
      code: 'no_alternate_feed_links',
      severity: 'warning',
      message: 'No RSS, Atom, or JSON Feed alternate links were found in HTML.',
    });
    if (includeCommonPaths) {
      try {
        const base = new URL(pageUrl);
        if (['http:', 'https:'].includes(base.protocol)) {
          for (const path of options.commonPaths || ['/feed', '/rss', '/atom.xml', '/feed.xml', '/index.xml', '/rss.xml']) {
            candidates.push({
              url: new URL(path, `${base.origin}/`).toString(),
              type: path.includes('atom') ? 'atom' : 'rss',
              source: 'common_path',
              confidence: 'low',
            });
          }
        } else {
          warnings.push({ code: 'common_paths_unavailable', severity: 'warning', message: `Common feed paths require an HTTP(S) page URL, received ${base.protocol}` });
        }
      } catch {
        warnings.push({ code: 'common_paths_unavailable', severity: 'warning', message: `Cannot build common feed paths from ${pageUrl}` });
      }
    }
  }

  const deduped = [];
  const seen = new Set();
  for (const candidate of candidates) {
    const key = canonicalUrl(candidate.url);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    deduped.push(candidate);
  }

  return {
    pageUrl,
    candidates: deduped,
    warnings,
  };
}

export function normalizeProcessingSource(value, index = 0) {
  const source = typeof value === 'string' ? { inputUrl: value } : { ...(value || {}) };
  const inputUrl = source.inputUrl || source.feedUrl || source.siteUrl || source.url;
  const inferredKind = source.feedUrl
    ? 'feed'
    : source.siteUrl && !source.inputUrl && !source.url
      ? 'page'
      : looksLikeFeedUrl(inputUrl)
        ? 'feed'
        : 'unknown';
  const urlKind = ['feed', 'page', 'unknown'].includes(source.urlKind) ? source.urlKind : inferredKind;
  return {
    ...source,
    sourceId: source.sourceId || stableHash(canonicalUrl(inputUrl || `missing:${index}`)),
    inputUrl,
    urlKind,
    ...(source.feedUrl || urlKind === 'feed' ? { feedUrl: source.feedUrl || inputUrl } : {}),
    ...(source.siteUrl ? { siteUrl: source.siteUrl } : {}),
  };
}

export async function processFeedRequest(rawRequest = {}) {
  const request = normalizeRequest(rawRequest);
  const results = new Array(request.sources.length);
  let nextIndex = 0;

  await Promise.all(Array.from(
    { length: Math.min(request.limits.concurrency, request.sources.length) },
    async () => {
      while (nextIndex < request.sources.length) {
        const index = nextIndex;
        nextIndex += 1;
        results[index] = await resolveSource(request.sources[index], request);
      }
    },
  ));

  dedupeResolvedSources(results);
  const sources = results.map((result) => result.source);
  const parsedItems = results.flatMap((result) => result.items);
  const scoped = applyScope(parsedItems, request.scope, request.now);
  const items = scoped.items;
  const warnings = [
    ...request.inputWarnings,
    ...results.flatMap((result) => result.warnings.map((warning) => ({ ...warning, sourceId: result.source.sourceId }))),
    ...scoped.warnings,
  ];
  const errors = results.flatMap((result) => result.errors.map((error) => ({ ...error, sourceId: result.source.sourceId })));
  const statusCount = (status) => sources.filter((source) => source.status === status).length;
  const transportSucceeded = sources.filter((source) => source.attempts.some((attempt) => attempt.stage === 'fetch' && attempt.transportOk)).length;
  const coverage = {
    requestedSources: sources.length,
    parsedSources: statusCount('parsed'),
    emptySources: statusCount('empty'),
    notModifiedSources: statusCount('not_modified'),
    failedSources: statusCount('failed'),
    skippedSources: statusCount('skipped'),
    recoveredSources: sources.filter((source) => source.recovered).length,
    transportSucceeded,
    parsedItems: parsedItems.length,
    selectedItems: items.length,
    skippedItems: scoped.skippedCount,
    requested: sources.length,
    fetched: transportSucceeded,
    notModified: statusCount('not_modified'),
    sourceCount: sources.length,
    erroredSources: statusCount('failed'),
  };
  const output = {
    schemaVersion: FEED_PROCESSING_SCHEMA_VERSION,
    generatedAt: request.now,
    implementation: {
      name: 'feed-processing-reference',
      protocolVersion: FEED_PROCESSING_SCHEMA_VERSION,
    },
    scope: request.scope,
    strictness: request.strictness,
    sources,
    items,
    skipped: scoped.skipped,
    warnings,
    errors,
    coverage,
  };
  output.validation = validateProcessingResult(output);
  return output;
}

function dedupeResolvedSources(results) {
  const byFeedUrl = new Map();
  for (const result of results) {
    const source = result.source;
    if (!['parsed', 'empty'].includes(source.status)) continue;
    const key = canonicalUrl(source.resolvedFeedUrl || source.feedUrl);
    if (!key) continue;
    if (!byFeedUrl.has(key)) {
      byFeedUrl.set(key, source.sourceId);
      continue;
    }
    const duplicateOfSourceId = byFeedUrl.get(key);
    source.duplicateOfSourceId = duplicateOfSourceId;
    const warning = {
      code: 'duplicate_resolved_source',
      severity: 'warning',
      message: `Resolved feed duplicates source ${duplicateOfSourceId}; duplicate items were omitted.`,
      duplicateOfSourceId,
      resolvedFeedUrl: source.resolvedFeedUrl || source.feedUrl,
    };
    result.warnings.push(warning);
    result.items = [];
  }
}

export function validateProcessingResult(result) {
  const errors = [];
  const warnings = [];
  if (result.schemaVersion !== FEED_PROCESSING_SCHEMA_VERSION) errors.push(`unsupported schemaVersion: ${result.schemaVersion || 'missing'}`);
  if (!['all', 'last_n_days', 'since_cursor', 'newest_n', 'date_range'].includes(result.scope?.mode)) errors.push(`invalid scope.mode: ${result.scope?.mode || 'missing'}`);
  if (!Array.isArray(result.sources)) errors.push('sources must be an array');
  if (!Array.isArray(result.items)) errors.push('items must be an array');
  if (!Array.isArray(result.skipped)) errors.push('skipped must be an array');
  if (!Array.isArray(result.errors)) errors.push('errors must be an array');
  if (!Array.isArray(result.warnings)) errors.push('warnings must be an array');

  const sources = Array.isArray(result.sources) ? result.sources : [];
  const sourceIds = new Set();
  for (const source of sources) {
    if (!source.sourceId) errors.push('source missing sourceId');
    else if (sourceIds.has(source.sourceId)) errors.push(`duplicate sourceId: ${source.sourceId}`);
    else sourceIds.add(source.sourceId);
    if (!source.inputUrl) errors.push(`source ${source.sourceId || 'unknown'} missing inputUrl`);
    if (!TERMINAL_STATUSES.has(source.status)) errors.push(`source ${source.sourceId || 'unknown'} has invalid status: ${source.status}`);
    if (!Array.isArray(source.attempts)) errors.push(`source ${source.sourceId || 'unknown'} attempts must be an array`);
    for (const error of source.errors || []) validateErrorShape(error, errors, `source ${source.sourceId || 'unknown'}`);
  }

  for (const error of result.errors || []) validateErrorShape(error, errors, 'result');
  for (const warning of result.warnings || []) {
    if (warning?.severity === 'error') errors.push(`processing warning is an error: ${warning.code || warning.message || 'unknown'}`);
  }

  for (const item of result.items || []) {
    if (!item.sourceId || !sourceIds.has(item.sourceId)) errors.push(`item ${item.itemId || item.title || 'unknown'} references an unknown source`);
  }

  const coverage = result.coverage || {};
  const terminalTotal = ['parsedSources', 'emptySources', 'notModifiedSources', 'failedSources', 'skippedSources']
    .reduce((sum, key) => sum + Number(coverage[key] || 0), 0);
  if (coverage.requestedSources !== undefined && Number(coverage.requestedSources) !== sources.length) {
    errors.push('coverage.requestedSources does not match sources length');
  }
  if (coverage.requestedSources !== undefined && terminalTotal !== Number(coverage.requestedSources)) {
    errors.push('terminal source coverage does not reconcile');
  }
  if (coverage.selectedItems !== undefined && Number(coverage.selectedItems) !== (result.items || []).length) {
    errors.push('coverage.selectedItems does not match items length');
  }
  if (coverage.parsedItems !== undefined && Number(coverage.parsedItems) < (result.items || []).length) {
    errors.push('coverage.parsedItems is smaller than selected items length');
  }
  if ((result.errors || []).length && Number(coverage.failedSources || 0) === 0) {
    warnings.push('result has errors but failedSources is zero');
  }
  return { ok: errors.length === 0, errors, warnings };
}

function validateErrorShape(error, validationErrors, owner) {
  for (const key of ['code', 'stage', 'retryable', 'severity', 'message', 'nextAction']) {
    if (error?.[key] === undefined) validationErrors.push(`${owner} error missing ${key}`);
  }
}

export function feedProcessingCapabilities() {
  return {
    schemaVersion: FEED_PROCESSING_SCHEMA_VERSION,
    interface: 'json-stdio',
    referenceRuntime: {
      name: 'node',
      minimumVersion: '18',
    },
    requiredCapabilities: ['process_execution', 'outbound_http_for_live_sources'],
    optionalCapabilities: ['filesystem', 'persistent_cache', 'browser_rendering', 'host_sink'],
    formats: ['rss', 'atom', 'jsonfeed', 'opml', 'source-list'],
    commands: ['process', 'validate', 'capabilities'],
  };
}

function normalizeRequest(rawRequest) {
  const request = Array.isArray(rawRequest) ? { sources: rawRequest } : { ...(rawRequest || {}) };
  const sources = (request.sources || []).map(normalizeProcessingSource);
  const now = request.now ? new Date(request.now) : new Date();
  return {
    schemaVersion: request.schemaVersion || FEED_PROCESSING_SCHEMA_VERSION,
    now: Number.isNaN(now.getTime()) ? new Date().toISOString() : now.toISOString(),
    scope: request.scope || { mode: 'all' },
    strictness: request.strictness === 'strict' ? 'strict' : 'best_effort',
    limits: normalizeLimits(request.limits),
    discovery: {
      includeCommonPaths: request.discovery?.includeCommonPaths !== false,
      commonPaths: request.discovery?.commonPaths,
    },
    userAgent: request.userAgent || DEFAULT_USER_AGENT,
    inputWarnings: Array.isArray(request.warnings) ? request.warnings : [],
    sources,
  };
}

async function resolveSource(source, request) {
  const attempts = [];
  const warnings = [];
  const attemptedUrls = new Set();
  const initialUrl = source.feedUrl || source.inputUrl || source.siteUrl;
  const baseSource = {
    ...source,
    status: 'failed',
    recovered: false,
    redirected: false,
    attempts,
    warnings,
    errors: [],
  };
  delete baseSource.payload;

  if (!initialUrl || (!validUrl(initialUrl) && source.payload === undefined)) {
    const error = makeFeedError('invalid_url', {
      stage: 'normalize',
      url: initialUrl,
      message: initialUrl ? `Invalid URL: ${initialUrl}` : 'Source has no URL.',
    });
    return terminalFailure(baseSource, error);
  }

  let outcome;
  if (source.payload !== undefined) {
    const payloadUrl = source.finalUrl || (validUrl(initialUrl) ? initialUrl : `urn:feed-source:${source.sourceId}`);
    const response = {
      url: initialUrl,
      finalUrl: payloadUrl,
      status: 200,
      ok: true,
      transportOk: true,
      notModified: false,
      contentType: source.contentType || null,
      contentKind: classifyPayload(source.payload, source.contentType),
      redirectChain: [],
      durationMs: 0,
      body: String(source.payload),
    };
    attempts.push({
      stage: 'input',
      url: initialUrl,
      finalUrl: payloadUrl,
      contentType: response.contentType,
      contentKind: response.contentKind,
      outcome: 'provided_payload',
    });
    outcome = await resolveResponse(response, 0, false);
  } else {
    outcome = await fetchAndResolve(initialUrl, 0, false);
  }
  if (!outcome) {
    const error = makeFeedError('unknown', { stage: 'process', url: initialUrl, message: 'Source resolution produced no outcome.' });
    return terminalFailure(baseSource, error);
  }
  if (outcome.terminal) return outcome.terminal;
  if (outcome.error) return terminalFailure(baseSource, outcome.error);

  const parsedSource = outcome.parsed.source;
  const status = outcome.parsed.items.length ? 'parsed' : 'empty';
  const resolvedFeedUrl = outcome.response.finalUrl || outcome.response.url;
  const sourceWarnings = [...warnings, ...outcome.parsed.warnings];
  const outputSource = {
    ...baseSource,
    ...parsedSource,
    sourceId: source.sourceId,
    inputUrl: source.inputUrl,
    originalUrl: source.inputUrl,
    feedUrl: resolvedFeedUrl,
    resolvedFeedUrl,
    siteUrl: parsedSource.siteUrl || source.siteUrl,
    status,
    recovered: outcome.recovered,
    redirected: attempts.some((attempt) => (attempt.redirectChain || []).length > 0),
    warnings: sourceWarnings,
    errors: [],
  };
  const items = outcome.parsed.items.map((item) => ({
    ...item,
    sourceId: source.sourceId,
    feedUrl: resolvedFeedUrl,
  }));
  return { source: outputSource, items, warnings: sourceWarnings, errors: [] };

  async function fetchAndResolve(url, depth, recovered) {
    const key = canonicalUrl(url);
    if (attemptedUrls.has(key)) {
      return { error: makeFeedError('redirect_loop', { stage: 'discover', url, message: `Candidate URL was already attempted: ${url}` }) };
    }
    attemptedUrls.add(key);
    const response = await fetchResource(url, {
      limits: request.limits,
      userAgent: request.userAgent,
      etag: depth === 0 ? source.etag : undefined,
      lastModified: depth === 0 ? source.lastModified : undefined,
    });
    attempts.push(fetchAttempt(response));
    if (!response.transportOk) return { error: response.error };
    if (response.notModified) {
      const outputSource = {
        ...baseSource,
        status: 'not_modified',
        resolvedFeedUrl: response.finalUrl || response.url,
        feedUrl: response.finalUrl || response.url,
        recovered,
        redirected: response.redirectChain.length > 0,
      };
      return { terminal: { source: outputSource, items: [], warnings, errors: [] } };
    }

    return resolveResponse(response, depth, recovered);
  }

  async function resolveResponse(response, depth, recovered) {
    const responseUrl = response.finalUrl || response.url;
    if (response.contentKind === 'html') {
      if (depth >= request.limits.maxDiscoveryDepth) {
        return {
          error: makeFeedError('no_feed_discovered', {
            stage: 'discover',
            url: response.url,
            finalUrl: responseUrl,
            message: `HTML discovery depth exceeds maxDiscoveryDepth (${request.limits.maxDiscoveryDepth}).`,
          }),
        };
      }
      const discovery = discoverFeedCandidates(response.body, responseUrl, {
        ...request.discovery,
        linkHeader: response.linkHeader,
      });
      warnings.push(...discovery.warnings);
      const candidates = discovery.candidates.slice(0, request.limits.maxCandidates);
      attempts.push({
        stage: 'discover',
        url: responseUrl,
        outcome: candidates.length ? 'candidates_found' : 'no_feed_discovered',
        candidateCount: candidates.length,
        candidates: candidates.map((candidate) => ({
          url: candidate.url,
          type: candidate.type,
          source: candidate.source,
          confidence: candidate.confidence,
        })),
      });
      let emptyOutcome = null;
      for (const candidate of candidates) {
        if (attemptedUrls.has(canonicalUrl(candidate.url))) continue;
        const candidateOutcome = await fetchAndResolve(candidate.url, depth + 1, true);
        if (candidateOutcome.terminal) return candidateOutcome;
        if (candidateOutcome.parsed) {
          if (candidateOutcome.parsed.items.length) return candidateOutcome;
          emptyOutcome ||= candidateOutcome;
        }
      }
      if (emptyOutcome) return emptyOutcome;
      return {
        error: makeFeedError('no_feed_discovered', {
          stage: 'discover',
          url: response.url,
          finalUrl: responseUrl,
          message: candidates.length
            ? `Discovered ${candidates.length} candidate feed(s), but none could be parsed.`
            : 'No feed candidates were discovered in the HTML response.',
        }),
      };
    }

    if (!isFeedPayloadKind(response.contentKind) && !['xml', 'unknown', 'text'].includes(response.contentKind)) {
      return {
        error: makeFeedError('unsupported_content_type', {
          stage: 'parse',
          url: response.url,
          finalUrl: responseUrl,
          message: `Unsupported response content: ${response.contentKind}.`,
          details: { contentType: response.contentType, contentKind: response.contentKind },
        }),
      };
    }

    try {
      const parsed = parseFeedContent(response.body || '', responseUrl);
      attempts.push({
        stage: 'parse',
        url: responseUrl,
        outcome: parsed.items.length ? 'parsed' : 'empty',
        format: parsed.source.format,
        itemCount: parsed.items.length,
      });
      return { parsed, response, recovered };
    } catch (error) {
      attempts.push({
        stage: 'parse',
        url: response.finalUrl || response.url,
        outcome: 'failed',
        error: makeFeedError('parse_error', {
          stage: 'parse',
          url: response.url,
          finalUrl: responseUrl,
          message: error.message,
        }),
      });
      return {
        error: makeFeedError('parse_error', {
          stage: 'parse',
          url: response.url,
          finalUrl: responseUrl,
          message: error.message,
        }),
      };
    }
  }
}

function applyScope(items, scope = { mode: 'all' }, nowValue) {
  const mode = scope?.mode || 'all';
  const now = new Date(nowValue);
  const included = [];
  const skippedRows = [];
  const warnings = [];

  if (mode === 'all') {
    included.push(...items);
  } else if (mode === 'last_n_days') {
    const days = Number(scope.days ?? 7);
    if (!Number.isFinite(days) || days < 0) {
      warnings.push({ code: 'invalid_scope', severity: 'error', message: 'last_n_days requires a non-negative days value.' });
    } else {
      const start = new Date(now.getTime() - days * 24 * 60 * 60 * 1000);
      for (const item of items) {
        const date = itemDate(item);
        if (!date) skippedRows.push({ reason: 'date_ambiguous', item });
        else if (date >= start && date <= now) included.push(item);
        else skippedRows.push({ reason: 'outside_window', item });
      }
    }
  } else if (mode === 'date_range') {
    const start = new Date(scope.start);
    const end = new Date(scope.end);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
      warnings.push({ code: 'invalid_scope', severity: 'error', message: 'date_range requires valid start and end timestamps.' });
    } else {
      for (const item of items) {
        const date = itemDate(item);
        if (!date) skippedRows.push({ reason: 'date_ambiguous', item });
        else if (date >= start && date <= end) included.push(item);
        else skippedRows.push({ reason: 'outside_window', item });
      }
    }
  } else if (mode === 'newest_n') {
    const rawCount = Number(scope.count ?? 10);
    if (!Number.isFinite(rawCount) || rawCount < 0) {
      warnings.push({ code: 'invalid_scope', severity: 'error', message: 'newest_n requires a non-negative count value.' });
    } else {
      const count = Math.floor(rawCount);
      const sorted = [...items].sort((a, b) => (itemDate(b)?.getTime() || 0) - (itemDate(a)?.getTime() || 0));
      included.push(...sorted.slice(0, count));
      skippedRows.push(...sorted.slice(count).map((item) => ({ reason: 'outside_newest_n', item })));
    }
  } else if (mode === 'since_cursor') {
    const cursor = scope.seen || scope.items || {};
    if (!cursor || typeof cursor !== 'object' || Array.isArray(cursor)) {
      warnings.push({ code: 'invalid_scope', severity: 'error', message: 'since_cursor requires an object in seen or items.' });
    } else {
      const seen = new Map(Object.entries(cursor));
      for (const item of items) {
        const identity = itemIdentity(item);
        const marker = item.updatedAt || item.publishedAt || item.title || '';
        if (!seen.has(identity) || seen.get(identity) !== marker) included.push(item);
        else skippedRows.push({ reason: 'unchanged_since_cursor', item });
      }
    }
  } else {
    warnings.push({ code: 'unsupported_scope', severity: 'error', message: `Unsupported scope mode: ${mode}` });
  }

  return {
    items: included,
    skipped: summarizeSkipped(skippedRows),
    skippedCount: skippedRows.length,
    warnings,
  };
}

function itemDate(item) {
  const raw = item.publishedAt || item.updatedAt;
  if (!raw) return null;
  const date = new Date(raw);
  return Number.isNaN(date.getTime()) ? null : date;
}

function summarizeSkipped(rows) {
  const byReason = new Map();
  for (const row of rows) {
    if (!byReason.has(row.reason)) byReason.set(row.reason, []);
    byReason.get(row.reason).push(row.item);
  }
  return [...byReason.entries()].map(([reason, reasonItems]) => ({
    reason,
    count: reasonItems.length,
    visibleItems: reasonItems.slice(0, 5).map((item) => ({
      sourceId: item.sourceId,
      itemId: item.itemId || null,
      title: item.title || null,
    })),
  }));
}

function terminalFailure(source, error) {
  const outputSource = {
    ...source,
    status: source.inputUrl ? 'failed' : 'skipped',
    errors: [error],
  };
  return { source: outputSource, items: [], warnings: source.warnings || [], errors: [error] };
}

function fetchAttempt(response) {
  return {
    stage: 'fetch',
    url: response.url,
    finalUrl: response.finalUrl,
    status: response.status,
    transportOk: response.transportOk,
    contentType: response.contentType,
    contentKind: response.contentKind,
    outcome: response.transportOk
      ? response.notModified
        ? 'not_modified'
        : response.contentKind === 'html'
          ? 'html_response'
          : 'fetched'
      : 'failed',
    durationMs: response.durationMs,
    redirectChain: response.redirectChain || [],
    ...(response.error ? { error: response.error } : {}),
  };
}

async function readResponseText(response, maxBytes) {
  const contentLength = Number(response.headers.get('content-length') || 0);
  if (contentLength > maxBytes) throw codedError('oversized_response', `response exceeds maxBytes (${maxBytes})`);
  if (!response.body) return '';

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let bytesRead = 0;
  let text = '';
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      bytesRead += value.byteLength;
      if (bytesRead > maxBytes) {
        await reader.cancel();
        throw codedError('oversized_response', `response exceeds maxBytes (${maxBytes})`);
      }
      text += decoder.decode(value, { stream: true });
    }
    text += decoder.decode();
    return text;
  } finally {
    reader.releaseLock();
  }
}

function errorForHttpResponse(response, url) {
  if (response.status === 401) {
    return makeFeedError('auth_required', { stage: 'fetch', url, finalUrl: response.url, status: response.status, message: 'HTTP 401' });
  }
  if (response.status === 429) {
    return makeFeedError('rate_limited', {
      stage: 'fetch',
      url,
      finalUrl: response.url,
      status: response.status,
      message: 'HTTP 429',
      details: { retryAfter: response.headers.get('retry-after') },
    });
  }
  return makeFeedError('http_error', {
    stage: 'fetch',
    url,
    finalUrl: response.url,
    status: response.status,
    retryable: response.status >= 500,
    nextAction: response.status >= 500 ? 'retry' : 'check_source_url',
    message: `HTTP ${response.status}`,
  });
}

function classifyFetchError(error) {
  if (error.name === 'AbortError') return 'timeout';
  if (ERROR_DEFAULTS[error.code]) return error.code;
  const causeCode = error.cause?.code;
  if (causeCode === 'UND_ERR_CONNECT_TIMEOUT' || causeCode === 'UND_ERR_HEADERS_TIMEOUT' || causeCode === 'UND_ERR_BODY_TIMEOUT') return 'timeout';
  return 'network_error';
}

function codedError(code, message) {
  const error = new Error(message);
  error.code = code;
  return error;
}

function normalizeHttpUrl(value) {
  let url;
  try {
    url = new URL(value);
  } catch {
    throw codedError('invalid_url', `Invalid URL: ${value}`);
  }
  if (!['http:', 'https:'].includes(url.protocol)) {
    throw codedError('unsupported_url_scheme', `Unsupported URL scheme: ${url.protocol}`);
  }
  if (url.username || url.password) {
    throw codedError('invalid_url', 'Credentialed URLs are not supported.');
  }
  return url.toString();
}

function candidatesFromLinkHeader(header, pageUrl) {
  if (!header) return [];
  const candidates = [];
  const re = /<([^>]+)>\s*;\s*([^,]+)/g;
  let match;
  while ((match = re.exec(header))) {
    const attrs = Object.fromEntries(String(match[2]).split(';').map((part) => {
      const [key, ...rest] = part.trim().split('=');
      return [String(key || '').toLowerCase(), rest.join('=').replace(/^['\"]|['\"]$/g, '')];
    }));
    if (!String(attrs.rel || '').toLowerCase().split(/\s+/).includes('alternate')) continue;
    const type = feedTypeFromMime(String(attrs.type || '').toLowerCase());
    const url = absoluteUrl(match[1], pageUrl);
    if (!type || !url) continue;
    candidates.push({ url, type, source: 'http_link_header', confidence: 'high' });
  }
  return candidates;
}

function feedTypeFromMime(type) {
  if (type.includes('rss')) return 'rss';
  if (type.includes('atom')) return 'atom';
  if (type.includes('json') || type.includes('feed+json')) return 'jsonfeed';
  return null;
}

function looksLikeFeedUrl(value) {
  if (!value) return false;
  try {
    const url = new URL(value);
    return /\.(xml|rss|atom|json)$/i.test(url.pathname) || /\/(feed|rss|atom)(\/|$)/i.test(url.pathname);
  } catch {
    return false;
  }
}

function positiveNumber(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? number : fallback;
}

function positiveInteger(value, fallback) {
  return Math.max(1, Math.floor(positiveNumber(value, fallback)));
}

function nonNegativeInteger(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) && number >= 0 ? Math.floor(number) : fallback;
}
