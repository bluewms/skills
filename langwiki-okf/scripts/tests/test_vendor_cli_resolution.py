import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parents[1] / "agent_pipeline.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("agent_pipeline", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["agent_pipeline"] = module
    spec.loader.exec_module(module)
    return module


class VendorCliResolutionTests(unittest.TestCase):
    def test_prefers_local_wrapper(self):
        module = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            fake_script = Path(tmp) / "agent_pipeline.py"
            fake_script.write_text("# test", encoding="utf-8")
            local_wrapper = Path(tmp) / "reference-agent"
            local_wrapper.write_text("#!/bin/sh\necho ok\n", encoding="utf-8")
            local_wrapper.chmod(0o755)

            with patch.object(module, "__file__", str(fake_script)), \
                 patch.object(module.shutil, "which", return_value="/usr/local/bin/reference-agent"):
                resolved = module.resolve_reference_agent_command()

            self.assertEqual(Path(resolved).resolve(), local_wrapper.resolve())

    def test_fallbacks_to_system_command(self):
        module = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            fake_script = Path(tmp) / "agent_pipeline.py"
            fake_script.write_text("# test", encoding="utf-8")

            with patch.object(module, "__file__", str(fake_script)), \
                 patch.object(module.shutil, "which", return_value="/usr/local/bin/reference-agent"):
                resolved = module.resolve_reference_agent_command()

            self.assertEqual(resolved, "/usr/local/bin/reference-agent")

    def test_raises_when_no_cli_found(self):
        module = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            fake_script = Path(tmp) / "agent_pipeline.py"
            fake_script.write_text("# test", encoding="utf-8")

            with patch.object(module, "__file__", str(fake_script)), \
                 patch.object(module.shutil, "which", return_value=None):
                with self.assertRaises(module.PipelineError) as ctx:
                    module.resolve_reference_agent_command()

            self.assertIn("bootstrap_local.sh", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
