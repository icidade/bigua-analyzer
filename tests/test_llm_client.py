from __future__ import annotations

import unittest
from unittest.mock import patch

from bigua_analyzer.ai.llm_client import _call_gemini


class GeminiClientFallbackTests(unittest.TestCase):
    def test_retries_without_system_instruction_on_http_400(self) -> None:
        payloads: list[dict] = []

        def fake_http_json(*, url: str, payload: dict, headers: dict | None = None, timeout: int = 120) -> dict:
            payloads.append(payload)
            if len(payloads) == 1:
                raise RuntimeError("LLM API returned HTTP 400: systemInstruction not supported")
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": "ok"},
                            ]
                        }
                    }
                ]
            }

        with patch("bigua_analyzer.ai.llm_client._http_json", side_effect=fake_http_json):
            response = _call_gemini(
                prompt="user prompt",
                system_prompt="system prompt",
                model="gemini-test",
                base_url="https://example.test/v1beta",
                api_key="fake-key",
                temperature=0.2,
                top_p=0.9,
                max_tokens=256,
            )

        self.assertEqual(response, "ok")
        self.assertEqual(len(payloads), 2)
        self.assertIn("systemInstruction", payloads[0])
        self.assertNotIn("systemInstruction", payloads[1])

    def test_does_not_retry_non_400_error(self) -> None:
        with patch(
            "bigua_analyzer.ai.llm_client._http_json",
            side_effect=RuntimeError("LLM API returned HTTP 500: internal"),
        ):
            with self.assertRaises(RuntimeError) as ctx:
                _call_gemini(
                    prompt="user prompt",
                    system_prompt="system prompt",
                    model="gemini-test",
                    base_url="https://example.test/v1beta",
                    api_key="fake-key",
                    temperature=0.2,
                    top_p=0.9,
                    max_tokens=256,
                )

        self.assertIn("HTTP 500", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
