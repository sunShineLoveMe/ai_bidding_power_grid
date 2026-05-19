import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class ModelStageConfigTest(unittest.TestCase):
    def test_deepseek_defaults_use_pro_for_reasoning_and_flash_for_generation(self):
        from backend.core.config import get_stage_model, load_runtime_settings

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "runtime_settings.json"
            with patch("backend.core.config.CONFIG_FILE", config_file), patch.dict(os.environ, {}, clear=True):
                settings = load_runtime_settings()

                self.assertEqual(settings["ai_provider"], "deepseek")
                self.assertEqual(get_stage_model("interpretation"), "deepseek-v4-pro")
                self.assertEqual(get_stage_model("interpretation_segment"), "deepseek-v4-flash")
                self.assertEqual(get_stage_model("outline"), "deepseek-v4-pro")
                self.assertEqual(get_stage_model("compliance"), "deepseek-v4-pro")
                self.assertEqual(get_stage_model("section_writing"), "deepseek-v4-flash")
                self.assertEqual(get_stage_model("section_supplement"), "deepseek-v4-flash")
                self.assertEqual(get_stage_model("knowledge"), "deepseek-v4-flash")

    def test_deepseek_stage_env_overrides_are_respected(self):
        from backend.core.config import get_stage_model

        env = {
            "AI_PROVIDER": "deepseek",
            "DEEPSEEK_INTERPRETATION_MODEL": "deepseek-v4-pro",
            "DEEPSEEK_INTERPRETATION_SEGMENT_MODEL": "deepseek-v4-flash",
            "DEEPSEEK_SECTION_WRITING_MODEL": "deepseek-v4-flash",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "runtime_settings.json"
            with patch("backend.core.config.CONFIG_FILE", config_file), patch.dict(os.environ, env, clear=True):
                self.assertEqual(get_stage_model("interpretation"), "deepseek-v4-pro")
                self.assertEqual(get_stage_model("interpretation_segment"), "deepseek-v4-flash")
                self.assertEqual(get_stage_model("section_writing"), "deepseek-v4-flash")


if __name__ == "__main__":
    unittest.main()
