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
        
        # Pasang Event Listener Perintah Selfbot Klien (Outgoing dari Owner)
        @client.on(events.NewMessage(outgoing=True))
        async def client_selfbot_handler(event):
            text = (event.text or "").strip()
            if not text.startswith(".") and not text.startswith("/"):
                return
                
            parts = text.split(" ", 1)
            cmd = parts[0].lower()
            cmd_name = cmd[1:]
            args = parts[1].strip() if len(parts) > 1 else ""
            
            async def reply_self(reply_text):
                try:
                    await event.edit(f"🤖 **[GEUNID SELF-PANEL]**\n\n{reply_text}")
                except Exception as edit_err:
                    logger.error(f"Gagal edit pesan perintah selfbot: {edit_err}")

            if cmd_name in ["help", "panel"]:
                help_text = (
                    "⚙️ **DAFTAR PERINTAH USERBOT GEUNID**\n"
                    f"{'━'*35}\n"
                    "• `.status` : Cek status langganan & sisa hari aktif\n"
                    "• `.jaseb start` : Mulai sebar iklan jaseb Anda\n"
                    "• `.jaseb stop` : Hentikan sebar iklan jaseb Anda\n"
                    "• `.setad <materi>` : Ganti materi iklan jaseb secara instan\n"
                    "• `.pmpermit <on/off>` : Aktifkan/matikan fitur PM Permit\n"
                    "• `.autoreply add <kunci> | <balasan>` : Tambah Auto Reply WTB\n"
                    "• `.autoreply del <kunci>` : Hapus Auto Reply WTB\n"
                    "• `.autoreply list` : Lihat daftar Auto Reply aktif\n\n"
                    "💡 _Catatan: Anda juga bisa menggunakan awalan garis miring (seperti `/panel` atau `/status`)._"
                )
                await reply_self(help_text)

            elif cmd_name == "status":
                from src.database import get_supabase, normalize_date
                supabase = get_supabase()
                res = supabase.table("subscriptions").select("status, end_date, capacity_lpm").eq("user_id", user_id).eq("status", "active").execute()
                if res.data:
                    row = res.data[0]
                    end_date_str = normalize_date(row.get("end_date", ""))
                    cap = row.get("capacity_lpm", 0)
                    from src.logic import active_broadcasts
                    is_sharing = "Aktif 🟢" if user_id in active_broadcasts else "Mati 🔴"
                    reply_msg = (
                        "🌟 **INFORMASI LANGGANAN USERBOT**\n\n"
                        f"💳 Status: **AKTIF**\n"
                        f"⏰ Berakhir: `{end_date_str}`\n"
                        f"📊 Kapasitas: **{cap} LPM**\n"
                        f"📡 Jaseb Status: **{is_sharing}**"
                    )
                else:
                    reply_msg = "❌ Anda tidak memiliki langganan paket userbot yang aktif saat ini."
                await reply_self(reply_msg)

            elif cmd_name == "jaseb":
                sub_cmd = args.lower()
                if sub_cmd == "start":
                    from src.database import db_get_active_subscription_status
                    sub = db_get_active_subscription_status(user_id)
                    if not sub:
                        await reply_self("❌ Gagal: Anda tidak memiliki paket aktif.")
                        return
                    from src.main import start_user_broadcast
                    asyncio.create_task(start_user_broadcast(user_id))
                    await reply_self("🚀 **Broadcast iklan jaseb berhasil dijalankan di latar belakang!**")
                elif sub_cmd == "stop":
                    from src.logic import active_broadcasts
                    active_broadcasts.discard(user_id)
                    await reply_self("🛑 **Broadcast iklan jaseb dihentikan paksa.**")
                else:
                    await reply_self("❌ Perintah tidak dikenal. Gunakan `.jaseb start` atau `.jaseb stop`.")

            elif cmd_name == "setad":
                if not args:
                    await reply_self("❌ **Format salah!** Gunakan: `.setad <teks_materi_iklan>`")
                    return
                from src.database import db_save_user_ad
                if db_save_user_ad(user_id, args, ""):
                    await reply_self("✅ **Materi iklan berhasil diperbarui secara instan!**")
                else:
                    await reply_self("❌ Gagal menyimpan materi iklan baru ke database.")

            elif cmd_name == "pmpermit":
                sub_cmd = args.lower()
                from src.database import get_supabase
                supabase = get_supabase()
                if sub_cmd == "on":
                    supabase.table("userbots").update({"pm_permit_status": True}).eq("user_id", user_id).execute()
                    await update_single_online_userbot_pm_permit(user_id, True)
                    await reply_self("🟢 **PM Permit diaktifkan!** Pesan masuk baru akan otomatis dibalas info funnel.")
                elif sub_cmd == "off":
                    supabase.table("userbots").update({"pm_permit_status": False}).eq("user_id", user_id).execute()
                    await update_single_online_userbot_pm_permit(user_id, False)
                    await reply_self("🔴 **PM Permit dimatikan.**")
                else:
                    await reply_self("❌ Perintah tidak dikenal. Gunakan `.pmpermit on` atau `.pmpermit off`.")

            elif cmd_name == "autoreply":
                parts_ar = args.split(" ", 1)
                ar_action = parts_ar[0].lower()
                ar_args = parts_ar[1].strip() if len(parts_ar) > 1 else ""
                
                if ar_action == "add":
                    ar_parts = [p.strip() for p in ar_args.split("|", 1)]
                    if len(ar_parts) < 2:
                        await reply_self("❌ **Format salah!** Gunakan: `.autoreply add <kunci> | <balasan>`")
                        return
                    keyword = ar_parts[0]
                    reply_text = ar_parts[1]
                    from src.database import db_add_auto_reply
                    if db_add_auto_reply(user_id, keyword, reply_text):
                        await reload_all_userbot_settings()
                        await reply_self(f"✅ **Auto-Reply ditambahkan!**\n🔑 Kunci: `{keyword}`\n📝 Balasan: `{reply_text}`")
                    else:
                        await reply_self("❌ Gagal menambahkan Auto-Reply. Kata kunci mungkin sudah terdaftar.")
                        
                elif ar_action == "del":
                    if not ar_args:
                        await reply_self("❌ **Format salah!** Gunakan: `.autoreply del <kata_kunci>`")
                        return
                    from src.database import db_delete_auto_reply
                    if db_delete_auto_reply(user_id, ar_args):
                        await reload_all_userbot_settings()
                        await reply_self(f"🗑 **Auto-Reply untuk kunci `{ar_args}` berhasil dihapus.**")
                    else:
                        await reply_self(f"❌ Gagal menghapus. Kunci `{ar_args}` tidak ditemukan.")
                        
                elif ar_action == "list":
                    from src.database import db_get_auto_replies
                    replies = db_get_auto_replies(user_id)
                    if not replies:
                        await reply_self("📋 Anda belum mengatur Auto-Reply WTB.")
                        return
                    lines = ["📋 **DAFTAR AUTO-REPLY AKTIF**\n"]
                    for rep in replies:
                        status_ar = "🟢" if rep.get("is_active") else "🔴"
                        lines.append(f"• {status_ar} `{rep['keyword']}` ➜ `{rep['reply_text'][:40]}`")
                    await reply_self("\n".join(lines))
                else:
                    await reply_self("❌ Perintah tidak dikenal. Gunakan `.autoreply add`, `.autoreply del`, atau `.autoreply list`.")

        # Pasang Event Listener Auto-Reply WTB & PM Permit (Incoming)
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
