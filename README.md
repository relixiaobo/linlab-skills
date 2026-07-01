# Linlab Skills

Personal Codex skills maintained by Linlab.

## Skills

- `code-review` - high-signal PR, branch, and local-diff review with confidence scoring and git-history context.
- `data-analysis` - trustworthy analysis of files, tables, metrics, experiments, and trends.
- `research` - source-grounded research with cited artifacts and claim verification.
- `video-studio` - manifest-driven local video editing, rendering, packaging, and QA.

## Install

For Codex CLI, copy or symlink a skill folder into the user skills directory:

```sh
mkdir -p ~/.agents/skills
ln -s "$PWD/code-review" ~/.agents/skills/code-review
```

To install all skills:

```sh
mkdir -p ~/.agents/skills
for skill in code-review data-analysis research video-studio; do
  ln -s "$PWD/$skill" "$HOME/.agents/skills/$skill"
done
```

Codex detects skill changes automatically in new sessions. If a skill does not
appear in `/skills` or `$` completion, restart Codex CLI.

## Validate

Validate a skill with Codex's skill validator:

```sh
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py code-review
```

Each skill is intentionally self-contained. Generated `*-workspace/` folders are local evaluation artifacts and are not part of the published source.
