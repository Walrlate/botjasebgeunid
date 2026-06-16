"""
logic.py — Pusat Logika Bisnis GEUNID JASEB (AUDITED BY JARVIS)
==============================================================
Menangani aktivasi paket, durasi, kapasitas, dan orkestrasi broadcast.
Mencegah circular import antara main.py dan admin_handlers.py.
"""

import asyncio
import logging
import re
import os
import random
from datetime import datetime, timedelta
from telethon.tl.types import PeerChannel, PeerUser, PeerChat

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# Helpers: Durasi & Kapasitas
# ─────────────────────────────────────────

def get_package_duration_days(package_name: str, amount: int, prices: dict) -> int:
    """Menganalisis durasi paket berdasarkan nama dan harga promo."""
    if not prices: return 30
    amount = int(amount)
    # Cek di kategori prices.json
    for category in ['regular', 'forward', 'userbot']:
        for item in prices.get(category, []):
            if int(item.get('promoPrice', 0)) == amount or int(item.get('price', 0)) == amount:
                dur_str = item.get('duration', '')
                days = int(re.search(r'(\d+)', dur_str).group(1)) if re.search(r'(\d+)', dur_str) else 30
                # Tambah bonus jika ada
                bonus = re.search(r'\+(\d+)', item.get('bonus', ''))
                if bonus: days += int(bonus.group(1))
                return days
    # Fallback ke pencarian teks di nama paket
    m = re.search(r'(\d+)\s*Hari', package_name, re.IGNORECASE)
    return int(m.group(1)) if m else 30

def get_capacity_from_package(package_name: str) -> int:
    """Mendapatkan kapasitas LPM dari teks nama paket."""
    for lpm in [50, 30, 20]:
        if str(lpm) in package_name: return lpm
    return 20

# ─────────────────────────────────────────
# Core: Aktivasi Paket (Mutlak & Aman)
# ─────────────────────────────────────────

async def process_activation(bot, db, trx_id: str, prices: dict, login_states: dict):
    """
    Proses aktivasi paket tunggal yang aman dari duplikasi.
    Digunakan oleh Bot Callback, API Web, dan Admin Paste Format.
    """
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    
    # 1. Lock transaksi agar tidak diproses 2x (Idempotency)
    cur = await db.execute("SELECT user_id, amount, package_id, status FROM transactions WHERE trx_id=?", (trx_id,))
    row = await cur.fetchone()
    
    if not row:
        return False, "Transaksi tidak ditemukan."
    
    uid, amt, pkg_name, status = row
    if status == 'success':
        return True, "Sudah aktif."

    # 2. Hitung Parameter Paket
    days = get_package_duration_days(pkg_name, amt, prices)
    cap = get_capacity_from_package(pkg_name)
    
    # 3. Update atau Insert Subskripsi
    # Gunakan TRIM untuk memastikan perbandingan string tanggal akurat
    cur = await db.execute("""
        SELECT id, end_date FROM subscriptions 
        WHERE user_id=? AND status='active' AND TRIM(end_date) > ?
        ORDER BY end_date DESC LIMIT 1
    """, (uid, now_str))
    active_sub = await cur.fetchone()
    
    if active_sub:
        # MODE PERPANJANG
        sub_id, old_end_str = active_sub
        try:
            old_end_dt = datetime.strptime(old_end_str.split(".")[0].strip(), "%Y-%m-%d %H:%M:%S")
            base_date = max(old_end_dt, now)
        except:
            base_date = now
        new_end = (base_date + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        await db.execute("UPDATE subscriptions SET end_date=?, capacity_lpm=?, package_name=? WHERE id=?", (new_end, cap, pkg_name, sub_id))
    else:
        # MODE BARU
        new_end = (now + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        await db.execute("""
            INSERT INTO subscriptions (user_id, package_name, capacity_lpm, start_date, end_date, status, broadcast_interval_hours)
            VALUES (?, ?, ?, ?, ?, 'active', 0.5)
        """, (uid, pkg_name, cap, now_str, new_end))
    
    # 4. Tandai transaksi sukses
    await db.execute("UPDATE transactions SET status='success' WHERE trx_id=?", (trx_id,))
    await db.commit()
    
    # 5. Set alur bot selanjutnya (Minta Materi / Minta HP)
    is_ubot = "userbot" in pkg_name.lower()
    login_states[uid] = {"state": "waiting_for_phone" if is_ubot else "waiting_for_ad"}
    
    # 6. Notifikasi User
    notif_msg = (
        f"🎉 **PEMBAYARAN DITERIMA!**\n\n"
        f"📦 Paket: **{pkg_name}**\n"
        f"⏳ Berlaku hingga: `{new_end[:10]}`\n\n"
    )
    if is_ubot:
        notif_msg += "🤖 Silakan kirimkan **Nomor HP** akun Telegram Anda (format: `+628xxx`):"
    else:
        notif_msg += "✍️ Silakan kirimkan **Materi Iklan** Anda (teks, foto, atau forward):"
        
    try:
        await bot.send_message(uid, notif_msg)
        from src.config import ADMIN_ID
        from src.notifications import notify_admin_payment_success
        await notify_admin_payment_success(bot, int(ADMIN_ID), uid, "Client", "", pkg_name, amt, new_end[:10])
    except Exception as e:
        logger.error(f"Gagal kirim notif aktivasi: {e}")
        
    return True, new_end

# ─────────────────────────────────────────
# Core: Orkestrasi Broadcast (Multi-Admin)
# ─────────────────────────────────────────

async def run_broadcast_cycle(bot, db, user_id: int, api_id, api_hash):
    """
    Eksekusi satu siklus broadcast. Menangani pemilihan pool admin atau ubot pembeli.
    """
    from src.jaseb_engine import JasebEngine
    from src.notifications import notify_client_broadcast_done
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 1. Ambil Langganan
    cur = await db.execute("""
        SELECT package_name, capacity_lpm, request_lpm, broadcast_interval_hours 
        FROM subscriptions WHERE user_id=? AND status='active' AND TRIM(end_date) > ? 
        ORDER BY end_date DESC LIMIT 1
    """, (user_id, now_str))
    sub = await cur.fetchone()
    if not sub: return
    
    pkg, cap, req_lpm, iv = sub
    
    # 2. Ambil Iklan
    cur = await db.execute("SELECT id FROM user_ads WHERE user_id=? ORDER BY created_at DESC LIMIT 1", (user_id,))
    ad = await cur.fetchone()
    if not ad:
        try: await bot.send_message(user_id, "⚠️ Iklan Anda kosong. Gunakan /edit_jaseb.");
        except: pass
        return
    ad_id = ad[0]
    
    # 3. Siapkan Target LPM
    links = [l.strip() for l in (req_lpm or "").split() if l.strip()]
    sisa = max(0, cap - len(links))
    if sisa > 0:
        cur = await db.execute("SELECT group_link FROM lpm_lists WHERE is_active=1 AND is_blacklisted=0 ORDER BY member_count DESC LIMIT ?", (sisa,))
        rows = await cur.fetchall()
        links.extend([r[0] for r in rows])

    if "userbot" in pkg.lower():
        # JALUR USERBOT PEMBELI
        cur = await db.execute("SELECT session_name, status FROM userbots WHERE user_id=?", (user_id,))
        ub = await cur.fetchone()
        if ub and ub[1] == 'connected':
            eng = JasebEngine(f"data/sessions/{ub[0]}", api_id, api_hash)
            try:
                await eng.start()
                res = await eng.broadcast_with_stealth(user_id, ad_id, links, 'slowly')
                await notify_client_broadcast_done(bot, user_id, res.get("success_count", 0), res.get("failed_count", 0), iv or 0.5)
            finally:
                await eng.stop()
        else:
            try: await bot.send_message(user_id, "⚠️ Userbot terputus! Sambungkan kembali.");
            except: pass
    else:
        # JALUR POOL ADMIN (FALLBACK)
        cur = await db.execute("""
            SELECT session_name, phone_number, id FROM admin_userbots 
            WHERE status='connected' AND (cooldown_until IS NULL OR TRIM(cooldown_until) < ?) 
            ORDER BY RANDOM()
        """, (now_str,))
        admins = await cur.fetchall()
        
        if not admins:
            logger.error(f"Pool Kosong untuk user {user_id}")
            return
            
        unprocessed = links.copy()
        total_succ = 0
        total_fail = 0
        
        for sess, phone, aid in admins:
            if not unprocessed: break
            eng = JasebEngine(f"data/sessions/{sess}", api_id, api_hash)
            try:
                await eng.start()
                res = await eng.broadcast_with_stealth(user_id, ad_id, unprocessed, 'slowly' if 'regular' in pkg.lower() else 'instant')
                total_succ += res.get("success_count", 0)
                total_fail += res.get("failed_count", 0)
                unprocessed = res.get("unprocessed_links", [])
                
                if res.get("floodwait_seconds", 0) > 300:
                    until = (datetime.now() + timedelta(seconds=res["floodwait_seconds"])).strftime("%Y-%m-%d %H:%M:%S")
                    await db.execute("UPDATE admin_userbots SET cooldown_until=? WHERE id=?", (until, aid))
                    await db.commit()
                    continue
                break
            except: continue
            finally: await eng.stop()
            
        await notify_client_broadcast_done(bot, user_id, total_succ, total_fail, iv or 0.5)
