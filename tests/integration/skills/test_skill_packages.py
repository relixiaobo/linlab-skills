#!/usr/bin/env python3
"""Repository-owned validation for active and archived Skill packages."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
MAX_SKILL_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
ALLOWED_FRONTMATTER_PROPERTIES = {
    "name",
    "description",
    "license",
    "allowed-tools",
    "metadata",
}
SKILL_PACKAGES = (
    ("code-review", ROOT / "skills" / "code-review"),
    ("data-analysis", ROOT / "skills" / "data-analysis"),
    ("document", ROOT / "skills" / "document"),
    ("feed-processing", ROOT / "skills" / "feed-processing"),
    ("pdf", ROOT / "skills" / "pdf"),
    ("presentation", ROOT / "skills" / "presentation"),
    ("shape-product-spec", ROOT / "skills" / "shape-product-spec"),
    ("spreadsheet", ROOT / "skills" / "spreadsheet"),
    ("video-studio", ROOT / "skills" / "video-studio"),
    ("archive/research", ROOT / "archive" / "research"),
)


def validate_skill(skill_path: Path) -> tuple[bool, str]:
    """Apply the checked-in equivalent of skill-creator quick_validate.py."""
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return False, "SKILL.md not found"

    content = skill_md.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return False, "No YAML frontmatter found"

    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return False, "Invalid frontmatter format"

    try:
        frontmatter = yaml.safe_load(match.group(1))
        if not isinstance(frontmatter, dict):
            return False, "Frontmatter must be a YAML dictionary"
    except yaml.YAMLError as exc:
        return False, f"Invalid YAML in frontmatter: {exc}"

    unexpected_keys = set(frontmatter) - ALLOWED_FRONTMATTER_PROPERTIES
    if unexpected_keys:
        allowed = ", ".join(sorted(ALLOWED_FRONTMATTER_PROPERTIES))
        unexpected = ", ".join(sorted(unexpected_keys))
        return (
            False,
            f"Unexpected key(s) in SKILL.md frontmatter: {unexpected}. "
            f"Allowed properties are: {allowed}",
        )

    if "name" not in frontmatter:
        return False, "Missing 'name' in frontmatter"
    if "description" not in frontmatter:
        return False, "Missing 'description' in frontmatter"

    name = frontmatter.get("name", "")
    if not isinstance(name, str):
        return False, f"Name must be a string, got {type(name).__name__}"
    name = name.strip()
    if name:
        if not re.match(r"^[a-z0-9-]+$", name):
            return (
                False,
                f"Name '{name}' should be hyphen-case "
                "(lowercase letters, digits, and hyphens only)",
            )
        if name.startswith("-") or name.endswith("-") or "--" in name:
            return (
                False,
                f"Name '{name}' cannot start/end with hyphen or contain consecutive hyphens",
            )
        if len(name) > MAX_SKILL_NAME_LENGTH:
            return (
                False,
                f"Name is too long ({len(name)} characters). "
                f"Maximum is {MAX_SKILL_NAME_LENGTH} characters.",
            )
    if name != skill_path.name:
        return False, f"Name '{name}' must match directory name '{skill_path.name}'"

    description = frontmatter.get("description", "")
    if not isinstance(description, str):
        return False, f"Description must be a string, got {type(description).__name__}"
    description = description.strip()
    if description:
        if "<" in description or ">" in description:
            return False, "Description cannot contain angle brackets (< or >)"
        if len(description) > MAX_DESCRIPTION_LENGTH:
            return (
                False,
                f"Description is too long ({len(description)} characters). "
                f"Maximum is {MAX_DESCRIPTION_LENGTH} characters.",
            )

    return True, "Skill is valid!"


class SkillPackageTests(unittest.TestCase):
    def test_active_and_archived_skill_packages(self) -> None:
        for logical_name, skill_path in SKILL_PACKAGES:
            with self.subTest(skill=logical_name):
                valid, message = validate_skill(skill_path)
                self.assertTrue(valid, message)


def main(argv: list[str]) -> int:
    if len(argv) == 1:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(SkillPackageTests)
        return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
    if len(argv) != 2:
        print(f"Usage: {argv[0]} [skill_directory]", file=sys.stderr)
        return 2

    skill_path = Path(argv[1])
    if not skill_path.is_absolute():
        skill_path = ROOT / skill_path
    valid, message = validate_skill(skill_path)
    print(message)
    return 0 if valid else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
