from pathlib import Path
import hashlib
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "openai" / "idea-spark"
VENDOR = ROOT / "vendor" / "researchstudio" / "skills" / "idea_spark"
PROMPTS = (
    "bottleneck_identify.txt",
    "coherence_trace.txt",
    "critique.txt",
    "derive_plain.txt",
    "expand.txt",
    "falsification_reaudit.txt",
    "ideate_generate.txt",
    "ideate_select.txt",
    "implementability_audit.txt",
    "refutation_recheck.txt",
    "revise.txt",
)

class OpenAISkillSourceContract(unittest.TestCase):
    def test_required_openai_layout(self):
        self.assertTrue((SKILL / "SKILL.md").is_file())
        self.assertTrue((SKILL / "agents" / "openai.yaml").is_file())

    def test_metadata_supports_chatgpt_and_codex(self):
        text = (SKILL / "agents" / "openai.yaml").read_text()
        self.assertIn("chatgpt", text)
        self.assertIn("codex", text)
        self.assertIn("allow_implicit_invocation", text)

    def test_native_routing_is_explicit(self):
        text = (SKILL / "SKILL.md").read_text() + "\n" + (SKILL / "references" / "native-retrieval-routing.md").read_text()
        for needle in ("GitHub", "web", "Files", "target_context.json", "source_manifest.json"):
            self.assertIn(needle, text)
        self.assertIn("Python", text)
        self.assertIn("deterministic", text)

    def test_all_reasoning_prompts_are_byte_identical_to_vendor(self):
        for name in PROMPTS:
            got = (SKILL / "references" / "system-prompts" / name).read_bytes()
            expected = (VENDOR / "references" / "system-prompts" / name).read_bytes()
            self.assertEqual(got, expected, name)

    def test_original_upstream_skill_is_preserved(self):
        self.assertEqual(
            (SKILL / "references" / "upstream" / "SKILL.md").read_bytes(),
            (VENDOR / "SKILL.md").read_bytes(),
        )

    def test_native_phase0_uses_upstream_compatible_grounding_sentinel(self):
        text = (SKILL / "SKILL.md").read_text() + "\n" + (SKILL / "references" / "openai-phase0.md").read_text()
        self.assertIn(".lit_grounding_mode", text)
        self.assertIn("webfallback", text)
        self.assertIn("target_context.json", text)

    def test_target_context_is_an_input_not_a_prompt_rewrite(self):
        text = (SKILL / "SKILL.md").read_text()
        self.assertIn("Phase 1", text)
        self.assertIn("target_context.json", text)
        self.assertIn("Do not modify", text)
        self.assertIn("system prompt", text)

    def test_native_mode_does_not_require_python_remote_retrievers(self):
        text = (SKILL / "SKILL.md").read_text() + "\n" + (SKILL / "references" / "native-retrieval-routing.md").read_text()
        self.assertIn("Do not install or invoke `scripts/search_*.py` for remote", text)
        self.assertIn("Do not call the bundled `scripts/search_*.py` retrievers", text)
        self.assertIn("deterministic", text)

    def test_source_tree_has_no_cache_or_credentials(self):
        bad = []
        for p in SKILL.rglob("*"):
            if not p.is_file():
                continue
            if p.name == ".env" or p.suffix == ".pyc" or "__pycache__" in p.parts:
                bad.append(str(p.relative_to(SKILL)))
        self.assertEqual(bad, [])

class OpenAISkillPackageContract(unittest.TestCase):
    def test_builder_creates_clean_skill_zip_with_exact_cards(self):
        builder = ROOT / "scripts" / "openai" / "build_skill.py"
        self.assertTrue(builder.is_file())
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            subprocess.run([sys.executable, str(builder), "--out", str(out)], cwd=ROOT, check=True)
            archive = out / "skill.zip"
            self.assertTrue(archive.is_file())
            with zipfile.ZipFile(archive) as zf:
                names = zf.namelist()
                self.assertTrue(any(n.endswith("agents/openai.yaml") for n in names))
                self.assertFalse(any("__pycache__" in n or n.endswith(".pyc") or n.endswith("/.env") for n in names))
                for i in range(31):
                    rel = f"references/ideation-sub-patterns/C{i:02d}.md"
                    packed = zf.read("idea-spark/" + rel)
                    expected = (VENDOR / rel).read_bytes()
                    self.assertEqual(packed, expected, rel)

if __name__ == "__main__":
    unittest.main()
