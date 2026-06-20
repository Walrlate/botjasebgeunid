-- SQL Migration Update - GEUNID JASEB Enterprise
-- Salin dan jalankan seluruh kode di bawah ini di SQL Editor Supabase Anda.

-- 1. Tambahkan kolom baru ke tabel subscriptions jika belum ada
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS broadcast_interval_hours DOUBLE PRECISION DEFAULT 0.5;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS schedule_start_hour INTEGER DEFAULT 0;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS schedule_end_hour INTEGER DEFAULT 23;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS assigned_admin_ub_id INTEGER;

-- 2. Tambahkan kolom baru ke tabel user_ads (iklan promosi admin) jika belum ada
ALTER TABLE user_ads ADD COLUMN IF NOT EXISTS buttons_json TEXT;

-- 3. Buat tabel admin_userbots jika belum terbentuk
CREATE TABLE IF NOT EXISTS admin_userbots (
    id SERIAL PRIMARY KEY,
    phone_number TEXT UNIQUE,
    session_name TEXT,
    status TEXT DEFAULT 'connected',
    cooldown_until TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    lpm_description TEXT DEFAULT 'Total LPM 100 Campur'
);
ALTER TABLE admin_userbots ADD COLUMN IF NOT EXISTS lpm_description TEXT DEFAULT 'Total LPM 100 Campur';

-- 4. Buat tabel auto_replies jika belum terbentuk
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

-- 5. Buat tabel custom_target_messages jika belum terbentuk
CREATE TABLE IF NOT EXISTS custom_target_messages (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    target_peer TEXT NOT NULL,
    custom_message TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, target_peer)
);

-- 6. Pasang foreign key constraint relasi bot admin pool
ALTER TABLE subscriptions DROP CONSTRAINT IF EXISTS fk_assigned_admin_ub;
ALTER TABLE subscriptions ADD CONSTRAINT fk_assigned_admin_ub FOREIGN KEY (assigned_admin_ub_id) REFERENCES admin_userbots(id) ON DELETE SET NULL;
