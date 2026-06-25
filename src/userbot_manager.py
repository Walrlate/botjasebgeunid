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
from src.config import API_ID, API_HASH, BOT_TOKEN
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

# Kamus global lock sesi untuk menghindari SQLite database lock file
session_locks = {}

# Deteksi BOT_ID secara dinamis dari token bot
try:
    BOT_ID = int(BOT_TOKEN.split(":")[0])
except Exception:
    BOT_ID = 0

def get_session_lock(session_name: str) -> asyncio.Lock:
    """Mendapatkan atau membuat lock memori untuk nama sesi tertentu."""
    if session_name not in session_locks:
        session_locks[session_name] = asyncio.Lock()
    return session_locks[session_name]

async def reload_all_userbot_settings():
    """Memuat ulang pengaturan PM Permit & Bio untuk semua klien aktif dari database ke memori."""
    try:
        from src.database import get_supabase
        supabase = get_supabase()
        try:
            res = supabase.table("userbots").select("phone_number, pm_permit_status, custom_bio").execute()
            if res.data:
                for r in res.data:
                    phone = r["phone_number"]
                    client_settings[phone] = {
                        "pm_permit": r.get("pm_permit_status", False),
                        "bio": r.get("custom_bio", "")
                    }
        except Exception as e_select:
            logger.warning(f"Gagal select lengkap userbot settings: {e_select}. Fallback ke query phone_number.")
            res = supabase.table("userbots").select("phone_number").execute()
            if res.data:
                for r in res.data:
                    phone = r["phone_number"]
                    client_settings[phone] = {
                        "pm_permit": False,
                        "bio": ""
                    }
        logger.info("✅ Pengaturan userbot klien berhasil dimuat ulang ke memori.")
    except Exception as e:
        logger.error(f"Error reload_all_userbot_settings: {e}")

async def update_all_online_userbot_bios(bio_text: str):
    """Mengubah bio Telegram secara fisik di akun klien yang sedang online."""
    from telethon.tl.functions.account import UpdateProfileRequest
    for phone, client in list(active_clients.items()):
        try:
            if client.is_connected():
                await client(UpdateProfileRequest(about=bio_text[:70]))
                logger.info(f"✅ Bio userbot {phone} berhasil diubah ke: {bio_text[:70]}")
        except Exception as e:
            logger.error(f"Gagal mengubah bio Telegram untuk {phone}: {e}")

async def start_client_userbot(user_id: int, session_name: str, phone: str):
    """Menghubungkan satu userbot klien dan memasang event listener Auto-Reply & PM Permit."""
    if phone in active_clients:
        return True
        
    session_path = f"data/sessions/{session_name}"
    if not os.path.exists(f"{session_path}.session"):
        logger.info(f"Sesi file untuk {phone} tidak ditemukan secara lokal. Mencoba mengunduh dari Supabase Storage...")
        from src.database import db_download_session_file
        downloaded = db_download_session_file(session_name)
        if not downloaded:
            logger.warning(f"Sesi file untuk {phone} (ID: {user_id}) tidak ditemukan secara lokal maupun di Supabase Storage.")
            from src.database import db_update_userbot_status
            db_update_userbot_status(phone, 'disconnected')
            return False

    async with get_session_lock(session_name):
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
            from src.database import db_update_userbot_status
            if not await client.is_user_authorized():
                logger.warning(f"Userbot {phone} (ID: {user_id}) tidak terotorisasi. Sesi expired/revoked.")
                db_update_userbot_status(phone, 'disconnected')
                await client.disconnect()
                
                # Notifikasi pembeli bahwa sesinya sudah tidak valid dan perlu login ulang
                try:
                    from src.main import bot
                    from telethon import Button
                    expired_msg = (
                        f"⚠️ **Sesi Userbot `{phone}` Tidak Valid!**\n\n"
                        f"Sesi Telegram Anda telah berakhir (dicabut oleh Telegram). "
                        f"Hal ini biasa terjadi jika Anda melakukan login dari perangkat lain atau akun terlalu lama tidak aktif.\n\n"
                        f"Silakan tekan tombol di bawah untuk menghapus sesi lama dan mendaftar ulang:"
                    )
                    buttons = [[Button.inline("♻️ Hapus Sesi & Daftar Ulang", f"del_session_{phone}".encode())]]
                    await bot.send_message(user_id, expired_msg, buttons=buttons)
                except Exception as notif_err:
                    logger.error(f"Gagal kirim notif sesi expired ke {user_id}: {notif_err}")
                    
                return False
                
            # Sukses Terhubung
            db_update_userbot_status(phone, 'connected')
            active_clients[phone] = client
            logger.info(f"🟢 Userbot Klien {phone} (ID: {user_id}) berhasil diaktifkan secara online.")
            
            # Ambil data profil userbot secara realtime dari Telegram API
            try:
                me = await client.get_me()
                display_name = f"{me.first_name or ''} {me.last_name or ''}".strip() or phone
                
                # Download foto profil
                avatar_dir = "frontend/public/avatars"
                os.makedirs(avatar_dir, exist_ok=True)
                avatar_filename = f"{phone.replace('+','')}.jpg"
                avatar_path = f"{avatar_dir}/{avatar_filename}"
                
                photo_url = None
                try:
                    if os.path.exists(avatar_path):
                        os.remove(avatar_path)
                    await client.download_profile_photo(me, file=avatar_path)
                    if os.path.exists(avatar_path):
                        photo_url = f"/avatars/{avatar_filename}"
                except Exception as photo_err:
                    logger.debug(f"Tidak ada foto profil untuk {phone} atau gagal diunduh: {photo_err}")
                
                from src.database import db_update_userbot_profile
                db_update_userbot_profile(phone, display_name, photo_url)
            except Exception as profile_err:
                logger.error(f"Gagal mengambil profil userbot dari Telegram API: {profile_err}")
            
            # Load profile settings untuk client ini
            from src.database import get_supabase
            supabase = get_supabase()
            try:
                res = supabase.table("userbots").select("pm_permit_status, custom_bio").eq("phone_number", phone).execute()
                if res.data:
                    client_settings[phone] = {
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
                            logger.warning(f"Gagal menset bio awal untuk {phone}: {bio_err}")
            except Exception as e_select:
                logger.warning(f"Gagal select pm_permit_status/custom_bio untuk {phone}: {e_select}. Menggunakan fallback.")
                client_settings[phone] = {
                    "pm_permit": False,
                    "bio": ""
                }
            
            # Pasang Event Listener Perintah Selfbot Klien (Outgoing dari Owner)
            @client.on(events.NewMessage(outgoing=True))
            async def client_selfbot_handler(event):
                # Proteksi Privasi: Hanya respon perintah self-panel jika dikirim di obrolan dengan bot utama
                if BOT_ID != 0 and event.chat_id != BOT_ID:
                    return

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
                        from src.database import db_delete_auto_reply_by_keyword
                        if db_delete_auto_reply_by_keyword(user_id, ar_args):
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
                uid_settings = client_settings.get(phone, {})
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
                            logger.info(f"🎯 PM Permit Auto-Funnel dikirim ke {sender_id} via userbot {phone}")
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
                            from src.database import db_cooldown_client_userbot
                            db_cooldown_client_userbot(phone, until)
                        except Exception as e:
                            logger.error(f"Gagal mengirim auto-reply: {e}")
                        break
                        
            # Definisikan background task pemantau disconnect secara real-time
            async def handle_disconnect_task(client_inst, uid, ph, u_name, f_name):
                try:
                    await client_inst.disconnected
                    if ph not in active_clients:
                        return  # Sudah di-stop secara sengaja, tidak perlu reconnect
                        
                    logger.warning(f"⚠️ Userbot {ph} terputus secara tidak terduga! Mencoba reconnect otomatis...")
                    active_clients.pop(ph, None)
                    
                    # AUTO-RECONNECT: Coba sampai 3 kali dengan jeda
                    max_retries = 3
                    reconnected = False
                    for attempt in range(1, max_retries + 1):
                        logger.info(f"🔄 Percobaan reconnect #{attempt} untuk {ph}...")
                        await asyncio.sleep(10 * attempt)  # Jeda makin panjang: 10s, 20s, 30s
                        try:
                            ok = await start_client_userbot(uid, f"user_{ph.replace('+','')}", ph)
                            if ok:
                                reconnected = True
                                logger.info(f"✅ Userbot {ph} berhasil reconnect otomatis pada percobaan #{attempt}!")
                                break
                        except Exception as retry_err:
                            logger.error(f"Gagal reconnect #{attempt} untuk {ph}: {retry_err}")
                    
                    if not reconnected:
                        from src.database import db_update_userbot_status
                        db_update_userbot_status(ph, 'disconnected')
                        
                        try:
                            from src.main import bot
                            from src.config import ADMIN_ID
                            from src.notifications import notify_admin_userbot_disconnected
                            await notify_admin_userbot_disconnected(bot, int(ADMIN_ID), uid, f_name, u_name)
                        except Exception as err:
                            logger.error(f"Gagal kirim notif diskoneksi admin: {err}")
                            
                        # Kirim notifikasi ke pembeli (client) beserta tombol aksi
                        try:
                            from src.main import bot
                            from telethon import Button
                            client_msg = (
                                f"⚠️ **Koneksi Userbot Anda Terputus!**\n\n"
                                f"Nomor: `{ph}`\n"
                                f"Status: **Disconnected**\n\n"
                                f"Silakan pilih tindakan di bawah ini untuk mencoba menyambungkan kembali secara otomatis atau mengganti nomor telepon:"
                            )
                            buttons = [
                                [
                                    Button.inline("🔄 Reconnect Otomatis", f"conn_toggle_{ph}".encode()),
                                    Button.inline("♻️ Ganti Nomor (Reset)", f"del_session_{ph}".encode())
                                ]
                            ]
                            await bot.send_message(uid, client_msg, buttons=buttons)
                        except Exception as client_err:
                            logger.error(f"Gagal kirim notif diskoneksi ke pembeli {uid}: {client_err}")
                except Exception as ex:
                    logger.error(f"Error di disconnect task untuk {ph}: {ex}")

            from src.database import db_get_user_info
            u_info = db_get_user_info(user_id)
            asyncio.create_task(handle_disconnect_task(client, user_id, phone, u_info["username"], u_info["full_name"]))

            return True
        except Exception as e:
            logger.error(f"Error saat mengaktifkan userbot {phone}: {e}")
            from src.database import db_update_userbot_status, db_get_user_info
            db_update_userbot_status(phone, 'disconnected')
            
            try:
                u_info = db_get_user_info(user_id)
                from src.main import bot
                from src.config import ADMIN_ID
                from src.notifications import notify_admin_userbot_disconnected
                await notify_admin_userbot_disconnected(bot, int(ADMIN_ID), user_id, u_info["full_name"], u_info["username"])
            except Exception as notif_err:
                logger.error(f"Gagal kirim notif kegagalan startup userbot ke admin: {notif_err}")
                
            try:
                if 'client' in locals() and client.is_connected():
                    await client.disconnect()
            except Exception as disc_err:
                logger.error(f"Gagal disconnect client saat cleanup: {disc_err}")
            return False

async def stop_client_userbot(phone_number: str):
    """Mematikan sesi online satu userbot klien berdasarkan nomor HP."""
    client = active_clients.pop(phone_number, None)
    if client:
        try:
            if client.is_connected():
                await client.disconnect()
            logger.info(f"🔌 Userbot Klien (Nomor: {phone_number}) berhasil dimatikan.")
            return True
        except Exception as e:
            logger.error(f"Error saat mematikan userbot {phone_number}: {e}")
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

async def update_single_online_userbot_bio(phone: str, bio_text: str):
    """Mengubah bio Telegram secara fisik di akun klien tertentu jika sedang online berdasarkan nomor HP."""
    client = active_clients.get(phone)
    if client:
        try:
            if client.is_connected():
                from telethon.tl.functions.account import UpdateProfileRequest
                await client(UpdateProfileRequest(about=bio_text[:70]))
                logger.info(f"✅ Bio userbot {phone} berhasil diubah secara live ke: {bio_text[:70]}")
        except Exception as e:
            logger.error(f"Gagal mengubah bio Telegram live untuk {phone}: {e}")

async def update_single_online_userbot_pm_permit(phone: str, pm_status: bool):
    """Memperbarui status cache PM Permit untuk klien tertentu secara instan berdasarkan nomor HP."""
    if phone in client_settings:
        client_settings[phone]["pm_permit"] = pm_status
    else:
        client_settings[phone] = {"pm_permit": pm_status, "bio": ""}

async def run_expired_userbots_cleaner(bot=None):
    """
    Daemon task yang berjalan periodik untuk mematikan koneksi userbot klien 
    yang masa langganannya telah habis (expired).
    """
    logger.info("⏰ Memulai cleaner daemon untuk mendeteksi userbot expired...")
    while True:
        try:
            from src.database import get_supabase
            supabase = get_supabase()
            
            # Ambil semua userbot yang berstatus terhubung
            res = supabase.table("userbots").select("phone_number, user_id").eq("status", "connected").execute()
            connected_userbots = res.data or []
            
            now_str = datetime.now(timezone.utc).isoformat()
            
            for ub in connected_userbots:
                phone = ub["phone_number"]
                user_id = ub["user_id"]
                
                # Cek apakah ada subscription aktif
                res_subs = supabase.table("subscriptions")\
                    .select("id")\
                    .eq("user_id", user_id)\
                    .eq("status", "active")\
                    .gt("end_date", now_str)\
                    .execute()
                
                # Jika tidak ada subscription aktif, matikan userbot secara paksa
                if not res_subs.data:
                    logger.info(f"🚨 Userbot {phone} milik User ID {user_id} terdeteksi expired. Mematikan koneksi...")
                    await stop_client_userbot(phone)
                    supabase.table("userbots").update({"status": "disconnected"}).eq("phone_number", phone).execute()
                    
                    try:
                        if bot:
                            await bot.send_message(
                                user_id, 
                                f"🚨 **MASA AKTIF USERBOT HABIS!**\n\n"
                                f"Layanan userbot `{phone}` Anda telah dinonaktifkan karena paket langganan Anda telah kedaluwarsa. "
                                "Silakan lakukan perpanjangan paket melalui Mini App agar layanan kembali aktif."
                            )
                            
                            from src.database import db_get_user_info
                            u_info = db_get_user_info(user_id)
                            from src.config import ADMIN_ID
                            from src.notifications import notify_admin_userbot_disconnected
                            await notify_admin_userbot_disconnected(
                                bot, 
                                int(ADMIN_ID), 
                                user_id, 
                                u_info["full_name"], 
                                u_info["username"]
                            )
                    except Exception as notif_err:
                        logger.error(f"Gagal mengirim notif expired userbot untuk {phone}: {notif_err}")
                    
        except Exception as e:
            logger.error(f"Error pada daemon run_expired_userbots_cleaner: {e}")
            
        # Berjalan setiap 1 jam
        await asyncio.sleep(3600)
