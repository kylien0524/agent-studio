"""
에이전트 스튜디오 실행기 — 한 구성을 끝까지 돌리고 결과물을 돌려준다.

터미널에서 바로:
  python team_runner.py                          # 연습 모드 (API 키 없이)
  python team_runner.py --provider gemini        # GEMINI_API_KEY 필요
  python team_runner.py --provider claude        # ANTHROPIC_API_KEY 필요
  python team_runner.py --request "송년회 포스터 만들어 줘 ..."
결과물은 output/ 폴더에 HTML 파일로 저장된다 (브라우저로 열면 바로 보임).
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from team_agents import Bus
from team_llm import make_llm
from team_mock import team_policies
from team_studio import ENTRY, REQUEST_EXAMPLES, build_team

DEFAULT_MODEL = {"gemini": "gemini-3.8-flash", "claude": "claude-sonnet-5-5", "mock": "mock"}
DEFAULT_REQUEST = REQUEST_EXAMPLES["사내 세미나 포스터"]


def run_system(provider="mock", api_key=None, model=None, thinking="low", max_calls=40,
               time_limit=600, request=None, listener=None, printer=None, on_publish=None):
    model = model or DEFAULT_MODEL[provider]
    llm = make_llm(provider, api_key, thinking, policies=team_policies())
    bus = Bus(max_calls=max_calls, time_limit=time_limit)
    for fn in (printer, listener):
        if fn:
            bus.listeners.append(fn)
    agents = build_team(bus, llm, model)
    bus.workspace.on_publish = on_publish   # 게시하면 실행할 일 (텔레그램 전송 등, 사람이 켰을 때만)
    for a in agents:
        a.start()
    entry = ENTRY
    bus.send("요청자", entry, request or DEFAULT_REQUEST)

    # 감시자: 순서를 정하지 않는다. 시간 초과·교착(모두 대기)만 확인한다.
    idle_since, nudges = None, 0
    while not bus.stop.is_set():
        time.sleep(0.3)
        if time.time() - bus.t0 > bus.time_limit:
            bus.finish("시간 초과")
            break
        idle = all(not a.busy for a in agents) and all(q.empty() for q in bus.queues.values())
        if not idle:
            idle_since = None
            continue
        idle_since = idle_since or time.time()
        if time.time() - idle_since > 2.5:
            if nudges < 2:
                nudges += 1
                bus.send("시스템", entry, "모두 대기 중입니다. 지금까지의 최신 버전으로 게시하세요.")
            else:
                bus.finish("교착 상태 (아무도 움직이지 않음)")
            idle_since = None
    elapsed = time.time() - bus.t0
    time.sleep(0.3)
    ws = bus.workspace
    published = (bus.final or {}).get("version")
    try:
        published = int(published)
    except (TypeError, ValueError):
        published = ws.pages[-1]["version"] if ws.pages else None
    return {
        "provider": provider, "model": model,
        "request": request or DEFAULT_REQUEST, "elapsed": round(elapsed, 1), "llm_calls": bus.calls,
        "stop_reason": bus.stop_reason, "final": bus.final, "published": published,
        "pages": ws.pages, "copies": ws.copies, "events": bus.events,
        "agents": [{"name": a.name, "emoji": a.emoji, "tools": list(a.tools)} for a in agents],
        "system_prompts": {a.name: a.system for a in agents},
        "memories": {a.name: a.memory for a in agents},
    }


# ───────────────── 터미널 출력 ─────────────────
os.system("")
COL = {"기획": "\033[94m", "카피": "\033[93m", "디자인": "\033[95m", "검토": "\033[92m"}
DIM, BOLD, RESET = "\033[2m", "\033[1m", "\033[0m"


def short(x, n=120):
    s = x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)
    s = s.replace("\n", " ")
    return s if len(s) <= n else s[:n] + "…"


def printer(ev):
    t, a, k = f"{DIM}[{ev['t']:5.1f}s]{RESET}", f"{COL.get(ev['agent'], '')}{ev['agent']}{RESET}", ev["kind"]
    if k == "message":
        print(f"{t} {a} ✉️  → {ev['to']}: {short(ev['content'])}")
    elif k == "tool":
        args = {x: (f"<HTML {len(str(v)):,}자>" if x == "html" else v) for x, v in ev["args"].items()}
        print(f"{t} {a} 🔧 {ev['tool']}({short(args, 80)}) → {DIM}{short(ev['result'], 100)}{RESET}")
    elif k == "thought":
        print(f"{t} {a} {DIM}💭 {ev['text']}{RESET}")
    elif k == "artifact" and ev["type"] == "page":
        print(f"{t} {a} {BOLD}📄 페이지 v{ev['version']} 저장{RESET} — {ev['note']}")
    elif k in ("error", "note"):
        print(f"{t} {a} ⚠️  {ev.get('error') or ev.get('text')}")
    elif k == "telegram":
        print(f"{t} {a} 📨 텔레그램: {ev['text']}")
    elif k == "finish":
        print(f"{t} {BOLD}■ 종료: {ev['reason']}{RESET}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["mock", "gemini", "claude"], default="mock")
    ap.add_argument("--model")
    ap.add_argument("--request", help="만들 결과물 요청 (생략하면 세미나 포스터 예시)")
    ap.add_argument("--max-calls", type=int, default=40)
    ap.add_argument("--thinking", default="low")
    a = ap.parse_args()
    key = None
    if a.provider != "mock":
        env = "GEMINI_API_KEY" if a.provider == "gemini" else "ANTHROPIC_API_KEY"
        key = os.environ.get(env) or (os.environ.get("GOOGLE_API_KEY") if a.provider == "gemini" else None)
        if not key:
            sys.exit(f"{env} 환경변수를 설정하세요.")
    out = Path("output")
    out.mkdir(exist_ok=True)
    stamp = f"{datetime.now():%Y%m%d_%H%M%S}"
    print(f"\n{BOLD}▶ 에이전트 4개 (제작팀){RESET}\n")
    r = run_system(a.provider, key, a.model, None if a.thinking == "none" else a.thinking,
                   a.max_calls, request=a.request, printer=printer)
    for p in r["pages"]:
        (out / f"{stamp}_team_v{p['version']}.html").write_text(p["html"], encoding="utf-8")
    print(f"\n  버전 {len(r['pages'])}개 · 게시: v{r['published']} · AI 호출 {r['llm_calls']}회 · {r['elapsed']}초")
    print(f"  저장: output/{stamp}_team_v*.html")


if __name__ == "__main__":
    main()
