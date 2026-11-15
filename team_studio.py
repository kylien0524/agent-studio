"""
에이전트 스튜디오 — 웹페이지·포스터를 만드는 에이전트들.

에이전트 4개(제작팀): 📋 기획 → ✍️ 카피 → 🎨 디자인 ⇄ 🔍 검토 → 📋 기획이 게시
(혼자 만드는 싱글 에이전트는 별도 프로그램 solo-studio)

결과물(카피 문서, 페이지 버전 v1·v2…)은 Workspace 에 쌓이고, 'artifact' 사건으로 화면에 실시간 전달된다.
"""
import re
import threading

from team_agents import Agent, Tool

REQUEST_EXAMPLES = {
    "사내 세미나 포스터": (
        "사내 'AI 업무 활용 세미나' 안내 포스터를 만들어 주세요.\n"
        "- 일시: 12월 3일(수) 오후 3시~5시\n- 장소: 본관 3층 대회의실\n- 대상: 전 직원, 선착순 40명\n"
        "- 내용: 생성형 AI로 보고서 초안 쓰기, 메일 정리, 엑셀 데이터 정리 실습\n"
        "- 준비물: 노트북\n- 신청: 11월 28일(금)까지 사내 게시판에서\n"
        "AI가 처음인 사람도 부담 없이 오고 싶게 만들어 주세요."),
    "제품 소개 페이지": (
        "가상의 회사 '한빛머티리얼즈'의 반도체 장비용 정밀 세라믹 부품을 소개하는 웹페이지를 만들어 주세요.\n"
        "- 강점: 고순도 알루미나 소재, 내플라즈마성, 납기 준수율 98%, 맞춤 가공\n"
        "- 대상: 반도체 장비 회사 구매·엔지니어 담당자\n- 마지막에 '견적 문의' 버튼\n"
        "신뢰감 있고 깔끔하게."),
    "송년회 안내": (
        "부서 송년회 안내 포스터를 만들어 주세요.\n"
        "- 일시: 12월 19일(금) 저녁 6시 30분\n- 장소: 회사 근처 한식당 '소담' 2층\n"
        "- 프로그램: 올해의 순간 사진 퀴즈, 작은 선물 교환(1만원 이내)\n- 참석 여부: 12월 12일까지 회신\n"
        "따뜻하고 즐거운 분위기로."),
}

HTML_RULES = """[HTML 결과물 규칙]
- 하나로 완결된 HTML 문서 (<!doctype html>부터 </html>까지). CSS는 <style> 안에.
- 외부 파일·이미지·폰트·스크립트 링크 금지 (http로 시작하는 주소 금지). 그림이 필요하면 이모지나 인라인 SVG, CSS 도형으로.
- 한국어. 휴대폰 화면에서도 깨지지 않게 (<meta name="viewport">).
- 요청에 있는 핵심 정보(날짜, 장소, 마감 등)는 빠짐없이, 한눈에 보이게.
- write_page 의 html 은 JSON 문자열로 넣거나, JSON 바로 다음 줄에 ```html 코드블록으로 붙이세요 (이 방법을 권장).
"""


# ───────────────── 작업 공간: 결과물이 쌓이는 곳 ─────────────────
class Workspace:
    def __init__(self, bus):
        self.bus = bus
        self.pages: list[dict] = []     # {"version", "author", "html", "note", "t"}
        self.copies: list[dict] = []    # {"author", "text"}
        self.lock = threading.Lock()
        # 게시 직후 프로그램이 실행할 일 (예: 텔레그램 전송). on_publish(version, html, summary) -> str
        # AI가 고르는 행동이 아니라, 사람이 켜 둔 설정에 따라 프로그램이 하는 일이다.
        self.on_publish = None

    def save_copy(self, author, text):
        with self.lock:
            self.copies.append({"author": author, "text": text, "no": len(self.copies) + 1})
            no = len(self.copies)
        self.bus.emit("artifact", author, type="copy", no=no, text=text)
        return no

    def write_page(self, author, html, note):
        with self.lock:
            v = len(self.pages) + 1
            self.pages.append({"version": v, "author": author, "html": html, "note": note})
        self.bus.emit("artifact", author, type="page", version=v, html=html, note=note)
        return v

    def latest(self):
        with self.lock:
            return self.pages[-1] if self.pages else None

    def get(self, v):
        with self.lock:
            return next((p for p in self.pages if p["version"] == v), None)


def auto_check(html: str) -> dict:
    """사람 눈 대신 기계적으로 확인할 수 있는 것들."""
    text = re.sub(r"<style.*?</style>|<script.*?</script>", "", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
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


# ───────────────── 도구 (누가 쓰는지 알기 위해 에이전트별로 만든다) ─────────────────
def make_tools(ws: Workspace, owner: str) -> dict:
    def save_copy(text: str):
        no = ws.save_copy(owner, str(text))
        return f"카피 문서 #{no} 저장 완료 ({len(str(text))}자)."

    def write_page(html: str = "", note: str = ""):
        html = str(html or "").strip()
        if "<" not in html or len(html) < 200:
            return "오류: html 내용이 비었거나 너무 짧습니다. 완결된 HTML 문서를 넣으세요."
        v = ws.write_page(owner, html, str(note))
        return f"v{v} 저장 완료 ({len(html):,}자). 화면에 바로 표시됩니다."

    def view_page(version: int = 0):
        p = ws.get(int(version)) if version else ws.latest()
        if not p:
            return "아직 저장된 페이지가 없습니다."
        return {"version": p["version"], "작성자": p["author"], "메모": p["note"], "html": p["html"]}

    def check_page(version: int = 0):
        p = ws.get(int(version)) if version else ws.latest()
        if not p:
            return "아직 저장된 페이지가 없습니다."
        return {"version": p["version"], **auto_check(p["html"])}

    def publish(version: int, summary: str = ""):
        try:
            v = int(version)
        except (TypeError, ValueError):
            return "오류: version은 숫자여야 합니다."
        page = ws.get(v)
        if not page:
            return f"오류: v{v}가 없습니다. 현재 최신은 v{len(ws.pages)}입니다."
        if ws.on_publish:   # 게시 후 전송 (사람이 켜 둔 경우에만)
            try:
                msg = ws.on_publish(v, page["html"], str(summary))
                ws.bus.emit("telegram", owner, ok=True, text=msg, version=v)
            except Exception as exc:
                ws.bus.emit("telegram", owner, ok=False, text=str(exc)[:300], version=v)
        return f"v{v} 게시 완료. 업무 종료."

    return {
        "save_copy": Tool("save_copy", "문구(카피) 문서 저장 — 제목, 부제, 본문, 버튼 문구 등", {"text": "문구 전체"}, save_copy),
        "write_page": Tool("write_page", "HTML 페이지를 새 버전으로 저장 (화면에 바로 보임)",
                           {"html": "완결된 HTML 문서", "note": "이번 버전에서 한 일 한 줄"}, write_page),
        "view_page": Tool("view_page", "저장된 페이지의 HTML 보기 (version 생략 시 최신)", {"version": "버전 번호(선택)"},
                          view_page),
        "check_page": Tool("check_page", "페이지 자동 점검 (외부 링크, 모바일 설정, 글자 수 등)", {"version": "버전 번호(선택)"},
                           check_page),
        "publish": Tool("publish", "최종 버전을 게시 (게시하면 업무 종료)", {"version": "게시할 버전 번호", "summary": "한 줄 요약"},
                        publish, terminal=True),
    }


TEAM = {
    "기획": "요청을 해석해 기획안을 만들고, 최종 게시를 결정",
    "카피": "제목·본문·버튼 문구 작성",
    "디자인": "HTML 페이지 제작·수정",
    "검토": "완성된 페이지만 보고 품질 점검 (디자이너의 작업 과정은 모름)",
}


def build_team(bus, llm, model):
    """에이전트 4개: 각자 자기 일에 필요한 도구만, 각자 자기 기억."""
    ws = Workspace(bus)
    bus.workspace = ws
    pick = lambda owner, names: [make_tools(ws, owner)[n] for n in names]
    common = dict(colleagues=TEAM, llm=llm, model=model, bus=bus)
    return [
        Agent("기획", "📋", "웹페이지·포스터 제작팀의 기획 담당 AI 에이전트입니다.",
              "요청자의 목적에 맞는 결과물이 나오도록 방향을 잡고, 품질이 충분하면 게시한다.",
              pick("기획", ["publish"]),
              extra_rules="7. 요청을 받으면 기획안(목적, 대상, 꼭 들어갈 정보, 구성, 분위기)을 정리해 카피와 디자인에게 보냅니다.\n"
                          "   직접 문구를 쓰거나 페이지를 만들지 않습니다.\n"
                          "8. 검토가 승인을 알려 오면 그 버전을 publish 합니다. 수정이 두 번 넘게 반복되면 가장 나은 버전을 게시합니다.\n"
                          "9. '시스템'이 재촉하면 최신 버전을 게시합니다.\n",
              **common),
        Agent("카피", "✍️", "웹페이지·포스터 제작팀의 카피라이터 AI 에이전트입니다.",
              "짧고 분명한 문구로 핵심 정보와 분위기를 전달한다.",
              pick("카피", ["save_copy"]),
              extra_rules="7. 기획안을 받으면 문구(큰 제목, 부제, 핵심 정보 정리, 본문 2~3문장, 버튼/마감 문구)를 써서 save_copy 로 저장하고,\n"
                          "   문구 전체를 디자인에게 메시지로 보냅니다. 문구 수정 요청을 받으면 고쳐서 다시 보냅니다.\n",
              **common),
        Agent("디자인", "🎨", "웹페이지·포스터 제작팀의 디자이너 AI 에이전트입니다.",
              "문구와 정보가 한눈에 들어오는, 보기 좋은 HTML 페이지를 만든다.",
              pick("디자인", ["write_page"]),
              extra_rules="7. 기획안과 카피 문구를 둘 다 받은 뒤에 페이지를 만듭니다. 카피가 아직 안 왔으면 wait 합니다.\n"
                          "8. write_page 로 저장한 뒤 검토에게 'vN 검토 부탁드립니다'라고 메시지를 보냅니다.\n"
                          "9. 검토 의견을 받으면 반영해 새 버전을 저장하고 다시 검토를 요청합니다.\n" + HTML_RULES,
              **common),
        Agent("검토", "🔍", "웹페이지·포스터 제작팀의 검토 담당 AI 에이전트입니다. 디자이너가 어떻게 만들었는지는 모르고, 결과물만 봅니다.",
              "요청자 입장에서 결과물만 보고, 빠진 정보·읽기 어려운 부분·규칙 위반을 찾아낸다.",
              pick("검토", ["view_page", "check_page"]),
              extra_rules="7. 검토 요청을 받으면 view_page 와 check_page 로 확인합니다. 요청 원문은 기획에게 물어볼 수 있습니다.\n"
                          "8. 고칠 점이 있으면 구체적인 수정 사항을 최대 3개까지 디자인에게 보냅니다 (문구 문제는 카피에게).\n"
                          "9. 충분히 좋으면 기획에게 'vN 승인'이라고 보냅니다. 수정 요청은 최대 2번까지, 그다음 버전은 큰 문제가 없으면 승인합니다.\n",
              **common),
    ]


ENTRY = "기획"   # 요청이 처음 들어가는 에이전트
