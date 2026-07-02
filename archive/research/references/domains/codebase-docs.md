# Domain Path: Codebase And Technical Docs

## Table Of Contents

- Use When
- Source Matrix
- Method
- Output Shape

## Use When

Use when research combines local code or implementation choices with external technical docs: library APIs, framework behavior, version migration, official best practices, package capabilities, or tool comparison for engineering decisions.

For pure code editing without external research, this domain path is unnecessary.

## Source Matrix

Prefer:

1. local codebase files and tests
2. official docs for the exact version
3. release notes, changelogs, migration guides
4. official GitHub repository source and examples
5. package registry metadata
6. maintainer discussions or issue threads for unresolved behavior
7. reputable engineering posts only as secondary context

For OpenAI, Cloudflare, payment, security, or other fast-moving APIs, use current official docs first.

## Method

1. Identify exact package, version, runtime, and local usage.
2. Read local code before recommending changes.
3. Verify API behavior in official docs or source.
4. Distinguish stable APIs from examples, blog posts, and old issue comments.
5. If comparing tools, define engineering criteria before ranking.

## Output Shape

Include:

- local context inspected
- version assumptions
- official docs consulted
- findings and implementation implications
- migration or risk notes
- unresolved docs gaps
