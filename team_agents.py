"""
멀티에이전트의 뼈대 — 시나리오와 무관한 부분.

- Bus     : 에이전트 사이의 우편함(메시지 큐) + 모든 사건 기록
- Agent   : 자기 스레드에서 돌아가는 독립 에이전트
            · 자기 기억(memory)   — 대화 기록이 에이전트마다 따로 쌓인다
            · 자기 도구(tools)    — 자기 부서 데이터만 조회 가능 (= 진짜 정보 격리)
            · 스스로 결정         — 매 순간 '도구 쓰기 / 동료에게 메시지 / 대기' 중 하나를 LLM이 고른다

진행 순서를 정하는 코드는 없다. 메시지가 오면 깨어나고, 할 일을 끝내면 잠든다.
"""
from __future__ import annotations

import json
import queue
import re
import threading
import time
from dataclasses import dataclass
from typing import Callable


@dataclass
class Tool:
    name: str
    description: str
    params: dict          # {"인자이름": "설명"}
    fn: Callable
    terminal: bool = False  # True면 이 도구를 쓰는 순간 전체 업무 종료 (예: 고객 회신)


class Bus:
    def __init__(self, max_calls: int = 60, time_limit: float = 300):
        self.queues: dict[str, queue.Queue] = {}
        self.events: list[dict] = []
        self.listeners: list[Callable] = []
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.calls, self.max_calls = 0, max_calls
        self.t0, self.time_limit = time.time(), time_limit
        self.final, self.stop_reason = None, None

    def register(self, name: str):
        self.queues[name] = queue.Queue()

    def send(self, frm: str, to: str, content: str):
        self.emit("message", frm, to=to, content=content)
        self.queues[to].put((frm, content))

    def emit(self, kind: str, agent: str, **data):
        ev = {"t": round(time.time() - self.t0, 1), "kind": kind, "agent": agent, **data}
        with self.lock:
            self.events.append(ev)
            for fn in self.listeners:
                fn(ev)

    def use_call(self) -> bool:
        with self.lock:
            if self.calls >= self.max_calls:
                return False
            self.calls += 1
            return True

    def finish(self, reason: str, final=None):
        if not self.stop.is_set():
            self.stop_reason, self.final = reason, final
            self.emit("finish", "시스템", reason=reason, final=final)
            self.stop.set()


def parse_action(text: str) -> dict | None:
    """LLM 출력에서 행동 JSON을 꺼낸다.
    HTML처럼 긴 내용은 JSON 뒤에 ```html 코드블록으로 붙여도 되고, 그러면 args.html 로 넣어 준다."""
    t = (text or "").strip()
    block = re.search(r"```html\s*(.*?)```", t, re.S)
    if block:
        t = t.replace(block.group(0), "")
    t = re.sub(r"```(?:json)?", "", t).strip()
    d = None
    start = t.find("{")
    while start != -1 and d is None:
        for cand in (t[start:], re.sub(r",\s*([}\]])", r"\1", t[start:])):
            try:
                obj, _ = json.JSONDecoder().raw_decode(cand)
                if isinstance(obj, dict) and "action" in obj:
                    d = obj
                    break
            except json.JSONDecodeError:
                pass
        start = t.find("{", start + 1) if d is None else start
    if d is None:
        return None
    if block:
        d.setdefault("args", {})
        if not isinstance(d["args"], dict):
            d["args"] = {}
        if len(str(d["args"].get("html", ""))) < len(block.group(1).strip()):
            d["args"]["html"] = block.group(1).strip()
    return d


class Agent(threading.Thread):
    def __init__(self, name: str, emoji: str, intro: str, goal: str, tools: list[Tool],
                 colleagues: dict[str, str], llm, model: str, bus: Bus, extra_rules: str = "",
                 max_steps: int = 8):
        super().__init__(daemon=True, name=name)  # self.name == 에이전트 이름 (스레드 이름)
        self.emoji = emoji
        self.intro, self.goal, self.extra_rules = intro, goal, extra_rules
        self.tools = {t.name: t for t in tools}
        self.colleagues = {k: v for k, v in colleagues.items() if k != name}
        self.llm, self.model, self.bus = llm, model, bus
        self.max_steps = max_steps
        self.memory: list[dict] = []        # 이 에이전트만의 기억
        self.received: list[tuple] = []     # 받은 메시지 (보낸 사람, 내용)
        self.busy = False
        bus.register(name)
        self.system = self._system_prompt()

    # ── 정체성: 역할·목표·동료·쓸 수 있는 행동 ──
    def _system_prompt(self) -> str:
        if self.colleagues:
            cols = ("[동료 에이전트] — send_message로 직접 연락할 수 있습니다. 동료들도 각자 따로 일하고 있습니다.\n"
                    + "\n".join(f"- {k}: {v}" for k, v in self.colleagues.items()))
            acts = ["- send_message(to, content): 동료에게 메시지를 보낸다. to는 "
                    + "/".join(self.colleagues) + " 중 하나"]
        else:  # 에이전트 1개 구성: 동료 없이 혼자 모든 도구로 처리
            cols = "[동료 에이전트] 없음 — 모든 일을 혼자 처리합니다."
            acts = []
        acts.append("- wait(): 지금 할 일을 마치고 새 메시지가 올 때까지 쉰다")
        for t in self.tools.values():
            ps = ", ".join(self.tools[t.name].params) if t.params else ""
            pdesc = "; ".join(f"{k}: {v}" for k, v in t.params.items())
            acts.append(f"- {t.name}({ps}): {t.description}" + (f" [{pdesc}]" if pdesc else ""))
        actions = "\n".join(acts)
        if self.colleagues:
            rules = """1. 한 번에 행동 하나만 합니다. 결과를 본 뒤 다음 행동을 정합니다.
2. 당신 도구로 알 수 없는 것은 추측하지 말고 그 정보를 가진 동료에게 직접 물어보세요.
   숫자는 도구 결과나 동료 답변에 나온 것만 씁니다.
3. 동료에게 질문을 보냈으면 답이 올 때까지 wait 하세요. 답장은 새 메시지로 도착합니다.
4. 질문을 받으면 필요한 도구로 확인한 뒤, 질문한 동료에게 답장하세요.
5. 메시지는 2~4문장으로, 숫자와 조건을 구체적으로 씁니다.
6. 부서 목표를 지키되, 회사 전체가 받아들일 수 있는 조건을 함께 찾습니다."""
        else:
            rules = """1. 한 번에 행동 하나만 합니다. 결과를 본 뒤 다음 행동을 정합니다.
2. 필요한 정보는 모두 당신 도구로 직접 조회할 수 있습니다. 추측하지 말고 조회하세요.
   숫자는 도구 결과에 나온 것만 씁니다.
3. 각 부서의 사정(원가, 일정, 품질)을 모두 고려해 회사 전체가 받아들일 수 있는 조건을 찾습니다."""
        return f"""당신은 {self.intro}

[당신의 목표]
{self.goal}

{cols}

[사용할 수 있는 행동]
{actions}

[규칙]
{rules}
{self.extra_rules}
[출력 형식] 다른 글 없이 JSON 하나만:
{{"thought": "지금 상황 판단과 이 행동을 고른 이유 (1~2문장)", "action": "행동 이름", "args": {{...}}}}"""

    # ── 기억 관리 ──
    def _add_user(self, text: str):
        if self.memory and self.memory[-1]["role"] == "user":  # user가 연달아 오면 합친다
            self.memory[-1]["content"] += "\n\n" + text
        else:
            self.memory.append({"role": "user", "content": text})

    # ── 생명 주기: 메시지 대기 → 깨어남 → 생각·행동 반복 → 다시 대기 ──
    def run(self):
        q = self.bus.queues[self.name]
        while not self.bus.stop.is_set():
            try:
                first = q.get(timeout=0.2)
            except queue.Empty:
                continue
            self.busy = True
            batch = [first]
            while True:
                try:
                    batch.append(q.get_nowait())
                except queue.Empty:
                    break
            self.received += batch
            self._add_user("[새 메시지]\n" + "\n".join(f"- 보낸 사람: {f}\n  내용: {c}" for f, c in batch))
            try:
                self._work()
            finally:
                self.busy = False

    def _work(self):
        for _ in range(self.max_steps):
            if self.bus.stop.is_set():
                return
            if not self.bus.use_call():
                self.bus.finish(f"LLM 호출 예산({self.bus.max_calls}회) 소진")
                return
            raw = self._call_llm()
            if raw is None:
                return
            act = parse_action(raw)
            self.memory.append({"role": "assistant", "content": raw.strip()})
            if act is None:
                self._add_user('[형식 오류] JSON {"thought", "action", "args"} 하나만 출력하세요.')
                continue
            if act.get("thought"):
                self.bus.emit("thought", self.name, text=str(act["thought"]))
            name, args = str(act.get("action", "")).strip(), act.get("args") or {}
            if name == "wait":
                self.bus.emit("wait", self.name)
                return
            result = self._execute(name, args)
            if self.bus.stop.is_set():
                return
            self._add_user(f"[행동 결과] {name}: {json.dumps(result, ensure_ascii=False)}")
        self.bus.emit("note", self.name, text=f"한 번에 {self.max_steps}단계를 넘어 일단 쉽니다.")

    def _call_llm(self):
        for attempt in range(2):
            try:
                return self.llm.chat(model=self.model, system=self.system, messages=self.memory, agent=self)
            except Exception as exc:
                if attempt == 0:
                    time.sleep(2)
                    continue
                self.bus.emit("error", self.name, error=str(exc)[:300])
                return None

    def _execute(self, name: str, args: dict):
        if name == "send_message":
            to = str(args.get("to", "")).replace("팀장", "").replace("팀", "").strip()
            content = str(args.get("content", "")).strip()
            if to not in self.colleagues:
                return f"오류: '{to}'라는 동료는 없습니다. 가능한 대상: {', '.join(self.colleagues)}"
            if not content:
                return "오류: 내용이 비었습니다."
            self.bus.send(self.name, to, content)
            return "전송 완료. 답장은 나중에 새 메시지로 옵니다."
        if name not in self.tools:
            return f"오류: '{name}'은(는) 당신이 쓸 수 없는 행동입니다."
        try:
            result = self.tools[name].fn(**args)
        except Exception as exc:
            result = f"오류: {exc}"
        self.bus.emit("tool", self.name, tool=name, args=args, result=result)
        if self.tools[name].terminal and not str(result).startswith("오류"):
            self.bus.finish(f"{self.name} 에이전트가 {name} 실행", final=args)
        return result
