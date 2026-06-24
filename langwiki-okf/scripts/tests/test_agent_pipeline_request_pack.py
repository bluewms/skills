import importlib.util
import json
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


class AgentPipelineRequestPackTests(unittest.TestCase):
    def test_parse_args_accepts_request_pack(self):
        module = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = Path(tmp) / "in"
            out_dir = Path(tmp) / "out"
            input_dir.mkdir(parents=True)
            argv = [
                "agent_pipeline.py",
                "--input",
                str(input_dir),
                "--out",
                str(out_dir),
                "--mode",
                "api",
                "--request-pack",
                str(Path(tmp) / "request-pack" / "one.json"),
            ]
            with patch("sys.argv", argv):
                cfg = module.parse_args()

            self.assertEqual(Path(cfg.request_pack).suffix, ".json")

    def test_parse_args_accepts_mock_response(self):
        module = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = Path(tmp) / "in"
            out_dir = Path(tmp) / "out"
            input_dir.mkdir(parents=True)
            argv = [
                "agent_pipeline.py",
                "--input",
                str(input_dir),
                "--out",
                str(out_dir),
                "--mode",
                "api",
                "--mock-response",
            ]
            with patch("sys.argv", argv):
                cfg = module.parse_args()

            self.assertTrue(cfg.mock_response)

    def test_api_mode_requires_okf_api_model(self):
        module = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            input_dir = base / "in"
            out_dir = base / "out"
            input_dir.mkdir(parents=True)
            request_pack = base / "request-pack.json"
            request_pack.write_text(
                json.dumps(
                    {
                        "concept_id": "demo_concept",
                        "source": str(base / "demo.pdf"),
                        "source_name": "demo.pdf",
                        "messages": [
                            {"role": "system", "content": "sys"},
                            {"role": "user", "content": "usr"},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            cfg = module.PipelineConfig(
                input_dir=input_dir,
                out_dir=out_dir,
                pattern="**/*.md",
                mode="api",
                model=None,
                request_pack=request_pack,
                max_chars=100,
                cli_retries=1,
                retry_wait=1,
                dry_run=True,
                mock_response=False,
                verbose=False,
            )

            with patch.object(module, "resolve_model", return_value=""):
                with self.assertRaises(module.PipelineError) as ctx:
                    module.run_api_mode(cfg)
            self.assertIn("OKF_API_MODEL", str(ctx.exception))

    def test_api_mode_reads_messages_from_request_pack(self):
        module = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            input_dir = base / "in"
            out_dir = base / "out"
            input_dir.mkdir(parents=True)
            request_pack = base / "request-pack.json"

            request_pack.write_text(
                json.dumps(
                    {
                        "concept_id": "demo_concept",
                        "source": str(base / "demo.pdf"),
                        "source_name": "demo.pdf",
                        "model": "gpt-5.3-codex",
                        "messages": [
                            {"role": "system", "content": "sys"},
                            {"role": "user", "content": "usr"},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            cfg = module.PipelineConfig(
                input_dir=input_dir,
                out_dir=out_dir,
                pattern="**/*.md",
                mode="api",
                model="gpt-5.3-codex",
                request_pack=request_pack,
                max_chars=100,
                cli_retries=1,
                retry_wait=1,
                dry_run=False,
                mock_response=False,
                verbose=False,
            )

            def fake_call(messages, model, base_url, api_key, timeout=90):
                self.assertEqual(messages[1]["content"], "usr")
                self.assertEqual(model, "gpt-5.3-codex")
                return "---\ntype: concept\nconcept_id: demo_concept\n---\n\n## Key Points\n待补充\n\n## Details\n待补充\n\n## References\n待补充\n"

            with patch.object(module, "call_openai_compatible_messages", side_effect=fake_call), patch.object(module, "run_validator", return_value=None), patch.object(module, "resolve_api_credentials", return_value=("https://example.com/v1", "sk-test")):
                module.run_api_mode(cfg)

            self.assertTrue((out_dir / "demo_concept.md").exists())

    def test_auto_mode_dry_run_directly_uses_api_path(self):
        module = _load_module()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            input_dir = base / "in"
            out_dir = base / "out"
            input_dir.mkdir(parents=True)
            (input_dir / "a.md").write_text("hello", encoding="utf-8")

            cfg = module.PipelineConfig(
                input_dir=input_dir,
                out_dir=out_dir,
                pattern="**/*.md",
                mode="auto",
                model=None,
                request_pack=None,
                max_chars=100,
                cli_retries=1,
                retry_wait=1,
                dry_run=True,
                mock_response=False,
                verbose=False,
            )

            with patch.object(module, "run_api_mode", return_value=None) as api_mock, patch.object(module, "run_cli_mode", side_effect=AssertionError("dry-run 不应进入 CLI")):
                module.run_auto_mode(cfg)

            api_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
