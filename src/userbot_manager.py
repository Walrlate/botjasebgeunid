"""
userbot_manager.py — Daemon Pengelola Koneksi Userbot Klien (GEUNID JASEB)
========================================================================
Bertanggung jawab menjaga userbot pembeli tetap online di latar belakang
untuk memproses Auto Reply (WTB) dan PM Permit secara real-time.
"""

import asyncio
import logging
import os
import re
from datetime import datetime, timezone, timedelta
from telethon import TelegramClient, events
from telethon.network import ConnectionTcpObfuscated
from telethon.errors import FloodWaitError
from src.config import API_ID, API_HASH
from src.database import (
    db_get_all_client_userbots,
    db_update_userbot_status,
    db_get_auto_replies,
    db_cooldown_client_userbot
)
from src.jaseb_engine import resolve_spintax

logger = logging.getLogger(__name__)

# Kamus global untuk menampung instance TelegramClient klien yang aktif
active_clients = {}
# Cache pengaturan klien (pm_permit & bio)
client_settings = {}

async def reload_all_userbot_settings():
    """Memuat ulang pengaturan PM Permit & Bio untuk semua klien aktif dari database ke memori."""
    try:
        from src.database import get_supabase
        supabase = get_supabase()
        res = supabase.table("userbots").select("user_id, pm_permit_status, custom_bio").execute()
        if res.data:
            for r in res.data:
                uid = r["user_id"]
                client_settings[uid] = {
                    "pm_permit": r.get("pm_permit_status", False),
                    "bio": r.get("custom_bio", "")
                }
        logger.info("✅ Pengaturan userbot klien berhasil dimuat ulang ke memori.")
    except Exception as e:
        logger.error(f"Error reload_all_userbot_settings: {e}")

async def update_all_online_userbot_bios(bio_text: str):
    """Mengubah bio Telegram secara fisik di akun klien yang sedang online."""
    from telethon.tl.functions.account import UpdateProfileRequest
    for uid, client in list(active_clients.items()):
        try:
            if client.is_connected():
                await client(UpdateProfileRequest(about=bio_text[:70]))
                logger.info(f"✅ Bio userbot {uid} berhasil diubah ke: {bio_text[:70]}")
        except Exception as e:
            logger.error(f"Gagal mengubah bio Telegram untuk {uid}: {e}")

async def start_client_userbot(user_id: int, session_name: str, phone: str):
    """Menghubungkan satu userbot klien dan memasang event listener Auto-Reply & PM Permit."""
    if user_id in active_clients:
        return True
        
    session_path = f"data/sessions/{session_name}"
    if not os.path.exists(f"{session_path}.session"):
        logger.warning(f"Sesi file untuk {phone} (ID: {user_id}) tidak ditemukan secara lokal.")
        db_update_userbot_status(user_id, 'disconnected')
        return False
        
    client = TelegramClient(
        session_path,
        API_ID,
        API_HASH,
        connection=ConnectionTcpObfuscated,
        timeout=30,
        connection_retries=5,
        retry_delay=5
    )
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
            logger.warning(f"Userbot {phone} (ID: {user_id}) tidak terotorisasi. Disconnect.")
            db_update_userbot_status(user_id, 'disconnected')
            await client.disconnect()
            return False
            
        # Sukses Terhubung
        db_update_userbot_status(user_id, 'connected')
        active_clients[user_id] = client
        logger.info(f"🟢 Userbot Klien {phone} (ID: {user_id}) berhasil diaktifkan secara online.")
        
        # Load profile settings untuk client ini
        from src.database import get_supabase
        supabase = get_supabase()
        res = supabase.table("userbots").select("pm_permit_status, custom_bio").eq("user_id", user_id).execute()
        if res.data:
            client_settings[user_id] = {
                "pm_permit": res.data[0].get("pm_permit_status", False),
                "bio": res.data[0].get("custom_bio", "")
            }
            # Set Bio jika diatur
            bio_val = res.data[0].get("custom_bio")
            if bio_val:
                try:
                    from telethon.tl.functions.account import UpdateProfileRequest
                    await client(UpdateProfileRequest(about=bio_val[:70]))
                except Exception as bio_err:
                    logger.warning(f"Gagal menset bio awal untuk {user_id}: {bio_err}")
        
        # Pasang Event Listener Auto-Reply WTB & PM Permit
        @client.on(events.NewMessage(incoming=True))
        async def client_message_handler(event):
            if not event.is_private:
                return
            sender = await event.get_sender()
            if not sender or sender.bot:
                return
                
            text = (event.text or "").strip().lower()
            sender_id = event.sender_id
            
            # 1. PM Permit Auto-Funnels
            uid_settings = client_settings.get(user_id, {})
            pm_permit_active = uid_settings.get("pm_permit", False)
            
            if pm_permit_active:
                if not hasattr(client, "funneled_users"):
                    client.funneled_users = set()
                if sender_id not in client.funneled_users:
                    client.funneled_users.add(sender_id)
                    import src.config
                    funnel_msg = (
                        "👋 **Halo!** Saya sedang menggunakan **GEUNID JASEB** untuk auto-broadcast.\n\n"
                        "Untuk informasi cepat & pemesanan jaseb otomatis, silakan hubungi:\n"
                        f"🤖 **Bot Utama:** @{src.config.BOT_USERNAME}\n"
                        "📢 **Channel Resmi:** @Geun_ID\n\n"
                        "Terima kasih!"
                    )
                    try:
                        async with client.action(event.chat_id, 'typing'):
                            await asyncio.sleep(2)
                        await event.reply(funnel_msg)
                        logger.info(f"🎯 PM Permit Auto-Funnel dikirim ke {sender_id} via userbot {user_id}")
                    except Exception as pm_err:
                        logger.error(f"Gagal mengirim PM Permit funnel: {pm_err}")
            
            # 2. Auto Reply WTB (Filter Cerdas)
            replies = db_get_auto_replies(user_id)
            if not replies:
                return
                
            for rep in replies:
                if not rep.get("is_active"):
                    continue
                    
                keyword = rep["keyword"].lower()
                if keyword in text:
                    # Filter Link
                    if rep.get("skip_links", True):
                        if "http" in text or "t.me/" in text or "@" in text:
                            logger.info(f"WTB Skip: Pesan mengandung link/username. Mengabaikan respon ke {sender_id}.")
                            continue
                            
                    # Filter Batas Karakter
                    if len(event.text or "") > rep.get("max_char_limit", 70):
                        logger.info(f"WTB Skip: Pesan melebihi batas {rep.get('max_char_limit')} karakter. Mengabaikan respon ke {sender_id}.")
                        continue
                        
                    # Filter Blacklist Username
                    skip_users = rep.get("skip_usernames")
                    if skip_users and hasattr(sender, "username") and sender.username:
                        usernames_to_skip = [u.strip().lower().replace("@","") for u in skip_users.split(",") if u.strip()]
                        if sender.username.lower() in usernames_to_skip:
                            logger.info(f"WTB Skip: Sender @{sender.username} ada di blacklist. Mengabaikan respon.")
                            continue
                    
                    # Kirim Auto Reply
                    reply_text = resolve_spintax(rep["reply_text"])
                    try:
                        async with client.action(event.chat_id, 'typing'):
                            await asyncio.sleep(len(reply_text) * 0.05 + 1)
                        await event.reply(reply_text)
                        logger.info(f"🚀 Auto-Reply Sukses terkirim ke {sender_id} untuk kata kunci: '{keyword}'")
                    except FloodWaitError as fwe:
                        logger.warning(f"Userbot {phone} terkena FloodWait {fwe.seconds} detik.")
                        until = (datetime.now(timezone.utc) + timedelta(seconds=fwe.seconds)).strftime("%Y-%m-%d %H:%M:%S")
                        db_cooldown_client_userbot(user_id, until)
                    except Exception as e:
                        logger.error(f"Gagal mengirim auto-reply: {e}")
                    break
                    
        return True
    except Exception as e:
        logger.error(f"Error saat mengaktifkan userbot {phone}: {e}")
        db_update_userbot_status(user_id, 'disconnected')
        return False

async def stop_client_userbot(user_id: int):
    """Mematikan sesi online satu userbot klien."""
    client = active_clients.pop(user_id, None)
    if client:
        try:
            if client.is_connected():
                await client.disconnect()
            logger.info(f"🔌 Userbot Klien (ID: {user_id}) berhasil dimatikan.")
            return True
        except Exception as e:
            logger.error(f"Error saat mematikan userbot {user_id}: {e}")
    return False

async def start_all_connected_userbots():
    """Membaca dan menghubungkan semua userbot yang berstatus connected di database saat startup."""
    logger.info("⏳ Memulai koneksi seluruh userbot klien di database...")
    await reload_all_userbot_settings()
    userbots = db_get_all_client_userbots(limit=100)
    
    tasks = []
    for ub in userbots:
        uid = ub["user_id"]
        phone = ub["phone_number"]
        sess = ub["session_name"]
        status = ub["status"]
        
        if status == 'connected':
            tasks.append(start_client_userbot(uid, sess, phone))
            
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    logger.info(f"✅ Selesai menginisialisasi {len(tasks)} userbot klien.")

async def update_single_online_userbot_bio(user_id: int, bio_text: str):
    """Mengubah bio Telegram secara fisik di akun klien tertentu jika sedang online."""
    client = active_clients.get(user_id)
    if client:
        try:
            if client.is_connected():
                from telethon.tl.functions.account import UpdateProfileRequest
                await client(UpdateProfileRequest(about=bio_text[:70]))
                logger.info(f"✅ Bio userbot {user_id} berhasil diubah secara live ke: {bio_text[:70]}")
        except Exception as e:
            logger.error(f"Gagal mengubah bio Telegram live untuk {user_id}: {e}")

async def update_single_online_userbot_pm_permit(user_id: int, pm_status: bool):
    """Memperbarui status cache PM Permit untuk klien tertentu secara instan."""
    if user_id in client_settings:
        client_settings[user_id]["pm_permit"] = pm_status
    else:
        client_settings[user_id] = {"pm_permit": pm_status, "bio": ""}
