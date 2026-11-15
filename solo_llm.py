"""
AI 연결부 — Gemini / Claude 를 같은 모양으로 부른다.

chat(model=..., system=..., messages=[{"role": "user"|"assistant", "content": str}, ...]) -> str

에이전트는 매번 대화 기록(messages) 전체를 넘긴다. AI 자체는 기억이 없고, 이 기록이 에이전트의 기억이다.
"""
from __future__ import annotations


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
