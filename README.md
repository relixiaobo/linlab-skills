# Linlab Skills

Personal Codex skills maintained by Linlab.

## Skills

- `code-review` - high-signal PR, branch, and local-diff review with confidence scoring and git-history context.
- `data-analysis` - trustworthy analysis of files, tables, metrics, experiments, and trends.
- `research` - source-grounded research with cited artifacts and claim verification.
- `video-studio` - manifest-driven local video editing, rendering, packaging, and QA.

## Install

Copy a skill folder into your Codex skills directory:

```sh
mkdir -p ~/.codex/skills
rsync -a code-review/ ~/.codex/skills/code-review/
```

To install all skills:

```sh
mkdir -p ~/.codex/skills
for skill in code-review data-analysis research video-studio; do
  rsync -a "$skill/" "$HOME/.codex/skills/$skill/"
done
```

## Validate

Validate a skill with Codex's skill validator:

```sh
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py code-review
```

Each skill is intentionally self-contained. Generated `*-workspace/` folders are local evaluation artifacts and are not part of the published source.
