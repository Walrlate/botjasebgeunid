-- SQL Migration - Sinkronisasi Tipe Data ke BIGINT/BIGSERIAL (Safe Version)
-- Jalankan query ini di SQL Editor Supabase Anda untuk kompatibilitas ID berukuran besar.

-- 1. Lepaskan foreign key constraints yang bergantung pada kolom yang akan diubah
ALTER TABLE subscriptions DROP CONSTRAINT IF EXISTS fk_assigned_admin_ub;
ALTER TABLE forward_logs DROP CONSTRAINT IF EXISTS forward_logs_ad_id_fkey;

-- 2. Ubah tipe kolom primary key id menjadi BIGINT
ALTER TABLE subscriptions ALTER COLUMN id TYPE BIGINT;
ALTER TABLE user_ads ALTER COLUMN id TYPE BIGINT;
ALTER TABLE lpm_lists ALTER COLUMN id TYPE BIGINT;
ALTER TABLE transactions ALTER COLUMN id TYPE BIGINT;
ALTER TABLE forward_logs ALTER COLUMN id TYPE BIGINT;
ALTER TABLE auto_replies ALTER COLUMN id TYPE BIGINT;
ALTER TABLE custom_target_messages ALTER COLUMN id TYPE BIGINT;
ALTER TABLE admin_userbots ALTER COLUMN id TYPE BIGINT;

-- 3. Ubah tipe kolom foreign key di tabel terkait menjadi BIGINT
ALTER TABLE subscriptions ALTER COLUMN assigned_admin_ub_id TYPE BIGINT;
ALTER TABLE forward_logs ALTER COLUMN ad_id TYPE BIGINT;

-- 4. Tambahkan kolom lpm_description ke admin_userbots jika belum ada
ALTER TABLE admin_userbots ADD COLUMN IF NOT EXISTS lpm_description TEXT DEFAULT 'Total LPM 100 Campur';

-- 5. Pasang kembali foreign key constraints
ALTER TABLE subscriptions ADD CONSTRAINT fk_assigned_admin_ub FOREIGN KEY (assigned_admin_ub_id) REFERENCES admin_userbots(id) ON DELETE SET NULL;
ALTER TABLE forward_logs ADD CONSTRAINT forward_logs_ad_id_fkey FOREIGN KEY (ad_id) REFERENCES user_ads(id) ON DELETE CASCADE;

-- 6. Ubah skema tabel userbots agar mendukung bulk (One-to-Many)
ALTER TABLE userbots DROP CONSTRAINT IF EXISTS userbots_pkey CASCADE;
ALTER TABLE userbots DROP CONSTRAINT IF EXISTS userbots_user_id_fkey CASCADE;
ALTER TABLE userbots ADD CONSTRAINT userbots_phone_number_pkey PRIMARY KEY (phone_number);
ALTER TABLE userbots ADD COLUMN IF NOT EXISTS subscription_id BIGINT REFERENCES subscriptions(id) ON DELETE SET NULL;
ALTER TABLE userbots ADD CONSTRAINT userbots_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE;
ALTER TABLE userbots ADD CONSTRAINT userbots_session_name_key UNIQUE (session_name);

-- 7. Tambahkan kolom kuota dan pelacakan langganan
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS quantity INTEGER DEFAULT 1;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS max_userbots INTEGER DEFAULT 1;
ALTER TABLE forward_logs ADD COLUMN IF NOT EXISTS subscription_id BIGINT REFERENCES subscriptions(id) ON DELETE SET NULL;

-- 8. Tambah kolom baru ke tabel userbots jika belum ada (PM Permit, Bio, dan Cooldown)
ALTER TABLE userbots ADD COLUMN IF NOT EXISTS pm_permit_status BOOLEAN DEFAULT FALSE;
ALTER TABLE userbots ADD COLUMN IF NOT EXISTS custom_bio TEXT;
ALTER TABLE userbots ADD COLUMN IF NOT EXISTS cooldown_until TIMESTAMPTZ;
ALTER TABLE userbots ADD COLUMN IF NOT EXISTS photo_url TEXT;
ALTER TABLE userbots ADD COLUMN IF NOT EXISTS display_name TEXT;
ALTER TABLE userbots ADD COLUMN IF NOT EXISTS groups_count INTEGER DEFAULT 0;


