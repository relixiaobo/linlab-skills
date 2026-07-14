# Portable Workflow

Use the lightest execution mode that preserves the portable contract.

## Reference CLI

1. Normalize request sources.
2. Fetch explicit or likely feed URLs with bounded redirects.
3. Classify the returned payload.
4. Parse RSS, Atom, and JSON Feed directly.
5. For HTML, discover candidates using the final URL as the base.
6. Fetch and parse candidates before accepting them.
7. Apply the requested scope.
8. Return terminal source states, attempts, errors, warnings, items, and
   reconcilable coverage.
9. Validate the result.

Run this path with `feed_process.mjs`.

## Protocol Adapter

Allow another runtime, MCP server, HTTP service, or native implementation to
replace the reference CLI only when it conforms to `portable-contract.md` and
the request/result schemas. Keep the same error codes and coverage invariant.

## Restricted Processing

When live HTTP or process execution is unavailable, accept caller-supplied feed
payloads. Do not claim that remote sources were fetched. Report missing
capabilities explicitly.

## Post-Processing

Apply rule filtering and selected full-text extraction after the portable
processor. Build and validate a feed-content pack before passing data to a
downstream consumer.

## Host Boundary

Let a host collect sources, persist state, schedule runs, and write results.
Keep host-specific APIs, object identifiers, sessions, and mutation instructions
outside this skill.
