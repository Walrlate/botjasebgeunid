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
from src.database import (
    db_get_transaction,
    db_get_active_subscription_id_and_end,
    db_update_subscription_dates,
    db_add_subscription,
    db_update_transaction_status,
    db_get_active_subscription_broadcast_details,
    db_get_latest_user_ad_id,
    db_get_active_lpm_lists,
    db_get_userbot_session_and_status,
    db_get_active_admin_userbots,
    db_cooldown_admin_userbot
)

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

active_broadcasts = set()

def get_capacity_from_package(package_name: str) -> int:
    """Mendapatkan kapasitas LPM dari teks nama paket secara dinamis."""
    m = re.search(r'(\d+)\s*LPM', package_name, re.IGNORECASE)
    if m:
        return int(m.group(1))
    for lpm in [100, 50, 30, 20]:
        if str(lpm) in package_name: return lpm
    return 20

# ─────────────────────────────────────────
# Core: Aktivasi Paket (Mutlak & Aman)
# ─────────────────────────────────────────

async def process_activation(bot, trx_id: str, prices: dict, login_states: dict):
    """
    Proses aktivasi paket tunggal yang aman dari duplikasi.
    Digunakan oleh Bot Callback, API Web, dan Admin Paste Format.
    """
    from datetime import timezone
    now = datetime.now(timezone.utc)
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    
    # 1. Lock transaksi agar tidak diproses 2x (Idempotency)
    row = db_get_transaction(trx_id)
    
    if not row:
        return False, "Transaksi tidak ditemukan."
    
    uid, amt, pkg_name, status = row
    if status == 'success':
        return True, "Sudah aktif."

    # 2. Hitung Parameter Paket
    days = get_package_duration_days(pkg_name, amt, prices)
    cap = get_capacity_from_package(pkg_name)
    
    # 3. Update atau Insert Subskripsi
    active_sub = db_get_active_subscription_id_and_end(uid)
    
    if active_sub:
        # MODE PERPANJANG
        sub_id, old_end_str = active_sub
        try:
            old_end_dt = datetime.strptime(old_end_str.split(".")[0].strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            base_date = max(old_end_dt, now)
        except:
            base_date = now
        new_end = (base_date + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        db_update_subscription_dates(sub_id, new_end, cap, pkg_name)
    else:
        # MODE BARU
        new_end = (now + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        db_add_subscription(uid, pkg_name, cap, now_str, new_end)
    
    # 4. Tandai transaksi sukses
    db_update_transaction_status(trx_id, "success")
    
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

async def run_broadcast_cycle(bot, user_id: int, api_id, api_hash):
    """
    Eksekusi satu siklus broadcast. Menangani pemilihan pool admin atau ubot pembeli.
    """
    if user_id in active_broadcasts:
        logger.warning(f"⚠️ Broadcast untuk user {user_id} sedang berjalan. Siklus ganda diabaikan.")
        return

    active_broadcasts.add(user_id)
    try:
        from src.jaseb_engine import JasebEngine
        from src.notifications import notify_client_broadcast_done
        from datetime import timezone
        
        # 1. Ambil Langganan
        sub = db_get_active_subscription_broadcast_details(user_id)
        if not sub: return
        
        pkg, cap, req_lpm, iv = sub
        
        # 2. Ambil Iklan
        ad = db_get_latest_user_ad_id(user_id)
        if not ad:
            try: await bot.send_message(user_id, "⚠️ Iklan Anda kosong. Gunakan /edit_jaseb.");
            except: pass
            return
        ad_id = ad[0]
        
        # 3. Siapkan Target LPM
        links = [l.strip() for l in (req_lpm or "").split() if l.strip()]
        sisa = max(0, cap - len(links))
        if sisa > 0:
            links.extend(db_get_active_lpm_lists(sisa))

        if "userbot" in pkg.lower():
            # JALUR USERBOT PEMBELI
            ub = db_get_userbot_session_and_status(user_id)
            if ub and ub[1] == 'connected':
                eng = JasebEngine(f"data/sessions/{ub[0]}", api_id, api_hash)
                try:
                    await eng.start()
                    res = await eng.broadcast_with_stealth(user_id, ad_id, links, 'slowly')
                    await notify_client_broadcast_done(bot, user_id, res.get("success_count", 0), res.get("failed_count", 0), iv or 0.5)
                except Exception as e:
                    logger.error(f"Gagal broadcast userbot pembeli {user_id}: {e}")
                    from src.database import db_update_userbot_status
                    db_update_userbot_status(user_id, 'disconnected')
                    try:
                        await bot.send_message(user_id, "⚠️ **USERBOT TERPUTUS!**\n\nSesi userbot Anda terputus atau kedaluwarsa. Silakan sambungkan kembali via Bot.")
                    except: pass
                finally:
                    await eng.stop()
            else:
                try: await bot.send_message(user_id, "⚠️ Userbot terputus! Sambungkan kembali.");
                except: pass
        else:
            # JALUR POOL ADMIN (FALLBACK)
            admins = db_get_active_admin_userbots()
            
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
                        until = (datetime.now(timezone.utc) + timedelta(seconds=res["floodwait_seconds"])).strftime("%Y-%m-%d %H:%M:%S")
                        db_cooldown_admin_userbot(aid, until)
                        continue
                    
                    if not unprocessed:
                        break
                except: continue
                finally: await eng.stop()
                
            await notify_client_broadcast_done(bot, user_id, total_succ, total_fail, iv or 0.5)
    finally:
        active_broadcasts.discard(user_id)
