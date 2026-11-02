"""Tests for the DeepSeek / OpenAI-compatible client and the provider dispatch.

These lock in the two things that matter: the client degrades with a clear error
(rather than crashing) and never includes the key, and `llm` routes to the right
backend based on AI_PROVIDER.
"""
import os
import unittest
from unittest import mock

from backend import deepseek_client as dc
from backend import llm, ollama_client


def _resp(content, status=200):
    r = mock.Mock()
    r.status_code = status
    r.text = "boom" if status != 200 else ""
    r.json.return_value = content
    return r


class DeepSeekClientTests(unittest.TestCase):
    def setUp(self):
        self.key = mock.patch.object(dc, "api_key", return_value="sk-test")
        self.key.start()
        self.addCleanup(self.key.stop)

    def test_preflight_requires_key(self):
        with mock.patch.object(dc, "api_key", return_value=""):
            self.assertIn("no API key", dc.preflight())

    def test_generate_returns_text(self):
        with mock.patch.object(dc.requests, "post", return_value=_resp(
            {"choices": [{"message": {"content": "Hello"}}]}
        )) as post:
            text, err = dc.generate("hi")
        self.assertEqual(text, "Hello")
        self.assertIsNone(err)
        # The Authorization header must carry the key; nothing logs it.
        headers = post.call_args.kwargs["headers"]
        self.assertEqual(headers["Authorization"], "Bearer sk-test")

    def test_generate_surfaces_provider_error(self):
        with mock.patch.object(dc.requests, "post", return_value=_resp({}, status=500)):
            text, err = dc.generate("hi")
        self.assertIsNone(text)
        self.assertIn("500", err)

    def test_generate_json_parses(self):
        with mock.patch.object(dc.requests, "post", return_value=_resp(
            {"choices": [{"message": {"content": '{"a": 1}'}}]}
        )):
            data, err = dc.generate_json("hi")
        self.assertEqual(data, {"a": 1})
        self.assertIsNone(err)

    def test_generate_json_strips_fences(self):
        with mock.patch.object(dc.requests, "post", return_value=_resp(
            {"choices": [{"message": {"content": '```json\n{"a": 1}\n```'}}]}
        )):
            data, err = dc.generate_json("hi")
        self.assertEqual(data, {"a": 1})
        self.assertIsNone(err)

    def test_generate_json_bad_json(self):
        with mock.patch.object(dc.requests, "post", return_value=_resp(
            {"choices": [{"message": {"content": "not json"}}]}
        )):
            data, err = dc.generate_json("hi")
        self.assertIsNone(data)
        self.assertIn("invalid JSON", err)


class LlmDispatchTests(unittest.TestCase):
    def test_ollama_is_default(self):
        saved = os.environ.pop("AI_PROVIDER", None)
        try:
            self.assertEqual(llm.provider(), "ollama")
        finally:
            if saved is not None:
                os.environ["AI_PROVIDER"] = saved

    def test_deepseek_routes_away_from_ollama(self):
        with mock.patch.dict("os.environ", {"AI_PROVIDER": "deepseek"}):
            self.assertIs(llm._client(), dc)

    def test_custom_routes_to_remote_client(self):
        with mock.patch.dict("os.environ", {"AI_PROVIDER": "custom"}):
            self.assertIs(llm._client(), dc)

    def test_ollama_routes_to_ollama(self):
        with mock.patch.dict("os.environ", {"AI_PROVIDER": "ollama"}):
            self.assertIs(llm._client(), ollama_client)


if __name__ == "__main__":
    unittest.main()
