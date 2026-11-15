"""
1인 에이전트 스튜디오 — 혼자 웹페이지·포스터를 만드는 AI 에이전트 (싱글 에이전트)
실행: streamlit run solo_app.py
"""
import json
import os
import threading
import time

import streamlit as st
import streamlit.components.v1 as components

from solo_llm import ClaudeChat, GeminiChat
from solo_mock import EXAMPLES, MockSolo
from solo_agent import SoloAgent
from solo_telegram import find_chat_ids, send_poster, send_text

st.set_page_config(page_title="1인 에이전트 스튜디오", page_icon="🧑‍🎨", layout="wide")
ss = st.session_state

DIAGRAM_SIZE = "5,2.6"   # 에이전트 그림 최대 크기 (가로,세로 인치). 더 작게: "4,2" / 더 크게: "7,3.5"
DEFAULT_MODEL = {"gemini": "gemini-3.8-flash", "claude": "claude-sonnet-5-5"}
TOOL_KO = {"save_copy": "문구 저장", "write_page": "페이지 저장", "view_page": "페이지 보기",
           "check_page": "자동 점검", "publish": "게시"}


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
                     help="연습 모드는 미리 써 둔 대본과 샘플 페이지입니다. 요청을 바꿔도 결과가 같습니다.")
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
    max_steps = st.slider("최대 행동 수", 5, 30, 20, help="에이전트가 끝없이 고치기만 하는 것을 막는 안전장치")

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
            send_text(tg_token, tg_chat, "✅ 1인 에이전트 스튜디오 연결 테스트")
            st.success("보냈습니다. 텔레그램을 확인하세요.")
        except Exception as exc:
            st.error(str(exc))
    tg_auto = st.checkbox("게시하면 자동으로 전송", value=False, disabled=not (tg_token and tg_chat),
                          help="밖으로 보내는 일은 사람이 켰을 때만 합니다 (안전장치).")

# ═════════════════════════ 입력 ═════════════════════════
st.title("🧑‍🎨 1인 에이전트 스튜디오")
st.caption("AI 에이전트 **한 명**이 기획·문구·디자인·검토·게시를 모두 혼자 해서 웹페이지·포스터를 만듭니다.")

ss.setdefault("req", EXAMPLES["사내 세미나 포스터"])
c1, c2 = st.columns([1, 3])
with c1:
    ex = st.selectbox("예시 요청", list(EXAMPLES))
    if st.button("이 예시로 채우기", use_container_width=True):
        ss.req = EXAMPLES[ex]
        st.rerun()
with c2:
    request = st.text_area("🙋 무엇을 만들까요? (자유롭게 써도 됩니다)", key="req", height=170)

need_key = provider != "mock" and not api_key
if need_key:
    st.warning("사이드바에 API 키를 넣어 주세요. (키 없이 화면만 보려면 '연습 모드')")


def worker(rec, agent, req):
    try:
        for ev in agent.run(req):
            rec["events"].append(ev)
    except Exception as exc:
        rec["events"].append({"t": 0, "kind": "error", "error": str(exc)})
        rec["events"].append({"t": 0, "kind": "finish", "reason": "오류로 중단", "version": None})


if st.button("▶ 만들기", type="primary", disabled=need_key):
    if provider == "gemini":
        llm = GeminiChat(api_key, thinking_level=thinking)
    elif provider == "claude":
        llm = ClaudeChat(api_key)
    else:
        llm = MockSolo()
    on_publish = None
    if tg_auto and tg_token and tg_chat:
        req_title = request.strip().splitlines()[0][:80] if request.strip() else "포스터"
        on_publish = lambda v, html, summary: send_poster(
            tg_token, tg_chat, html, f"🧑‍🎨 1인 에이전트 스튜디오 · v{v} 게시\n{summary or req_title}", f"solo_v{v}.html")
    agent = SoloAgent(llm, model, max_steps=max_steps, on_publish=on_publish)
    rec = {"events": [], "agent": agent, "t0": time.time()}
    rec["thread"] = threading.Thread(target=worker, args=(rec, agent, request.strip()), daemon=True)
    rec["thread"].start()
    ss.run = rec


# ═════════════════════════ 그리기 ═════════════════════════
def diagram(evs, done):
    used = {}
    for e in evs:
        if e["kind"] == "tool" and e["tool"] in TOOL_KO:
            used[e["tool"]] = used.get(e["tool"], 0) + 1
    last = next((e for e in reversed(evs) if e["kind"] in ("thought", "tool")), None)
    on = not done and last is not None
    state = "✅ 종료" if done else ("🟢 일하는 중" if on else "⚪ 시작 전")
    c, f = "#0d9488", "#ccfbf1"
    L = ['digraph G {', f'rankdir=LR; bgcolor="transparent"; nodesep=0.15; ranksep=0.4; size="{DIAGRAM_SIZE}"; ratio=compress;',
         'node [fontname="Malgun Gothic,Apple SD Gothic Neo,sans-serif" fontsize=9 margin="0.05,0.02"];',
         'edge [fontsize=9 fontcolor="#888888"];',
         '"요청자" [label="🙋 요청자" shape=box style="rounded,filled" color="#6b7280" fillcolor="#f3f4f6"];',
         f'"혼자" [label="🧑‍🎨 혼자\\n{state}" shape=circle width=0.85 style=filled color="{c}" '
         f'fillcolor="{c if on else f}" fontcolor="{"white" if on else "black"}" penwidth={4 if on else 1.5}];',
         '"요청자" -> "혼자" [style=dashed color="#999999"];']
    cur = last["tool"] if last and last["kind"] == "tool" else (last.get("action") if last else None)
    for t, ko in TOOL_KO.items():
        k = used.get(t, 0)
        hot = on and cur == t
        L.append(f'"{t}" [label="{ko}" shape=box style="rounded,filled" fontsize=8 height=0.25 color="{c}" '
                 f'fillcolor="{c if hot else (f if k else "white")}" fontcolor="{"white" if hot else "black"}"];')
        L.append(f'"혼자" -> "{t}" [arrowhead=none color="{c}" style={"solid" if k else "dashed"} '
                 f'penwidth={2 if k else 0.8}{f" label={k}" if k else ""}];')
    L.append("}")
    return "\n".join(L)


def draw_left(rec, done):
    evs = list(rec["events"])
    pages = [e for e in evs if e["kind"] == "page"]
    elapsed = (evs[-1]["t"] if done and evs else time.time() - rec["t0"])
    m = st.columns(4)
    m[0].metric("AI 판단", rec["agent"].calls)
    m[1].metric("도구 사용", sum(e["kind"] == "tool" for e in evs))
    m[2].metric("페이지 버전", len(pages))
    m[3].metric("경과", f"{elapsed:.0f}초")
    st.graphviz_chart(diagram(evs, done), use_container_width=False)
    fin = next((e for e in evs if e["kind"] == "finish"), None)
    if fin:
        (st.success if fin.get("version") else st.warning)(
            f"**{fin['reason']}**" + (f" — v{fin['version']}" if fin.get("version") else ""))
    for e in evs:
        if e["kind"] == "error":
            st.error(f"오류: {short(e['error'], 300)}")
        elif e["kind"] == "telegram":
            (st.success if e["ok"] else st.error)(f"📨 텔레그램: {short(e['text'], 300)}")
    st.markdown("#### 🧠 에이전트의 생각과 행동")
    with st.container(height=380):
        rows = []
        for e in evs:
            if e["kind"] == "thought":
                rows.append(f"`{e['t']:5.1f}s` 💭 *{e['text']}*")
            elif e["kind"] == "tool":
                res = e["result"]
                if isinstance(res, dict) and "html" in res:
                    res = {**res, "html": f"<HTML {len(res['html']):,}자>"}
                rows.append(f"`{e['t']:5.1f}s` 🔧 **{TOOL_KO.get(e['tool'], e['tool'])}** → `{short(res, 140)}`")
            elif e["kind"] == "note":
                rows.append(f"`{e['t']:5.1f}s` ⚠️ {e['text']}")
            elif e["kind"] == "telegram":
                rows.append(f"`{e['t']:5.1f}s` 📨 **텔레그램** → {short(e['text'], 140)}")
            elif e["kind"] == "finish":
                rows.append(f"`{e['t']:5.1f}s` ■ **{e['reason']}**")
        for r in reversed(rows):
            st.markdown(r)
        if not rows:
            st.caption("요청을 읽는 중…")


def draw_page(rec, done):
    evs = list(rec["events"])
    pages = [e for e in evs if e["kind"] == "page"]
    st.markdown("#### 📄 결과물")
    if not pages:
        st.info("아직 페이지가 없습니다. 작업 중…")
        return
    if done:
        vs = [p["version"] for p in pages]
        fin = next((e for e in evs if e["kind"] == "finish"), {})
        pub = fin.get("version") or vs[-1]
        v = st.radio("버전", vs, index=vs.index(pub) if pub in vs else len(vs) - 1, horizontal=True,
                     format_func=lambda x: f"v{x}" + (" ✅게시" if x == pub else ""), key="ver")
        page = next(p for p in pages if p["version"] == v)
    else:
        page = pages[-1]
    st.caption(f"v{page['version']} · {page.get('note', '')}")
    components.html(page["html"], height=780, scrolling=True)
    if done:
        c1, c2 = st.columns(2)
        c1.download_button(f"⬇️ v{page['version']} 저장 (.html)", page["html"], file_name=f"solo_v{page['version']}.html",
                           mime="text/html", use_container_width=True)
        if c2.button(f"📨 v{page['version']} 텔레그램으로 보내기", use_container_width=True,
                     disabled=not (tg_token and tg_chat), key="tg_manual",
                     help="사이드바에 봇 토큰과 chat_id 를 넣으면 쓸 수 있습니다."):
            try:
                with st.spinner("보내는 중…"):
                    msg = send_poster(tg_token, tg_chat, page["html"], f"🧑‍🎨 1인 에이전트 스튜디오 · v{page['version']}",
                                      f"solo_v{page['version']}.html")
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
        n = sum(e["kind"] == "page" for e in rec["events"])
        if final or n != shown:            # 페이지는 새 버전이 나올 때만 다시 그림 (깜빡임 방지)
            shown = n
            with s_page.container():
                draw_page(rec, final)

    while rec["thread"].is_alive():
        draw(final=False)
        time.sleep(0.6)
    draw(final=True)
    with st.expander("📜 이 에이전트의 정의 (시스템 프롬프트 원문)"):
        st.code(rec["agent"].system, language=None, wrap_lines=True)
    with st.expander(f"🗂️ 에이전트의 기억 (AI와 주고받은 기록 {len(rec['agent'].memory)}개)"):
        for m in rec["agent"].memory:
            who = "🙋/🔧 에이전트에게 들어온 것" if m["role"] == "user" else "🧑‍🎨 AI가 답한 것"
            st.markdown(f"**{who}**")
            st.code(short(m["content"], 1500), language=None, wrap_lines=True)
else:
    st.info("요청을 확인하고 **▶ 만들기**를 누르세요. 처음엔 **연습 모드**로 화면을 익혀도 좋습니다.")
