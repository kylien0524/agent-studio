"""
LLM 연결부 — Gemini / Claude / 모의(Mock) 세 가지를 같은 모양으로 쓴다.

chat(model=..., system=..., messages=[{"role": "user"|"assistant", "content": str}, ...], agent=...) -> str

에이전트는 대화 기록(messages)을 통째로 넘긴다. 즉, 에이전트마다 '자기 기억'이 따로 있다.
"""
from __future__ import annotations

import json
import random
import time


class GeminiChat:
    def __init__(self, api_key: str, thinking_level: str | None = "low"):
        from google import genai
        from google.genai import types
        self.client = genai.Client(api_key=api_key)
        self.types = types
        self.thinking_level = thinking_level
        self._thinking_ok: dict[str, bool] = {}

    def _config(self, system, with_thinking):
        kw = dict(system_instruction=system, max_output_tokens=16384,
                  response_mime_type="application/json")
        if with_thinking and self.thinking_level:
            kw["thinking_config"] = self.types.ThinkingConfig(thinking_level=self.thinking_level)
        return self.types.GenerateContentConfig(**kw)

    def chat(self, *, model, system, messages, agent=None) -> str:
        contents = [{"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]}
                    for m in messages]
        use_thinking = self._thinking_ok.get(model, True)
        try:
            resp = self.client.models.generate_content(
                model=model, contents=contents, config=self._config(system, use_thinking))
        except Exception as exc:
            if use_thinking and "thinking" in str(exc).lower():  # thinking 미지원 모델이면 빼고 재시도
                self._thinking_ok[model] = False
                resp = self.client.models.generate_content(
                    model=model, contents=contents, config=self._config(system, False))
            else:
                raise
        if not resp.text:
            raise RuntimeError("Gemini가 빈 응답을 보냈습니다.")
        return resp.text

    def list_models(self) -> list[str]:
        names = []
        for m in self.client.models.list():
            acts = getattr(m, "supported_actions", None) or []
            if "gemini" in m.name and (not acts or "generateContent" in acts):
                names.append(m.name.removeprefix("models/"))
        return sorted(names)


class ClaudeChat:
    def __init__(self, api_key: str):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)

    def chat(self, *, model, system, messages, agent=None) -> str:
        resp = self.client.messages.create(model=model, max_tokens=8192, system=system, messages=messages)
        text = "".join(getattr(b, "text", "") for b in resp.content)
        if not text:
            raise RuntimeError(f"Claude가 빈 응답을 보냈습니다 (stop_reason={resp.stop_reason}).")
        return text

    def list_models(self) -> list[str]:
        return sorted(m.id for m in self.client.models.list(limit=100))


class MockChat:
    """API 없이 돌려보는 가짜 두뇌. 에이전트별 '대본(policy)'이 새 메시지에 반응해 행동을 정한다.
    실제 LLM과 똑같은 JSON 행동을 내놓고, 에이전트·스레드·메시지 구조는 실제 모드와 100% 같다."""

    def __init__(self, policies: dict, delay=(0.4, 1.2)):
        self.policies = policies
        self.delay = delay
        self.state: dict[str, dict] = {}

    def chat(self, *, model, system, messages, agent=None) -> str:
        time.sleep(random.uniform(*self.delay))  # 실제 API처럼 생각하는 시간 흉내 → 동시 실행이 눈에 보임
        st = self.state.setdefault(agent.name, {"seen": 0, "todo": []})
        for frm, content in agent.received[st["seen"]:]:
            st["todo"] += self.policies[agent.name](frm, content, agent, st)
        st["seen"] = len(agent.received)
        if st["todo"]:
            return json.dumps(st["todo"].pop(0), ensure_ascii=False)
        return json.dumps({"thought": "지금 할 일은 끝났다. 새 메시지를 기다린다.", "action": "wait", "args": {}},
                          ensure_ascii=False)


def make_llm(provider: str, api_key: str | None = None, thinking: str | None = "low", policies=None):
    if provider == "gemini":
        return GeminiChat(api_key, thinking_level=thinking)
    if provider == "claude":
        return ClaudeChat(api_key)
    return MockChat(policies)
