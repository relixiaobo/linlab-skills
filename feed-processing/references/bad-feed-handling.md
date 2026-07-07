# Bad Feed Handling

Default to best-effort mixed-batch processing. One broken source should produce a
per-source error and coverage loss, not abort the entire batch.

## Error Classes

- `network_error`
- `http_error`
- `redirect_loop`
- `unsupported_content_type`
- `oversized_response`
- `parse_error`
- `no_feed_discovered`
- `auth_required`
- `rate_limited`
- `date_ambiguous`
- `unknown`

Include `retryable`, severity, message, and next action when possible.

## Recovery Order

1. Follow safe redirects within the redirect limit.
2. Try HTML feed autodiscovery for page URLs.
3. Try common feed paths only after autodiscovery fails.
4. Suggest RSSHub or RSS-Bridge routes only as explicit recovery options with
   provenance and licensing/terms caveats.
5. Ask the user for an alternate URL or authorized content when access is gated.
