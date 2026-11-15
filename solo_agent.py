"""
싱글 에이전트 — 웹페이지·포스터를 혼자 만드는 AI 에이전트.

에이전트의 전부는 아래 반복문 하나다.

    요청을 기억에 넣는다
    반복:
        AI에게 기억 전체를 보여 주고 "다음 행동은?" 묻는다   → {"thought", "action", "args"}
        그 행동(도구)을 파이썬이 실제로 실행한다
        실행 결과를 기억에 덧붙인다
        publish(게시)를 했으면 끝

AI는 글자만 쓴다. 파일 저장·점검 같은 실제 일은 전부 파이썬 도구 함수가 한다.
동료도, 우편함도, 스레드도 없다 — 혼자 생각하고 혼자 검토한다.
"""
from __future__ import annotations

import json
import re
import time

# ═════════════════════════ 1. 에이전트의 정체성 (시스템 프롬프트) ═════════════════════════
SYSTEM_PROMPT = """당신은 웹페이지·포스터를 혼자 만드는 AI 에이전트입니다. 기획·문구·디자인·검토·게시를 모두 직접 합니다.

[목표]
요청자의 목적에 맞는, 핵심 정보가 한눈에 보이는 보기 좋은 결과물을 만들어 게시한다.

[사용할 수 있는 도구]
- save_copy(text): 문구(제목, 부제, 핵심 정보, 본문, 버튼 문구) 문서 저장
- write_page(html, note): HTML 페이지를 새 버전으로 저장 (화면에 바로 보임). note는 이번 버전에서 한 일 한 줄
- view_page(version): 저장된 페이지의 HTML 보기 (version 생략 시 최신)
- check_page(version): 페이지 자동 점검 (외부 링크, 모바일 설정, 글자 수 등)
- publish(version, summary): 최종 버전 게시 — 게시하면 업무 종료

[일하는 순서]
요청 해석 → save_copy 로 문구 저장 → write_page 로 페이지 저장 → view_page·check_page 로 스스로 점검
→ 고칠 점이 있으면 고쳐서 새 버전 저장 → publish 로 게시

[HTML 결과물 규칙]
- 하나로 완결된 HTML 문서 (<!doctype html>부터 </html>까지). CSS는 <style> 안에.
- 외부 파일·이미지·폰트·스크립트 링크 금지 (http로 시작하는 주소 금지). 그림이 필요하면 이모지·인라인 SVG·CSS 도형으로.
- 한국어. 휴대폰 화면에서도 깨지지 않게 (<meta name="viewport">).
- 요청에 있는 핵심 정보(날짜, 장소, 마감 등)는 빠짐없이, 한눈에 보이게.
- write_page 의 html 은 JSON 문자열로 넣거나, JSON 바로 다음 줄에 ```html 코드블록으로 붙이세요 (이 방법을 권장).

[규칙]
1. 한 번에 행동 하나만 합니다. 결과를 본 뒤 다음 행동을 정합니다.
2. 숫자·날짜는 요청에 나온 것만 씁니다. 지어내지 마세요.

[출력 형식] 다른 글 없이 JSON 하나만:
{"thought": "지금 상황 판단과 이 행동을 고른 이유 (1~2문장)", "action": "도구 이름", "args": {...}}"""


# ═════════════════════════ 2. 작업 공간 + 도구 (실제 일을 하는 파이썬 함수) ═════════════════════════
class Workspace:
    """결과물이 쌓이는 곳: 문구 문서, 페이지 버전 v1·v2…"""

    def __init__(self):
        self.copies: list[str] = []
        self.pages: list[dict] = []   # {"version", "html", "note"}

    def get(self, version=0):
        if not self.pages:
            return None
        if not version:
            return self.pages[-1]
        return next((p for p in self.pages if p["version"] == int(version)), None)


def auto_check(html: str) -> dict:
    """사람 눈 대신 기계적으로 확인할 수 있는 것들."""
    text = re.sub(r"<style.*?</style>|<script.*?</script>", "", html, flags=re.S | re.I)
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()
    ext = re.findall(r"""(?:src|href)\s*=\s*["']https?://|@import|url\(\s*["']?https?://""", html, re.I)
    return {
        "완결된 HTML": bool(re.search(r"<html", html, re.I) and re.search(r"</html>", html, re.I)),
        "모바일 viewport 설정": bool(re.search(r'name=["\']viewport', html, re.I)),
        "외부 리소스 링크 수(0이어야 함)": len(ext),
        "<img> 태그 수(외부 이미지 금지)": len(re.findall(r"<img", html, re.I)),
        "큰 제목(h1) 수": len(re.findall(r"<h1", html, re.I)),
        "화면에 보이는 글자 수": len(text),
        "글자 수 판단": "많음 — 줄이는 걸 고려" if len(text) > 900 else ("적당" if len(text) > 120 else "너무 적음"),
    }


def make_tools(ws: Workspace) -> dict:
    def save_copy(text: str = ""):
        ws.copies.append(str(text))
        return f"문구 문서 #{len(ws.copies)} 저장 완료 ({len(str(text))}자)."

    def write_page(html: str = "", note: str = ""):
        html = str(html or "").strip()
        if "<" not in html or len(html) < 200:
            return "오류: html 내용이 비었거나 너무 짧습니다. 완결된 HTML 문서를 넣으세요."
        v = len(ws.pages) + 1
        ws.pages.append({"version": v, "html": html, "note": str(note)})
        return f"v{v} 저장 완료 ({len(html):,}자). 화면에 바로 표시됩니다."

    def view_page(version: int = 0):
        p = ws.get(version)
        return {"version": p["version"], "메모": p["note"], "html": p["html"]} if p else "아직 저장된 페이지가 없습니다."

    def check_page(version: int = 0):
        p = ws.get(version)
        return {"version": p["version"], **auto_check(p["html"])} if p else "아직 저장된 페이지가 없습니다."

    def publish(version: int = 0, summary: str = ""):
        p = ws.get(version)
        return f"v{p['version']} 게시 완료. 업무 종료." if p else "오류: 게시할 페이지가 없습니다."

    return {"save_copy": save_copy, "write_page": write_page, "view_page": view_page,
            "check_page": check_page, "publish": publish}


# ═════════════════════════ 3. AI 답에서 행동 꺼내기 ═════════════════════════
def parse_action(text: str) -> dict | None:
    """AI 출력에서 행동 JSON을 꺼낸다. ```html 코드블록이 붙어 있으면 args.html 로 넣어 준다."""
    t = (text or "").strip()
    block = re.search(r"```html\s*(.*?)```", t, re.S)
    if block:
        t = t.replace(block.group(0), "")
    t = re.sub(r"```(?:json)?", "", t).strip()
    start = t.find("{")
    while start != -1:
        for cand in (t[start:], re.sub(r",\s*([}\]])", r"\1", t[start:])):
            try:
                obj, _ = json.JSONDecoder().raw_decode(cand)
                if isinstance(obj, dict) and "action" in obj:
                    if not isinstance(obj.get("args"), dict):
                        obj["args"] = {}
                    if block and len(str(obj["args"].get("html", ""))) < len(block.group(1).strip()):
                        obj["args"]["html"] = block.group(1).strip()
                    return obj
            except json.JSONDecodeError:
                pass
        start = t.find("{", start + 1)
    return None


# ═════════════════════════ 4. 에이전트 = 반복문 ═════════════════════════
class SoloAgent:
    def __init__(self, llm, model: str, max_steps: int = 20, on_publish=None):
        """on_publish(version, html, summary) -> str : 게시 직후 프로그램이 실행할 일 (예: 텔레그램 전송).
        AI가 고르는 행동이 아니라, 사람이 켜 둔 설정에 따라 프로그램이 하는 일이다."""
        self.llm, self.model, self.max_steps = llm, model, max_steps
        self.on_publish = on_publish
        self.system = SYSTEM_PROMPT
        self.ws = Workspace()
        self.tools = make_tools(self.ws)
        self.memory: list[dict] = []   # 에이전트의 기억 = AI와 주고받은 기록 전체
        self.calls = 0

    def _remember_user(self, text):
        if self.memory and self.memory[-1]["role"] == "user":
            self.memory[-1]["content"] += "\n\n" + text
        else:
            self.memory.append({"role": "user", "content": text})

    def run(self, request: str):
        """요청을 처리하며 사건(event)을 하나씩 내보낸다. 화면은 이걸 받아 실시간으로 그린다."""
        t0 = time.time()
        ev = lambda kind, **d: {"t": round(time.time() - t0, 1), "kind": kind, **d}
        self._remember_user(f"[요청]\n{request}")
        yield ev("request", text=request)

        for _ in range(self.max_steps):
            # ① 생각: AI에게 기억 전체를 보여 주고 다음 행동을 묻는다
            raw = None
            for attempt in range(2):
                try:
                    self.calls += 1
                    raw = self.llm.chat(model=self.model, system=self.system, messages=self.memory)
                    break
                except Exception as exc:
                    if attempt == 1:
                        yield ev("error", error=str(exc)[:300])
                        yield ev("finish", reason="AI 호출 오류", version=None)
                        return
                    time.sleep(2)
            act = parse_action(raw)
            self.memory.append({"role": "assistant", "content": raw.strip()})
            if act is None:
                self._remember_user('[형식 오류] JSON {"thought", "action", "args"} 하나만 출력하세요.')
                yield ev("note", text="AI 답 형식이 맞지 않아 다시 요청")
                continue
            name, args = str(act.get("action", "")).strip(), act["args"]
            yield ev("thought", text=str(act.get("thought", "")), action=name)

            # ② 행동: 파이썬이 도구를 실제로 실행한다
            if name not in self.tools:
                result = f"오류: '{name}'이라는 도구는 없습니다. 쓸 수 있는 도구: {', '.join(self.tools)}"
                if name == "wait":
                    result = "기다릴 상대가 없습니다. 혼자 일하고 있습니다. 다음 작업을 하거나 publish 하세요."
            else:
                try:
                    result = self.tools[name](**args)
                except Exception as exc:
                    result = f"오류: {exc}"
            yield ev("tool", tool=name, args=args, result=result)
            if name == "write_page" and str(result).startswith("v"):
                p = self.ws.pages[-1]
                yield ev("page", version=p["version"], html=p["html"], note=p["note"])
            if name == "save_copy" and not str(result).startswith("오류"):
                yield ev("copy", text=self.ws.copies[-1])

            # ③ 결과를 기억에 덧붙인다 (게시했으면 끝)
            if name == "publish" and not str(result).startswith("오류"):
                page = self.ws.get(args.get("version", 0))
                if self.on_publish:   # 게시 후 전송 (사람이 켜 둔 경우에만)
                    try:
                        msg = self.on_publish(page["version"], page["html"], str(args.get("summary", "")))
                        yield ev("telegram", ok=True, text=msg, version=page["version"])
                    except Exception as exc:
                        yield ev("telegram", ok=False, text=str(exc)[:300], version=page["version"])
                yield ev("finish", reason="게시 완료", version=page["version"], summary=args.get("summary", ""))
                return
            self._remember_user(f"[도구 결과] {name}: {json.dumps(result, ensure_ascii=False)}")

        last = self.ws.pages[-1]["version"] if self.ws.pages else None
        yield ev("finish", reason=f"단계 상한({self.max_steps}) 도달 — 최신 버전으로 마감", version=last)


# ═════════════════════════ 터미널 실행: python solo_agent.py [--provider gemini|claude] ═════════════════════════
if __name__ == "__main__":
    import argparse
    import os
    from pathlib import Path

    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["mock", "gemini", "claude"], default="mock")
    ap.add_argument("--model")
    ap.add_argument("--request")
    a = ap.parse_args()
    from solo_mock import EXAMPLES, MockSolo
    if a.provider == "gemini":
        from solo_llm import GeminiChat
        llm, model = GeminiChat(os.environ["GEMINI_API_KEY"]), a.model or "gemini-3.8-flash"
    elif a.provider == "claude":
        from solo_llm import ClaudeChat
        llm, model = ClaudeChat(os.environ["ANTHROPIC_API_KEY"]), a.model or "claude-sonnet-5-5"
    else:
        llm, model = MockSolo(), "mock"
    agent = SoloAgent(llm, model)
    Path("output").mkdir(exist_ok=True)
    for e in agent.run(a.request or EXAMPLES["사내 세미나 포스터"]):
        if e["kind"] == "thought":
            print(f"[{e['t']:5.1f}s] 💭 {e['text']}")
        elif e["kind"] == "tool":
            print(f"[{e['t']:5.1f}s] 🔧 {e['tool']} → {str(e['result'])[:100]}")
        elif e["kind"] == "page":
            Path(f"output/solo_v{e['version']}.html").write_text(e["html"], encoding="utf-8")
            print(f"[{e['t']:5.1f}s] 📄 v{e['version']} 저장 → output/solo_v{e['version']}.html")
        elif e["kind"] in ("error", "finish"):
            print(f"[{e['t']:5.1f}s] ■ {e.get('reason') or e.get('error')}")
    print(f"AI 호출 {agent.calls}회")
