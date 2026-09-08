from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPARK = ROOT / "commands" / "spark.md"
NATIVE = ROOT / "skills" / "ideaspark-native" / "SKILL.md"
README = ROOT / "README.md"
PLUGIN = ROOT / ".claude-plugin" / "plugin.json"

class NativeHostAdapterContract(unittest.TestCase):
    def test_native_adapter_skill_exists(self):
        self.assertTrue(NATIVE.exists())

    def test_spark_defaults_to_native_and_preserves_upstream_fallback(self):
        text = SPARK.read_text()
        self.assertIn("retrieval_mode", text)
        self.assertIn("native", text)
        self.assertIn("upstream", text)

    def test_spark_drives_existing_workflow_one_step_at_a_time(self):
        text = SPARK.read_text()
        self.assertIn("run.py\" next", text)
        self.assertIn("max_steps", text)
        self.assertIn("1", text)
        self.assertIn('name: "ideaspark"', text)

    def test_native_phase0_contract_is_explicit(self):
        text = NATIVE.read_text()
        for name in (
            "phase0/user_query.txt",
            "phase0/lit_results.json",
            "phase0/lit_table.md",
            "phase0/fulltext_cache.json",
            "phase0/source_manifest.json",
            "phase0/target_context.json",
        ):
            self.assertIn(name, text)
        self.assertIn("GitHub", text)
        self.assertIn("WebSearch", text)
        self.assertIn("literature-only", text)

    def test_native_collision_contract_is_explicit(self):
        text = NATIVE.read_text()
        for name in (
            "phase3_collision/collision_hits.json",
            "phase3_collision/.collision_terms.json",
            "phase3_collision/source_manifest.json",
        ):
            self.assertIn(name, text)
        self.assertIn("signature_terms", text)
        self.assertIn("alias_terms", text)
        self.assertIn("do not decide novelty", text.lower())

    def test_reasoning_prompts_are_not_rewritten_by_adapter(self):
        text = NATIVE.read_text()
        self.assertIn("Do not rewrite", text)
        self.assertIn("system prompts", text)
        self.assertIn("fresh", text.lower())

class ProductSurfaceContract(unittest.TestCase):
    def test_primary_docs_describe_two_surfaces_not_playwright(self):
        text = README.read_text()
        self.assertIn("ChatGPT", text)
        self.assertIn("Codex", text)
        self.assertIn("openai/idea-spark", text)
        self.assertIn("GitHub", text)
        self.assertIn("native", text.lower())
        self.assertNotIn("playwright-extension", text)
        self.assertNotIn("skills/ideaspark-web", text)

    def test_installer_installs_native_skill_not_web_track(self):
        text = (ROOT / "scripts" / "init_research.py").read_text()
        self.assertIn("ideaspark-native", text)
        self.assertIn('"retrieval_mode": "native"', text)
        self.assertNotIn("ideaspark-web", text)
        self.assertNotIn("scripts/web", text)

    def test_selftest_runs_native_and_openai_contracts(self):
        text = (ROOT / "tests" / "selftest.sh").read_text()
        self.assertIn("test_native_host_adapter.py", text)
        self.assertIn("test_openai_skill.py", text)
        self.assertIn("scripts/openai/build_skill.py", text)
        self.assertNotIn("scripts/web/web.py", text)

    def test_spark_command_keeps_required_name_frontmatter(self):
        text = SPARK.read_text()
        self.assertIn("name: spark", text.split("---", 2)[1])

    def test_plugin_metadata_drops_playwright(self):
        text = PLUGIN.read_text()
        self.assertNotIn("playwright", text.lower())
        self.assertIn("native", text.lower())
        self.assertIn("openai", text.lower())

if __name__ == "__main__":
    unittest.main()
