from __future__ import annotations

import secrets
import asyncio
import json
import urllib.request
import time
import hmac
import hashlib
from pathlib import Path
from typing import Annotated
import mimetypes
import re

import aiosqlite
from fastapi import Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from bot.config import Config
from bot.db.repo import Repo
from fastapi import APIRouter

from google_auth_oauthlib.flow import Flow


_security = HTTPBasic()


def _check_auth(cfg: Config, creds: HTTPBasicCredentials):
    u_ok = secrets.compare_digest(creds.username or "", cfg.admin_panel_user)
    p_ok = secrets.compare_digest(creds.password or "", cfg.admin_panel_pass)
    if not (u_ok and p_ok):
        raise HTTPException(status_code=401, detail="Unauthorized", headers={"WWW-Authenticate": "Basic"})


def _escape_textarea(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;")


def _escape_attr(s: str) -> str:
    return _escape_textarea(s).replace("'", "&#39;")


def _layout(cfg: Config, title: str, body: str, active: str) -> str:
    def _nav_item(label: str, href: str, key: str) -> str:
        cls = "nav-item nav-item--active" if key == active else "nav-item"
        return f"<a class='{cls}' href='{href}'>{label}</a>"

    nav = (
        "<nav class='nav'>"
        + _nav_item("Dashboard", "/admin", "dashboard")
        + _nav_item("Users", "/admin/users", "users")
        + _nav_item("Prices", "/admin/prices", "prices")
        + _nav_item("Gemini akkaunt", "/admin/accounts/gemini", "gemini")
        + _nav_item("ChatGPT Business", "/admin/accounts/chatgpt", "chatgpt")
        + _nav_item("ChatGPT Plus", "/admin/accounts/chatgpt_plus", "chatgpt_plus")
        + _nav_item("Spotify Premium", "/admin/accounts/spotify_premium", "spotify_premium")
        + _nav_item("YouTube Premium", "/admin/accounts/youtube_premium", "youtube_premium")
        + _nav_item("Super Grok", "/admin/accounts/super_grok", "super_grok")
        + _nav_item("Canva Pro", "/admin/accounts/canva_pro", "canva_pro")
        + _nav_item("CapCut Pro", "/admin/accounts/capcut_pro", "capcut_pro")
        + _nav_item("Orders", "/admin/orders", "orders")
        + _nav_item("Buyers", "/admin/buyers", "buyers")
        + _nav_item("Topups", "/admin/topups", "topups")
        + _nav_item("Purchases", "/admin/purchases", "purchases")
        + _nav_item("Referrals", "/admin/referrals", "referrals")
        + _nav_item("Broadcast", "/admin/broadcast", "broadcast")
        + _nav_item("Canva Pro Link", "/admin/canva_pro_link", "canva_pro_link")
        + _nav_item("Health", "/admin/health", "health")
        + "</nav>"
    )

    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>Admin</title>"
        "<style>"
        "body{font-family:system-ui,Segoe UI,Roboto,Arial;margin:0;background:#0b0c10;color:#e8e8e8}"
        ".wrap{max-width:1100px;margin:0 auto;padding:22px}"
        ".top{display:flex;justify-content:space-between;align-items:baseline;gap:16px}"
        ".title{margin:0;font-size:22px}"
        ".meta{opacity:.8;font-size:13px}"
        ".nav{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0 18px 0}"
        ".nav-item{padding:8px 10px;border:1px solid #222;border-radius:10px;color:#e8e8e8;text-decoration:none}"
        ".nav-item--active{background:#151821;border-color:#2a2f40}"
        ".panel{background:#0f1117;border:1px solid #1d2130;border-radius:14px;padding:16px}"
        ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}"
        ".card{background:#0b0c10;border:1px solid #202437;border-radius:14px;padding:14px}"
        ".num{font-size:26px;margin-top:6px}"
        ".table-wrap{overflow:auto}"
        "table{width:100%;border-collapse:collapse;font-size:13px}"
        "th,td{padding:10px 8px;border-bottom:1px solid #1d2130;text-align:left;vertical-align:top}"
        "th{font-size:12px;opacity:.85}"
        ".toolbar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:0 0 12px 0}"
        ".input{background:#0b0c10;border:1px solid #202437;border-radius:10px;padding:8px 10px;color:#e8e8e8}"
        ".textarea{min-height:110px;width:100%}"
        ".btn{background:#1f6feb;border:0;border-radius:10px;color:white;padding:8px 12px;cursor:pointer}"
        ".btn--ghost{background:transparent;border:1px solid #202437;color:#e8e8e8}"
        ".stack{display:flex;flex-direction:column;gap:12px}"
        "code{background:#0b0c10;border:1px solid #202437;border-radius:8px;padding:2px 6px}"
        "</style>"
        "</head><body><div class='wrap'>"
        "<div class='top'>"
        f"<h1 class='title'>{title}</h1>"
        f"<div class='meta'>{cfg.admin_panel_host}:{cfg.admin_panel_port}</div>"
        "</div>"
        f"{nav}"
        f"<section class='panel'>{body}</section>"
        "</div></body></html>"
    )


def create_youtube_oauth_router(cfg: Config, repo: Repo) -> APIRouter:
    router = APIRouter()

    def _parse_signed_state(st: str) -> tuple[int, str | None] | None:
        # Supported formats:
        # 1) user_id:ts:nonce:sig
        # 2) user_id:ts:nonce:verifier:sig
        try:
            parts = (st or "").split(":")
            if len(parts) not in (4, 5):
                return None
            uid = int(parts[0])
            ts = int(parts[1])
            nonce = parts[2]
            if uid <= 0 or not nonce:
                return None
            verifier = None
            if len(parts) == 4:
                sig = parts[3]
                payload = f"{uid}:{ts}:{nonce}"
            else:
                verifier = parts[3]
                sig = parts[4]
                payload = f"{uid}:{ts}:{nonce}:{verifier}"

            key = (cfg.youtube_oauth_client_secret or cfg.bot_token or "").encode("utf-8")
            exp_sig = hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()[:20]
            if not secrets.compare_digest(exp_sig, sig):
                return None
            if int(time.time()) - ts > 30 * 60:
                return None
            return uid, verifier
        except Exception:
            return None

    def _yt_oauth_enabled() -> bool:
        return bool(
            (cfg.youtube_oauth_client_id or "").strip()
            and (cfg.youtube_oauth_client_secret or "").strip()
            and (cfg.youtube_oauth_redirect_url or "").strip()
        )

    def _yt_flow(state: str | None = None) -> Flow:
        client_config = {
            "web": {
                "client_id": (cfg.youtube_oauth_client_id or "").strip(),
                "client_secret": (cfg.youtube_oauth_client_secret or "").strip(),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }
        flow = Flow.from_client_config(
            client_config,
            scopes=["https://www.googleapis.com/auth/youtube.upload"],
            redirect_uri=(cfg.youtube_oauth_redirect_url or "").strip(),
        )
        if state:
            flow.state = str(state)
        return flow

    @router.get("/oauth/youtube/start")
    async def yt_oauth_start(state: str):
        if not _yt_oauth_enabled():
            raise HTTPException(status_code=500, detail="YouTube OAuth is not configured")
        st = (state or "").strip()
        if not st:
            raise HTTPException(status_code=400, detail="Missing state")

        flow = _yt_flow(state=st)

        parsed = _parse_signed_state(st)
        if parsed and parsed[1]:
            try:
                flow.code_verifier = str(parsed[1])
            except Exception:
                pass
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=st,
        )
        return RedirectResponse(url=str(auth_url), status_code=302)

    @router.get("/oauth/youtube/callback", response_class=HTMLResponse)
    async def yt_oauth_callback(state: str | None = None, code: str | None = None, error: str | None = None):
        if error:
            body = (
                "<div style='font-family:system-ui;padding:22px'>"
                "<h2>Failed</h2>"
                + f"<div>Error: <code>{_escape_textarea(str(error))}</code></div>"
                + "<div style='margin-top:10px'>Botga qayting.</div>"
                + "</div>"
            )
            return body

        st = (state or "").strip()
        if not st or not code:
            raise HTTPException(status_code=400, detail="Missing state/code")

        user_id = await repo.yt_oauth_consume_state(st)

        parsed = _parse_signed_state(st)
        verifier = parsed[1] if parsed else None
        if not user_id and parsed:
            user_id = parsed[0]

        if not user_id:
            body = (
                "<div style='font-family:system-ui;padding:22px'>"
                "<h2>Expired</h2>"
                "<div>State eskirgan yoki noto'g'ri. Botdan qaytadan ulab ko'ring.</div>"
                "</div>"
            )
            return body

        if not _yt_oauth_enabled():
            raise HTTPException(status_code=500, detail="YouTube OAuth is not configured")

        flow = _yt_flow(state=st)
        if verifier:
            try:
                flow.code_verifier = str(verifier)
            except Exception:
                pass
        try:
            await asyncio.to_thread(flow.fetch_token, code=code)
        except Exception as e:
            body = (
                "<div style='font-family:system-ui;padding:22px'>"
                "<h2>Failed</h2>"
                + f"<div>Token error: <code>{_escape_textarea(str(e))}</code></div>"
                + "</div>"
            )
            return body

        creds = flow.credentials
        await repo.yt_set_token(int(user_id), creds.to_json())
        body = (
            "<div style='font-family:system-ui;padding:22px'>"
            "<h2>Connected</h2>"
            "<div>Endi botga qaytib video yuklashingiz mumkin.</div>"
            "</div>"
        )
        return body

    return router


def create_admin_app(cfg: Config, repo: Repo) -> APIRouter:
    router = APIRouter()

    async def _notify_user_balance_changed(user_id: int, money_delta: int, points_delta: int):
        token = (cfg.bot_token or "").strip()
        if not token:
            return
        if int(money_delta) == 0 and int(points_delta) == 0:
            return

        def _fmt(n: int) -> str:
            sign = "+" if int(n) > 0 else ""
            return f"{sign}{int(n):,}".replace(",", " ")

        parts: list[str] = []
        if int(money_delta) != 0:
            parts.append(f"💳 Balans: <b>{_fmt(int(money_delta))}</b> so'm")
        if int(points_delta) != 0:
            parts.append(f"🎁 Ball: <b>{_fmt(int(points_delta))}</b>")
        text = "✅ Admin hisobingizni yangiladi.\n\n" + "\n".join(parts)

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": int(user_id),
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        def _send():
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as _:
                return

        try:
            await asyncio.to_thread(_send)
        except Exception:
            return

    return router


def create_admin_app(cfg: Config, repo: Repo) -> APIRouter:
    router = APIRouter()

    async def _notify_user_balance_changed(user_id: int, money_delta: int, points_delta: int):
        token = (cfg.bot_token or "").strip()
        if not token:
            return
        if int(money_delta) == 0 and int(points_delta) == 0:
            return

        def _fmt(n: int) -> str:
            sign = "+" if int(n) > 0 else ""
            return f"{sign}{int(n):,}".replace(",", " ")

        parts: list[str] = []
        if int(money_delta) != 0:
            parts.append(f"💳 Balans: <b>{_fmt(int(money_delta))}</b> so'm")
        if int(points_delta) != 0:
            parts.append(f"🎁 Ball: <b>{_fmt(int(points_delta))}</b>")
        text = "✅ Admin hisobingizni yangiladi.\n\n" + "\n".join(parts)

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": int(user_id),
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        def _send():
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as _:
                return

        try:
            await asyncio.to_thread(_send)
        except Exception:
            return

    async def _auth(creds: Annotated[HTTPBasicCredentials, Depends(_security)]):
        _check_auth(cfg, creds)
        return creds

    def _fmt_money(n: int) -> str:
        return f"{int(n):,}".replace(",", " ")

    @router.get("/canva_pro_link", response_class=HTMLResponse)
    async def admin_canva_pro_link(credentials: HTTPBasicCredentials = Depends(_auth)):
        link, _ = await repo.admin_get_texts("canva_pro_link")
        body = (
            "<div class='stack'>"
            "<div class='field'><b>Canva Pro Link</b>"
            "<div class='meta'>Bu yerga bitta link saqlaysiz. Botda Canva Pro Link sotib olganlarga shu link ko‘rsatiladi.</div>"
            "</div>"
            "<form method='post' action='/admin/canva_pro_link' class='stack'>"
            "<textarea class='input textarea' name='link' placeholder='https://...' >"
            + _escape_textarea(str(link or ""))
            + "</textarea>"
            "<div><button class='btn' type='submit'>Saqlash</button></div>"
            "</form>"
            "</div>"
        )
        return _layout(cfg, "Canva Pro Link", body, active="canva_pro_link")

    @router.post("/canva_pro_link")
    async def admin_canva_pro_link_save(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        link: str = Form(""),
    ):
        await repo.admin_set_texts("canva_pro_link", save_text=str(link or ""), send_text="")
        return RedirectResponse(url="/admin/canva_pro_link", status_code=303)

    def _tg_api_url(path: str) -> str:
        token = cfg.bot_token
        return f"https://api.telegram.org/bot{token}/{path.lstrip('/')}"

    def _tg_file_url(file_path: str) -> str:
        token = cfg.bot_token
        return f"https://api.telegram.org/file/bot{token}/{file_path.lstrip('/')}"

    def _tg_send_message(chat_id: int, text: str):
        payload = json.dumps({"chat_id": int(chat_id), "text": str(text), "parse_mode": "HTML"}).encode("utf-8")
        req = urllib.request.Request(
            _tg_api_url("sendMessage"),
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as _:
            return

    def _tg_send_photo(chat_id: int, photo_bytes: bytes, filename: str, caption: str | None = None):
        boundary = "----tgform" + secrets.token_hex(16)

        def _part(name: str, value: str) -> bytes:
            return (
                f"--{boundary}\r\n"
                f"Content-Disposition: form-data; name=\"{name}\"\r\n\r\n"
                f"{value}\r\n"
            ).encode("utf-8")

        mime = mimetypes.guess_type(filename or "photo.jpg")[0] or "application/octet-stream"
        file_header = (
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data; name=\"photo\"; filename=\"{filename or 'photo.jpg'}\"\r\n"
            f"Content-Type: {mime}\r\n\r\n"
        ).encode("utf-8")
        end = f"\r\n--{boundary}--\r\n".encode("utf-8")

        body = b"".join(
            [
                _part("chat_id", str(int(chat_id))),
                _part("parse_mode", "HTML"),
                _part("caption", str(caption or "")),
                file_header,
                photo_bytes,
                end,
            ]
        )

        req = urllib.request.Request(
            _tg_api_url("sendPhoto"),
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as _:
            return

    @router.get("/", response_class=HTMLResponse)
    async def admin_home(credentials: HTTPBasicCredentials = Depends(_auth)):
        stats = await repo.get_admin_stats()
        body = (
            "<div class='grid'>"
            f"<div class='card'><b>Users</b><div class='num'>{stats['users']}</div></div>"
            f"<div class='card'><b>Orders</b><div class='num'>{stats['orders']}</div></div>"
            f"<div class='card'><b>Topups</b><div class='num'>{stats['topups']}</div></div>"
            f"<div class='card'><b>Paid topups</b><div class='num'>{stats['paid_topups']}</div></div>"
            "</div>"
        )
        return _layout(cfg, "Admin Dashboard", body, active="dashboard")

    @router.get("/users", response_class=HTMLResponse)
    async def admin_users(
        credentials: HTTPBasicCredentials = Depends(_auth),
        q: str | None = None,
    ):
        rows = await repo.admin_list_users(q=q, limit=200)

        q_val = (q or "").replace("\"", "&quot;")
        body = (
            "<form method='get' class='toolbar'>"
            f"<input class='input' name='q' placeholder='Search: id, username, name' value=\"{q_val}\">"
            "<button class='btn' type='submit'>Search</button>"
            "</form>"
            "<div class='table-wrap'>"
            "<table>"
            "<thead><tr>"
            "<th>ID</th>"
            "<th>Username</th>"
            "<th>Status</th>"
            "<th>Money (so'm)</th>"
            "<th>Points</th>"
            "<th>Update</th>"
            "<th>Block</th>"
            "</tr></thead><tbody>"
        )

        for r in rows:
            blocked_val = 0
            try:
                blocked_val = int(r["blocked"] or 0)
            except Exception:
                blocked_val = 0

            is_blocked = blocked_val == 1
            status_label = "Blocked" if is_blocked else "Active"
            block_btn = "Unblock" if is_blocked else "Block"
            block_action = "/admin/users/unblock" if is_blocked else "/admin/users/block"
            body += (
                "<tr>"
                f"<td><code>{int(r['id'])}</code></td>"
                f"<td>{(r['username'] or '')}</td>"
                f"<td><code>{status_label}</code></td>"
                f"<td>{_fmt_money(int(r['money_uzs'] or 0))}</td>"
                f"<td>{int(r['points'] or 0)}</td>"
                "<td>"
                "<form method='post' action='/admin/users/update' class='rowform'>"
                f"<input type='hidden' name='user_id' value='{int(r['id'])}'>"
                "<input class='input' name='money_delta' placeholder='money +/-' style='width:120px'>"
                "<input class='input' name='points_delta' placeholder='points +/-' style='width:120px'>"
                "<button class='btn' type='submit'>Apply</button>"
                "</form>"
                "</td>"
                "<td>"
                f"<form method='post' action='{block_action}' class='rowform'>"
                f"<input type='hidden' name='user_id' value='{int(r['id'])}'>"
                f"<button class='btn' type='submit' style='border-color:rgba(248,113,113,.65);background:rgba(248,113,113,.12)'>{block_btn}</button>"
                "</form>"
                "</td>"
                "</tr>"
            )

        body += "</tbody></table></div>"
        return _layout(cfg, "Users & Balances", body, active="users")

    @router.get("/prices", response_class=HTMLResponse)
    async def admin_prices(credentials: HTTPBasicCredentials = Depends(_auth)):
        from bot.services.pricing import PRICING

        rows = await repo.admin_list_plan_prices()
        label_rows = await repo.admin_list_plan_labels()
        overrides: dict[str, dict[str, int]] = {}
        for r in rows:
            pk = str(r.get("product_key") or "")
            pl = str(r.get("plan_key") or "")
            pv = int(r.get("price_uzs") or 0)
            if pk and pl:
                overrides.setdefault(pk, {})[pl] = pv

        label_overrides: dict[str, dict[str, str]] = {}
        for r in label_rows:
            pk = str(r.get("product_key") or "")
            pl = str(r.get("plan_key") or "")
            lv = str(r.get("label") or "")
            if pk and pl and lv.strip():
                label_overrides.setdefault(pk, {})[pl] = lv

        body = "<div class='stack'>"
        body += "<div class='meta'>Set plan prices. Leave empty to keep default price.</div>"

        for product_key, product in PRICING.items():
            title = str((product or {}).get("title") or product_key)
            plans = (product or {}).get("plans") or {}
            if not plans:
                continue

            body += "<div class='card'>"
            body += f"<div style='font-weight:700;margin-bottom:8px'>{title} <span class='meta'>(key: <code>{product_key}</code>)</span></div>"
            body += "<form method='post' action='/admin/prices/set' class='rowform'>"
            body += f"<input type='hidden' name='product_key' value='{_escape_attr(str(product_key))}'>"

            for plan_key, p in plans.items():
                default_price = int((p or {}).get("price_uzs") or 0)
                cur_val = overrides.get(str(product_key), {}).get(str(plan_key))
                show_val = "" if cur_val is None else str(int(cur_val))
                default_label = str((p or {}).get("label") or "")
                cur_label = label_overrides.get(str(product_key), {}).get(str(plan_key))
                show_label = "" if cur_label is None else str(cur_label)
                body += "<div class='field' style='min-width:220px'>"
                body += f"<b>Plan <code>{_escape_attr(str(plan_key))}</code></b>"
                body += f"<input class='input' name='price_{_escape_attr(str(plan_key))}' placeholder='default: {_fmt_money(default_price)}' value='{_escape_attr(show_val)}' style='width:180px'>"
                body += f"<input class='input' name='label_{_escape_attr(str(plan_key))}' placeholder='label: {_escape_attr(default_label)}' value='{_escape_attr(show_label)}' style='width:180px;margin-top:6px'>"
                body += "</div>"

            body += "<div style='align-self:flex-end'><button class='btn' type='submit'>Save</button></div>"
            body += "</form>"
            body += "</div>"

        body += "</div>"
        return _layout(cfg, "Prices", body, active="prices")

    @router.post("/prices/set")
    async def admin_prices_set(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        product_key: str = Form(...),
    ):
        from bot.services.pricing import PRICING

        form = await request.form()
        product = PRICING.get(str(product_key)) or {}
        plans = (product or {}).get("plans") or {}

        for plan_key in plans.keys():
            field = f"price_{plan_key}"
            raw = str(form.get(field) or "").strip()
            if raw == "":
                continue
            try:
                val = int(raw)
            except Exception:
                continue
            if val <= 0:
                continue
            await repo.admin_set_plan_price(product_key=str(product_key), plan_key=str(plan_key), price_uzs=int(val))

        for plan_key in plans.keys():
            field = f"label_{plan_key}"
            raw = str(form.get(field) or "").strip()
            if raw == "":
                continue
            await repo.admin_set_plan_label(product_key=str(product_key), plan_key=str(plan_key), label=str(raw))

        return RedirectResponse(url=str(request.headers.get("referer") or "/admin/prices"), status_code=303)

    @router.post("/users/update")
    async def admin_users_update(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        user_id: int = Form(...),
        money_delta: str = Form(""),
        points_delta: str = Form(""),
    ):
        def _parse_int(s: str) -> int:
            s = (s or "").strip()
            if s == "":
                return 0
            return int(s)

        m_delta = _parse_int(money_delta)
        p_delta = _parse_int(points_delta)

        await repo.admin_apply_balance_delta(
            user_id=user_id,
            money_delta=m_delta,
            points_delta=p_delta,
        )
        await _notify_user_balance_changed(user_id=user_id, money_delta=m_delta, points_delta=p_delta)
        return RedirectResponse(url=str(request.headers.get("referer") or "/admin/users"), status_code=303)

    @router.post("/users/delete")
    async def admin_users_delete(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        user_id: int = Form(...),
    ):
        await repo.admin_delete_user(user_id=user_id)
        return RedirectResponse(url=str(request.headers.get("referer") or "/admin/users"), status_code=303)

    @router.post("/users/block")
    async def admin_users_block(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        user_id: int = Form(...),
    ):
        await repo.admin_set_user_blocked(user_id=user_id, blocked=True)
        return RedirectResponse(url=str(request.headers.get("referer") or "/admin/users"), status_code=303)

    @router.post("/users/unblock")
    async def admin_users_unblock(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        user_id: int = Form(...),
    ):
        await repo.admin_set_user_blocked(user_id=user_id, blocked=False)
        return RedirectResponse(url=str(request.headers.get("referer") or "/admin/users"), status_code=303)

    @router.get("/orders", response_class=HTMLResponse)
    async def admin_orders(
        credentials: HTTPBasicCredentials = Depends(_auth),
        status: str | None = None,
        pay_type: str | None = None,
        limit: int = 200,
    ):
        pay_type = (pay_type or "money").strip() or "money"
        if pay_type not in ("money", "points"):
            pay_type = "money"

        rows = await repo.admin_list_orders(
            status=status,
            pay_type=pay_type,
            limit=min(max(limit, 1), 500),
        )

        def _opt(label: str, v: str | None):
            sel = " selected" if v == status else ""
            return f"<option value='{v or ''}'{sel}>{label}</option>"

        def _tab(label: str, v: str) -> str:
            cls = "btn" if v == pay_type else "btn btn--ghost"
            href = f"/admin/orders?pay_type={v}&status={_escape_attr(str(status or ''))}&limit={int(limit)}"
            return f"<a class='{cls}' href='{href}' style='text-decoration:none'>" + label + "</a>"

        body = "".join(
            [
                "<div class='rowform' style='justify-content:flex-start;margin-bottom:10px'>",
                _tab("Pul bilan", "money"),
                _tab("Referal (ball)", "points"),
                "</div>",
                "<form method='get' class='toolbar'>",
                f"<input type='hidden' name='pay_type' value='{_escape_attr(str(pay_type))}'>",
                "<span class='meta'>Status</span>",
                "<select class='select' name='status'>",
                _opt("All", None),
                _opt("new", "new"),
                _opt("paid", "paid"),
                _opt("delivered", "delivered"),
                _opt("cancelled", "cancelled"),
                "</select>",
                "<span class='meta'>Limit</span>",
                f"<input class='input' name='limit' value='{int(limit)}' style='width:90px'>",
                "<button class='btn' type='submit'>Apply</button>",
                "</form>",
                "<div class='table-wrap'>",
                "<table>",
                "<thead><tr>",
                "<th>ID</th>",
                "<th>User</th>",
                "<th>Product</th>",
                "<th>Plan</th>",
                ("<th>Price</th>" if pay_type == "money" else "<th>Points</th>"),
                "<th>Status</th>",
                "<th>Update</th>",
                "</tr></thead><tbody>",
            ]
        )

        for r in rows:
            price_cell = (
                f"<td>{_fmt_money(int(r['price_uzs'] or 0))}</td>"
                if pay_type == "money"
                else f"<td>{int(r['points_cost'] or 0)}</td>"
            )

            try:
                username = str(r["username"] or "")
            except Exception:
                username = ""
            try:
                full_name = str(r["full_name"] or "")
            except Exception:
                full_name = ""
            user_cell = f"<code>{int(r['user_id'])}</code>"
            if username:
                u = username
                if not u.startswith("@"):  # keep consistent display
                    u = "@" + u
                user_cell += f"<div class='meta'>{_escape_textarea(u)}</div>"
            elif full_name:
                user_cell += f"<div class='meta'>{_escape_textarea(full_name)}</div>"
            body += "".join(
                [
                    "<tr>",
                    f"<td><code>{int(r['id'])}</code></td>",
                    f"<td>{user_cell}</td>",
                    f"<td>{r['product_key']}</td>",
                    f"<td>{r['plan_key']}</td>",
                    price_cell,
                    f"<td>{r['status']}</td>",
                    "<td>",
                    "<form method='post' action='/admin/orders/update' class='rowform'>",
                    f"<input type='hidden' name='order_id' value='{int(r['id'])}'>",
                    "<select class='select' name='status'>",
                    "<option value='new'>new</option>",
                    "<option value='paid'>paid</option>",
                    "<option value='delivered'>delivered</option>",
                    "<option value='cancelled'>cancelled</option>",
                    "</select>",
                    "<button class='btn' type='submit'>Set</button>",
                    "</form>",
                    "</td>",
                    "</tr>",
                ]
            )

        body += "</tbody></table></div>"
        return _layout(cfg, "Orders", body, active="orders")

    @router.get("/referrals", response_class=HTMLResponse)
    async def admin_referrals(
        credentials: HTTPBasicCredentials = Depends(_auth),
        limit: int = 50,
    ):
        rows = await repo.admin_referral_top(limit=min(max(int(limit), 1), 200))

        body = (
            "<form method='get' class='toolbar'>"
            "<span class='meta'>Limit</span>"
            f"<input class='input' name='limit' value='{limit}' style='width:90px'>"
            "<button class='btn' type='submit'>Apply</button>"
            "</form>"
            "<div class='table-wrap'>"
            "<table>"
            "<thead><tr>"
            "<th>User</th>"
            "<th>Name</th>"
            "<th>Username</th>"
            "<th>Invited</th>"
            "<th>Rewarded</th>"
            "<th>Total bonus (so'm)</th>"
            "</tr></thead><tbody>"
        )

        for r in rows:
            body += (
                "<tr>"
                f"<td><code>{int(r['referrer_id'])}</code></td>"
                f"<td>{(r['full_name'] or '')}</td>"
                f"<td>{(r['username'] or '')}</td>"
                f"<td>{int(r['invited'] or 0)}</td>"
                f"<td>{int(r['rewarded_count'] or 0)}</td>"
                f"<td>{_fmt_money(int(r['total_bonus_uzs'] or 0))}</td>"
                "</tr>"
            )

        body += "</tbody></table></div>"
        return _layout(cfg, "Referrals", body, active="referrals")

    @router.post("/orders/update")
    async def admin_orders_update(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        order_id: int = Form(...),
        status: str = Form(...),
    ):
        await repo.admin_set_order_status(order_id=order_id, status=status)
        return RedirectResponse(url=str(request.headers.get("referer") or "/admin/orders"), status_code=303)

    @router.get("/topups", response_class=HTMLResponse)
    async def admin_topups(
        credentials: HTTPBasicCredentials = Depends(_auth),
        status: str | None = None,
        limit: int = 200,
    ):
        status = "pending" if status is None else str(status)
        status_for_query: str | None = None if status == "" else status
        rows = await repo.admin_list_topups(status=status_for_query, limit=min(max(limit, 1), 500))

        def _opt(label: str, v: str | None):
            sel = " selected" if v == status else ""
            return f"<option value='{v or ''}'{sel}>{label}</option>"

        body = (
            "<form method='get' class='toolbar'>"
            "<span class='meta'>Status</span>"
            "<select class='select' name='status'>"
            + _opt("All", "")
            + _opt("pending", "pending")
            + _opt("paid", "paid")
            + _opt("failed", "failed")
            + _opt("cancelled", "cancelled")
            + "</select>"
            "<span class='meta'>Limit</span>"
            f"<input class='input' name='limit' value='{limit}' style='width:90px'>"
            "<button class='btn' type='submit'>Apply</button>"
            "</form>"
            "<div class='table-wrap'>"
            "<table>"
            "<thead><tr>"
            "<th>ID</th>"
            "<th>User</th>"
            "<th>Provider</th>"
            "<th>Amount</th>"
            "<th>Status</th>"
            "<th>Proof</th>"
            "<th>Update</th>"
            "<th>Delete</th>"
            "</tr></thead><tbody>"
        )

        for r in rows:
            proof = ""
            has_proof = bool(r["proof_file_id"])
            if has_proof:
                proof = (
                    f"{(r['proof_type'] or '')}: <code>{_escape_attr(str(r['proof_file_id'] or ''))}</code> "
                    f"<a class='btn' href='/admin/topups/proof/{int(r['id'])}' style='padding:6px 10px;border-radius:10px'>Download</a>"
                )

            username = ""
            full_name = ""
            try:
                username = str(r["username"] or "")
                full_name = str(r["full_name"] or "")
            except Exception:
                username = ""
                full_name = ""
            user_label = f"<code>{int(r['user_id'])}</code>"
            if username:
                user_label += f"<br><span class='meta'>@{_escape_textarea(username)}</span>"
            if full_name:
                user_label += f"<br><span class='meta'>{_escape_textarea(full_name)}</span>"
            body += (
                "<tr>"
                f"<td><code>{int(r['id'])}</code></td>"
                f"<td>{user_label}</td>"
                f"<td>{r['provider']}</td>"
                f"<td>{_fmt_money(int(r['amount_uzs']))}</td>"
                f"<td>{r['status']}</td>"
                f"<td>{proof}</td>"
                "<td>"
                "<form method='post' action='/admin/topups/update' class='rowform'>"
                f"<input type='hidden' name='topup_id' value='{int(r['id'])}'>"
                "<select class='select' name='status'>"
                "<option value='pending'>pending</option>"
                "<option value='paid'>paid</option>"
                "<option value='failed'>failed</option>"
                "<option value='cancelled'>cancelled</option>"
                "</select>"
                "<button class='btn' type='submit'>Set</button>"
                "</form>"
                "</td>"
                "<td>"
                "<form method='post' action='/admin/topups/delete' class='rowform'>"
                f"<input type='hidden' name='topup_id' value='{int(r['id'])}'>"
                "<button class='btn' type='submit' onclick=\"return confirm('Topup o\'chirilsinmi?')\" style='border-color:rgba(248,113,113,.65);background:rgba(248,113,113,.12)'>Delete</button>"
                "</form>"
                "</td>"
                "</tr>"
            )

        body += "</tbody></table></div>"
        return _layout(cfg, "Topups", body, active="topups")

    @router.get("/buyers", response_class=HTMLResponse)
    async def admin_buyers(
        credentials: HTTPBasicCredentials = Depends(_auth),
        limit: int = 200,
    ):
        rows = await repo.admin_list_paid_topups(limit=min(max(limit, 1), 500))
        body = (
            "<form method='get' class='toolbar'>"
            "<span class='meta'>Limit</span>"
            f"<input class='input' name='limit' value='{limit}' style='width:90px'>"
            "<button class='btn' type='submit'>Apply</button>"
            "</form>"
            "<div class='table-wrap'>"
            "<table>"
            "<thead><tr>"
            "<th>ID</th>"
            "<th>User</th>"
            "<th>Name</th>"
            "<th>Username</th>"
            "<th>Provider</th>"
            "<th>Amount</th>"
            "<th>Paid at</th>"
            "</tr></thead><tbody>"
        )

        for r in rows:
            body += (
                "<tr>"
                f"<td><code>{int(r['id'])}</code></td>"
                f"<td><code>{int(r['user_id'])}</code></td>"
                f"<td>{(r['full_name'] or '')}</td>"
                f"<td>{(r['username'] or '')}</td>"
                f"<td>{(r['provider'] or '')}</td>"
                f"<td>{_fmt_money(int(r['amount_uzs'] or 0))}</td>"
                f"<td>{(r['created_at'] or '')}</td>"
                "</tr>"
            )

        body += "</tbody></table></div>"
        return _layout(cfg, "Hisob To`ldirganlar", body, active="buyers")

    @router.get("/topups/proof/{topup_id}")
    async def admin_topup_proof_download(
        topup_id: int,
        credentials: HTTPBasicCredentials = Depends(_auth),
    ):
        row = await repo.admin_get_topup(topup_id=topup_id)
        if not row or not row["proof_file_id"]:
            raise HTTPException(status_code=404, detail="Proof not found")

        file_id = str(row["proof_file_id"])

        def _fetch() -> tuple[bytes, str]:
            with urllib.request.urlopen(_tg_api_url(f"getFile?file_id={file_id}"), timeout=15) as resp:
                meta = json.loads(resp.read().decode("utf-8"))
            file_path = (meta.get("result") or {}).get("file_path")
            if not file_path:
                raise RuntimeError("No file_path")

            with urllib.request.urlopen(_tg_file_url(str(file_path)), timeout=30) as fresp:
                data = fresp.read()

            filename = Path(str(file_path)).name or f"topup_{topup_id}"
            return data, filename

        try:
            data, filename = await asyncio.to_thread(_fetch)
        except Exception:
            raise HTTPException(status_code=502, detail="Failed to download from Telegram")

        return StreamingResponse(
            iter([data]),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename=\"{filename}\""},
        )

    @router.get("/purchases", response_class=HTMLResponse)
    async def admin_purchases(
        credentials: HTTPBasicCredentials = Depends(_auth),
        limit: int = 200,
    ):
        rows = await repo.admin_list_purchases(limit=min(max(limit, 1), 500))
        body = (
            "<form method='get' class='toolbar'>"
            "<span class='meta'>Limit</span>"
            f"<input class='input' name='limit' value='{limit}' style='width:90px'>"
            "<button class='btn' type='submit'>Apply</button>"
            "</form>"
            "<div class='table-wrap'>"
            "<table>"
            "<thead><tr>"
            "<th>Order</th>"
            "<th>User</th>"
            "<th>Product</th>"
            "<th>Plan</th>"
            "<th>Price</th>"
            "<th>Status</th>"
            "<th>Login</th>"
            "<th>Parol</th>"
            "<th>Assigned</th>"
            "</tr></thead><tbody>"
        )

        for r in rows:
            uname = ""
            try:
                uname = str(r["username"] or "").strip()
            except Exception:
                uname = ""
            if uname and not uname.startswith("@"): 
                uname = "@" + uname
            body += (
                "<tr>"
                f"<td><code>{int(r['order_id'])}</code></td>"
                f"<td><code>{int(r['user_id'])}</code>" + (f"<div class='meta'>{_escape_textarea(uname)}</div>" if uname else "") + "</td>"
                f"<td>{r['product_key']}</td>"
                f"<td>{r['plan_key']}</td>"
                f"<td>{_fmt_money(int(r['price_uzs']))}</td>"
                f"<td>{r['status']}</td>"
                f"<td>{(r['account_login'] or '')}</td>"
                f"<td>{(r['account_password'] or '')}</td>"
                f"<td>{(r['assigned_at'] or '')}</td>"
                "</tr>"
            )

        body += "</tbody></table></div>"
        return _layout(cfg, "Purchases", body, active="purchases")

    @router.post("/topups/update")
    async def admin_topups_update(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        topup_id: int = Form(...),
        status: str = Form(...),
    ):
        before = await repo.admin_get_topup(topup_id=topup_id)
        prev_status = "" if not before else str(before["status"] or "")
        user_id = None if not before else int(before["user_id"])
        amount_uzs = 0 if not before else int(before["amount_uzs"] or 0)

        await repo.admin_set_topup_status(topup_id=topup_id, status=status)

        if before and prev_status != status and user_id:
            try:
                if status == "paid":
                    msg = (
                        "✅ <b>Hisob to‘ldirish tasdiqlandi</b>\n\n"
                        f"Topup ID: <code>{int(topup_id)}</code>\n"
                        f"Summa: <b>{_fmt_money(int(amount_uzs))} so'm</b>\n\n"
                        "Pul hisobingizga qo‘shildi."
                    )
                elif status == "failed":
                    msg = (
                        "❌ <b>Hisob to‘ldirish rad etildi</b>\n\n"
                        f"Topup ID: <code>{int(topup_id)}</code>\n"
                        f"Summa: <b>{_fmt_money(int(amount_uzs))} so'm</b>\n\n"
                        "Pul hisobingizga qo‘shilmadi."
                    )
                elif status == "cancelled":
                    msg = (
                        "⚠️ <b>Hisob to‘ldirish bekor qilindi</b>\n\n"
                        f"Topup ID: <code>{int(topup_id)}</code>\n"
                        f"Summa: <b>{_fmt_money(int(amount_uzs))} so'm</b>\n\n"
                        "Pul hisobingizga qo‘shilmadi."
                    )
                else:
                    msg = ""

                if msg:
                    await asyncio.to_thread(_tg_send_message, user_id, msg)
            except Exception:
                pass
        if status == "paid":
            return RedirectResponse(url="/admin/buyers", status_code=303)
        if status != "pending":
            return RedirectResponse(url="/admin/topups", status_code=303)
        return RedirectResponse(url=str(request.headers.get("referer") or "/admin/topups"), status_code=303)

    @router.post("/topups/delete")
    async def admin_topups_delete(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        topup_id: int = Form(...),
    ):
        await repo.admin_delete_topup(topup_id=topup_id)
        return RedirectResponse(url=str(request.headers.get("referer") or "/admin/topups"), status_code=303)

    @router.get("/health", response_class=HTMLResponse)
    async def admin_health(credentials: HTTPBasicCredentials = Depends(_auth)):
        async with aiosqlite.connect(cfg.db_path) as db:
            await db.execute("SELECT 1")
        return _layout(cfg, "Health", "<div>OK</div>", active="dashboard")

    @router.get("/broadcast", response_class=HTMLResponse)
    async def admin_broadcast(credentials: HTTPBasicCredentials = Depends(_auth)):
        body = (
            "<div class='stack'>"
            "<form method='post' action='/admin/broadcast/send' class='stack'>"
            "<div class='field'>"
            "<b>Message (HTML)</b>"
            "<textarea class='input textarea' name='text' placeholder='Write message...'></textarea>"
            "</div>"
            "<div class='rowform'>"
            "<button class='btn' type='submit' onclick=\"return confirm('Hamma userlarga yuborilsinmi?')\">Send</button>"
            "</div>"
            "</form>"
            "<div style='height:1px;background:rgba(148,163,184,.18);margin:12px 0'></div>"
            "<form method='post' action='/admin/broadcast/send_user' class='stack'>"
            "<div class='field'>"
            "<b>Username</b>"
            "<input class='input' name='username' placeholder='@username yoki username' value=''>"
            "</div>"
            "<div class='field'>"
            "<b>Message (HTML)</b>"
            "<textarea class='input textarea' name='text' placeholder='Write message...'></textarea>"
            "</div>"
            "<div class='rowform'>"
            "<button class='btn' type='submit'>Send to user</button>"
            "</div>"
            "</form>"
            "<div style='height:1px;background:rgba(148,163,184,.18);margin:12px 0'></div>"
            "<form method='post' action='/admin/broadcast/send_userid' class='stack'>"
            "<div class='field'>"
            "<b>User ID</b>"
            "<input class='input' name='user_id' placeholder='123456789' value=''>"
            "</div>"
            "<div class='field'>"
            "<b>Message (HTML)</b>"
            "<textarea class='input textarea' name='text' placeholder='Write message...'></textarea>"
            "</div>"
            "<div class='rowform'>"
            "<button class='btn' type='submit'>Send to user (ID)</button>"
            "</div>"
            "</form>"
            "<div style='height:1px;background:rgba(148,163,184,.18);margin:12px 0'></div>"
            "<form method='post' action='/admin/broadcast/send_photo' class='stack' enctype='multipart/form-data'>"
            "<div class='field'>"
            "<b>Photo</b>"
            "<input class='input' type='file' name='photo' accept='image/*' required>"
            "</div>"
            "<div class='field'>"
            "<b>Caption (HTML, optional)</b>"
            "<textarea class='input textarea' name='caption' placeholder='Caption...'></textarea>"
            "</div>"
            "<div class='rowform'>"
            "<button class='btn' type='submit' onclick=\"return confirm('Rasm hamma userlarga yuborilsinmi?')\">Send photo</button>"
            "</div>"
            "</form>"
            "<div style='height:1px;background:rgba(148,163,184,.18);margin:12px 0'></div>"
            "<form method='post' action='/admin/broadcast/send_user_photo' class='stack' enctype='multipart/form-data'>"
            "<div class='field'>"
            "<b>Username</b>"
            "<input class='input' name='username' placeholder='@username yoki username' value=''>"
            "</div>"
            "<div class='field'>"
            "<b>Photo</b>"
            "<input class='input' type='file' name='photo' accept='image/*' required>"
            "</div>"
            "<div class='field'>"
            "<b>Caption (HTML, optional)</b>"
            "<textarea class='input textarea' name='caption' placeholder='Caption...'></textarea>"
            "</div>"
            "<div class='rowform'>"
            "<button class='btn' type='submit'>Send photo to user</button>"
            "</div>"
            "</form>"
            "<div style='height:1px;background:rgba(148,163,184,.18);margin:12px 0'></div>"
            "<form method='post' action='/admin/broadcast/send_userid_photo' class='stack' enctype='multipart/form-data'>"
            "<div class='field'>"
            "<b>User ID</b>"
            "<input class='input' name='user_id' placeholder='123456789' value=''>"
            "</div>"
            "<div class='field'>"
            "<b>Photo</b>"
            "<input class='input' type='file' name='photo' accept='image/*' required>"
            "</div>"
            "<div class='field'>"
            "<b>Caption (HTML, optional)</b>"
            "<textarea class='input textarea' name='caption' placeholder='Caption...'></textarea>"
            "</div>"
            "<div class='rowform'>"
            "<button class='btn' type='submit'>Send photo to user (ID)</button>"
            "</div>"
            "</form>"
            "<div class='meta'>Eslatma: matn HTML parse_mode bilan yuboriladi.</div>"
            "</div>"
        )
        return _layout(cfg, "Broadcast", body, active="broadcast")

    @router.post("/broadcast/send_user", response_class=HTMLResponse)
    async def admin_broadcast_send_user(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        username: str = Form(""),
        text: str = Form(""),
    ):
        text = (text or "").strip()
        username = (username or "").strip()
        if not username:
            raise HTTPException(status_code=400, detail="Empty username")
        if text == "":
            raise HTTPException(status_code=400, detail="Empty text")

        uid = await repo.admin_get_user_id_by_username(username)
        if not uid:
            body = (
                "<div class='stack'>"
                "<div class='card'><b>Status</b><div class='num'>User not found</div></div>"
                f"<div class='meta'>Username: <code>{_escape_textarea(username)}</code></div>"
                "<div style='margin-top:10px'><a class='btn' href='/admin/broadcast'>Back</a></div>"
                "</div>"
            )
            return _layout(cfg, "Send to user", body, active="broadcast")

        ok = True
        error = ""
        try:
            await asyncio.to_thread(_tg_send_message, int(uid), text)
        except Exception as e:
            ok = False
            error = str(e)

        body = (
            "<div class='stack'>"
            + (
                "<div class='card'><b>Status</b><div class='num'>Sent</div></div>"
                if ok
                else "<div class='card'><b>Status</b><div class='num'>Failed</div></div>"
            )
            + f"<div class='meta'>Username: <code>{_escape_textarea(username)}</code></div>"
            + f"<div class='meta'>User ID: <code>{int(uid)}</code></div>"
            + (
                f"<div class='meta'>Error: <code>{_escape_textarea(error)}</code></div>"
                if (not ok and error)
                else ""
            )
            + "<div style='margin-top:10px'><a class='btn' href='/admin/broadcast'>Back</a></div>"
            + "</div>"
        )
        return _layout(cfg, "Send to user", body, active="broadcast")

    @router.post("/broadcast/send_userid", response_class=HTMLResponse)
    async def admin_broadcast_send_userid(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        user_id: str = Form(""),
        text: str = Form(""),
    ):
        text = (text or "").strip()
        raw_id = (user_id or "").strip()
        if not raw_id:
            raise HTTPException(status_code=400, detail="Empty user_id")
        if text == "":
            raise HTTPException(status_code=400, detail="Empty text")

        try:
            uid = int(raw_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid user_id")

        ok = True
        error = ""
        try:
            await asyncio.to_thread(_tg_send_message, int(uid), text)
        except Exception as e:
            ok = False
            error = str(e)

        body = (
            "<div class='stack'>"
            + ("<div class='card'><b>Status</b><div class='num'>Sent</div></div>" if ok else "<div class='card'><b>Status</b><div class='num'>Failed</div></div>")
            + f"<div class='meta'>User ID: <code>{int(uid)}</code></div>"
            + (f"<div class='meta'>Error: <code>{_escape_textarea(error)}</code></div>" if (not ok and error) else "")
            + "<div style='margin-top:10px'><a class='btn' href='/admin/broadcast'>Back</a></div>"
            + "</div>"
        )
        return _layout(cfg, "Send to user (ID)", body, active="broadcast")

    @router.post("/broadcast/send", response_class=HTMLResponse)
    async def admin_broadcast_send(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        text: str = Form(""),
    ):
        text = (text or "").strip()
        if text == "":
            raise HTTPException(status_code=400, detail="Empty text")

        sent = 0
        failed = 0
        total = 0

        blocked = 0
        deactivated = 0
        not_found = 0
        flood = 0
        other = 0

        offset = 0
        limit = 500
        while True:
            ids = await repo.admin_list_user_ids_chunk(limit=limit, offset=offset)
            if not ids:
                break
            total += len(ids)
            for uid in ids:
                try:
                    await asyncio.to_thread(_tg_send_message, int(uid), text)
                    sent += 1
                except Exception as e:
                    failed += 1

                    emsg = str(e).lower()
                    if "blocked" in emsg:
                        blocked += 1
                    elif "deactivated" in emsg:
                        deactivated += 1
                    elif "chat not found" in emsg or "user not found" in emsg:
                        not_found += 1
                    elif "too many requests" in emsg or "retry after" in emsg or "flood" in emsg:
                        flood += 1
                    else:
                        other += 1

                await asyncio.sleep(0.035)

            offset += len(ids)

        body = (
            "<div class='stack'>"
            "<div class='grid'>"
            "<div class='card'><b>Total users</b><div class='num'>"
            + str(int(total))
            + "</div></div>"
            "<div class='card'><b>Sent</b><div class='num'>"
            + str(int(sent))
            + "</div></div>"
            "<div class='card'><b>Failed</b><div class='num'>"
            + str(int(failed))
            + "</div></div>"
            "<div class='card'><b>Blocked</b><div class='num'>"
            + str(int(blocked))
            + "</div></div>"
            "</div>"
            "<div class='grid' style='margin-top:12px'>"
            "<div class='card'><b>Deactivated</b><div class='num'>"
            + str(int(deactivated))
            + "</div></div>"
            "<div class='card'><b>Chat not found</b><div class='num'>"
            + str(int(not_found))
            + "</div></div>"
            "<div class='card'><b>Flood / Retry</b><div class='num'>"
            + str(int(flood))
            + "</div></div>"
            "<div class='card'><b>Other</b><div class='num'>"
            + str(int(other))
            + "</div></div>"
            "</div>"
            "<div style='margin-top:10px'><a class='btn' href='/admin/broadcast'>Back</a></div>"
            "</div>"
        )
        return _layout(cfg, "Broadcast result", body, active="broadcast")

    @router.post("/broadcast/send_photo", response_class=HTMLResponse)
    async def admin_broadcast_send_photo(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        photo: UploadFile = File(...),
        caption: str = Form(""),
    ):
        caption = (caption or "").strip()
        file_bytes = await photo.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Empty photo")

        filename = str(photo.filename or "photo.jpg")

        sent = 0
        failed = 0
        total = 0

        blocked = 0
        deactivated = 0
        not_found = 0
        flood = 0
        other = 0

        offset = 0
        limit = 300
        while True:
            ids = await repo.admin_list_user_ids_chunk(limit=limit, offset=offset)
            if not ids:
                break
            total += len(ids)
            for uid in ids:
                try:
                    await asyncio.to_thread(_tg_send_photo, int(uid), file_bytes, filename, caption)
                    sent += 1
                except Exception as e:
                    failed += 1
                    emsg = str(e).lower()
                    if "blocked" in emsg:
                        blocked += 1
                    elif "deactivated" in emsg:
                        deactivated += 1
                    elif "chat not found" in emsg or "user not found" in emsg:
                        not_found += 1
                    elif "too many requests" in emsg or "retry after" in emsg or "flood" in emsg:
                        flood += 1
                    else:
                        other += 1

                await asyncio.sleep(0.05)

            offset += len(ids)

        body = (
            "<div class='stack'>"
            "<div class='grid'>"
            "<div class='card'><b>Total users</b><div class='num'>"
            + str(int(total))
            + "</div></div>"
            "<div class='card'><b>Sent</b><div class='num'>"
            + str(int(sent))
            + "</div></div>"
            "<div class='card'><b>Failed</b><div class='num'>"
            + str(int(failed))
            + "</div></div>"
            "<div class='card'><b>Blocked</b><div class='num'>"
            + str(int(blocked))
            + "</div></div>"
            "</div>"
            "<div class='grid' style='margin-top:12px'>"
            "<div class='card'><b>Deactivated</b><div class='num'>"
            + str(int(deactivated))
            + "</div></div>"
            "<div class='card'><b>Chat not found</b><div class='num'>"
            + str(int(not_found))
            + "</div></div>"
            "<div class='card'><b>Flood / Retry</b><div class='num'>"
            + str(int(flood))
            + "</div></div>"
            "<div class='card'><b>Other</b><div class='num'>"
            + str(int(other))
            + "</div></div>"
            "</div>"
            "<div style='margin-top:10px'><a class='btn' href='/admin/broadcast'>Back</a></div>"
            "</div>"
        )
        return _layout(cfg, "Broadcast photo result", body, active="broadcast")

    @router.post("/broadcast/send_user_photo", response_class=HTMLResponse)
    async def admin_broadcast_send_user_photo(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        username: str = Form(""),
        photo: UploadFile = File(...),
        caption: str = Form(""),
    ):
        username = (username or "").strip()
        if not username:
            raise HTTPException(status_code=400, detail="Empty username")

        file_bytes = await photo.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Empty photo")

        uid = await repo.admin_get_user_id_by_username(username)
        if not uid:
            body = (
                "<div class='stack'>"
                "<div class='card'><b>Status</b><div class='num'>User not found</div></div>"
                f"<div class='meta'>Username: <code>{_escape_textarea(username)}</code></div>"
                "<div style='margin-top:10px'><a class='btn' href='/admin/broadcast'>Back</a></div>"
                "</div>"
            )
            return _layout(cfg, "Send photo to user", body, active="broadcast")

    @router.post("/broadcast/send_userid_photo", response_class=HTMLResponse)
    async def admin_broadcast_send_userid_photo(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        user_id: str = Form(""),
        photo: UploadFile = File(...),
        caption: str = Form(""),
    ):
        raw_id = (user_id or "").strip()
        if not raw_id:
            raise HTTPException(status_code=400, detail="Empty user_id")

        try:
            uid = int(raw_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid user_id")

        file_bytes = await photo.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Empty photo")

        filename = str(photo.filename or "photo.jpg")

        ok = True
        error = ""
        try:
            await asyncio.to_thread(_tg_send_photo, int(uid), file_bytes, filename, (caption or "").strip())
        except Exception as e:
            ok = False
            error = str(e)

        body = (
            "<div class='stack'>"
            + ("<div class='card'><b>Status</b><div class='num'>Sent</div></div>" if ok else "<div class='card'><b>Status</b><div class='num'>Failed</div></div>")
            + f"<div class='meta'>User ID: <code>{int(uid)}</code></div>"
            + (f"<div class='meta'>Error: <code>{_escape_textarea(error)}</code></div>" if (not ok and error) else "")
            + "<div style='margin-top:10px'><a class='btn' href='/admin/broadcast'>Back</a></div>"
            + "</div>"
        )
        return _layout(cfg, "Send photo to user (ID)", body, active="broadcast")

        filename = str(photo.filename or "photo.jpg")

        ok = True
        error = ""
        try:
            await asyncio.to_thread(_tg_send_photo, int(uid), file_bytes, filename, (caption or "").strip())
        except Exception as e:
            ok = False
            error = str(e)

        body = (
            "<div class='stack'>"
            + ("<div class='card'><b>Status</b><div class='num'>Sent</div></div>" if ok else "<div class='card'><b>Status</b><div class='num'>Failed</div></div>")
            + f"<div class='meta'>Username: <code>{_escape_textarea(username)}</code></div>"
            + f"<div class='meta'>User ID: <code>{int(uid)}</code></div>"
            + (f"<div class='meta'>Error: <code>{_escape_textarea(error)}</code></div>" if (not ok and error) else "")
            + "<div style='margin-top:10px'><a class='btn' href='/admin/broadcast'>Back</a></div>"
            + "</div>"
        )
        return _layout(cfg, "Send photo to user", body, active="broadcast")

    def _escape_textarea(s: str) -> str:
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _escape_attr(s: str) -> str:
        return _escape_textarea(s).replace("\"", "&quot;").replace("'", "&#39;")

    async def _bulk_add_from_txt(product_key: str, accounts_file: UploadFile) -> dict:
        raw = await accounts_file.read()
        text = ""
        for enc in ("utf-8-sig", "utf-8", "cp1251", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except Exception:
                continue

        added = 0
        skipped = 0
        dup_file = 0
        dup_db = 0
        seen: set[str] = set()

        for line in (text or "").splitlines():
            s = (line or "").strip()
            if not s:
                continue
            if s.startswith("#"):
                continue

            s = re.sub(r"\s*\|\s*", "|", s)
            if "|" not in s:
                skipped += 1
                continue

            login, password = s.split("|", 1)
            login = (login or "").strip()
            password = (password or "").strip()
            if not login or not password:
                skipped += 1
                continue

            key = f"{login}|{password}".lower()
            if key in seen:
                dup_file += 1
                continue
            seen.add(key)

            try:
                if await repo.admin_exists_available_product_account(product_key, login=login, password=password):
                    dup_db += 1
                    continue
            except Exception:
                skipped += 1
                continue

            try:
                await repo.admin_add_product_account(product_key, login=login, password=password)
                added += 1
            except Exception:
                skipped += 1

        return {
            "added": added,
            "skipped": skipped,
            "dup_file": dup_file,
            "dup_db": dup_db,
            "total": added + skipped + dup_file + dup_db,
        }

    async def _account_page(
        title: str,
        product_key: str,
        active: str,
        post_url: str,
        delete_post_url: str,
        edit_post_url: str,
    ) -> str:
        rows = await repo.admin_list_available_product_accounts(product_key=product_key, limit=300)
        body = (
            "<div class='stack'>"
            "<div id='acct-forms' class='stack'>"
            f"<form method='post' action='{post_url}' class='stack acct-form' enctype='multipart/form-data'>"
            "<div class='field'>"
            "<b>Login</b>"
            "<input class='input' name='login' placeholder='Login' value=''>"
            "</div>"
            "<div class='field'>"
            "<b>Parol</b>"
            "<input class='input' name='password' placeholder='Parol' value=''>"
            "</div>"
            "<div class='field'>"
            "<b>.txt file (login|password)</b>"
            "<input class='input' type='file' name='accounts_file' accept='.txt,text/plain'>"
            "</div>"
            "<div>"
            "<button class='btn' type='submit'>Saqlash</button>"
            "</div>"
            "</form>"
            "</div>"
            "<div style='margin-top:10px'>"
            "<button class='btn' type='button' id='btn-add-acct'>+ Yangi Login/Parol</button>"
            "</div>"
            "<template id='acct-form-template'>"
            f"<form method='post' action='{post_url}' class='stack acct-form' style='margin-top:10px' enctype='multipart/form-data'>"
            "<div class='field'>"
            "<b>Login</b>"
            "<input class='input' name='login' placeholder='Login' value=''>"
            "</div>"
            "<div class='field'>"
            "<b>Parol</b>"
            "<input class='input' name='password' placeholder='Parol' value=''>"
            "</div>"
            "<div class='field'>"
            "<b>.txt file (login|password)</b>"
            "<input class='input' type='file' name='accounts_file' accept='.txt,text/plain'>"
            "</div>"
            "<div>"
            "<button class='btn' type='submit'>Saqlash</button>"
            "</div>"
            "</form>"
            "</template>"
            "<script>"
            "(function(){"
            "var btn=document.getElementById('btn-add-acct');"
            "var tpl=document.getElementById('acct-form-template');"
            "var wrap=document.getElementById('acct-forms');"
            "if(!btn||!tpl||!wrap) return;"
            "btn.addEventListener('click',function(){"
            "wrap.appendChild(tpl.content.cloneNode(true));"
            "var forms=wrap.querySelectorAll('form.acct-form');"
            "var last=forms[forms.length-1];"
            "if(last){var inp=last.querySelector('input[name=login]'); if(inp) inp.focus();}"
            "});"
            "wrap.addEventListener('submit', function(e){"
            "var f=e.target; if(!f||!f.classList||!f.classList.contains('acct-form')) return;"
            "e.preventDefault();"
            "var fd=new FormData(f);"
            "fetch(f.action,{method:'POST',body:fd,headers:{'X-Requested-With':'fetch'}})"
            ".then(r=>r.json())"
            ".then(d=>{"
            "if(!d||!d.ok){alert((d&&d.error)?d.error:'Xato'); return;}"
            "if(d.bulk){alert('Yuklandi: '+(d.added||0)+' ta. Dublikat(file): '+(d.dup_file||0)+' ta. Dublikat(baza): '+(d.dup_db||0)+' ta. Skip: '+(d.skipped||0)+' ta'); window.location.reload(); return;}"
            "var tb=document.getElementById('acct-table-body');"
            "if(tb){"
            "var tr=document.createElement('tr');"
            "tr.innerHTML='<td><code>'+d.id+'</code></td><td>'+d.login+'</td><td>'+d.password+'</td><td>'+d.created_at+'</td><td><form method=\'post\' action=\''+d.edit_url+'\' class=\'rowform\' style=\'gap:6px\'><input type=\'hidden\' name=\'account_id\' value=\''+d.id+'\'><input class=\'input\' name=\'login\' value=\''+(d.login||'')+'\' style=\'width:140px\'><input class=\'input\' name=\'password\' value=\''+(d.password||'')+'\' style=\'width:140px\'><button class=\'btn\' type=\'submit\'>Save</button></form></td><td><form method=\'post\' action=\''+d.delete_url+'\' class=\'rowform\'><input type=\'hidden\' name=\'account_id\' value=\''+d.id+'\'><button class=\'btn\' type=\'submit\' onclick=\"return confirm(\\'O\\'chirish?\\')\" style=\'border-color:rgba(248,113,113,.65);background:rgba(248,113,113,.12)\'>Delete</button></form></td>';"
            "tb.appendChild(tr);"
            "}"
            "});"
            "});"
            "})();"
            "</script>"
        )

        body += (
            "<div class='meta'>Available: " + str(len(rows)) + "</div>"
            "<div class='table-wrap'>"
            "<table>"
            "<thead><tr><th>ID</th><th>Login</th><th>Parol</th><th>Created</th><th>Edit</th><th>Delete</th></tr></thead>"
            "<tbody id='acct-table-body'>"
        )

        for r in rows:
            body += (
                "<tr>"
                f"<td><code>{int(r['id'])}</code></td>"
                f"<td>{(r['login'] or '')}</td>"
                f"<td>{(r['password'] or '')}</td>"
                f"<td>{(r['created_at'] or '')}</td>"
                "<td>"
                f"<form method='post' action='{_escape_attr(str(edit_post_url))}' class='rowform' style='gap:6px'>"
                f"<input type='hidden' name='account_id' value='{int(r['id'])}'>"
                f"<input class='input' name='login' value='{_escape_attr(str(r['login'] or ''))}' style='width:140px'>"
                f"<input class='input' name='password' value='{_escape_attr(str(r['password'] or ''))}' style='width:140px'>"
                "<button class='btn' type='submit'>Save</button>"
                "</form>"
                "</td>"
                "<td>"
                f"<form method='post' action='{_escape_attr(str(delete_post_url))}' class='rowform'>"
                f"<input type='hidden' name='account_id' value='{int(r['id'])}'>"
                "<button class='btn' type='submit' onclick=\"return confirm('O\'chirish?')\" style='border-color:rgba(248,113,113,.65);background:rgba(248,113,113,.12)'>Delete</button>"
                "</form>"
                "</td>"
                "</tr>"
            )

        body += "</tbody></table></div></div>"
        return _layout(cfg, title, body, active=active)

    @router.get("/accounts/chatgpt", response_class=HTMLResponse)
    async def admin_chatgpt(credentials: HTTPBasicCredentials = Depends(_auth)):
        return await _account_page(
            "ChatGPT akkaunt",
            product_key="chatgpt_business",
            active="chatgpt",
            post_url="/admin/accounts/chatgpt",
            delete_post_url="/admin/accounts/chatgpt/delete",
            edit_post_url="/admin/accounts/chatgpt/edit",
        )

    @router.post("/accounts/chatgpt")
    async def admin_chatgpt_save(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        login: str = Form(""),
        password: str = Form(""),
        accounts_file: UploadFile | None = File(None),
    ):
        if accounts_file and (accounts_file.filename or ""):
            res = await _bulk_add_from_txt("chatgpt_business", accounts_file)
            if request.headers.get("X-Requested-With") == "fetch":
                return JSONResponse({"ok": True, "bulk": True, **res})
            return RedirectResponse(url="/admin/accounts/chatgpt", status_code=303)

        if await repo.admin_exists_available_product_account("chatgpt_business", login=login, password=password):
            if request.headers.get("X-Requested-With") == "fetch":
                return JSONResponse({"ok": False, "error": "Dublikat login/parol (bazada bor)"})
            return RedirectResponse(url="/admin/accounts/chatgpt", status_code=303)

        acc_id = await repo.admin_add_product_account("chatgpt_business", login=login, password=password)
        if request.headers.get("X-Requested-With") == "fetch":
            return JSONResponse(
                {
                    "ok": True,
                    "id": acc_id,
                    "login": login,
                    "password": password,
                    "created_at": "",
                    "delete_url": "/admin/accounts/chatgpt/delete",
                    "edit_url": "/admin/accounts/chatgpt/edit",
                }
            )
        return RedirectResponse(url="/admin/accounts/chatgpt", status_code=303)

    @router.post("/accounts/chatgpt/edit")
    async def admin_chatgpt_edit(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        account_id: int = Form(...),
        login: str = Form(""),
        password: str = Form(""),
    ):
        await repo.admin_update_product_account("chatgpt_business", account_id=account_id, login=login, password=password)
        return RedirectResponse(url=str(request.headers.get("referer") or "/admin/accounts/chatgpt"), status_code=303)

    @router.post("/accounts/chatgpt/delete")
    async def admin_chatgpt_delete(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        account_id: int = Form(...),
    ):
        await repo.admin_delete_product_account("chatgpt_business", account_id=account_id)
        return RedirectResponse(url=str(request.headers.get("referer") or "/admin/accounts/chatgpt"), status_code=303)

    @router.get("/accounts/chatgpt_plus", response_class=HTMLResponse)
    async def admin_chatgpt_plus(credentials: HTTPBasicCredentials = Depends(_auth)):
        return await _account_page(
            "ChatGPT Plus",
            product_key="chatgpt_plus",
            active="chatgpt_plus",
            post_url="/admin/accounts/chatgpt_plus",
            delete_post_url="/admin/accounts/chatgpt_plus/delete",
            edit_post_url="/admin/accounts/chatgpt_plus/edit",
        )

    @router.post("/accounts/chatgpt_plus")
    async def admin_chatgpt_plus_save(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        login: str = Form(""),
        password: str = Form(""),
        accounts_file: UploadFile | None = File(None),
    ):
        if accounts_file and (accounts_file.filename or ""):
            res = await _bulk_add_from_txt("chatgpt_plus", accounts_file)
            if request.headers.get("X-Requested-With") == "fetch":
                return JSONResponse({"ok": True, "bulk": True, **res})
            return RedirectResponse(url="/admin/accounts/chatgpt_plus", status_code=303)

        if await repo.admin_exists_available_product_account("chatgpt_plus", login=login, password=password):
            if request.headers.get("X-Requested-With") == "fetch":
                return JSONResponse({"ok": False, "error": "Dublikat login/parol (bazada bor)"})
            return RedirectResponse(url="/admin/accounts/chatgpt_plus", status_code=303)

        acc_id = await repo.admin_add_product_account("chatgpt_plus", login=login, password=password)
        if request.headers.get("X-Requested-With") == "fetch":
            return JSONResponse(
                {
                    "ok": True,
                    "id": acc_id,
                    "login": login,
                    "password": password,
                    "created_at": "",
                    "delete_url": "/admin/accounts/chatgpt_plus/delete",
                    "edit_url": "/admin/accounts/chatgpt_plus/edit",
                }
            )
        return RedirectResponse(url="/admin/accounts/chatgpt_plus", status_code=303)

    @router.post("/accounts/chatgpt_plus/edit")
    async def admin_chatgpt_plus_edit(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        account_id: int = Form(...),
        login: str = Form(""),
        password: str = Form(""),
    ):
        await repo.admin_update_product_account("chatgpt_plus", account_id=account_id, login=login, password=password)
        return RedirectResponse(url=str(request.headers.get("referer") or "/admin/accounts/chatgpt_plus"), status_code=303)

    @router.post("/accounts/chatgpt_plus/delete")
    async def admin_chatgpt_plus_delete(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        account_id: int = Form(...),
    ):
        await repo.admin_delete_product_account("chatgpt_plus", account_id=account_id)
        return RedirectResponse(url=str(request.headers.get("referer") or "/admin/accounts/chatgpt_plus"), status_code=303)

    @router.get("/accounts/spotify_premium", response_class=HTMLResponse)
    async def admin_spotify_premium(credentials: HTTPBasicCredentials = Depends(_auth)):
        return await _account_page(
            "Spotify Premium",
            product_key="spotify_premium",
            active="spotify_premium",
            post_url="/admin/accounts/spotify_premium",
            delete_post_url="/admin/accounts/spotify_premium/delete",
            edit_post_url="/admin/accounts/spotify_premium/edit",
        )

    @router.post("/accounts/spotify_premium")
    async def admin_spotify_premium_save(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        login: str = Form(""),
        password: str = Form(""),
        accounts_file: UploadFile | None = File(None),
    ):
        if accounts_file and (accounts_file.filename or ""):
            res = await _bulk_add_from_txt("spotify_premium", accounts_file)
            if request.headers.get("X-Requested-With") == "fetch":
                return JSONResponse({"ok": True, "bulk": True, **res})
            return RedirectResponse(url="/admin/accounts/spotify_premium", status_code=303)

        if await repo.admin_exists_available_product_account("spotify_premium", login=login, password=password):
            if request.headers.get("X-Requested-With") == "fetch":
                return JSONResponse({"ok": False, "error": "Dublikat login/parol (bazada bor)"})
            return RedirectResponse(url="/admin/accounts/spotify_premium", status_code=303)

        acc_id = await repo.admin_add_product_account("spotify_premium", login=login, password=password)
        if request.headers.get("X-Requested-With") == "fetch":
            return JSONResponse(
                {
                    "ok": True,
                    "id": acc_id,
                    "login": login,
                    "password": password,
                    "created_at": "",
                    "delete_url": "/admin/accounts/spotify_premium/delete",
                    "edit_url": "/admin/accounts/spotify_premium/edit",
                }
            )
        return RedirectResponse(url="/admin/accounts/spotify_premium", status_code=303)

    @router.post("/accounts/spotify_premium/edit")
    async def admin_spotify_premium_edit(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        account_id: int = Form(...),
        login: str = Form(""),
        password: str = Form(""),
    ):
        await repo.admin_update_product_account("spotify_premium", account_id=account_id, login=login, password=password)
        return RedirectResponse(url=str(request.headers.get("referer") or "/admin/accounts/spotify_premium"), status_code=303)

    @router.post("/accounts/spotify_premium/delete")
    async def admin_spotify_premium_delete(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        account_id: int = Form(...),
    ):
        await repo.admin_delete_product_account("spotify_premium", account_id=account_id)
        return RedirectResponse(url=str(request.headers.get("referer") or "/admin/accounts/spotify_premium"), status_code=303)

    @router.get("/accounts/youtube_premium", response_class=HTMLResponse)
    async def admin_youtube_premium(credentials: HTTPBasicCredentials = Depends(_auth)):
        return await _account_page(
            "YouTube Premium",
            product_key="youtube_premium",
            active="youtube_premium",
            post_url="/admin/accounts/youtube_premium",
            delete_post_url="/admin/accounts/youtube_premium/delete",
            edit_post_url="/admin/accounts/youtube_premium/edit",
        )

    @router.post("/accounts/youtube_premium")
    async def admin_youtube_premium_save(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        login: str = Form(""),
        password: str = Form(""),
        accounts_file: UploadFile | None = File(None),
    ):
        if accounts_file and (accounts_file.filename or ""):
            res = await _bulk_add_from_txt("youtube_premium", accounts_file)
            if request.headers.get("X-Requested-With") == "fetch":
                return JSONResponse({"ok": True, "bulk": True, **res})
            return RedirectResponse(url="/admin/accounts/youtube_premium", status_code=303)

        if await repo.admin_exists_available_product_account("youtube_premium", login=login, password=password):
            if request.headers.get("X-Requested-With") == "fetch":
                return JSONResponse({"ok": False, "error": "Dublikat login/parol (bazada bor)"})
            return RedirectResponse(url="/admin/accounts/youtube_premium", status_code=303)

        acc_id = await repo.admin_add_product_account("youtube_premium", login=login, password=password)
        if request.headers.get("X-Requested-With") == "fetch":
            return JSONResponse(
                {
                    "ok": True,
                    "id": acc_id,
                    "login": login,
                    "password": password,
                    "created_at": "",
                    "delete_url": "/admin/accounts/youtube_premium/delete",
                    "edit_url": "/admin/accounts/youtube_premium/edit",
                }
            )
        return RedirectResponse(url="/admin/accounts/youtube_premium", status_code=303)

    @router.post("/accounts/youtube_premium/edit")
    async def admin_youtube_premium_edit(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        account_id: int = Form(...),
        login: str = Form(""),
        password: str = Form(""),
    ):
        await repo.admin_update_product_account("youtube_premium", account_id=account_id, login=login, password=password)
        return RedirectResponse(url=str(request.headers.get("referer") or "/admin/accounts/youtube_premium"), status_code=303)

    @router.post("/accounts/youtube_premium/delete")
    async def admin_youtube_premium_delete(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        account_id: int = Form(...),
    ):
        await repo.admin_delete_product_account("youtube_premium", account_id=account_id)
        return RedirectResponse(url=str(request.headers.get("referer") or "/admin/accounts/youtube_premium"), status_code=303)

    @router.get("/accounts/super_grok", response_class=HTMLResponse)
    async def admin_super_grok(credentials: HTTPBasicCredentials = Depends(_auth)):
        return await _account_page(
            "Super Grok",
            product_key="super_grok",
            active="super_grok",
            post_url="/admin/accounts/super_grok",
            delete_post_url="/admin/accounts/super_grok/delete",
            edit_post_url="/admin/accounts/super_grok/edit",
        )

    @router.post("/accounts/super_grok")
    async def admin_super_grok_save(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        login: str = Form(""),
        password: str = Form(""),
        accounts_file: UploadFile | None = File(None),
    ):
        if accounts_file and (accounts_file.filename or ""):
            res = await _bulk_add_from_txt("super_grok", accounts_file)
            if request.headers.get("X-Requested-With") == "fetch":
                return JSONResponse({"ok": True, "bulk": True, **res})
            return RedirectResponse(url="/admin/accounts/super_grok", status_code=303)

        if await repo.admin_exists_available_product_account("super_grok", login=login, password=password):
            if request.headers.get("X-Requested-With") == "fetch":
                return JSONResponse({"ok": False, "error": "Dublikat login/parol (bazada bor)"})
            return RedirectResponse(url="/admin/accounts/super_grok", status_code=303)

        acc_id = await repo.admin_add_product_account("super_grok", login=login, password=password)
        if request.headers.get("X-Requested-With") == "fetch":
            return JSONResponse(
                {
                    "ok": True,
                    "id": acc_id,
                    "login": login,
                    "password": password,
                    "created_at": "",
                    "delete_url": "/admin/accounts/super_grok/delete",
                    "edit_url": "/admin/accounts/super_grok/edit",
                }
            )
        return RedirectResponse(url="/admin/accounts/super_grok", status_code=303)

    @router.post("/accounts/super_grok/edit")
    async def admin_super_grok_edit(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        account_id: int = Form(...),
        login: str = Form(""),
        password: str = Form(""),
    ):
        await repo.admin_update_product_account("super_grok", account_id=account_id, login=login, password=password)
        return RedirectResponse(url=str(request.headers.get("referer") or "/admin/accounts/super_grok"), status_code=303)

    @router.post("/accounts/super_grok/delete")
    async def admin_super_grok_delete(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        account_id: int = Form(...),
    ):
        await repo.admin_delete_product_account("super_grok", account_id=account_id)
        return RedirectResponse(url=str(request.headers.get("referer") or "/admin/accounts/super_grok"), status_code=303)

    @router.get("/accounts/canva_pro", response_class=HTMLResponse)
    async def admin_canva_pro(credentials: HTTPBasicCredentials = Depends(_auth)):
        return await _account_page(
            "Canva Pro",
            product_key="canva_pro",
            active="canva_pro",
            post_url="/admin/accounts/canva_pro",
            delete_post_url="/admin/accounts/canva_pro/delete",
            edit_post_url="/admin/accounts/canva_pro/edit",
        )

    @router.post("/accounts/canva_pro")
    async def admin_canva_pro_save(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        login: str = Form(""),
        password: str = Form(""),
        accounts_file: UploadFile | None = File(None),
    ):
        if accounts_file and (accounts_file.filename or ""):
            res = await _bulk_add_from_txt("canva_pro", accounts_file)
            if request.headers.get("X-Requested-With") == "fetch":
                return JSONResponse({"ok": True, "bulk": True, **res})
            return RedirectResponse(url="/admin/accounts/canva_pro", status_code=303)

        if await repo.admin_exists_available_product_account("canva_pro", login=login, password=password):
            if request.headers.get("X-Requested-With") == "fetch":
                return JSONResponse({"ok": False, "error": "Dublikat login/parol (bazada bor)"})
            return RedirectResponse(url="/admin/accounts/canva_pro", status_code=303)

        acc_id = await repo.admin_add_product_account("canva_pro", login=login, password=password)
        if request.headers.get("X-Requested-With") == "fetch":
            return JSONResponse(
                {
                    "ok": True,
                    "id": acc_id,
                    "login": login,
                    "password": password,
                    "created_at": "",
                    "delete_url": "/admin/accounts/canva_pro/delete",
                    "edit_url": "/admin/accounts/canva_pro/edit",
                }
            )
        return RedirectResponse(url="/admin/accounts/canva_pro", status_code=303)

    @router.post("/accounts/canva_pro/edit")
    async def admin_canva_pro_edit(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        account_id: int = Form(...),
        login: str = Form(""),
        password: str = Form(""),
    ):
        await repo.admin_update_product_account("canva_pro", account_id=account_id, login=login, password=password)
        return RedirectResponse(url=str(request.headers.get("referer") or "/admin/accounts/canva_pro"), status_code=303)

    @router.post("/accounts/canva_pro/delete")
    async def admin_canva_pro_delete(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        account_id: int = Form(...),
    ):
        await repo.admin_delete_product_account("canva_pro", account_id=account_id)
        return RedirectResponse(url=str(request.headers.get("referer") or "/admin/accounts/canva_pro"), status_code=303)

    @router.get("/accounts/capcut_pro", response_class=HTMLResponse)
    async def admin_capcut_pro(credentials: HTTPBasicCredentials = Depends(_auth)):
        return await _account_page(
            "CapCut Pro",
            product_key="capcut_pro",
            active="capcut_pro",
            post_url="/admin/accounts/capcut_pro",
            delete_post_url="/admin/accounts/capcut_pro/delete",
            edit_post_url="/admin/accounts/capcut_pro/edit",
        )

    @router.post("/accounts/capcut_pro")
    async def admin_capcut_pro_save(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        login: str = Form(""),
        password: str = Form(""),
        accounts_file: UploadFile | None = File(None),
    ):
        if accounts_file and (accounts_file.filename or ""):
            res = await _bulk_add_from_txt("capcut_pro", accounts_file)
            if request.headers.get("X-Requested-With") == "fetch":
                return JSONResponse({"ok": True, "bulk": True, **res})
            return RedirectResponse(url="/admin/accounts/capcut_pro", status_code=303)

        if await repo.admin_exists_available_product_account("capcut_pro", login=login, password=password):
            if request.headers.get("X-Requested-With") == "fetch":
                return JSONResponse({"ok": False, "error": "Dublikat login/parol (bazada bor)"})
            return RedirectResponse(url="/admin/accounts/capcut_pro", status_code=303)

        acc_id = await repo.admin_add_product_account("capcut_pro", login=login, password=password)
        if request.headers.get("X-Requested-With") == "fetch":
            return JSONResponse(
                {
                    "ok": True,
                    "id": acc_id,
                    "login": login,
                    "password": password,
                    "created_at": "",
                    "delete_url": "/admin/accounts/capcut_pro/delete",
                    "edit_url": "/admin/accounts/capcut_pro/edit",
                }
            )
        return RedirectResponse(url="/admin/accounts/capcut_pro", status_code=303)

    @router.post("/accounts/capcut_pro/edit")
    async def admin_capcut_pro_edit(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        account_id: int = Form(...),
        login: str = Form(""),
        password: str = Form(""),
    ):
        await repo.admin_update_product_account("capcut_pro", account_id=account_id, login=login, password=password)
        return RedirectResponse(url=str(request.headers.get("referer") or "/admin/accounts/capcut_pro"), status_code=303)

    @router.post("/accounts/capcut_pro/delete")
    async def admin_capcut_pro_delete(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        account_id: int = Form(...),
    ):
        await repo.admin_delete_product_account("capcut_pro", account_id=account_id)
        return RedirectResponse(url=str(request.headers.get("referer") or "/admin/accounts/capcut_pro"), status_code=303)

    @router.get("/accounts/gemini", response_class=HTMLResponse)
    async def admin_gemini(credentials: HTTPBasicCredentials = Depends(_auth)):
        return await _account_page(
            "Gemini akkaunt",
            product_key="gemine",
            active="gemini",
            post_url="/admin/accounts/gemini",
            delete_post_url="/admin/accounts/gemini/delete",
            edit_post_url="/admin/accounts/gemini/edit",
        )

    @router.post("/accounts/gemini")
    async def admin_gemini_save(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        login: str = Form(""),
        password: str = Form(""),
        accounts_file: UploadFile | None = File(None),
    ):
        if accounts_file and (accounts_file.filename or ""):
            res = await _bulk_add_from_txt("gemine", accounts_file)
            if request.headers.get("X-Requested-With") == "fetch":
                return JSONResponse({"ok": True, "bulk": True, **res})
            return RedirectResponse(url="/admin/accounts/gemini", status_code=303)

        if await repo.admin_exists_available_product_account("gemine", login=login, password=password):
            if request.headers.get("X-Requested-With") == "fetch":
                return JSONResponse({"ok": False, "error": "Dublikat login/parol (bazada bor)"})
            return RedirectResponse(url="/admin/accounts/gemini", status_code=303)

        acc_id = await repo.admin_add_product_account("gemine", login=login, password=password)
        if request.headers.get("X-Requested-With") == "fetch":
            return JSONResponse(
                {
                    "ok": True,
                    "id": acc_id,
                    "login": login,
                    "password": password,
                    "created_at": "",
                    "delete_url": "/admin/accounts/gemini/delete",
                    "edit_url": "/admin/accounts/gemini/edit",
                }
            )
        return RedirectResponse(url="/admin/accounts/gemini", status_code=303)

    @router.post("/accounts/gemini/edit")
    async def admin_gemini_edit(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        account_id: int = Form(...),
        login: str = Form(""),
        password: str = Form(""),
    ):
        await repo.admin_update_product_account("gemine", account_id=account_id, login=login, password=password)
        return RedirectResponse(url=str(request.headers.get("referer") or "/admin/accounts/gemini"), status_code=303)

    @router.post("/accounts/gemini/delete")
    async def admin_gemini_delete(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        account_id: int = Form(...),
    ):
        await repo.admin_delete_product_account("gemine", account_id=account_id)
        return RedirectResponse(url=str(request.headers.get("referer") or "/admin/accounts/gemini"), status_code=303)

    return router
