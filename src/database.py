import aiosqlite
import os
from src.config import DB_PATH

async def init_db():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    async with aiosqlite.connect(DB_PATH, timeout=30) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA synchronous=NORMAL;")
        
        # 1. Table Users
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 2. Table Subscriptions (Pondasi Langganan)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                package_name TEXT,
                capacity_lpm INTEGER,
                start_date TIMESTAMP,
                end_date TIMESTAMP,
                status TEXT DEFAULT 'active',
                request_lpm TEXT,
                broadcast_interval_hours REAL DEFAULT 0.5,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # 3. Table User Ads (Materi Iklan - Support Native Forward)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS user_ads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title TEXT,
                content TEXT,
                media_path TEXT,
                fwd_chat_id TEXT,
                fwd_peer_type TEXT,
                fwd_msg_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # 4. Table LPM Lists (Database Grup Global)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS lpm_lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_link TEXT UNIQUE,
                group_id INTEGER,
                group_name TEXT,
                member_count INTEGER DEFAULT 0,
                last_active TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                is_blacklisted BOOLEAN DEFAULT 0
            )
        ''')

        # 5. Table Transactions (Tracking Pembayaran)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                trx_id TEXT UNIQUE,
                package_id TEXT,
                amount INTEGER,
                status TEXT DEFAULT 'pending',
                payment_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')

        # 6. Table Forward Logs (Bukti Kirim - Proof Hub)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS forward_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                ad_id INTEGER,
                group_id INTEGER,
                msg_link TEXT,
                status TEXT,
                error_msg TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (ad_id) REFERENCES user_ads (id)
            )
        ''')

        # 7. Table Userbots (Client Stealth Mode)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS userbots (
                user_id INTEGER PRIMARY KEY,
                phone_number TEXT,
                session_name TEXT,
                status TEXT DEFAULT 'disconnected',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')

        # 8. Table Admin Userbots (Pool Pengirim & Redundansi)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS admin_userbots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT UNIQUE,
                session_name TEXT,
                status TEXT DEFAULT 'connected',
                cooldown_until TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 9. Automated Migrations (Untuk DB lama yang sudah ada)
        migrations = [
            "ALTER TABLE subscriptions ADD COLUMN request_lpm TEXT",
            "ALTER TABLE subscriptions ADD COLUMN broadcast_interval_hours REAL DEFAULT 0.5",
            "ALTER TABLE lpm_lists ADD COLUMN is_blacklisted BOOLEAN DEFAULT 0",
            "ALTER TABLE user_ads ADD COLUMN fwd_chat_id TEXT",
            "ALTER TABLE user_ads ADD COLUMN fwd_peer_type TEXT",
            "ALTER TABLE user_ads ADD COLUMN fwd_msg_id INTEGER",
            "ALTER TABLE forward_logs ADD COLUMN ad_id INTEGER",
            "UPDATE subscriptions SET broadcast_interval_hours = 0.5 WHERE status = 'active'"
        ]
        
        for m in migrations:
            try: await db.execute(m)
            except: pass
            
        await db.commit()

def get_db():
    return aiosqlite.connect(DB_PATH, timeout=30)
