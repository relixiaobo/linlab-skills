# Bad Feed Handling

Process mixed batches best-effort by default. Preserve every source in a
terminal state rather than aborting the batch.

## Error Contract

Include `code`, `stage`, `retryable`, `severity`, `message`, and
`nextAction`. Use:

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

Do not use transport success as feed validity. An HTTP 200 HTML response is a
successful fetch that requires discovery, not a parsed feed.

## Recovery Order

1. Follow bounded HTTP(S) redirects and record the chain.
2. Parse recognized feed payloads.
3. For HTML, discover alternate links using the final response URL.
4. Try a bounded common-path set only when alternate discovery finds nothing.
5. Fetch and parse every accepted candidate.
6. Prefer a non-empty valid candidate; retain an empty valid feed when no
   non-empty candidate succeeds.
7. Mark the source failed only after recovery is exhausted.

Suggest third-party bridge routes only as explicit options with provenance,
publisher-policy, licensing, and reliability caveats.
