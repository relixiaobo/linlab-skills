# Domain Routing

## Table Of Contents

- Routing Rule
- Domain Signals
- Ambiguity
- Non-Domain Execution Modes

## Routing Rule

Stay in the general research kernel unless the topic needs a distinct source matrix, judgment standard, or output shape.

Do not create separate routes for quick, standard, deep, or batch. Those are execution modes.

Route conservatively. A single weak word match is not enough if the topic is otherwise general. For example, do not treat `OpenClaw` as a law/regulatory task because it contains the substring `law`, and do not treat every company mention as a dossier unless the user asks for diligence, background, risks, or meeting prep.

## Domain Signals

| Domain path | Strong signals | Load |
|---|---|---|
| literature | literature review, papers, systematic review, meta-analysis, DOI, PubMed, arXiv, citations, related work, research gap | `domains/literature.md` |
| entity-dossier | due diligence, background on a person/company/org, meeting prep, investment diligence, red flags, hypothesis about an entity | `domains/entity-dossier.md` |
| pulse | current conversation, sentiment, trend, buzz, what are people saying, Reddit, Hacker News, X/Twitter, community feedback | `domains/pulse.md` |
| patent | patent, prior art, novelty, freedom to operate, FTO, claims, USPTO, Espacenet, Lens | `domains/patent.md` |
| grants | grant, funding opportunity, NIH, R01, study section, foundation funding, program officer | `domains/grants.md` |
| codebase-docs | library/framework/API research, official docs, migration, changelog, local code plus external docs | `domains/codebase-docs.md` |
| standards-regulatory | regulation, compliance, law, policy, standard, RFC, ISO, NIST, FDA, SEC, EU act, jurisdiction | `domains/standards-regulatory.md` |

## Ambiguity

Ask one clarification if domain choice changes the source matrix. Example:

- "Are you asking for the current market conversation about this company, or a decision-grade diligence dossier?"

If no clarification is needed, state the assumption and proceed.

## Non-Domain Execution Modes

- quick lookup: lower depth budget
- deep report: higher depth budget and artifacts
- batch comparison: read `batch-mode.md`
- explicit fact-check: read `claim-verification.md`
- citation audit: read `claim-verification.md`
