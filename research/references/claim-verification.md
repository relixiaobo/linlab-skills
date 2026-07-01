# Claim Verification

## Table Of Contents

- When To Use
- Method
- Verdict Labels
- Final Audit

## When To Use

Use this as the main flow when the user asks whether a claim is true, asks to fact-check, pastes another AI's answer, forwards a news item, or asks for verification.

Use this as a quality gate inside deep research for:

- high-impact claims
- numeric claims
- legal, medical, financial, safety, or reputation claims
- claims based on social posts or secondary media
- surprising conclusions

## Method

1. Decompose the input into atomic claims.
2. Triage by impact and error likelihood.
3. Downgrade second-hand material to a lead list.
4. Trace each claim to the highest available evidence tier.
5. Distinguish absence of evidence from contradicting evidence.
6. Label each claim and cite source ids.

For numeric claims, find the numeric source. Do not accept a percentage, valuation, market size, shipment count, or performance metric without an original or authoritative source.

## Verdict Labels

| Verdict | Meaning |
|---|---|
| CONFIRMED | Supported by Tier S or strong independent Tier A evidence |
| PARTIAL | Directionally true but incomplete, scoped, stale, or missing important caveats |
| WRONG | Contradicted by stronger evidence or materially misleading |
| UNVERIFIED | No adequate evidence found |

Pair every verdict with a confidence level (high / medium / low) and a short "what would change this" note. The verdict says which way the evidence points; the confidence says how firmly; the note tells the reader what to check before relying on it. A WRONG verdict with no confidence level still leaves the reader unsure whether to trust the correction over the original claim — which defeats the purpose of verification. The person asking is usually about to act on the answer (cite it, file it, ship it), so make the verdict callable on its own: `WRONG (high confidence) — would only change if NIST issued a 2024+ deprecation notice for SHA-256, which a current csrc.nist.gov check did not find.`

## Final Audit

Before delivering a deep report, scan the final answer:

- Are all material factual claims tied to source ids?
- Are C-tier sources excluded from verdicts?
- Are stale facts dated?
- Are conflicts surfaced?
- Are unsupported claims marked unresolved?

If a report cannot pass the audit, revise or label limitations explicitly.
