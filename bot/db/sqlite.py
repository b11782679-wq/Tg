import aiosqlite

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  full_name TEXT,
  username TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  referrer_id INTEGER,
  referral_code TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS balances (
  user_id INTEGER PRIMARY KEY,
  points INTEGER NOT NULL DEFAULT 0,
  money_uzs INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS referrals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  referrer_id INTEGER NOT NULL,
  invited_id INTEGER NOT NULL,
  rewarded INTEGER NOT NULL DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now')),
  UNIQUE(referrer_id, invited_id)
);

CREATE TABLE IF NOT EXISTS product_orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  product_key TEXT NOT NULL,
  plan_key TEXT NOT NULL,
  price_uzs INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'new',  -- new/paid/delivered/cancelled
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS topups (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  provider TEXT NOT NULL,            -- click/payme/manual
  amount_uzs INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',   -- pending/paid/failed/cancelled
  provider_invoice_id TEXT,
  proof_file_id TEXT,
  proof_type TEXT,
  proof_caption TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS admin_texts (
  key TEXT PRIMARY KEY,
  save_text TEXT NOT NULL DEFAULT '',
  send_text TEXT NOT NULL DEFAULT '',
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_accounts (
  user_id INTEGER NOT NULL,
  product_key TEXT NOT NULL,
  login TEXT NOT NULL DEFAULT '',
  password TEXT NOT NULL DEFAULT '',
  updated_at TEXT DEFAULT (datetime('now')),
  PRIMARY KEY(user_id, product_key)
);

CREATE TABLE IF NOT EXISTS product_accounts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  product_key TEXT NOT NULL,
  login TEXT NOT NULL,
  password TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'available',
  created_at TEXT DEFAULT (datetime('now')),
  assigned_user_id INTEGER,
  assigned_order_id INTEGER,
  assigned_at TEXT
);

CREATE TABLE IF NOT EXISTS youtuber_audits (
  user_id INTEGER PRIMARY KEY,
  channel_data_json TEXT NOT NULL DEFAULT '',
  audit_text TEXT NOT NULL DEFAULT '',
  issues_json TEXT NOT NULL DEFAULT '[]',
  updated_at TEXT DEFAULT (datetime('now'))
);
"""

async def init_db(db_path: str):
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(SCHEMA)

        cur = await db.execute("PRAGMA table_info(users)")
        user_cols = {str(r[1]).lower() for r in await cur.fetchall()}
        if "ref_action_done" not in user_cols:
            await db.execute("ALTER TABLE users ADD COLUMN ref_action_done INTEGER NOT NULL DEFAULT 0")
        if "language" not in user_cols:
            await db.execute("ALTER TABLE users ADD COLUMN language TEXT NOT NULL DEFAULT 'uz'")
        if "blocked" not in user_cols:
            await db.execute("ALTER TABLE users ADD COLUMN blocked INTEGER NOT NULL DEFAULT 0")

        cur = await db.execute("PRAGMA table_info(referrals)")
        cols = {str(r[1]).lower() for r in await cur.fetchall()}
        if "rewarded" not in cols:
            await db.execute("ALTER TABLE referrals ADD COLUMN rewarded INTEGER NOT NULL DEFAULT 0")

        cur = await db.execute("PRAGMA table_info(topups)")
        topup_cols = {str(r[1]).lower() for r in await cur.fetchall()}
        if "proof_file_id" not in topup_cols:
            await db.execute("ALTER TABLE topups ADD COLUMN proof_file_id TEXT")
        if "proof_type" not in topup_cols:
            await db.execute("ALTER TABLE topups ADD COLUMN proof_type TEXT")
        if "proof_caption" not in topup_cols:
            await db.execute("ALTER TABLE topups ADD COLUMN proof_caption TEXT")

        cur = await db.execute("PRAGMA table_info(product_orders)")
        order_cols = {str(r[1]).lower() for r in await cur.fetchall()}
        if "pay_type" not in order_cols:
            await db.execute("ALTER TABLE product_orders ADD COLUMN pay_type TEXT NOT NULL DEFAULT 'money'")
        if "points_cost" not in order_cols:
            await db.execute("ALTER TABLE product_orders ADD COLUMN points_cost INTEGER NOT NULL DEFAULT 0")

        await db.commit()
