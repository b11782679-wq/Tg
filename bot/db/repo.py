import secrets
import aiosqlite

from bot.constants import REF_BONUS_POINTS, REF_MONEY_BONUS_UZS


def _new_ref_code() -> str:
    return secrets.token_urlsafe(8).replace("-", "").replace("_", "")


class Repo:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def _conn(self):
        return aiosqlite.connect(self.db_path)

    async def ensure_user(self, user_id: int, full_name: str, username: str | None, referrer_id: int | None):
        """
        Userni bazaga kiritadi (agar yo'q bo'lsa).
        Eslatma: Referral pul/bonus berish bu yerda qilinmaydi.
        """
        async with await self._conn() as db:
            db.row_factory = aiosqlite.Row

            # Race condition'ni oldini olish uchun idempotent upsert.
            ref_code = _new_ref_code()
            safe_referrer_id = None
            if referrer_id and int(referrer_id) != int(user_id):
                safe_referrer_id = int(referrer_id)

            await db.execute(
                "INSERT OR IGNORE INTO users(id, full_name, username, referrer_id, referral_code) VALUES(?,?,?,?,?)",
                (int(user_id), str(full_name or ""), username, safe_referrer_id, ref_code),
            )
            await db.execute(
                "INSERT OR IGNORE INTO balances(user_id, points, money_uzs) VALUES(?,?,?)",
                (int(user_id), 0, 0),
            )

            # Har doim username/full_name yangilab turamiz (foydalanuvchi o'zgartirishi mumkin)
            await db.execute(
                "UPDATE users SET full_name=?, username=? WHERE id=?",
                (str(full_name or ""), username, int(user_id)),
            )

            # Referrer faqat birinchi marta o'rnatilsin.
            if safe_referrer_id is not None:
                await db.execute(
                    "UPDATE users SET referrer_id=? WHERE id=? AND referrer_id IS NULL",
                    (int(safe_referrer_id), int(user_id)),
                )

            await db.commit()

    async def get_user(self, user_id: int):
        async with await self._conn() as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM users WHERE id=?", (user_id,))
            return await cur.fetchone()

    async def get_user_id_by_ref_code(self, ref_code: str) -> int | None:
        ref_code = (ref_code or "").strip()
        if ref_code == "":
            return None
        async with await self._conn() as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT id FROM users WHERE referral_code=?", (ref_code,))
            row = await cur.fetchone()
            return int(row["id"]) if row else None

    async def get_balance(self, user_id: int):
        async with await self._conn() as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM balances WHERE user_id=?", (user_id,))
            return await cur.fetchone()

    async def add_money(self, user_id: int, amount_uzs: int):
        async with await self._conn() as db:
            await db.execute(
                "UPDATE balances SET money_uzs=money_uzs+?, updated_at=datetime('now') WHERE user_id=?",
                (amount_uzs, user_id),
            )
            await db.commit()

    async def deduct_money(self, user_id: int, amount_uzs: int) -> bool:
        amount_uzs = int(amount_uzs)
        if amount_uzs <= 0:
            return True

        async with await self._conn() as db:
            await db.execute(
                "INSERT OR IGNORE INTO balances(user_id, points, money_uzs) VALUES(?,?,?)",
                (int(user_id), 0, 0),
            )
            cur = await db.execute(
                "UPDATE balances "
                "SET money_uzs = money_uzs - ?, updated_at=datetime('now') "
                "WHERE user_id = ? AND money_uzs >= ?",
                (amount_uzs, int(user_id), amount_uzs),
            )
            await db.commit()
            return (cur.rowcount or 0) > 0

    async def admin_add_product_account(self, product_key: str, login: str, password: str) -> int:
        async with await self._conn() as db:
            cur = await db.execute(
                "INSERT INTO product_accounts(product_key, login, password, status) VALUES(?,?,?, 'available')",
                (str(product_key), login or "", password or ""),
            )
            await db.commit()
            return int(cur.lastrowid or 0)

    async def admin_list_available_product_accounts(self, product_key: str, limit: int = 200):
        limit = min(max(int(limit), 1), 500)
        async with await self._conn() as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT id, product_key, login, password, created_at FROM product_accounts "
                "WHERE product_key=? AND status='available' ORDER BY id ASC LIMIT ?",
                (str(product_key), limit),
            )
            return await cur.fetchall()

    async def admin_delete_product_account(self, product_key: str, account_id: int) -> bool:
        async with await self._conn() as db:
            cur = await db.execute(
                "DELETE FROM product_accounts WHERE id=? AND product_key=? AND status='available'",
                (int(account_id), str(product_key)),
            )
            await db.commit()
            return (cur.rowcount or 0) > 0

    async def admin_update_product_account(self, product_key: str, account_id: int, login: str, password: str) -> bool:
        async with await self._conn() as db:
            cur = await db.execute(
                "UPDATE product_accounts SET login=?, password=? WHERE id=? AND product_key=? AND status='available'",
                (login or "", password or "", int(account_id), str(product_key)),
            )
            await db.commit()
            return (cur.rowcount or 0) > 0

    async def admin_list_purchases(self, limit: int = 200):
        limit = min(max(int(limit), 1), 500)
        query = """
        SELECT
            o.id as order_id,
            o.user_id,
            o.product_key,
            o.plan_key,
            o.price_uzs,
            o.status,
            o.created_at,
            a.login as account_login,
            a.password as account_password,
            a.assigned_at
        FROM product_orders o
        LEFT JOIN product_accounts a ON a.assigned_order_id = o.id
        ORDER BY o.created_at DESC
        LIMIT ?
        """
        async with await self._conn() as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(query, (limit,))
            return await cur.fetchall()

    async def admin_list_paid_topups(self, limit: int = 200):
        limit = min(max(int(limit), 1), 500)
        query = """
        SELECT
            t.id,
            t.user_id,
            COALESCE(u.full_name, '') AS full_name,
            COALESCE(u.username, '') AS username,
            t.provider,
            t.amount_uzs,
            t.status,
            t.created_at,
            t.proof_file_id,
            t.proof_type
        FROM topups t
        LEFT JOIN users u ON u.id = t.user_id
        WHERE t.status='paid'
        ORDER BY t.created_at DESC
        LIMIT ?
        """
        async with await self._conn() as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(query, (limit,))
            return await cur.fetchall()

    async def expire_old_assigned_accounts(self, days: int = 7) -> int:
        days = max(int(days), 1)
        async with await self._conn() as db:
            cur = await db.execute(
                "UPDATE product_accounts "
                "SET status='expired' "
                "WHERE status='assigned' AND assigned_at IS NOT NULL AND assigned_at < datetime('now', ?) ",
                (f"-{days} days",),
            )
            await db.commit()
            return int(cur.rowcount or 0)

    async def get_recent_user_accounts(self, user_id: int, days: int = 7, limit: int = 10):
        days = max(int(days), 1)
        limit = min(max(int(limit), 1), 50)
        async with await self._conn() as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT product_key, login, password, assigned_at, assigned_order_id "
                "FROM product_accounts "
                "WHERE assigned_user_id=? AND status='assigned' AND assigned_at IS NOT NULL "
                "AND assigned_at >= datetime('now', ?) "
                "ORDER BY assigned_at DESC "
                "LIMIT ?",
                (int(user_id), f"-{days} days", limit),
            )
            return await cur.fetchall()

    async def purchase_account(self, user_id: int, product_key: str, plan_key: str, price_uzs: int) -> tuple[bool, str, dict | None]:
        """Returns (ok, reason, payload).
        reason: ok/no_stock/no_money/race
        payload: {order_id, login, password}
        """

        user_id = int(user_id)
        product_key = str(product_key)
        plan_key = str(plan_key)
        price_uzs = int(price_uzs)

        async with await self._conn() as db:
            db.row_factory = aiosqlite.Row

            for _ in range(3):
                await db.execute("BEGIN IMMEDIATE")

                await db.execute(
                    "INSERT OR IGNORE INTO balances(user_id, points, money_uzs) VALUES(?,?,?)",
                    (user_id, 0, 0),
                )

                cur = await db.execute(
                    "SELECT id, login, password FROM product_accounts "
                    "WHERE product_key=? AND status='available' ORDER BY id ASC LIMIT 1",
                    (product_key,),
                )
                acc = await cur.fetchone()
                if not acc:
                    await db.execute("ROLLBACK")
                    return False, "no_stock", None

                cur = await db.execute(
                    "UPDATE balances SET money_uzs = money_uzs - ?, updated_at=datetime('now') "
                    "WHERE user_id = ? AND money_uzs >= ?",
                    (price_uzs, user_id, price_uzs),
                )
                if (cur.rowcount or 0) <= 0:
                    await db.execute("ROLLBACK")
                    return False, "no_money", None

                cur = await db.execute(
                    "INSERT INTO product_orders(user_id, product_key, plan_key, price_uzs, status) VALUES(?,?,?,?, 'paid')",
                    (user_id, product_key, plan_key, price_uzs),
                )
                order_id = int(cur.lastrowid or 0)

                cur = await db.execute(
                    "UPDATE product_accounts SET status='assigned', assigned_user_id=?, assigned_order_id=?, assigned_at=datetime('now') "
                    "WHERE id=? AND status='available'",
                    (user_id, order_id, int(acc["id"])),
                )
                if (cur.rowcount or 0) <= 0:
                    await db.execute("ROLLBACK")
                    continue

                await db.commit()
                return True, "ok", {
                    "order_id": order_id,
                    "login": str(acc["login"] or ""),
                    "password": str(acc["password"] or ""),
                }

            return False, "race", None

    async def deduct_points(self, user_id: int, points: int) -> bool:
        async with await self._conn() as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT points FROM balances WHERE user_id=?", (user_id,))
            row = await cur.fetchone()
            if not row or int(row["points"]) < points:
                return False
            await db.execute(
                "UPDATE balances SET points=points-?, updated_at=datetime('now') WHERE user_id=?",
                (points, user_id),
            )
            await db.commit()
            return True

    async def create_topup(self, user_id: int, provider: str, amount_uzs: int, provider_invoice_id: str | None = None) -> int:
        async with await self._conn() as db:
            cur = await db.execute(
                "INSERT INTO topups(user_id, provider, amount_uzs, provider_invoice_id) VALUES(?,?,?,?)",
                (user_id, provider, amount_uzs, provider_invoice_id),
            )
            await db.commit()
            return cur.lastrowid

    async def find_pending_manual_topup_needing_proof(self, user_id: int):
        async with await self._conn() as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT id, amount_uzs, created_at FROM topups "
                "WHERE user_id=? AND provider='manual' AND status='pending' "
                "AND (proof_file_id IS NULL OR proof_file_id='') "
                "ORDER BY id DESC LIMIT 1",
                (int(user_id),),
            )
            return await cur.fetchone()

    async def attach_topup_proof(self, topup_id: int, user_id: int, proof_file_id: str, proof_type: str, proof_caption: str = "") -> bool:
        async with await self._conn() as db:
            cur = await db.execute(
                "UPDATE topups SET proof_file_id=?, proof_type=?, proof_caption=? "
                "WHERE id=? AND user_id=? AND provider='manual' AND status='pending' "
                "AND (proof_file_id IS NULL OR proof_file_id='')",
                (str(proof_file_id), str(proof_type), str(proof_caption or ""), int(topup_id), int(user_id)),
            )
            await db.commit()
            return int(cur.rowcount or 0) > 0

    async def set_topup_status(self, topup_id: int, status: str):
        async with await self._conn() as db:
            await db.execute("UPDATE topups SET status=? WHERE id=?", (status, topup_id))
            await db.commit()

    async def get_admin_stats(self) -> dict:
        async with await self._conn() as db:
            cur = await db.execute("SELECT COUNT(*) FROM users")
            users = int((await cur.fetchone() or [0])[0])

            cur = await db.execute("SELECT COUNT(*) FROM product_orders")
            orders = int((await cur.fetchone() or [0])[0])

            cur = await db.execute("SELECT COUNT(*) FROM topups")
            topups = int((await cur.fetchone() or [0])[0])

            cur = await db.execute("SELECT COUNT(*) FROM topups WHERE status='paid'")
            paid_topups = int((await cur.fetchone() or [0])[0])

            return {
                "users": users,
                "orders": orders,
                "topups": topups,
                "paid_topups": paid_topups,
            }

    async def admin_referral_top(self, limit: int = 50):
        limit = min(max(int(limit), 1), 200)
        query = """
        SELECT
            r.referrer_id,
            COALESCE(u.full_name, '') AS full_name,
            COALESCE(u.username, '') AS username,
            COUNT(*) AS invited,
            SUM(CASE WHEN r.rewarded=1 THEN 1 ELSE 0 END) AS rewarded_count,
            SUM(CASE WHEN r.rewarded=1 THEN ? ELSE 0 END) AS total_bonus_uzs
        FROM referrals r
        LEFT JOIN users u ON u.id = r.referrer_id
        GROUP BY r.referrer_id
        ORDER BY invited DESC
        LIMIT ?
        """
        async with await self._conn() as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(query, (REF_MONEY_BONUS_UZS, limit))
            return await cur.fetchall()

    async def admin_get_texts(self, key: str) -> tuple[str, str]:
        async with await self._conn() as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT save_text, send_text FROM admin_texts WHERE key=?", (key,))
            row = await cur.fetchone()
            if not row:
                return "", ""
            return str(row["save_text"] or ""), str(row["send_text"] or "")

    async def admin_set_texts(self, key: str, save_text: str, send_text: str):
        async with await self._conn() as db:
            await db.execute(
                "INSERT INTO admin_texts(key, save_text, send_text) VALUES(?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET save_text=excluded.save_text, send_text=excluded.send_text, updated_at=datetime('now')",
                (key, save_text or "", send_text or ""),
            )
            await db.commit()

    async def admin_get_user_account(self, user_id: int, product_key: str) -> tuple[str, str]:
        async with await self._conn() as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT login, password FROM user_accounts WHERE user_id=? AND product_key=?",
                (int(user_id), str(product_key)),
            )
            row = await cur.fetchone()
            if not row:
                return "", ""
            return str(row["login"] or ""), str(row["password"] or "")

    async def admin_set_user_account(self, user_id: int, product_key: str, login: str, password: str):
        async with await self._conn() as db:
            await db.execute(
                "INSERT INTO user_accounts(user_id, product_key, login, password) VALUES(?,?,?,?) "
                "ON CONFLICT(user_id, product_key) DO UPDATE SET login=excluded.login, password=excluded.password, updated_at=datetime('now')",
                (int(user_id), str(product_key), login or "", password or ""),
            )
            await db.commit()

    async def admin_list_users(self, q: str | None, limit: int = 200):
        q = (q or "").strip()
        limit = min(max(int(limit), 1), 500)

        where = "1=1"
        params: list[object] = []

        if q:
            if q.isdigit():
                where = "u.id = ?"
                params.append(int(q))
            else:
                where = "(u.full_name LIKE ? OR u.username LIKE ?)"
                like = f"%{q}%"
                params.extend([like, like])

        query = f"""
        SELECT
            u.id,
            u.full_name,
            u.username,
            COALESCE(b.money_uzs, 0) AS money_uzs,
            COALESCE(b.points, 0) AS points
        FROM users u
        LEFT JOIN balances b ON b.user_id = u.id
        WHERE {where}
        ORDER BY u.created_at DESC
        LIMIT ?
        """

        async with await self._conn() as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(query, (*params, limit))
            return await cur.fetchall()

    async def admin_get_topup(self, topup_id: int):
        async with await self._conn() as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT id, user_id, provider, amount_uzs, status, provider_invoice_id, "
                "proof_file_id, proof_type, proof_caption, created_at "
                "FROM topups WHERE id=?",
                (int(topup_id),),
            )
            return await cur.fetchone()

    async def admin_delete_topup(self, topup_id: int) -> int:
        async with await self._conn() as db:
            cur = await db.execute("DELETE FROM topups WHERE id=?", (int(topup_id),))
            await db.commit()
            return int(cur.rowcount or 0)

    async def admin_apply_balance_delta(self, user_id: int, money_delta: int, points_delta: int):
        async with await self._conn() as db:
            await db.execute(
                "INSERT OR IGNORE INTO balances(user_id, points, money_uzs) VALUES(?,?,?)",
                (user_id, 0, 0),
            )
            await db.execute(
                "UPDATE balances SET money_uzs=money_uzs+?, points=points+?, updated_at=datetime('now') WHERE user_id=?",
                (int(money_delta), int(points_delta), int(user_id)),
            )
            await db.commit()

    async def admin_delete_user(self, user_id: int) -> int:
        user_id = int(user_id)
        async with await self._conn() as db:
            await db.execute("BEGIN IMMEDIATE")

            await db.execute(
                "UPDATE product_accounts "
                "SET status='expired', assigned_user_id=NULL, assigned_order_id=NULL "
                "WHERE assigned_user_id=?",
                (user_id,),
            )

            await db.execute("DELETE FROM user_accounts WHERE user_id=?", (user_id,))
            await db.execute("DELETE FROM product_orders WHERE user_id=?", (user_id,))
            await db.execute("DELETE FROM topups WHERE user_id=?", (user_id,))
            await db.execute(
                "DELETE FROM referrals WHERE referrer_id=? OR invited_id=?",
                (user_id, user_id),
            )
            await db.execute("DELETE FROM balances WHERE user_id=?", (user_id,))
            cur = await db.execute("DELETE FROM users WHERE id=?", (user_id,))

            await db.commit()
            return int(cur.rowcount or 0)

    async def admin_list_orders(self, status: str | None, limit: int = 200):
        status = (status or "").strip()
        limit = min(max(int(limit), 1), 500)

        where = "1=1"
        params: list[object] = []
        if status:
            where = "status = ?"
            params.append(status)

        query = f"""
        SELECT id, user_id, product_key, plan_key, price_uzs, status, created_at
        FROM product_orders
        WHERE {where}
        ORDER BY created_at DESC
        LIMIT ?
        """

        async with await self._conn() as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(query, (*params, limit))
            return await cur.fetchall()

    async def admin_set_order_status(self, order_id: int, status: str):
        allowed = {"new", "paid", "delivered", "cancelled"}
        if status not in allowed:
            raise ValueError("Invalid status")

        async with await self._conn() as db:
            await db.execute("UPDATE product_orders SET status=? WHERE id=?", (status, int(order_id)))
            await db.commit()

    async def admin_list_topups(self, status: str | None, limit: int = 200):
        status = (status or "").strip()
        limit = min(max(int(limit), 1), 500)

        where = "1=1"
        params: list[object] = []
        if status:
            where = "status = ?"
            params.append(status)

        query = f"""
        SELECT
            t.id,
            t.user_id,
            COALESCE(u.username, '') AS username,
            COALESCE(u.full_name, '') AS full_name,
            t.provider,
            t.amount_uzs,
            t.status,
            t.provider_invoice_id,
            t.proof_file_id,
            t.proof_type,
            t.proof_caption,
            t.created_at
        FROM topups t
        LEFT JOIN users u ON u.id = t.user_id
        WHERE {where}
        ORDER BY t.created_at DESC
        LIMIT ?
        """

        async with await self._conn() as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(query, (*params, limit))
            return await cur.fetchall()

    async def admin_set_topup_status(self, topup_id: int, status: str):
        allowed = {"pending", "paid", "failed", "cancelled"}
        if status not in allowed:
            raise ValueError("Invalid status")

        async with await self._conn() as db:
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")

            cur = await db.execute(
                "SELECT user_id, amount_uzs, status FROM topups WHERE id=?",
                (int(topup_id),),
            )
            row = await cur.fetchone()
            if not row:
                await db.execute("ROLLBACK")
                return

            prev_status = str(row["status"] or "")
            user_id = int(row["user_id"])
            amount_uzs = int(row["amount_uzs"])

            await db.execute("UPDATE topups SET status=? WHERE id=?", (status, int(topup_id)))

            if status == "paid" and prev_status != "paid":
                await db.execute(
                    "INSERT OR IGNORE INTO balances(user_id, points, money_uzs) VALUES(?,?,?)",
                    (user_id, 0, 0),
                )
                await db.execute(
                    "UPDATE balances SET money_uzs=money_uzs+?, updated_at=datetime('now') WHERE user_id=?",
                    (amount_uzs, user_id),
                )

            await db.commit()

    # =========================
    # Referral stats
    # =========================
    async def get_ref_stats(self, user_id: int) -> dict:
        async with await self._conn() as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT COUNT(*) as c FROM referrals WHERE referrer_id=?", (user_id,))
            row = await cur.fetchone()
            return {"invited": int(row["c"] if row else 0)}

    # ✅ referral linkdan start bo'lganda 1 marta yozib qo'yish
    async def create_referral_if_new(self, referrer_id: int, invited_id: int) -> bool:
        """
        referrals jadvaliga (referrer_id, invited_id) ni 1 marta qo'shadi.
        True => yangi referral yaratildi
        False => oldin ham bor edi (yoki xato)
        """
        async with await self._conn() as db:
            try:
                await db.execute(
                    "INSERT INTO referrals(referrer_id, invited_id, rewarded) VALUES(?,?,0)",
                    (referrer_id, invited_id),
                )
                await db.commit()
                return True
            except Exception:
                return False

    # ✅ invited kanalga a'zo bo'lganda referrerga 2000 so'm berish (faqat 1 marta)
    async def reward_referrer_if_needed(self, invited_id: int) -> tuple[int, int] | None:
        """
        Return: (referrer_id, amount) yoki None
        """
        async with await self._conn() as db:
            db.row_factory = aiosqlite.Row

            cur = await db.execute("SELECT referrer_id FROM users WHERE id=?", (invited_id,))
            u = await cur.fetchone()
            if not u or not u["referrer_id"]:
                return None

            referrer_id = int(u["referrer_id"])

            cur = await db.execute(
                "SELECT rewarded FROM referrals WHERE referrer_id=? AND invited_id=?",
                (referrer_id, invited_id),
            )
            r = await cur.fetchone()
            if not r or int(r["rewarded"]) == 1:
                return None

            # ✅ money bonus
            await db.execute(
                "INSERT OR IGNORE INTO balances(user_id, points, money_uzs) VALUES(?,?,?)",
                (referrer_id, 0, 0),
            )
            await db.execute(
                "UPDATE balances SET money_uzs = money_uzs + ?, updated_at=datetime('now') WHERE user_id=?",
                (REF_MONEY_BONUS_UZS, referrer_id),
            )
            await db.execute(
                "UPDATE referrals SET rewarded=1 WHERE referrer_id=? AND invited_id=?",
                (referrer_id, invited_id),
            )
            await db.commit()

            return (referrer_id, REF_MONEY_BONUS_UZS)

    async def reward_referrer_by_pair(self, referrer_id: int, invited_id: int) -> tuple[int, int] | None:
        """Bonusni referrer/invited juftligi bo'yicha beradi.
        Kick qilingan user qayta /start qilganda ham ishlashi uchun.
        Return: (referrer_id, amount) yoki None
        """

        referrer_id = int(referrer_id)
        invited_id = int(invited_id)
        if referrer_id <= 0 or invited_id <= 0 or referrer_id == invited_id:
            return None

        async with await self._conn() as db:
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")

            await db.execute(
                "INSERT OR IGNORE INTO referrals(referrer_id, invited_id, rewarded) VALUES(?,?,0)",
                (referrer_id, invited_id),
            )

            cur = await db.execute(
                "SELECT rewarded FROM referrals WHERE referrer_id=? AND invited_id=?",
                (referrer_id, invited_id),
            )
            r = await cur.fetchone()
            if not r or int(r["rewarded"] or 0) == 1:
                await db.execute("ROLLBACK")
                return None

            await db.execute(
                "INSERT OR IGNORE INTO balances(user_id, points, money_uzs) VALUES(?,?,?)",
                (referrer_id, 0, 0),
            )
            await db.execute(
                "UPDATE balances SET money_uzs = money_uzs + ?, updated_at=datetime('now') WHERE user_id=?",
                (REF_MONEY_BONUS_UZS, referrer_id),
            )
            await db.execute(
                "UPDATE referrals SET rewarded=1 WHERE referrer_id=? AND invited_id=?",
                (referrer_id, invited_id),
            )
            await db.commit()
            return (referrer_id, REF_MONEY_BONUS_UZS)

    async def activate_ref_action_and_reward(self, invited_id: int) -> tuple[int, int] | None:
        invited_id = int(invited_id)
        async with await self._conn() as db:
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")

            cur = await db.execute("SELECT ref_action_done FROM users WHERE id=?", (invited_id,))
            row = await cur.fetchone()
            if not row:
                await db.execute("ROLLBACK")
                return None

            if int(row["ref_action_done"] or 0) == 0:
                await db.execute(
                    "UPDATE users SET ref_action_done=1 WHERE id=?",
                    (invited_id,),
                )

            cur = await db.execute(
                "SELECT referrer_id FROM referrals WHERE invited_id=? AND rewarded=0 ORDER BY created_at ASC LIMIT 1",
                (invited_id,),
            )
            rr = await cur.fetchone()
            if not rr or not rr["referrer_id"]:
                await db.commit()
                return None

            referrer_id = int(rr["referrer_id"])
            if referrer_id == invited_id:
                await db.commit()
                return None

            await db.execute(
                "INSERT OR IGNORE INTO balances(user_id, points, money_uzs) VALUES(?,?,?)",
                (referrer_id, 0, 0),
            )
            await db.execute(
                "UPDATE balances SET money_uzs = money_uzs + ?, updated_at=datetime('now') WHERE user_id=?",
                (REF_MONEY_BONUS_UZS, referrer_id),
            )
            await db.execute(
                "UPDATE referrals SET rewarded=1 WHERE referrer_id=? AND invited_id=?",
                (referrer_id, invited_id),
            )
            await db.commit()
            return (referrer_id, REF_MONEY_BONUS_UZS)

    # =========================
    # Stats
    # =========================
    async def get_orders_count(self, user_id: int) -> int:
        async with await self._conn() as db:
            cur = await db.execute("SELECT COUNT(*) FROM product_orders WHERE user_id=?", (user_id,))
            row = await cur.fetchone()
            return int(row[0] if row else 0)

    async def get_rank_by_points(self, user_id: int) -> tuple[int, int, int]:
        """
        Rank points bo'yicha:
        - rank: 1 = eng yuqori
        - points: user points
        - total: jami userlar
        """
        async with await self._conn() as db:
            db.row_factory = aiosqlite.Row

            cur = await db.execute("SELECT points FROM balances WHERE user_id=?", (user_id,))
            row = await cur.fetchone()
            points = int(row["points"]) if row else 0

            cur = await db.execute("SELECT COUNT(*) as total FROM users")
            total_row = await cur.fetchone()
            total = int(total_row["total"] if total_row else 0)

            cur = await db.execute("SELECT COUNT(*) as better FROM balances WHERE points > ?", (points,))
            better_row = await cur.fetchone()
            better = int(better_row["better"] if better_row else 0)

            rank = (better + 1) if total > 0 else 1
            return rank, points, total

    # =========================
    # Top-5 leaderboard
    # =========================
    async def get_topup_leaderboard(self, period: str, limit: int = 5):
        """
        period: today | week | month | all
        return: list[(user_id, name, total_uzs)]
        """
        if period == "today":
            where = "t.created_at >= datetime('now','start of day')"
        elif period == "week":
            where = "t.created_at >= datetime('now','-6 days')"  # oxirgi 7 kun
        elif period == "month":
            where = "t.created_at >= datetime('now','start of month')"
        else:
            where = "1=1"  # all time

        query = f"""
        SELECT
            u.id AS user_id,
            COALESCE(NULLIF(u.full_name,''), COALESCE(u.username,'User')) AS name,
            SUM(t.amount_uzs) AS total
        FROM topups t
        JOIN users u ON u.id = t.user_id
        WHERE t.status='paid' AND ({where})
        GROUP BY u.id
        ORDER BY total DESC
        LIMIT ?
        """

        async with await self._conn() as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(query, (limit,))
            rows = await cur.fetchall()

            out = []
            for r in rows:
                out.append((int(r["user_id"]), str(r["name"]), int(r["total"] or 0)))
            return out
