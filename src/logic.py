import logging
import re
import os
import asyncio
import random
from datetime import datetime, timedelta
from telethon import Button
from telethon.tl.types import PeerChannel, PeerUser, PeerChat

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# Logic: Durasi & Kapasitas
# ─────────────────────────────────────────

def get_package_duration_days(package_name: str, amount: int, prices: dict) -> int:
    """Tentukan durasi paket berdasarkan nama dan harga dari prices.json."""
    if not prices: return 30
    amount = int(amount)
    for category in ['regular', 'forward', 'userbot']:
        for item in prices.get(category, []):
            if int(item.get('promoPrice', 0)) == amount or int(item.get('price', 0)) == amount:
                dur = item.get('duration', '')
                m = re.search(r'(\d+)', dur)
                days = int(m.group(1)) if m else 30
                bonus = re.search(r'\+(\d+)', item.get('bonus', ''))
                if bonus: days += int(bonus.group(1))
                return days
    return 30

def get_capacity_from_package(package_name: str) -> int:
    """Ekstrak kapasitas LPM dari nama paket."""
    for lpm in [50, 30, 20]:
        if str(lpm) in package_name: return lpm
    return 20

# ─────────────────────────────────────────
# Logic: Aktivasi & Pembayaran
# ─────────────────────────────────────────

async def process_successful_payment(bot, db, trx_id: str, prices: dict, login_states: dict):
    """
    Logika tunggal aktivasi paket. 
    Dipanggil oleh: check_payment_status_handler (Bot) dan handle_check_status_api (Web).
    """
    from src.notifications import notify_admin_payment_success
    
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    
    cur = await db.execute("SELECT user_id, amount, package_id, status FROM transactions WHERE trx_id=?", (trx_id,))
    row = await cur.fetchone()
    if not row or row[3] == 'success': 
        return False, "Already processed or not found"
        
    uid, amt, pkg, _ = row
    days = get_package_duration_days(pkg, amt, prices)
    cap = get_capacity_from_package(pkg)
    
    # Cek subskripsi aktif untuk perpanjangan
    cur = await db.execute("""
        SELECT id, end_date FROM subscriptions 
        WHERE user_id=? AND status='active' AND TRIM(end_date) > ?
        ORDER BY end_date DESC LIMIT 1
    """, (uid, now_str))
    sub = await cur.fetchone()
    
    if sub:
        sub_id, old_end_str = sub
        try:
            old_end_dt = datetime.strptime(old_end_str.split(".")[0].strip(), "%Y-%m-%d %H:%M:%S")
            base_date = max(old_end_dt, now)
        except:
            base_date = now
        new_end = (base_date + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        await db.execute("UPDATE subscriptions SET end_date=?, capacity_lpm=?, package_name=? WHERE id=?", (new_end, cap, pkg, sub_id))
    else:
        new_end = (now + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        await db.execute("""
            INSERT INTO subscriptions (user_id, package_name, capacity_lpm, start_date, end_date, status, broadcast_interval_hours)
            VALUES (?, ?, ?, ?, ?, 'active', 0.5)
        """, (uid, pkg, cap, now_str, new_end))
        
    await db.execute("UPDATE transactions SET status='success' WHERE trx_id=?", (trx_id,))
    await db.commit()
    
    # Update login state agar bot meminta input selanjutnya
    is_ub = "userbot" in pkg.lower()
    login_states[uid] = {"state": "waiting_for_phone" if is_ub else "waiting_for_ad"}
    
    # Notifikasi
    msg = f"🎉 **PEMBAYARAN TERVERIFIKASI!**\n\nPaket **{pkg}** Anda telah AKTIF hingga `{new_end[:10]}`.\n\n"
    msg += "🤖 Silakan kirimkan **Nomor HP** akun Telegram Anda:" if is_ub else "✍️ Silakan kirimkan **Materi Iklan** Anda (teks/foto):"
    
    try:
        await bot.send_message(uid, msg)
        from src.config import ADMIN_ID
        await notify_admin_payment_success(bot, int(ADMIN_ID), uid, "Client", "", pkg, amt, new_end[:10])
    except: pass
    
    return True, new_end

# ─────────────────────────────────────────
# Logic: Broadcast Engine Bridge
# ─────────────────────────────────────────

async def start_user_broadcast_logic(bot, db, user_id: int, api_id, api_hash):
    """
    Menjalankan proses broadcast untuk satu user.
    Memastikan penggunaan pool admin yang tepat atau ubot pribadi.
    """
    from src.jaseb_engine import JasebEngine
    from src.notifications import notify_client_broadcast_done
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 1. Ambil data subskripsi
    cur = await db.execute("""
        SELECT package_name, capacity_lpm, request_lpm, broadcast_interval_hours 
        FROM subscriptions WHERE user_id=? AND status='active' AND TRIM(end_date) > ? 
        ORDER BY end_date DESC LIMIT 1
    """, (user_id, now_str))
    sub = await cur.fetchone()
    if not sub: return
    
    pkg, cap, req_lpm, iv = sub
    
    # 2. Ambil materi iklan
    cur = await db.execute("SELECT id FROM user_ads WHERE user_id=? ORDER BY created_at DESC LIMIT 1", (user_id,))
    ad = await cur.fetchone()
    if not ad:
        try: await bot.send_message(user_id, "⚠️ Iklan Anda belum di-set. Gunakan menu /edit_jaseb.");
        except: pass
        return
    ad_id = ad[0]
    
    # 3. Kumpulkan target LPM
    links = [l.strip() for l in (req_lpm or "").split() if l.strip()]
    sisa = max(0, cap - len(links))
    if sisa > 0:
        cur = await db.execute("SELECT group_link FROM lpm_lists WHERE is_active=1 AND is_blacklisted=0 ORDER BY member_count DESC LIMIT ?", (sisa,))
        links.extend(r[0] for r in await cur.fetchall())

    if "userbot" in pkg.lower():
        # LOGIKA USERBOT PRIBADI
        cur = await db.execute("SELECT session_name, status FROM userbots WHERE user_id=?", (user_id,))
        ub = await cur.fetchone()
        if ub and ub[1] == 'connected':
            eng = JasebEngine(f"data/sessions/{ub[0]}", api_id, api_hash)
            await eng.start()
            res = await eng.broadcast_with_stealth(user_id, ad_id, links, 'slowly', True)
            await eng.stop()
            await notify_client_broadcast_done(bot, user_id, res.get("success_count", 0), res.get("failed_count", 0), iv or 0.5)
        else:
            try: await bot.send_message(user_id, "⚠️ Userbot Anda terputus! Hubungkan kembali via /start.");
            except: pass
    else:
        # LOGIKA POOL ADMIN (FALLBACK)
        cur = await db.execute("""
            SELECT session_name, phone_number, id FROM admin_userbots 
            WHERE status='connected' AND (cooldown_until IS NULL OR TRIM(cooldown_until) < ?) 
            ORDER BY RANDOM()
        """, (now_str,))
        admins = await cur.fetchall()
        
        if not admins:
            logger.error(f"Jarvis: All admin pool offline for user {user_id}")
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
            except Exception as e:
                logger.error(f"Fallback Error ({phone}): {e}")
            finally:
                await eng.stop()
        
        await notify_client_broadcast_done(bot, user_id, total_succ, total_fail, iv or 0.5)
