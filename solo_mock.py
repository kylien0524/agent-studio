"""
연습 모드(API 없이) — 미리 써 둔 행동 대본과 샘플 페이지. 실제 AI 모드에서는 쓰이지 않는다.
'사내 세미나 포스터' 예시를 가정한 대본이라, 요청을 바꿔도 결과가 같다.
"""
import json
import random
import time

EXAMPLES = {
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

SOLO_V1 = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI 업무 활용 세미나</title>
<style>
body{margin:0;background:#f6f5fb;font-family:"Malgun Gothic","Apple SD Gothic Neo",sans-serif;color:#222}
.box{max-width:660px;margin:20px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 6px 20px rgba(0,0,0,.08)}
.top{background:linear-gradient(120deg,#7c3aed,#a855f7);color:#fff;padding:36px 32px}
.top h1{margin:0 0 8px;font-size:34px}
.top p{margin:0;opacity:.9}
.body{padding:24px 32px 32px}
table{width:100%;border-collapse:collapse;margin:8px 0 20px}
td{padding:10px 8px;border-bottom:1px solid #eee}
td:first-child{color:#7c3aed;font-weight:700;width:90px}
ul{line-height:1.9}
.small{color:#888;font-size:13px;margin-top:20px}
</style></head><body><div class="box">
<div class="top"><h1>🤖 AI 업무 활용 세미나</h1><p>AI가 처음이어도 부담 없이, 업무에 바로 써 보는 실습</p></div>
<div class="body">
<table>
<tr><td>일시</td><td>12월 3일(수) 오후 3시~5시</td></tr>
<tr><td>장소</td><td>본관 3층 대회의실</td></tr>
<tr><td>대상</td><td>전 직원 (선착순 40명)</td></tr>
<tr><td>준비물</td><td>노트북</td></tr>
</table>
<b>실습 내용</b>
<ul><li>보고서 초안 쓰기</li><li>메일 정리</li><li>엑셀 데이터 정리</li></ul>
<p class="small">신청은 11월 28일(금)까지 사내 게시판에서 해 주세요.</p>
</div></div></body></html>"""

COPY = ("[큰 제목] AI, 오늘부터 내 업무 비서\n[부제] 처음이어도 괜찮아요. 2시간이면 바로 써먹습니다.\n"
        "[핵심 정보] 12월 3일(수) 15:00–17:00 · 본관 3층 대회의실 · 전 직원 선착순 40명 · 준비물: 노트북\n"
        "[실습] ① 보고서 초안 — 메모 몇 줄로 초안 완성 ② 메일 정리 — 긴 메일을 3줄 요약 ③ 엑셀 데이터 정리 — 지저분한 표를 한 번에\n"
        "[마감] 11월 28일(금)까지 사내 게시판에서 신청 · 자리가 차면 조기 마감\n[버튼] 사내 게시판에서 신청하기")


def _a(thought, action, **args):
    return {"thought": thought, "action": action, "args": args}


SCRIPT = [
    _a("요청을 정리해 문구부터 쓴다.", "save_copy", text=COPY),
    _a("문구를 바탕으로 페이지를 만든다.", "write_page", html=SOLO_V1, note="첫 버전"),
    _a("내가 만든 걸 내가 다시 열어 본다.", "view_page"),
    _a("자동 점검도 돌린다.", "check_page"),
    _a("규칙 위반은 없다. 내가 보기엔 괜찮다. 게시한다.", "publish", version=1, summary="AI 업무 활용 세미나 안내 포스터"),
]


class MockSolo:
    """실제 AI 대신 SCRIPT 를 차례로 내놓는 가짜 두뇌 (생각하는 시간도 흉내)."""

    def __init__(self, delay=(0.6, 1.4)):
        self.i, self.delay = 0, delay

    def chat(self, *, model, system, messages):
        time.sleep(random.uniform(*self.delay))
        act = SCRIPT[min(self.i, len(SCRIPT) - 1)]
        self.i += 1
        return json.dumps(act, ensure_ascii=False)
