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

