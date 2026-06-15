import aiosqlite
import os
from src.config import DB_PATH

async def init_db():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        # Table for Users
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Table for Packages/Subscriptions
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
                broadcast_interval_hours INTEGER DEFAULT 2,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Table for User Ads (Materi Jaseb)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS user_ads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title TEXT,
                content TEXT,
                media_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Table for LPM Lists
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

        # Table for Transaction Tracking (KlikQRIS)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                trx_id TEXT UNIQUE,
                package_id INTEGER,
                amount INTEGER,
                status TEXT DEFAULT 'pending',
                payment_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')

        # Table for Forward Logs (Proof Hub)
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

        # Table for Multi-Session Userbots
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
        
        # Safe migration for existing DB — tambahkan kolom baru tanpa drop table
        migrations = [
            "ALTER TABLE subscriptions ADD COLUMN request_lpm TEXT",
            "ALTER TABLE subscriptions ADD COLUMN broadcast_interval_hours INTEGER DEFAULT 2",
            "ALTER TABLE lpm_lists ADD COLUMN is_blacklisted BOOLEAN DEFAULT 0",
            "ALTER TABLE user_ads ADD COLUMN fwd_chat_id TEXT",
            "ALTER TABLE user_ads ADD COLUMN fwd_peer_type TEXT",
            "ALTER TABLE user_ads ADD COLUMN fwd_msg_id INTEGER",
        ]
        for migration in migrations:
            try:
                await db.execute(migration)
            except Exception:
                pass  # Kolom sudah ada, skip
            
        await db.commit()

def get_db():
    return aiosqlite.connect(DB_PATH)
