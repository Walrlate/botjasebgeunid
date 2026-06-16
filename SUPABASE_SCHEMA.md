# Skema Database Supabase - GeunID Jaseb (PostgreSQL)

Silakan **Copy** semua kode SQL di bawah ini dan **Paste** ke dalam **SQL Editor** di Dashboard Supabase Anda, lalu klik **RUN**.

```sql
-- ==========================================
-- GEUNID JASEB - SUPABASE POSTGRESQL SCHEMA
-- ==========================================

-- 1. Table Users
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    joined_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 2. Table Subscriptions
CREATE TABLE IF NOT EXISTS subscriptions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    package_name TEXT,
    capacity_lpm INTEGER,
    start_date TIMESTAMPTZ,
    end_date TIMESTAMPTZ,
    status TEXT DEFAULT 'active',
    request_lpm TEXT,
    broadcast_interval_hours REAL DEFAULT 0.5
);

-- 3. Table User Ads
CREATE TABLE IF NOT EXISTS user_ads (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    title TEXT,
    content TEXT,
    media_path TEXT,
    fwd_chat_id TEXT,
    fwd_peer_type TEXT,
    fwd_msg_id BIGINT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 4. Table LPM Lists
CREATE TABLE IF NOT EXISTS lpm_lists (
    id BIGSERIAL PRIMARY KEY,
    group_link TEXT UNIQUE,
    group_id BIGINT,
    group_name TEXT,
    member_count INTEGER DEFAULT 0,
    last_active TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    is_blacklisted BOOLEAN DEFAULT FALSE
);

-- 5. Table Transactions
CREATE TABLE IF NOT EXISTS transactions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    trx_id TEXT UNIQUE,
    package_id TEXT,
    amount INTEGER,
    status TEXT DEFAULT 'pending',
    payment_url TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 6. Table Forward Logs
CREATE TABLE IF NOT EXISTS forward_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    ad_id BIGINT REFERENCES user_ads(id) ON DELETE SET NULL,
    group_id BIGINT,
    msg_link TEXT,
    status TEXT,
    error_msg TEXT,
    sent_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 7. Table Userbots (Client)
CREATE TABLE IF NOT EXISTS userbots (
    user_id BIGINT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    phone_number TEXT,
    session_name TEXT, 
    status TEXT DEFAULT 'disconnected',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 8. Table Admin Userbots (Pool)
CREATE TABLE IF NOT EXISTS admin_userbots (
    id BIGSERIAL PRIMARY KEY,
    phone_number TEXT UNIQUE,
    session_name TEXT, 
    status TEXT DEFAULT 'connected',
    cooldown_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 9. Optimasi Kecepatan (Indexes untuk Dashboard Cepat)
CREATE INDEX IF NOT EXISTS idx_subs_user_active ON subscriptions(user_id, status);
CREATE INDEX IF NOT EXISTS idx_trans_trxid ON transactions(trx_id);
CREATE INDEX IF NOT EXISTS idx_fwd_user ON forward_logs(user_id);
```