# 🧑‍🎨 1인 에이전트 스튜디오 (싱글 에이전트)

AI 에이전트 **한 명**이 기획·문구·디자인·검토·게시를 혼자 해서 웹페이지·포스터(HTML)를 만듭니다.
다른 폴더의 파일을 쓰지 않는 독립 프로그램입니다.

## 실행

```bash
pip install -r solo_requirements.txt
streamlit run solo_app.py
```
1. 사이드바: AI 선택(Gemini / Claude) → API 키 → (선택) 📋 모델 불러오기. 키 없이 화면만 보려면 **연습 모드**
2. 만들 것을 고르거나 직접 씀 → **▶ 만들기**
3. 왼쪽: 에이전트가 지금 쓰는 도구(그림), 생각과 행동 기록 / 오른쪽: 만들어지는 페이지
4. 끝나면 버전 넘겨 보기, HTML 저장, 에이전트의 정의(프롬프트)와 기억 전체 보기

터미널만으로: `python solo_agent.py --provider gemini` → `output/solo_v1.html` …

## 파일

| 파일 | 역할 |
|---|---|
| `solo_app.py` | 화면 (Streamlit) — **이걸 실행** |
| `solo_agent.py` | **에이전트 본체.** 프롬프트, 도구 5개, 생각→행동→결과 반복문 |
| `solo_llm.py` | AI 연결 (Gemini / Claude) |
| `solo_mock.py` | 연습 모드 대본·샘플 페이지, 예시 요청 |
| `solo_telegram.py` | 텔레그램 전송 (봇 토큰·chat_id, 미리보기 이미지) |
| `solo_requirements.txt` | 설치할 패키지 목록 |


## 📨 텔레그램 전송 (선택)

게시한 포스터를 텔레그램으로 보냅니다. **사이드바에서 사람이 켰을 때만** 보냅니다 (밖으로 보내는 일 = 안전장치 대상).

1. 텔레그램에서 **@BotFather** → `/newbot` → 봇 이름 정하기 → **토큰** 받기
2. 만든 봇에게 아무 메시지나 한 번 보내기 (단체방이면 봇을 방에 초대하고 방에서 한 번 말하기)
3. 앱 사이드바 **📨 텔레그램 전송**에 토큰 입력 → **내 chat_id 찾기** → 나온 번호를 chat_id 칸에 입력 → **테스트 전송**
4. **게시하면 자동으로 전송** 체크 → 만들기. 끝난 뒤 다른 버전은 결과물 아래 **📨 텔레그램으로 보내기** 버튼으로

- 보내는 것: HTML 파일(텔레그램에서 열면 브라우저로 보임) + 미리보기 이미지
- 미리보기 이미지는 playwright가 있을 때만 함께 갑니다 (없으면 HTML 파일만):
  `pip install playwright` 후 `playwright install chromium`
- 매번 입력하기 싫다면 `.streamlit/secrets.toml`에 `TELEGRAM_BOT_TOKEN = "..."`, `TELEGRAM_CHAT_ID = "..."`
- 봇 토큰은 비밀번호와 같습니다. 공유하지 마세요.

## 에이전트의 원리 (`solo_agent.py`의 `SoloAgent.run`)

```
요청을 기억에 넣는다
반복:
  ① 생각: AI에게 기억 전체를 보여 주고 "다음 행동은?" → {"thought", "action", "args"}
  ② 행동: 파이썬이 그 도구를 실제로 실행 (문구 저장, 페이지 저장, 점검, 게시…)
  ③ 기억: 실행 결과를 기억에 덧붙임 → 다시 ①
publish(게시)하면 끝
```
AI는 글자만 씁니다. 실제 일은 전부 도구(파이썬 함수)가 합니다.
혼자 일하므로 우편함·동료·스레드가 없고, **자기가 만든 결과물을 자기가 검토**합니다.

멀티에이전트 버전(제작팀)은 별도 프로그램 `agent-studio`입니다. 두 프로그램을 창 두 개에 띄우면 나란히 비교할 수 있습니다:
```bash
streamlit run solo_app.py --server.port 8501     # 싱글
streamlit run team_app.py --server.port 8502     # 멀티
```
