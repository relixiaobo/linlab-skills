# Full-Text Extraction

Correct full-text retrieval is a core quality surface. A feed item body can be
complete, partial, missing, or polluted by boilerplate.

## Strategy Ladder

1. Use feed-provided content when it appears complete.
2. Fetch the article page and run static extraction.
3. Try alternate static extraction when the first result is empty, too short,
   title-mismatched, or boilerplate-heavy.
4. Use a host browser-rendered adapter only when the host explicitly provides
   that capability and the user needs it.
5. Accept user-provided article content when login, paywall, or policy blocks
   automated retrieval.

## Why Engines Disagree

Extractors score different signals: text density, link density, headings,
metadata, article containers, JSON-LD, code/math preservation, and boilerplate
removal. One engine may recover a page another rejects because the page is
client-rendered, has unusual markup, contains code or math, or looks too much
like navigation/commentary.

## Attempt Ledger

Record every strategy with status, failure reason, character count, word count,
confidence, and selected result. Do not collapse this to a single "full text:
yes/no" flag.

Common failure codes: `feed_summary_only`, `no_article_url`, `fetch_failed`,
`http_error`, `unsupported_content_type`, `requires_auth`, `paywall_or_preview`,
`client_rendered`, `script_required`, `extractor_empty`,
`extractor_too_short`, `title_mismatch`, `boilerplate_dominant`,
`language_mismatch`, `oversized_response`, `blocked_by_policy`, and `unknown`.
