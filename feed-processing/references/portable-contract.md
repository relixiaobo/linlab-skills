# Portable Processing Contract

Use this contract when invoking the bundled reference CLI or implementing an
adapter for another agent runtime.

## Boundary

The feed-processing core accepts source records and returns a validated,
sink-neutral result. A host may collect sources, provide execution and network
capabilities, persist state, schedule work, or write the result elsewhere, but
those operations are outside this contract.

Do not require a particular agent tool name, browser session, host object,
filesystem layout, scheduler, or output application.

## Capability Profiles

- **Reference CLI:** execute Node.js 18 or newer and allow outbound HTTP(S) for
  live sources.
- **Protocol adapter:** implement the same request, state, error, coverage, and
  validation semantics through MCP, HTTP, another runtime, or native tools.
- **Restricted:** process supplied payloads when live network access is
  unavailable but a processor or conforming adapter exists. If neither execution
  nor an adapter is available, report `capability_unavailable`.

Filesystem access, persistent caching, browser rendering, and host writes are
optional capabilities.

## Interface

Use JSON on stdin and stdout as the portable reference interface. Send logs to
stderr. File arguments are conveniences, not protocol requirements.

```sh
node <skill-root>/scripts/feed_process.mjs process --input -
node <skill-root>/scripts/feed_process.mjs validate --input -
node <skill-root>/scripts/feed_process.mjs capabilities
```

See `feed-request.schema.json` and `feed-result.schema.json` for the normative
field shapes.

Use `payload`, `contentType`, and `finalUrl` on a source when the caller
already has a feed payload. Do not count supplied payloads as network transport.
Apply the request `scope` before returning selected items.

## Source States

Every requested source must end in exactly one state:

- `parsed`
- `empty`
- `not_modified`
- `failed`
- `skipped`

`recovered` and `redirected` are independent dimensions, not terminal states.
Preserve the caller-provided `sourceId` across redirects, discovery, candidate
validation, and canonical URL changes.

When multiple source records resolve to the same canonical feed, preserve every
source record, set `duplicateOfSourceId` on later sources, and omit duplicate
items.

## Recovery

1. Fetch an explicit or likely feed URL.
2. Parse RSS, Atom, or JSON Feed payloads.
3. When the response is HTML, discover alternate feed links using the final
   response URL as the base.
4. When no alternate link exists, try a bounded common-path candidate set.
5. Fetch and parse candidates before accepting them.
6. Return `empty` for a structurally valid feed with no items.
7. Return `failed` only after bounded recovery is exhausted.

Do not automatically use third-party bridge services. Present them as explicit
recovery options subject to provenance, licensing, and publisher constraints.

## Error Shape

Every error must include `code`, `stage`, `retryable`, `severity`, `message`, and
`nextAction`. Use these stable codes:

- `invalid_url`
- `unsupported_url_scheme`
- `network_error`
- `timeout`
- `http_error`
- `redirect_loop`
- `too_many_redirects`
- `redirect_missing_location`
- `unsupported_content_type`
- `oversized_response`
- `parse_error`
- `no_feed_discovered`
- `auth_required`
- `rate_limited`
- `capability_unavailable`
- `unknown`

## Coverage Invariant

Require this equality:

```text
requestedSources = parsedSources + emptySources + notModifiedSources
                 + failedSources + skippedSources
```

Keep transport success, recovery, parsed item count, selected item count, and
skipped item count as separate dimensions.
