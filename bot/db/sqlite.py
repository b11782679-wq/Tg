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

CREATE TABLE IF NOT EXISTS product_plan_prices (
  product_key TEXT NOT NULL,
  plan_key TEXT NOT NULL,
  price_uzs INTEGER NOT NULL,
  updated_at TEXT DEFAULT (datetime('now')),
  PRIMARY KEY(product_key, plan_key)
);

CREATE TABLE IF NOT EXISTS product_plan_labels (
  product_key TEXT NOT NULL,
  plan_key TEXT NOT NULL,
  label TEXT NOT NULL,
  updated_at TEXT DEFAULT (datetime('now')),
  PRIMARY KEY(product_key, plan_key)
);

CREATE TABLE IF NOT EXISTS youtube_oauth_states (
  state TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS youtube_oauth_tokens (
  user_id INTEGER PRIMARY KEY,
  token_json TEXT NOT NULL DEFAULT '',
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS youtube_pending_uploads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  file_path TEXT NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  visibility TEXT NOT NULL DEFAULT 'private',
  timezone TEXT NOT NULL DEFAULT '',
  scheduled_at TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  error TEXT NOT NULL DEFAULT '',
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now')),
  -- Extended metadata fields
  made_for_kids INTEGER DEFAULT 0,
  tags TEXT DEFAULT '',
  category TEXT DEFAULT '',
  language TEXT DEFAULT '',
  recording_date TEXT,
  video_location TEXT DEFAULT '',
  licence TEXT DEFAULT 'Standard YouTube licence',
  allow_embedding INTEGER DEFAULT 1,
  shorts_remixing TEXT DEFAULT 'allow_video_audio',
  comments TEXT DEFAULT 'on',
  age_restricted INTEGER DEFAULT 0,
  paid_promotion INTEGER DEFAULT 0,
  altered_content INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS youtube_upload_drafts (
  user_id INTEGER PRIMARY KEY,
  step TEXT NOT NULL DEFAULT '',
  file_path TEXT NOT NULL DEFAULT '',
  title TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  visibility TEXT NOT NULL DEFAULT 'private',
  timezone TEXT NOT NULL DEFAULT '',
  scheduled_at TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now')),
  -- Extended metadata fields
  made_for_kids INTEGER DEFAULT 0,
  tags TEXT DEFAULT '',
  category TEXT DEFAULT '',
  language TEXT DEFAULT '',
  recording_date TEXT,
  video_location TEXT DEFAULT '',
  licence TEXT DEFAULT 'Standard YouTube licence',
  allow_embedding INTEGER DEFAULT 1,
  shorts_remixing TEXT DEFAULT 'allow_video_audio',
  comments TEXT DEFAULT 'on',
  age_restricted INTEGER DEFAULT 0,
  paid_promotion INTEGER DEFAULT 0,
  altered_content INTEGER DEFAULT 0
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

        # Add extended metadata columns to youtube_pending_uploads
        cur = await db.execute("PRAGMA table_info(youtube_pending_uploads)")
        pending_cols = {str(r[1]).lower() for r in await cur.fetchall()}
        metadata_cols = [
            ("made_for_kids", "INTEGER DEFAULT 0"),
            ("tags", "TEXT DEFAULT ''"),
            ("category", "TEXT DEFAULT ''"),
            ("language", "TEXT DEFAULT ''"),
            ("recording_date", "TEXT"),
            ("video_location", "TEXT DEFAULT ''"),
            ("licence", "TEXT DEFAULT 'Standard YouTube licence'"),
            ("allow_embedding", "INTEGER DEFAULT 1"),
            ("shorts_remixing", "TEXT DEFAULT 'allow_video_audio'"),
            ("comments", "TEXT DEFAULT 'on'"),
            ("age_restricted", "INTEGER DEFAULT 0"),
            ("paid_promotion", "INTEGER DEFAULT 0"),
            ("altered_content", "INTEGER DEFAULT 0"),
        ]
        for col_name, col_type in metadata_cols:
            if col_name not in pending_cols:
                await db.execute(f"ALTER TABLE youtube_pending_uploads ADD COLUMN {col_name} {col_type}")

        # Add extended metadata columns to youtube_upload_drafts
        cur = await db.execute("PRAGMA table_info(youtube_upload_drafts)")
        draft_cols = {str(r[1]).lower() for r in await cur.fetchall()}
        for col_name, col_type in metadata_cols:
            if col_name not in draft_cols:
                await db.execute(f"ALTER TABLE youtube_upload_drafts ADD COLUMN {col_name} {col_type}")

        await db.commit()
