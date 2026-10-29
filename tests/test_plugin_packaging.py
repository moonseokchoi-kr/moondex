"""Verify the skill bundle remains usable outside its source checkout."""
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILLS = {"project-guidelines", "code-quality-setup", "tdd-tidy-first", "deeper-prompt"}


class PluginPackaging(unittest.TestCase):
    def test_manifest_and_marketplace_identify_the_bundle(self):
        plugin = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
        self.assertEqual(plugin["name"], "moondex")
        self.assertEqual(plugin["skills"], "./skills/")
        self.assertFalse({"hooks", "agents", "mcpServers", "apps"} & plugin.keys())
        self.assertTrue(set(plugin) <= {
            "name", "version", "description", "author", "homepage", "repository",
            "license", "keywords", "skills", "interface",
        })
        self.assertRegex(plugin["version"], r"^\d+\.\d+\.\d+$")
        names = set()
        for prompt in plugin["interface"]["defaultPrompt"]:
            match = re.match(r"\$moondex:([a-z-]+)\b", prompt)
            self.assertIsNotNone(match)
            names.add(match.group(1))
        self.assertEqual(names, SKILLS)
        marketplace_path = ROOT / ".codex-plugin/marketplace.json"
        marketplace = json.loads(marketplace_path.read_text())
        self.assertEqual(marketplace["name"], plugin["name"])
        self.assertEqual(len(marketplace["plugins"]), 1)
        entry = marketplace["plugins"][0]
        self.assertEqual(entry["name"], plugin["name"])
        self.assertEqual((marketplace_path.parent / entry["source"]["path"]).resolve(), ROOT)

    def test_installed_skills_and_references_are_self_contained(self):
        with tempfile.TemporaryDirectory(prefix="moondex-install-") as temporary:
            installation = Path(temporary) / "unrelated path" / "moondex"
            shutil.copytree(ROOT / "skills", installation / "skills")
            discovered = {p.parent.name for p in (installation / "skills").glob("*/SKILL.md")}
            self.assertEqual(discovered, SKILLS)
            for skill in (installation / "skills").glob("*/SKILL.md"):
                text = skill.read_text()
                self.assertTrue(text.startswith("---\n"))
                frontmatter = text.split("---\n", 2)[1]
                self.assertRegex(frontmatter, rf"(?m)^name: {skill.parent.name}$")
                self.assertRegex(frontmatter, r"(?m)^description: .+")
                for link in re.findall(r"\]\(([^)]+)\)", text):
                    if link.startswith(("https:", "http:", "#")):
                        continue
                    target = (skill.parent / link).resolve()
                    self.assertTrue(target.is_relative_to(installation.resolve()))
                    self.assertTrue(target.is_file(), link)
                    self.assertTrue(target.read_text().strip())
            for name in ("code-quality-setup", "tdd-tidy-first"):
                references = installation / "skills" / name / "references"
                self.assertEqual({p.name for p in references.iterdir()}, {
                    "typescript.md", "python.md", "rust.md", "cpp.md",
                })
            for name in ("tdd-tidy-first", "deeper-prompt"):
                policy = installation / "skills" / name / "agents/openai.yaml"
                self.assertTrue(policy.is_file())
                self.assertRegex(policy.read_text(), r"(?m)^policy:\n  allow_implicit_invocation: false$")

    def test_bundle_has_no_retired_execution_dependencies(self):
        for name in ("agents", "hooks", "harness_core", "runtime", "legacy", "scripts"):
            self.assertFalse((ROOT / name).exists(), name)
        for path in [ROOT / "README.md", ROOT / "AGENTS.md", *(ROOT / "skills").rglob("*.md")]:
            text = path.read_text()
            self.assertNotIn("<moondex-runtime>", text)
            self.assertNotIn("python3 -m harness_core", text)
            self.assertNotRegex(text, r"\$moondex:(execute|harness|pr-converge|self-improve|handoff|idea-workshop|code-mapper|git-worktree|adversarial-review)\b")


if __name__ == "__main__":
    unittest.main()
