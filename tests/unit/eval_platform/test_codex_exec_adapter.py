from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from evals.runners.codex_exec_adapter import (
    build_codex_command,
    parse_jsonl,
    parse_jsonl_best_effort,
    provider_overrides,
    selected_skills,
    usage_from_events,
)


class CodexExecAdapterTests(unittest.TestCase):
    def test_command_pins_isolation_and_model_configuration(self) -> None:
        command = build_codex_command(
            codex_bin="codex",
            workspace=Path("/tmp/random-workspace"),
            response_path=Path("/tmp/random-workspace/deliverables/response.md"),
            model="gpt-5.6-sol",
            reasoning_effort="medium",
            network_access=True,
            user_prompt="Create the requested presentation.",
        )
        joined = " ".join(command)
        self.assertIn("--ephemeral", command)
        self.assertIn("--ignore-user-config", command)
        self.assertIn("--ignore-rules", command)
        self.assertIn("--disable plugins", joined)
        self.assertIn("--disable multi_agent", joined)
        self.assertIn("--model gpt-5.6-sol", joined)
        self.assertIn('model_reasoning_effort="medium"', command)
        self.assertIn("sandbox_workspace_write.network_access=true", command)
        self.assertNotIn("oracle", joined.lower())

    def test_jsonl_usage_and_skill_selection_are_parsed(self) -> None:
        events = parse_jsonl(
            "\n".join(
                [
                    '{"type":"thread.started","thread_id":"thread-1"}',
                    '{"type":"item.completed","item":{"type":"command_execution",'
                    '"command":"sed -n 1,200p skills/presentation/SKILL.md"}}',
                    '{"type":"turn.completed","usage":{"input_tokens":120,'
                    '"cached_input_tokens":80,"output_tokens":30,'
                    '"reasoning_output_tokens":10}}',
                ]
            )
        )
        selected = selected_skills(events, [{"name": "presentation"}, {"name": "document"}])
        self.assertEqual(selected, ["presentation"])
        self.assertEqual(
            usage_from_events(events),
            {
                "input_tokens": 120,
                "output_tokens": 30,
                "total_tokens": 150,
                "estimated_cost_usd": None,
            },
        )

    def test_only_safe_active_provider_fields_are_forwarded(self) -> None:
        with TemporaryDirectory(prefix="codex_provider_test_") as temp:
            config = Path(temp) / "config.toml"
            config.write_text(
                'model_provider = "proxy"\n'
                '[model_providers.proxy]\n'
                'name = "Proxy"\n'
                'base_url = "https://proxy.example.test/v1"\n'
                'wire_api = "responses"\n'
                'requires_openai_auth = true\n'
                '[mcp_servers.private]\n'
                'bearer_token_env_var = "SECRET_TOKEN"\n',
                encoding="utf-8",
            )
            provider_id, overrides = provider_overrides(config)
            joined = " ".join(overrides)
            self.assertEqual(provider_id, "proxy")
            self.assertIn('model_provider="proxy"', joined)
            self.assertIn("proxy.example.test", joined)
            self.assertNotIn("mcp_servers", joined)
            self.assertNotIn("SECRET_TOKEN", joined)

    def test_invalid_jsonl_is_rejected(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "line 1 is invalid"):
            parse_jsonl("not-json")

    def test_best_effort_jsonl_retains_usage_after_a_corrupt_large_event(self) -> None:
        events, diagnostics = parse_jsonl_best_effort(
            "\n".join(
                [
                    '{"type":"thread.started"}',
                    '{"type":"item.completed","item":{"aggregated_output":"unterminated}',
                    '{"type":"turn.completed","usage":{"input_tokens":7,"output_tokens":3}}',
                ]
            )
        )
        self.assertEqual(len(events), 2)
        self.assertEqual(diagnostics[0]["line"], 2)
        self.assertEqual(diagnostics[0]["kind"], "invalid-json")
        self.assertEqual(usage_from_events(events)["total_tokens"], 10)


if __name__ == "__main__":
    unittest.main()
