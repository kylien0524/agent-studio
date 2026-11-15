"""
에이전트 스튜디오 — 웹페이지·포스터를 만드는 AI 제작팀 (멀티에이전트)
실행: streamlit run team_app.py

요청을 넣고 버튼을 누르면 실제 AI(Gemini/Claude) 에이전트 4명(기획·카피·디자인·검토)이
서로 메시지를 주고받으며 결과물을 만든다. 페이지가 v1 → 검토 의견 → v2 로 바뀌는 과정이 실시간으로 보인다.
(혼자 만드는 싱글 에이전트는 별도 프로그램 solo-studio)
"""
import json
import os
import threading
import time

import streamlit as st
import streamlit.components.v1 as components

from team_llm import ClaudeChat, GeminiChat
from team_runner import DEFAULT_MODEL, run_system
from team_studio import REQUEST_EXAMPLES
from team_telegram import find_chat_ids, send_poster, send_text

st.set_page_config(page_title="에이전트 스튜디오", page_icon="🎨", layout="wide")
ss = st.session_state

DIAGRAM_SIZE = "6.5,3"   # 에이전트 관계 그림 최대 크기 (가로,세로 인치). 더 작게: "5,2.4" / 더 크게: "8,4"
COLOR = {"기획": ("#2563eb", "#dbeafe"), "카피": ("#d97706", "#fef3c7"), "디자인": ("#c026d3", "#fae8ff"),
         "검토": ("#059669", "#d1fae5"), "요청자": ("#6b7280", "#f3f4f6"), "시스템": ("#6b7280", "#f3f4f6")}
EMOJI = {"기획": "📋", "카피": "✍️", "디자인": "🎨", "검토": "🔍", "요청자": "🙋", "시스템": "⚙️"}
TOOL_KO = {"save_copy": "카피 문서", "write_page": "페이지 저장", "view_page": "페이지 보기",
           "check_page": "자동 점검", "publish": "게시"}
TOOLS_OF = {"기획": ["publish"], "카피": ["save_copy"], "디자인": ["write_page"], "검토": ["view_page", "check_page"]}
NAMES = list(TOOLS_OF)


def short(x, n=150):
    s = x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)
    s = s.replace("\n", " ")
    return s if len(s) <= n else s[:n] + "…"


def default_key(envs):
    for n in envs:
        if os.environ.get(n):
            return os.environ[n]
        try:
            if st.secrets.get(n):
                return st.secrets[n]
        except Exception:
            pass
    return ""


# ═════════════════════════ 사이드바 ═════════════════════════
with st.sidebar:
    st.header("⚙️ AI 연결")
    label = st.radio("어떤 AI로 만들까요?", ["Gemini", "Claude", "연습 모드 (API 없이)"],
                     help="연습 모드는 미리 만들어 둔 대본과 샘플 페이지입니다. 요청을 바꿔도 결과가 같습니다.")
    provider = {"Gemini": "gemini", "Claude": "claude"}.get(label, "mock")
    api_key, model, thinking = None, "mock", None
    if provider != "mock":
        envs = ["GEMINI_API_KEY", "GOOGLE_API_KEY"] if provider == "gemini" else ["ANTHROPIC_API_KEY"]
        api_key = st.text_input(f"{label} API 키", value=default_key(envs), type="password", key=f"key_{provider}")
        if st.button("📋 사용 가능한 모델 불러오기", use_container_width=True, disabled=not api_key):
            try:
                ss[f"models_{provider}"] = (GeminiChat if provider == "gemini" else ClaudeChat)(api_key).list_models()
            except Exception as exc:
                st.error(f"모델 목록을 못 불러왔습니다: {exc}")
        models = ss.get(f"models_{provider}") or []
        if models:
            hint = "flash" if provider == "gemini" else "sonnet"
            picks = [m for m in models if hint in m and "lite" not in m]
            model = st.selectbox("모델", models, index=models.index(picks[-1]) if picks else 0)
        else:
            model = st.text_input("모델 이름", DEFAULT_MODEL[provider], key=f"model_{provider}")
        if provider == "gemini":
            th = st.selectbox("생각(thinking) 수준", ["low", "medium", "high", "끄기"])
            thinking = None if th == "끄기" else th
    st.caption("네 에이전트 모두 **같은 모델**을 씁니다. 디자인 품질이 중요하면 너무 작은 모델은 피하세요.")
    max_calls = st.slider("AI 호출 상한", 15, 80, 40, step=5,
                          help="에이전트끼리 끝없이 수정만 반복하며 비용이 나가는 것을 막는 안전장치")

    st.header("📨 텔레그램 전송")
    tg_token = st.text_input("봇 토큰", value=default_key(["TELEGRAM_BOT_TOKEN"]), type="password",
                             help="텔레그램 @BotFather 에서 /newbot 으로 봇을 만들면 받는 토큰")
    tg_chat = st.text_input("chat_id", value=default_key(["TELEGRAM_CHAT_ID"]),
                            help="받을 사람(또는 단체방)의 번호. 봇에게 메시지를 한 번 보낸 뒤 아래 버튼으로 찾으세요.")
    c_a, c_b = st.columns(2)
    if c_a.button("내 chat_id 찾기", use_container_width=True, disabled=not tg_token):
        try:
            found = find_chat_ids(tg_token)
            if found:
                for cid, name in found:
                    st.code(f"{cid}  ({name})", language=None)
            else:
                st.warning("봇에게 온 메시지가 없습니다. 텔레그램에서 봇에게 아무 말이나 보낸 뒤 다시 누르세요.")
        except Exception as exc:
            st.error(str(exc))
    if c_b.button("테스트 전송", use_container_width=True, disabled=not (tg_token and tg_chat)):
        try:
            send_text(tg_token, tg_chat, "✅ AI 제작팀(에이전트 스튜디오) 연결 테스트")
            st.success("보냈습니다. 텔레그램을 확인하세요.")
        except Exception as exc:
            st.error(str(exc))
    tg_auto = st.checkbox("게시하면 자동으로 전송", value=False, disabled=not (tg_token and tg_chat),
                          help="밖으로 보내는 일은 사람이 켰을 때만 합니다 (안전장치). 게시 권한이 있는 📋 기획이 게시하는 순간 전송됩니다.")

# ═════════════════════════ 입력 ═════════════════════════
st.title("🎨 에이전트 스튜디오 — AI 제작팀")
st.caption("📋 기획 · ✍️ 카피 · 🎨 디자인 · 🔍 검토 — AI 에이전트 **네 명**이 각자 자기 일만 하며, "
           "서로 메시지를 주고받아 웹페이지·포스터를 만듭니다. 검토는 디자이너의 생각을 모른 채 **결과물만** 봅니다.")

ss.setdefault("req", REQUEST_EXAMPLES["사내 세미나 포스터"])
c1, c2 = st.columns([1, 3])
with c1:
    ex = st.selectbox("예시 요청", list(REQUEST_EXAMPLES))
    if st.button("이 예시로 채우기", use_container_width=True):
        ss.req = REQUEST_EXAMPLES[ex]
        st.rerun()
with c2:
    request = st.text_area("🙋 무엇을 만들까요? (자유롭게 써도 됩니다)", key="req", height=170)

need_key = provider != "mock" and not api_key
if need_key:
    st.warning("사이드바에 API 키를 넣어 주세요. (키 없이 화면만 보려면 '연습 모드')")


def worker(rec, kw):
    try:
        rec["result"] = run_system(listener=rec["events"].append, **kw)
    except Exception as exc:
        rec["error"] = str(exc)


if st.button("▶ 만들기", type="primary", disabled=need_key):
    kw = dict(provider=provider, api_key=api_key, model=model, thinking=thinking, max_calls=max_calls,
              request=request.strip())
    if tg_auto and tg_token and tg_chat:
        req_title = request.strip().splitlines()[0][:80] if request.strip() else "포스터"
        kw["on_publish"] = lambda v, html, summary: send_poster(
            tg_token, tg_chat, html, f"👥 AI 제작팀 · v{v} 게시\n{summary or req_title}", f"team_v{v}.html")
    rec = {"events": [], "result": None, "error": None, "t0": time.time()}
    rec["thread"] = threading.Thread(target=worker, args=(rec, kw), daemon=True)
    rec["thread"].start()
    ss.run = rec


# ═════════════════════════ 그리기 ═════════════════════════
def pages_of(evs):
    return [e for e in evs if e["kind"] == "artifact" and e.get("type") == "page"]


def state_of(name, evs, done):
    if done:
        return "✅", "종료"
    mine = [e for e in evs if e["agent"] == name and e["kind"] in ("thought", "tool", "message", "wait", "error")]
    if not mine:
        return "⚪", "시작 전"
    return ("💤", "대기") if mine[-1]["kind"] == "wait" else ("🟢", "일하는 중")


def diagram(evs, done):
    """누가 어떤 도구를 쓸 수 있고(점선), 실제로 썼고(실선), 누구에게 메시지를 보냈나(굵은 화살표)."""
    L = ['digraph G {', f'rankdir=LR; bgcolor="transparent"; nodesep=0.15; ranksep=0.35; size="{DIAGRAM_SIZE}"; ratio=compress;',
         'node [fontname="Malgun Gothic,Apple SD Gothic Neo,sans-serif" fontsize=9 margin="0.05,0.02"];',
         'edge [fontsize=10 fontcolor="#888888"];']
    c, f = COLOR["요청자"]
    L.append(f'"요청자" [label="🙋 요청자" shape=box style="rounded,filled" color="{c}" fillcolor="{f}"];')
    used = {}
    for e in evs:
        if e["kind"] == "tool":
            used[(e["agent"], e["tool"])] = used.get((e["agent"], e["tool"]), 0) + 1
    for n in NAMES:
        c, f = COLOR[n]
        icon, st_ = state_of(n, evs, done)
        on = icon == "🟢"
        L.append(f'"{n}" [label="{EMOJI[n]} {n}\\n{icon} {st_}" shape=circle width=0.75 style=filled color="{c}" '
                 f'fillcolor="{c if on else f}" fontcolor="{"white" if on else "black"}" penwidth={4 if on else 1.5}];')
        for t in TOOLS_OF[n]:
            k = used.get((n, t), 0)
            tid = f"{n}:{t}"
            L.append(f'"{tid}" [label="{TOOL_KO[t]}" shape=box style="rounded,filled" fontsize=8 height=0.25 color="{c}" '
                     f'fillcolor="{f if k else "white"}"];')
            L.append(f'"{n}" -> "{tid}" [arrowhead=none color="{c}" style={"solid" if k else "dashed"} '
                     f'penwidth={2 if k else 0.8}{f" label={k}" if k else ""}];')
    L.append(f'"요청자" -> "{NAMES[0]}" [style=dashed color="#999999"];')
    for n in NAMES[1:]:
        L.append(f'"{NAMES[0]}" -> "{n}" [style=invis];')
    pairs = {}
    for e in evs:
        if e["kind"] == "message" and e["agent"] in NAMES and e.get("to") in NAMES:
            pairs[(e["agent"], e["to"])] = pairs.get((e["agent"], e["to"]), 0) + 1
    for (a, b), k in pairs.items():
        L.append(f'"{a}" -> "{b}" [color="{COLOR[a][0]}" penwidth={1.5 + k} label="✉ {k}" constraint=false];')
    L.append("}")
    return "\n".join(L)


def memory(name, evs):
    out = []
    for e in evs:
        if e["kind"] == "message" and e.get("to") == name:
            out.append(f"📨 **{e['agent']} →** {short(e['content'], 400)}")
        elif e["kind"] == "tool" and e["agent"] == name:
            res = e["result"]
            if isinstance(res, dict) and "html" in res:
                res = {**res, "html": f"<HTML {len(res['html']):,}자>"}
            out.append(f"🔧 **{TOOL_KO.get(e['tool'], e['tool'])}**: `{short(res, 200)}`")
        elif e["kind"] == "message" and e["agent"] == name:
            out.append(f"📤 **→ {e['to']}**: {short(e['content'], 400)}")
    return out


def draw_left(rec, done):
    evs = list(rec["events"])
    elapsed = rec["result"]["elapsed"] if rec.get("result") else time.time() - rec["t0"]
    m = st.columns(4)
    m[0].metric("AI 판단", sum(e["kind"] == "thought" for e in evs))
    m[1].metric("에이전트 간 메시지", sum(e["kind"] == "message" and e["agent"] in NAMES and e.get("to") in NAMES for e in evs))
    m[2].metric("페이지 버전", len(pages_of(evs)))
    m[3].metric("경과", f"{elapsed:.0f}초")
    st.graphviz_chart(diagram(evs, done), use_container_width=False)
    fin = next((e for e in evs if e["kind"] == "finish"), None)
    if fin and fin.get("final"):
        st.success(f"**게시 완료: v{fin['final'].get('version')}** — {fin['final'].get('summary', '')}")
    elif fin:
        st.warning(f"종료: {fin['reason']}")
    for e in evs:
        if e["kind"] == "telegram":
            (st.success if e["ok"] else st.error)(f"📨 텔레그램: {short(e['text'], 300)}")
    errs = [e for e in evs if e["kind"] == "error"]
    if rec.get("error") or errs:
        st.error(f"오류: {rec.get('error') or short(errs[-1].get('error', ''), 300)}")

    st.markdown("#### 🔍 각 에이전트가 아는 것 (기억)")
    tabs = st.tabs([f"{EMOJI[n]} {n} ({len(memory(n, evs))})" for n in NAMES])
    for tab, n in zip(tabs, NAMES):
        with tab:
            with st.container(height=220):
                items = memory(n, evs)
                for it in items:
                    st.markdown(it)
                if not items:
                    st.caption("아직 아무것도 모릅니다. 메시지가 와야 깨어납니다.")
            if done and rec.get("result"):
                with st.expander("📜 이 에이전트의 정의 (시스템 프롬프트 원문)"):
                    st.code(rec["result"]["system_prompts"][n], language=None, wrap_lines=True)
    st.markdown("#### 🕒 진행 기록")
    with st.container(height=260):
        rows = []
        for e in evs:
            a = f"{EMOJI.get(e['agent'], '')} **{e['agent']}**"
            if e["kind"] == "message":
                rows.append(f"`{e['t']:5.1f}s` {a} ✉️ → **{e['to']}**: {short(e['content'], 120)}")
            elif e["kind"] == "thought":
                rows.append(f"`{e['t']:5.1f}s` {a} 💭 *{short(e['text'], 120)}*")
            elif e["kind"] == "artifact" and e.get("type") == "page":
                rows.append(f"`{e['t']:5.1f}s` {a} 📄 **v{e['version']} 저장**")
            elif e["kind"] == "tool" and e["tool"] != "write_page":
                rows.append(f"`{e['t']:5.1f}s` {a} 🔧 {TOOL_KO.get(e['tool'], e['tool'])}")
            elif e["kind"] == "telegram":
                rows.append(f"`{e['t']:5.1f}s` {a} 📨 **텔레그램** → {short(e['text'], 120)}")
            elif e["kind"] == "finish":
                rows.append(f"`{e['t']:5.1f}s` ■ **종료** — {e['reason']}")
        for r in reversed(rows[-40:]):
            st.markdown(r)


def draw_page(rec, done):
    evs = list(rec["events"])
    pages = pages_of(evs)
    st.markdown("#### 📄 결과물")
    if not pages:
        st.info("아직 페이지가 없습니다. 기획·문구 작업 중…")
        return
    if done:
        vs = [p["version"] for p in pages]
        pub = (rec.get("result") or {}).get("published") or vs[-1]
        v = st.radio("버전", vs, index=vs.index(pub) if pub in vs else len(vs) - 1, horizontal=True,
                     format_func=lambda x: f"v{x}" + (" ✅게시" if x == pub else ""), key="ver")
        page = next(p for p in pages if p["version"] == v)
    else:
        page = pages[-1]
    st.caption(f"v{page['version']} · {page['agent']} · {page.get('note', '')}")
    components.html(page["html"], height=780, scrolling=True)
    flow = []
    for e in evs:
        if e["kind"] == "artifact" and e.get("type") == "page":
            flow.append(f"📄 **v{e['version']}** 저장 ({EMOJI.get(e['agent'], '')} {e['agent']}) — {e.get('note', '')}")
        elif e["kind"] == "message" and e["agent"] == "검토":
            flow.append(f"🔍 **검토 → {e['to']}**: {e['content']}")
    if flow:
        with st.expander(f"🔁 고쳐 온 과정 ({len(flow)})", expanded=done):
            for x in flow:
                st.markdown(x)
    if done:
        c1, c2 = st.columns(2)
        c1.download_button(f"⬇️ v{page['version']} 저장 (.html)", page["html"], file_name=f"team_v{page['version']}.html",
                           mime="text/html", use_container_width=True)
        if c2.button(f"📨 v{page['version']} 텔레그램으로 보내기", use_container_width=True,
                     disabled=not (tg_token and tg_chat), key="tg_manual",
                     help="사이드바에 봇 토큰과 chat_id 를 넣으면 쓸 수 있습니다."):
            try:
                with st.spinner("보내는 중…"):
                    msg = send_poster(tg_token, tg_chat, page["html"], f"👥 AI 제작팀 · v{page['version']}",
                                      f"team_v{page['version']}.html")
                st.success(f"📨 {msg}")
            except Exception as exc:
                st.error(f"📨 전송 실패: {exc}")


rec = ss.get("run")
if rec:
    st.divider()
    left, right = st.columns([1, 1.25], gap="large")
    s_left, s_page = left.empty(), right.empty()
    shown = -1

    def draw(final):
        global shown
        done = final or not rec["thread"].is_alive()
        with s_left.container():
            draw_left(rec, done)
        n = len(pages_of(rec["events"]))
        if final or n != shown:            # 페이지는 새 버전이 나올 때만 다시 그림 (깜빡임 방지)
            shown = n
            with s_page.container():
                draw_page(rec, final)

    while rec["thread"].is_alive():
        draw(final=False)
        time.sleep(0.7)
    draw(final=True)
    if rec.get("result"):
        slim = {x: y for x, y in rec["result"].items() if x != "memories"}
        st.download_button("🗄️ 전체 기록 저장 (.json)", json.dumps(slim, ensure_ascii=False, indent=1),
                           file_name="team_log.json", mime="application/json")
else:
    st.info("요청을 확인하고 **▶ 만들기**를 누르세요. 처음엔 **연습 모드**로 화면을 익혀도 좋습니다.")
