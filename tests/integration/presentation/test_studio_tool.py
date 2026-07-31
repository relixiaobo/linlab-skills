from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
TOOL = REPO / "skills" / "presentation" / "scripts" / "studio_tool.mjs"


class StudioToolTests(unittest.TestCase):
    def run_tool(self, *args: str):
        return subprocess.run(
            ["node", str(TOOL), *args],
            cwd=REPO,
            capture_output=True,
            text=True,
        )

    def test_init_creates_a_self_consistent_project_and_static_checks_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "deck-project"
            init = self.run_tool(
                "init",
                str(project),
                "--theme",
                "modern-swiss",
                "--archetype",
                "conference-talk",
            )
            self.assertEqual(init.returncode, 0, init.stderr)

            config = json.loads((project / "studio.config.json").read_text())
            package = json.loads((project / "package.json").read_text())
            archetype = json.loads((project / "narrative" / "archetype.json").read_text())
            layouts = json.loads((project / "layout-library.json").read_text())
            self.assertEqual(config["themeId"], "modern-swiss")
            self.assertEqual(config["archetypeId"], "conference-talk")
            self.assertEqual(config["archetype"], "narrative/archetype.json")
            self.assertEqual(config["layoutLibrary"], "layout-library.json")
            self.assertEqual(archetype["id"], "conference-talk")
            self.assertEqual(len(layouts["layouts"]), 20)
            self.assertEqual(config["compiler"]["version"], "2.0.3")
            self.assertEqual(package["dependencies"]["dom-to-pptx"], "2.0.3")
            self.assertTrue((project / "theme" / "tokens.css").is_file())
            self.assertTrue((project / "theme" / "preview.webp").is_file())

            check = self.run_tool("check", str(project))
            self.assertEqual(check.returncode, 0, check.stderr)
            report = json.loads(check.stdout)
            self.assertTrue(report["ok"])
            self.assertEqual(report["html"]["slide_count"], 5)
            self.assertEqual(report["html"]["warnings"], [])
            self.assertEqual(report["evidence"]["warnings"], [])

    def test_init_refuses_to_overwrite_an_unrelated_nonempty_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "occupied"
            project.mkdir()
            (project / "user-file.txt").write_text("keep", encoding="utf-8")
            result = self.run_tool("init", str(project))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not empty", result.stderr)
            self.assertEqual((project / "user-file.txt").read_text(), "keep")

    def test_catalogs_are_exposed_by_the_cli(self):
        theme_result = self.run_tool("themes")
        archetype_result = self.run_tool("archetypes")
        layout_result = self.run_tool("layouts")
        self.assertEqual(theme_result.returncode, 0, theme_result.stderr)
        self.assertEqual(archetype_result.returncode, 0, archetype_result.stderr)
        self.assertEqual(layout_result.returncode, 0, layout_result.stderr)

        themes = json.loads(theme_result.stdout)
        archetypes = json.loads(archetype_result.stdout)
        layouts = json.loads(layout_result.stdout)
        self.assertEqual(len(themes), 9)
        self.assertEqual(len(archetypes), 7)
        self.assertEqual(len(layouts), 20)
        self.assertIn("photo-editorial", {theme["id"] for theme in themes})
        self.assertIn("learning-workshop", {item["id"] for item in archetypes})
        self.assertIn("table-takeaway", {layout["id"] for layout in layouts})


if __name__ == "__main__":
    unittest.main()
