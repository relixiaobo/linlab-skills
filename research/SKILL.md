---
name: research
description: Source-grounded general research and deep research kernel. Use when the user asks to research, investigate, compare, verify, gather current information, produce a cited report, conduct literature review, entity due diligence, trend/pulse analysis, patent/grant research, standards/regulatory research, or combine external sources with code/docs. The skill defaults to a general research method and loads domain paths only when the domain needs a distinct source matrix, judgment standard, or output shape.
---

# Research

## Core Model

This skill is a general research kernel, not a collection of shallow pseudo-experts.

Use the general method for intake, depth budgeting, search planning, source selection, evidence extraction, synthesis, claim verification, and artifact storage. Load a domain path only when the topic needs a specialized source matrix, specialized judgment criteria, or a specialized output structure.

Domain paths do not replace the kernel. They override source selection, evaluation standards, and report shape.

## Start Here

1. Normalize the question into one research objective, expected output, time horizon, and known constraints.
2. Decide depth:
   - **quick**: answer-sized research, normally 2-4 high-quality sources.
   - **standard**: structured research, normally 5-12 sources and a short plan.
   - **deep**: report-scale research, multiple angles, artifacts, source audit, and claim verification.
3. Decide whether a domain path is needed. If not, stay in the general kernel.
4. Apply source policy before synthesis. Do not cite search snippets, memory, or another AI's answer as evidence.
5. For standard/deep work, create `.research/<topic-slug>/` artifacts with `scripts/init_run.py`.
6. Produce an answer or report with confidence, uncertainty, and source quality notes.

## What To Load

Always keep `SKILL.md` small in context. Load references only when needed:

- General method: `references/core-method.md`
- Source ranking and evidence tiers: `references/source-policy.md`
- Research artifact layout and JSONL schemas: `references/artifact-contract.md`
- Domain selection rules: `references/domain-routing.md`
- Explicit fact-checking or final claim audit: `references/claim-verification.md`
- Many-item comparisons or repeated entity research: `references/batch-mode.md`

Load one domain file only when its domain clearly applies:

- Academic papers and literature: `references/domains/literature.md`
- Company/person/org due diligence: `references/domains/entity-dossier.md`
- Current conversation, sentiment, and trend pulse: `references/domains/pulse.md`
- Patent/prior-art/FTO/landscape research: `references/domains/patent.md`
- Funding and grants research: `references/domains/grants.md`
- Codebase, API, library, and technical docs research: `references/domains/codebase-docs.md`
- Standards, policy, regulatory, and compliance research: `references/domains/standards-regulatory.md`

## Domain Routing Principle

Do not route by depth. `quick`, `standard`, `deep`, and `batch` are execution modes inside the kernel.

Route only when the domain changes at least one of:

- where to search first
- how to judge source quality
- what counts as sufficient evidence
- what the final artifact should contain

When routing is ambiguous, ask at most one clarifying question if the answer would materially change the source matrix. Otherwise use the general kernel and state the assumption.

## Required Research Discipline

- Cite only sources actually opened or retrieved in the current run.
- Treat second-hand claims, social posts, screenshots, and AI outputs as leads, not evidence.
- Prefer primary sources for factual claims and official/current sources for time-sensitive facts.
- Record source tier, date accessed, and what each source supports.
- Search for disconfirming evidence for important conclusions.
- Mark unsupported or unresolved claims explicitly.
- Never hide thin evidence behind confident language.
- Close every answer or verdict with a calibrated confidence label (high / medium / low / unresolved) and one line on what evidence is still missing or what would change the conclusion. This is not boilerplate: a reader cannot safely act on a finding they cannot calibrate, and research output often gets pasted straight into a compliance doc, a filing, or a decision. The reader needs to know how much to trust the answer and what to check before relying on it — a bare conclusion, even a correct one, leaves them guessing.

## Useful Scripts

- `scripts/classify_domain.py`: deterministic first-pass classifier for domain, depth, batch, and verification signals.
- `scripts/init_run.py`: creates `.research/<slug>/` with source, claim, report, and audit files.
- `scripts/source_tier.py`: lightweight URL/source-tier classifier.
- `scripts/validate_artifacts.py`: validates required files and JSONL artifacts before final delivery.

Use scripts when helpful; do not let script output override judgment.
