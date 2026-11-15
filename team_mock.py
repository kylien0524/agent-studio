"""
연습 모드(API 없이) 대본과 샘플 페이지. 실제 AI 모드에서는 쓰이지 않는다.
요청이 '사내 세미나 포스터' 예시일 때를 가정한 대본이다.
"""

TEAM_V1 = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI 업무 활용 세미나</title>
<style>
body{margin:0;background:#f4f4f4;font-family:"Malgun Gothic","Apple SD Gothic Neo",sans-serif;color:#333}
.wrap{max-width:640px;margin:24px auto;background:#fff;padding:40px 36px;border:1px solid #ddd}
h1{font-size:30px;margin:0 0 8px;color:#222}
.sub{color:#666;margin:0 0 24px}
p{line-height:1.8}
ul{line-height:1.9;padding-left:20px}
.foot{margin-top:32px;font-size:12px;color:#999;border-top:1px solid #eee;padding-top:12px}
</style></head><body><div class="wrap">
<h1>AI 업무 활용 세미나</h1>
<p class="sub">AI, 어렵지 않아요. 오늘부터 내 업무 비서로!</p>
<p>생성형 AI를 업무에 바로 써 볼 수 있는 실습형 세미나입니다. 12월 3일(수) 오후 3시부터 5시까지 본관 3층 대회의실에서 진행되며,
전 직원 누구나 참여할 수 있습니다(선착순 40명). AI가 처음인 분도 부담 없이 오세요.</p>
<ul><li>보고서 초안 쓰기</li><li>메일 정리하기</li><li>엑셀 데이터 정리하기</li></ul>
<p>노트북을 꼭 지참해 주세요.</p>
<div class="foot">신청: 11월 28일(금)까지 사내 게시판</div>
</div></body></html>"""

TEAM_V2 = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI 업무 활용 세미나</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#eef2f7;font-family:"Malgun Gothic","Apple SD Gothic Neo",sans-serif;color:#1d2433}
.poster{max-width:680px;margin:20px auto;background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 10px 30px rgba(20,40,80,.12)}
.hero{background:linear-gradient(135deg,#1e3a8a,#2563eb 60%,#38bdf8);color:#fff;padding:44px 36px 36px;position:relative}
.tag{display:inline-block;background:rgba(255,255,255,.18);padding:6px 12px;border-radius:999px;font-size:13px;letter-spacing:.04em}
.hero h1{font-size:40px;line-height:1.2;margin:16px 0 10px;letter-spacing:-.02em}
.hero p{margin:0;font-size:17px;opacity:.92}
.bot{position:absolute;right:28px;top:28px;font-size:56px}
.info{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:24px 28px 8px}
.card{background:#f5f8ff;border-radius:14px;padding:14px 16px}
.card .k{font-size:13px;color:#5b6b8c}
.card .v{font-size:18px;font-weight:700;margin-top:2px}
h2{font-size:18px;margin:22px 28px 10px}
.steps{display:grid;gap:10px;padding:0 28px}
.step{display:flex;gap:14px;align-items:center;border:1px solid #e3e8f2;border-radius:14px;padding:12px 16px}
.num{flex:none;width:34px;height:34px;border-radius:50%;background:#2563eb;color:#fff;display:grid;place-items:center;font-weight:700}
.deadline{margin:24px 28px 0;background:#fff7ed;border:2px solid #fb923c;border-radius:14px;padding:16px 18px;text-align:center}
.deadline b{display:block;font-size:22px;color:#c2410c}
.cta{display:block;margin:16px 28px 30px;background:#1e3a8a;color:#fff;text-align:center;padding:16px;border-radius:14px;font-size:18px;font-weight:700;text-decoration:none}
.note{text-align:center;color:#6b7280;font-size:13px;margin:-14px 0 26px}
@media (max-width:480px){.hero h1{font-size:30px}.bot{font-size:40px}.info{grid-template-columns:1fr}}
</style></head><body><div class="poster">
<div class="hero"><span class="tag">사내 실습 세미나</span><div class="bot">🤖</div>
<h1>AI, 오늘부터<br>내 업무 비서</h1><p>처음이어도 괜찮아요. 2시간이면 바로 써먹습니다.</p></div>
<div class="info">
<div class="card"><div class="k">📅 일시</div><div class="v">12월 3일(수) 15:00–17:00</div></div>
<div class="card"><div class="k">📍 장소</div><div class="v">본관 3층 대회의실</div></div>
<div class="card"><div class="k">👥 대상</div><div class="v">전 직원 · 선착순 40명</div></div>
<div class="card"><div class="k">💻 준비물</div><div class="v">노트북</div></div>
</div>
<h2>이런 걸 직접 해 봅니다</h2>
<div class="steps">
<div class="step"><div class="num">1</div><div><b>보고서 초안</b> — 메모 몇 줄로 초안 완성</div></div>
<div class="step"><div class="num">2</div><div><b>메일 정리</b> — 긴 메일 스레드를 3줄 요약</div></div>
<div class="step"><div class="num">3</div><div><b>엑셀 데이터 정리</b> — 지저분한 표를 한 번에 정돈</div></div>
</div>
<div class="deadline">신청 마감<b>11월 28일(금)까지</b>선착순 40명 · 자리가 차면 조기 마감</div>
<a class="cta" href="#">사내 게시판에서 신청하기 →</a>
<p class="note">문의: 교육 담당자</p>
</div></body></html>"""

BRIEF = ("기획안입니다. 목적: AI가 낯선 직원도 '가 볼까?' 하게 만드는 세미나 안내. 대상: 전 직원. "
         "꼭 들어갈 정보: 12/3(수) 15~17시, 본관 3층 대회의실, 선착순 40명, 노트북 지참, 실습 3가지, 11/28(금) 신청 마감. "
         "구성: 큰 제목 → 핵심 정보 → 실습 내용 → 마감·신청. 분위기: 친근하지만 업무용으로 깔끔하게.")
COPY = ("[큰 제목] AI, 오늘부터 내 업무 비서\n[부제] 처음이어도 괜찮아요. 2시간이면 바로 써먹습니다.\n"
        "[핵심 정보] 12월 3일(수) 15:00–17:00 · 본관 3층 대회의실 · 전 직원 선착순 40명 · 준비물: 노트북\n"
        "[실습] ① 보고서 초안 — 메모 몇 줄로 초안 완성 ② 메일 정리 — 긴 메일을 3줄 요약 ③ 엑셀 데이터 정리 — 지저분한 표를 한 번에\n"
        "[마감] 11월 28일(금)까지 사내 게시판에서 신청 · 자리가 차면 조기 마감\n[버튼] 사내 게시판에서 신청하기")
FEEDBACK = ("v1 검토 의견입니다. ① 신청 마감(11/28)이 맨 아래 작은 회색 글씨라 거의 안 보입니다 — 눈에 띄게 강조해 주세요. "
            "② 일시·장소가 본문 문장 속에 묻혀 있습니다 — 따로 한눈에 보이게 정리해 주세요. "
            "③ 카피의 큰 제목('AI, 오늘부터 내 업무 비서')이 부제로 밀려났습니다 — 큰 제목으로 올려 주세요.")


def _a(thought, action, **args):
    return {"thought": thought, "action": action, "args": args}


def team_policies():
    def plan(frm, content, agent, st):
        if frm == "요청자":
            return [_a("요청을 기획안으로 정리해 카피에게 먼저 보낸다.", "send_message", to="카피", content=BRIEF),
                    _a("디자인에게도 같은 기획안을 보낸다. 문구는 카피가 따로 보낼 것.", "send_message", to="디자인", content=BRIEF)]
        if frm == "검토" and "승인" in content or frm == "시스템":
            v = 2 if "v2" in content else 1
            return [_a(f"검토가 v{v}를 승인했다. 게시한다.", "publish", version=v, summary="AI 업무 활용 세미나 안내 포스터")]
        return []

    def copy(frm, content, agent, st):
        if frm == "기획":
            return [_a("기획안의 핵심 정보와 분위기를 살려 문구를 쓴다.", "save_copy", text=COPY),
                    _a("디자인이 바로 쓸 수 있게 문구 전체를 보낸다.", "send_message", to="디자인", content=COPY)]
        return []

    def design(frm, content, agent, st):
        if frm == "카피":
            return [_a("기획안과 카피가 다 왔다. 첫 버전을 만든다.", "write_page", html=TEAM_V1, note="첫 버전"),
                    _a("검토에게 확인을 부탁한다.", "send_message", to="검토", content="v1 검토 부탁드립니다.")]
        if frm == "검토" and "의견" in content:
            return [_a("마감 강조, 정보 카드, 큰 제목 교체 — 세 가지를 반영해 다시 만든다.", "write_page", html=TEAM_V2,
                       note="검토 의견 3개 반영: 마감 강조, 정보 카드, 큰 제목"),
                    _a("다시 검토를 요청한다.", "send_message", to="검토", content="v2 검토 부탁드립니다. 의견 3개 모두 반영했습니다.")]
        return []

    def review(frm, content, agent, st):
        if frm != "디자인":
            return []
        st["n"] = st.get("n", 0) + 1
        if st["n"] == 1:
            return [_a("디자이너가 어떻게 만들었는지는 모른다. 결과물만 열어 본다.", "view_page"),
                    _a("기계적으로 확인할 것도 돌려 본다.", "check_page"),
                    _a("마감이 거의 안 보이고 일시·장소가 문장 속에 묻혀 있다. 고칠 점을 보낸다.", "send_message",
                       to="디자인", content=FEEDBACK)]
        return [_a("v2를 열어 본다.", "view_page"), _a("자동 점검.", "check_page"),
                _a("세 가지 모두 해결됐다. 기획에게 승인을 알린다.", "send_message", to="기획",
                   content="v2 승인합니다. 마감·핵심 정보가 한눈에 보이고 규칙 위반도 없습니다.")]

    return {"기획": plan, "카피": copy, "디자인": design, "검토": review}
