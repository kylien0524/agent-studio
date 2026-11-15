"""
텔레그램 전송 — 완성한 포스터(HTML 파일 + 가능하면 미리보기 이미지)를 텔레그램으로 보낸다.
추가 설치 없이 파이썬 기본 기능(urllib)만 쓴다.

준비 (한 번만):
  1. 텔레그램에서 @BotFather 에게 /newbot → 봇 이름 정하기 → 토큰(123456:ABC...)을 받는다
  2. 만든 봇에게 아무 메시지나 한 번 보낸다 (봇이 나에게 말을 걸 수 있게)
  3. 앱 사이드바의 '내 chat_id 찾기' 버튼을 누르면 chat_id 가 나온다
     (단체방이면 봇을 방에 초대하고 방에서 메시지를 한 번 보낸 뒤 찾기)

미리보기 이미지는 playwright 가 설치되어 있을 때만 함께 보낸다 (없으면 HTML 파일만):
  pip install playwright && playwright install chromium
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid

API_BASE = os.environ.get("TELEGRAM_API_BASE", "https://api.telegram.org")


def _call(token: str, method: str, fields: dict | None = None, files: dict | None = None, timeout=30) -> dict:
    """텔레그램 Bot API 호출. files = {"document": (파일이름, bytes, MIME)}"""
    url = f"{API_BASE}/bot{token}/{method}"
    if files:
        boundary = uuid.uuid4().hex
        body = b""
        for k, v in (fields or {}).items():
            body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n").encode("utf-8")
        for k, (fname, data, mime) in files.items():
            body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{fname}\"\r\n"
                     f"Content-Type: {mime}\r\n\r\n").encode("utf-8") + data + b"\r\n"
        body += f"--{boundary}--\r\n".encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    else:
        req = urllib.request.Request(url, data=json.dumps(fields or {}).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            res = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            res = json.loads(e.read().decode("utf-8"))
        except Exception:
            raise RuntimeError(f"텔레그램 오류 HTTP {e.code}") from None
    if not res.get("ok"):
        raise RuntimeError(f"텔레그램 오류: {res.get('description', res)}")
    return res["result"]


def find_chat_ids(token: str) -> list[tuple[str, str]]:
    """봇에게 최근 메시지를 보낸 대화방 목록 [(chat_id, 이름)]."""
    seen = {}
    for u in _call(token, "getUpdates", {"limit": 50}):
        msg = u.get("message") or u.get("channel_post") or u.get("my_chat_member") or {}
        chat = msg.get("chat") or {}
        if "id" in chat:
            name = chat.get("title") or " ".join(x for x in (chat.get("first_name"), chat.get("last_name")) if x) \
                or chat.get("username") or "이름 없음"
            seen[str(chat["id"])] = name
    return list(seen.items())


def send_text(token: str, chat_id: str, text: str):
    return _call(token, "sendMessage", {"chat_id": chat_id, "text": text[:4000]})


def screenshot_html(html: str, width: int = 560) -> bytes | None:
    """HTML을 PNG 이미지로. playwright 가 없거나 실패하면 None (그러면 HTML 파일만 보낸다)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page(viewport={"width": width, "height": 300}, device_scale_factor=2)
            page.set_content(html, wait_until="load")
            png = page.screenshot(full_page=True)
            b.close()
            return png
    except Exception:
        return None


def send_poster(token: str, chat_id: str, html: str, caption: str, filename: str = "poster.html") -> str:
    """포스터를 보낸다: 미리보기 이미지(가능하면) + HTML 파일. 결과를 한 줄로 돌려준다."""
    caption = caption[:1000]
    sent = []
    png = screenshot_html(html)
    if png:
        _call(token, "sendPhoto", {"chat_id": chat_id, "caption": caption},
              {"photo": (filename.rsplit(".", 1)[0] + ".png", png, "image/png")})
        sent.append("미리보기 이미지")
    _call(token, "sendDocument", {"chat_id": chat_id, "caption": "" if png else caption},
          {"document": (filename, html.encode("utf-8"), "text/html")})
    sent.append("HTML 파일")
    return " + ".join(sent) + " 전송 완료"
