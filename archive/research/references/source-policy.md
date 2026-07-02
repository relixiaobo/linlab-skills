# Source Policy

## Table Of Contents

- Evidence Tiers
- Source Selection Algorithm
- Independence And Corroboration
- Recency
- Common Failure Modes

## Evidence Tiers

Use these tiers across all domains unless a loaded domain reference defines a stricter matrix.

| Tier | Meaning | Examples | Use |
|---|---|---|---|
| S | Primary or official source | regulator filing, government database, court record, company IR, standards document, official docs, original dataset, original paper | Treat as fact source if current and relevant |
| A | Authoritative secondary or expert source | signed trade press, peer-reviewed review, reputable industry analysis, major newsroom with named sources | Use as strong support, but label framing or interpretation |
| B | Ordinary secondary source | blogs, newsletters, vendor comparisons, database aggregators, unsourced media summaries | Use for context and leads; verify material claims |
| C | Lead only | social posts, forums, anonymous claims, screenshots, another AI output, marketing logo walls | Never use alone for factual verdicts |

## Source Selection Algorithm

For every material claim:

1. Identify what kind of claim it is: factual, numeric, causal, trend, legal/regulatory, technical, reputation, or opinion.
2. Look for the highest natural source tier for that claim.
3. Open the source. Snippets are not evidence.
4. Record source tier and access date.
5. If only B/C sources exist, mark the claim low-confidence or unresolved.
6. If sources conflict, prefer the more primary, more recent, more specific, and more directly relevant source.

## Independence And Corroboration

Multiple sources are not independent when they repeat the same press release, quote the same anonymous source, or cite each other circularly.

Count independent evidence by original source, not by number of pages repeating it.

For high-impact claims, seek at least one primary source or two independent A-tier sources. For claims about current status, verify dates and find the latest source.

## Recency

Freshness is domain-specific:

- current events, funding, pricing, leadership, law, product capabilities: verify current sources
- academic literature: include recent work but do not ignore seminal work
- patents and regulations: current legal status and jurisdiction matter
- technical docs: use version-specific official docs and changelogs

Always state the date basis when the answer could go stale.

## Common Failure Modes

- circular citation: several articles trace back to one unverified post
- stale fact: old funding, pricing, customer, or legal status presented as current
- marketing display as fact: logo walls and case-study claims need stronger support
- unverified magnitude: numbers without original data source
- source laundering: AI output or social post repeated by a blog
- missing jurisdiction: legal, patent, funding, and compliance claims without country/state/body
- snippet citation: citing search result text without opening the source
