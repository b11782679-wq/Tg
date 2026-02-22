from __future__ import annotations

import secrets
import asyncio
import json
import urllib.request
from pathlib import Path
from typing import Annotated
import mimetypes

import aiosqlite
from fastapi import Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from bot.config import Config
from bot.db.repo import Repo
from fastapi import APIRouter


_security = HTTPBasic()


def _check_auth(cfg: Config, creds: HTTPBasicCredentials):
    u_ok = secrets.compare_digest(creds.username or "", cfg.admin_panel_user)
    p_ok = secrets.compare_digest(creds.password or "", cfg.admin_panel_pass)
    if not (u_ok and p_ok):
        raise HTTPException(status_code=401, detail="Unauthorized", headers={"WWW-Authenticate": "Basic"})


def create_admin_app(cfg: Config, repo: Repo) -> APIRouter:
    router = APIRouter()

    async def _auth(creds: Annotated[HTTPBasicCredentials, Depends(_security)]):
        _check_auth(cfg, creds)
        return creds

    def _layout(title: str, body: str, active: str) -> str:
        def _nav_item(label: str, href: str, key: str) -> str:
            cls = "nav-item nav-item--active" if key == active else "nav-item"
            return f"<a class='{cls}' href='{href}'>{label}</a>"

        nav = (
            "<nav class='nav'>"
            + _nav_item("Dashboard", "/admin", "dashboard")
            + _nav_item("Users", "/admin/users", "users")
            + _nav_item("Referrals", "/admin/referrals", "referrals")
            + _nav_item("Orders", "/admin/orders", "orders")
            + _nav_item("Sotib olganlar", "/admin/buyers", "buyers")
            + _nav_item("Purchases", "/admin/purchases", "purchases")
            + _nav_item("Topups", "/admin/topups", "topups")
            + _nav_item("Broadcast", "/admin/broadcast", "broadcast")
            + _nav_item("ChatGPT", "/admin/accounts/chatgpt", "chatgpt")
            + _nav_item("Gemini", "/admin/accounts/gemini", "gemini")
            + "</nav>"
        )
        return (
            "<!doctype html>"
            "<html><head><meta charset='utf-8'>"
            f"<title>{title}</title>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<style>"
            ":root{--bg:#0b0f19;--panel:#0f172a;--panel2:#111c33;--text:#e5e7eb;--muted:#94a3b8;--border:rgba(148,163,184,.18);--accent:#60a5fa;--accent2:#a78bfa;}"
            "*{box-sizing:border-box}"
            "html,body{height:100%}"
            "body{margin:0;font-family:ui-sans-serif,system-ui,Segoe UI,Arial;background:radial-gradient(1200px 800px at 20% -10%, rgba(96,165,250,.25), transparent 60%),radial-gradient(900px 700px at 90% 0%, rgba(167,139,250,.18), transparent 55%),var(--bg);color:var(--text)}"
            ".wrap{max-width:1100px;margin:28px auto;padding:0 14px}"
            ".top{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin-bottom:14px}"
            ".title{margin:0;font-size:20px;font-weight:650;letter-spacing:.2px}"
            ".meta{color:var(--muted);font-size:12px}"
            ".nav{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0 16px 0}"
            ".nav-item{display:inline-flex;align-items:center;gap:8px;padding:8px 10px;border:1px solid var(--border);border-radius:10px;background:rgba(15,23,42,.65);color:var(--text);text-decoration:none;font-size:13px}"
            ".nav-item:hover{border-color:rgba(96,165,250,.55)}"
            ".nav-item--active{border-color:rgba(96,165,250,.75);background:rgba(96,165,250,.10)}"
            ".panel{border:1px solid var(--border);background:linear-gradient(180deg, rgba(15,23,42,.82), rgba(15,23,42,.55));border-radius:16px;padding:14px}"
            ".grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}"
            "@media(max-width:900px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}"
            "@media(max-width:520px){.grid{grid-template-columns:1fr}}"
            ".card{border:1px solid var(--border);background:rgba(17,28,51,.55);border-radius:14px;padding:12px}"
            ".card b{display:block;color:var(--muted);font-weight:600;font-size:12px;margin-bottom:8px}"
            ".card .num{font-size:22px;font-weight:700}"
            ".toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:12px}"
            ".input,.select{appearance:none;border:1px solid var(--border);background:rgba(15,23,42,.65);color:var(--text);padding:9px 10px;border-radius:12px;font-size:13px;outline:none}"
            ".input:focus,.select:focus{border-color:rgba(96,165,250,.75);box-shadow:0 0 0 3px rgba(96,165,250,.12)}"
            ".textarea{width:100%;min-height:160px;resize:vertical;line-height:1.35}"
            ".btn{border:1px solid rgba(96,165,250,.55);background:rgba(96,165,250,.12);color:var(--text);padding:9px 12px;border-radius:12px;font-size:13px;cursor:pointer}"
            ".btn:hover{background:rgba(96,165,250,.18)}"
            ".table-wrap{overflow:auto;border:1px solid var(--border);border-radius:16px}"
            "table{border-collapse:separate;border-spacing:0;width:100%}"
            "thead th{position:sticky;top:0;background:rgba(15,23,42,.92);backdrop-filter: blur(10px);text-align:left;color:var(--muted);font-size:12px;font-weight:650;border-bottom:1px solid var(--border);padding:10px}"
            "tbody td{border-bottom:1px solid rgba(148,163,184,.12);padding:10px;font-size:13px;vertical-align:middle}"
            "tbody tr:hover td{background:rgba(96,165,250,.05)}"
            "code{color:#c7d2fe}"
            ".rowform{display:flex;gap:8px;align-items:center;flex-wrap:wrap}"
            ".rowform .input{padding:7px 9px;border-radius:10px}"
            ".rowform .btn{padding:7px 10px;border-radius:10px}"
            ".stack{display:grid;grid-template-columns:1fr;gap:12px}"
            ".field b{display:block;color:var(--muted);font-weight:650;font-size:12px;margin-bottom:8px}"
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

    def _fmt_money(n: int) -> str:
        return f"{int(n):,}".replace(",", " ")

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
        return _layout("Admin Dashboard", body, active="dashboard")

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
            "<th>Name</th>"
            "<th>Username</th>"
            "<th>Money (so'm)</th>"
            "<th>Points</th>"
            "<th>Update</th>"
            "<th>Kick</th>"
            "</tr></thead><tbody>"
        )

        for r in rows:
            body += (
                "<tr>"
                f"<td><code>{int(r['id'])}</code></td>"
                f"<td>{(r['full_name'] or '')}</td>"
                f"<td>{(r['username'] or '')}</td>"
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
                "<form method='post' action='/admin/users/delete' class='rowform'>"
                f"<input type='hidden' name='user_id' value='{int(r['id'])}'>"
                "<button class='btn' type='submit' onclick=\"return confirm('User o\'chirilsinmi?')\" style='border-color:rgba(248,113,113,.65);background:rgba(248,113,113,.12)'>Delete</button>"
                "</form>"
                "</td>"
                "</tr>"
            )

        body += "</tbody></table></div>"
        return _layout("Users & Balances", body, active="users")

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

        await repo.admin_apply_balance_delta(
            user_id=user_id,
            money_delta=_parse_int(money_delta),
            points_delta=_parse_int(points_delta),
        )
        return RedirectResponse(url=str(request.headers.get("referer") or "/admin/users"), status_code=303)

    @router.post("/users/delete")
    async def admin_users_delete(
        request: Request,
        credentials: HTTPBasicCredentials = Depends(_auth),
        user_id: int = Form(...),
    ):
        await repo.admin_delete_user(user_id=user_id)
        return RedirectResponse(url=str(request.headers.get("referer") or "/admin/users"), status_code=303)

    @router.get("/orders", response_class=HTMLResponse)
    async def admin_orders(
        credentials: HTTPBasicCredentials = Depends(_auth),
        status: str | None = None,
        limit: int = 200,
    ):
        rows = await repo.admin_list_orders(status=status, limit=min(max(limit, 1), 500))

        def _opt(label: str, v: str | None):
            sel = " selected" if v == status else ""
            return f"<option value='{v or ''}'{sel}>{label}</option>"

        body = (
            "<form method='get' class='toolbar'>"
            "<span class='meta'>Status</span>"
            "<select class='select' name='status'>"
            + _opt("All", None)
            + _opt("new", "new")
            + _opt("paid", "paid")
            + _opt("delivered", "delivered")
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
            "<th>Product</th>"
            "<th>Plan</th>"
            "<th>Price</th>"
            "<th>Status</th>"
            "<th>Update</th>"
            "</tr></thead><tbody>"
        )

        for r in rows:
            body += (
                "<tr>"
                f"<td><code>{int(r['id'])}</code></td>"
                f"<td><code>{int(r['user_id'])}</code></td>"
                f"<td>{r['product_key']}</td>"
                f"<td>{r['plan_key']}</td>"
                f"<td>{_fmt_money(int(r['price_uzs']))}</td>"
                f"<td>{r['status']}</td>"
                "<td>"
                "<form method='post' action='/admin/orders/update' class='rowform'>"
                f"<input type='hidden' name='order_id' value='{int(r['id'])}'>"
                "<select class='select' name='status'>"
                "<option value='new'>new</option>"
                "<option value='paid'>paid</option>"
                "<option value='delivered'>delivered</option>"
                "<option value='cancelled'>cancelled</option>"
                "</select>"
                "<button class='btn' type='submit'>Set</button>"
                "</form>"
                "</td>"
                "</tr>"
            )

        body += "</tbody></table></div>"
        return _layout("Orders", body, active="orders")

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
        return _layout("Referrals", body, active="referrals")

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
        return _layout("Topups", body, active="topups")

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
        return _layout("Sotib olganlar", body, active="buyers")

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
            body += (
                "<tr>"
                f"<td><code>{int(r['order_id'])}</code></td>"
                f"<td><code>{int(r['user_id'])}</code></td>"
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
        return _layout("Purchases", body, active="purchases")

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
        return _layout("Health", "<div>OK</div>", active="dashboard")

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
            "<div class='meta'>Eslatma: matn HTML parse_mode bilan yuboriladi.</div>"
            "</div>"
        )
        return _layout("Broadcast", body, active="broadcast")

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
        return _layout("Broadcast result", body, active="broadcast")

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
        return _layout("Broadcast photo result", body, active="broadcast")

    def _escape_textarea(s: str) -> str:
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _escape_attr(s: str) -> str:
        return _escape_textarea(s).replace("\"", "&quot;").replace("'", "&#39;")

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
            f"<form method='post' action='{post_url}' class='stack acct-form'>"
            "<div class='field'>"
            "<b>Login</b>"
            "<input class='input' name='login' placeholder='Login' value=''>"
            "</div>"
            "<div class='field'>"
            "<b>Parol</b>"
            "<input class='input' name='password' placeholder='Parol' value=''>"
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
            f"<form method='post' action='{post_url}' class='stack acct-form' style='margin-top:10px'>"
            "<div class='field'>"
            "<b>Login</b>"
            "<input class='input' name='login' placeholder='Login' value=''>"
            "</div>"
            "<div class='field'>"
            "<b>Parol</b>"
            "<input class='input' name='password' placeholder='Parol' value=''>"
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
            "if(!d||!d.ok){alert('Xato'); return;}"
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
        return _layout(title, body, active=active)

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
    ):
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
    ):
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
