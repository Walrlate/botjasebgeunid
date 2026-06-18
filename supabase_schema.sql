-- SQL Schema untuk Supabase (PostgreSQL)
-- GeunID Jaseb Master - Enterprise Edition
-- Jalankan kode ini di SQL Editor Supabase Anda.

-- 1. Table Users
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Table Subscriptions
CREATE TABLE IF NOT EXISTS subscriptions (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    package_name TEXT,
    capacity_lpm INTEGER,
    start_date TIMESTAMP WITH TIME ZONE,
    end_date TIMESTAMP WITH TIME ZONE,
    status TEXT DEFAULT 'active',
    request_lpm TEXT,
    broadcast_interval_hours DOUBLE PRECISION DEFAULT 0.5,
    schedule_start_hour INTEGER DEFAULT 0,
    schedule_end_hour INTEGER DEFAULT 23,
    assigned_admin_ub_id INTEGER
);

-- 3. Table User Ads
CREATE TABLE IF NOT EXISTS user_ads (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    title TEXT,
    content TEXT,
    media_path TEXT,
    fwd_chat_id TEXT,
    fwd_peer_type TEXT,
    fwd_msg_id BIGINT,
    buttons_json TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Table LPM Lists
CREATE TABLE IF NOT EXISTS lpm_lists (
    id SERIAL PRIMARY KEY,
    group_link TEXT UNIQUE,
    group_id BIGINT,
    group_name TEXT,
    member_count INTEGER DEFAULT 0,
    last_active TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    is_blacklisted BOOLEAN DEFAULT FALSE
);

-- 5. Table Transactions
CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    trx_id TEXT UNIQUE,
    package_id TEXT,
    amount INTEGER,
    status TEXT DEFAULT 'pending',
    payment_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 6. Table Forward Logs
CREATE TABLE IF NOT EXISTS forward_logs (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    ad_id INTEGER REFERENCES user_ads(id) ON DELETE CASCADE,
    group_id BIGINT,
    msg_link TEXT,
    status TEXT,
    error_msg TEXT,
    sent_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 7. Table Userbots
CREATE TABLE IF NOT EXISTS userbots (
    user_id BIGINT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    phone_number TEXT,
    session_name TEXT,
    status TEXT DEFAULT 'disconnected',
    pm_permit_status BOOLEAN DEFAULT FALSE,
    custom_bio TEXT,
    cooldown_until TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 8. Table Admin Userbots
CREATE TABLE IF NOT EXISTS admin_userbots (
    id SERIAL PRIMARY KEY,
    phone_number TEXT UNIQUE,
    session_name TEXT,
    status TEXT DEFAULT 'connected',
    cooldown_until TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tambahkan foreign key untuk assigned_admin_ub_id di subscriptions setelah admin_userbots terbuat
ALTER TABLE subscriptions ADD CONSTRAINT fk_assigned_admin_ub FOREIGN KEY (assigned_admin_ub_id) REFERENCES admin_userbots(id) ON DELETE SET NULL;

-- 9. Table Activation Tokens (Voucher Paket)
CREATE TABLE IF NOT EXISTS activation_tokens (
    token TEXT PRIMARY KEY,
    package_id TEXT NOT NULL,
    lpm_capacity INTEGER DEFAULT 20,
    duration_days INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    used_by BIGINT REFERENCES users(user_id) ON DELETE SET NULL,
    used_at TIMESTAMP WITH TIME ZONE
);

-- 10. Table Auto Replies (WTB Cerdasar)
CREATE TABLE IF NOT EXISTS auto_replies (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    keyword TEXT NOT NULL,
    reply_text TEXT NOT NULL,
    skip_links BOOLEAN DEFAULT TRUE,
    max_char_limit INTEGER DEFAULT 70,
    skip_usernames TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, keyword)
);

-- 11. Table Custom Target Messages
CREATE TABLE IF NOT EXISTS custom_target_messages (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    target_peer TEXT NOT NULL,
    custom_message TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, target_peer)
);
