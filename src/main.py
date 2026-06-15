"""
main.py — Core Bot GEUNID JASEB
================================
Bertanggung jawab atas:
- Inisialisasi bot dan database
- Handler /start (menu utama client & admin)
- State machine: waiting_for_ad, waiting_for_lpm_request, waiting_for_phone, waiting_for_otp, waiting_for_password
- Payment flow: check_payment_status_handler
- Order format parser (auto-invoice dari format teks)
- LPM Scanner (/scan) — admin only
- Userbot installer (/install) — admin only
- Scheduler autopilot & auto-reminder perpanjang
- Integrasi client_handlers dan admin_handlers
"""

import asyncio
import logging
import re
import os
import json
from datetime import datetime, timedelta

from telethon import TelegramClient, events, Button
from telethon.errors import UserNotParticipantError
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.tl.types import KeyboardButtonWebView, KeyboardButtonCallback, KeyboardButtonUrl

from src.config import API_ID, API_HASH, BOT_TOKEN, ADMIN_ID, CHANNEL_USERNAME, ADMIN_USERNAME, MINI_APP_URL
from src.database import init_db, get_db
from src.ui_styles import EMOJI_UI, format_menu_text
from src.payments import create_qris_transaction, check_transaction_status
from src.jaseb_engine import JasebEngine
from src.notifications import (
    notify_admin_payment_success,
    notify_client_broadcast_start,
    notify_client_broadcast_done,
    notify_client_subscription_expiring,
    notify_client_ad_saved,
)

# ─────────────────────────────────────────
# Konfigurasi Logging
# ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# Inisialisasi Bot Client
# Simpan session di data/ agar persisten di Railway
# ─────────────────────────────────────────
os.makedirs("data", exist_ok=True)
bot = TelegramClient('data/bot_session', API_ID, API_HASH)

# State machine untuk percakapan multi-langkah
login_states = {}

async def clear_login_state(user_id):
    """Membersihkan state login client dengan aman dan memutus koneksi client jika ada."""
    state_data = login_states.pop(user_id, None)
    if state_data and "client" in state_data:
        try:
            client = state_data["client"]
            if client and client.is_connected():
                await client.disconnect()
        except Exception as e:
            logger.error(f"Gagal memutuskan koneksi client saat clear state: {e}")


# ─────────────────────────────────────────
# Helpers: Load Prices
# ─────────────────────────────────────────
def load_prices():
    try:
        prices_path = os.path.join("frontend", "src", "prices.json")
        if os.path.exists(prices_path):
            with open(prices_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Gagal memuat prices.json: {e}")
    return {}


def get_package_duration_days(package_name: str, amount: int) -> int:
    prices = load_prices()
    if not prices:
        return 30
    amount = int(amount)
    for category in ['regular', 'forward', 'userbot']:
        for item in prices.get(category, []):
            if int(item.get('promoPrice', 0)) == amount:
                duration_str = item.get('duration', '')
                days = 0
                m = re.search(r'(\d+)\s*Hari', duration_str, re.IGNORECASE)
                if m:
                    days = int(m.group(1))
                bonus_str = item.get('bonus', '')
                if bonus_str:
                    bm = re.search(r'\+(\d+)\s*Hari', bonus_str, re.IGNORECASE)
                    if bm:
                        days += int(bm.group(1))
                if days > 0:
                    return days
    m = re.search(r'(\d+)\s*Hari', package_name, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return 30


def get_capacity_from_package(package_name: str) -> int:
    """Ambil kapasitas LPM dari nama paket."""
    for lpm in [50, 30, 20]:
        if str(lpm) in package_name:
            return lpm
    return 20  # default


# ─────────────────────────────────────────
# Helper: Cek Channel Join
# ─────────────────────────────────────────
async def check_channel_join(event) -> bool:
    user_id = event.sender_id
    if not user_id or user_id == ADMIN_ID:
        return True
    if not CHANNEL_USERNAME:
        return True
    try:
        await bot(GetParticipantRequest(channel=CHANNEL_USERNAME, participant=user_id))
        return True
    except UserNotParticipantError:
        invite_link = f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"
        text = format_menu_text(
            f"{EMOJI_UI['shield']} WAJIB BERGABUNG CHANNEL",
            f"Untuk menggunakan bot ini, bergabunglah ke channel resmi kami terlebih dahulu.\n\n"
            f"Channel: **{CHANNEL_USERNAME}**\n\n"
            "Setelah bergabung, klik tombol **🔄 Cek Status** di bawah."
        )
        buttons = [
            [Button.url(f"{EMOJI_UI['rocket']} Gabung Channel", invite_link)],
            [Button.inline("🔄 Cek Status", b"check_join_status")]
        ]
        if hasattr(event, "edit"):
            try:
                await event.edit(text, buttons=buttons)
            except Exception:
                await event.respond(text, buttons=buttons)
        else:
            await event.respond(text, buttons=buttons)
        return False
    except Exception as e:
        logger.error(f"Error cek channel join: {e}")
        return True


@bot.on(events.CallbackQuery(data=b"check_join_status"))
async def check_join_status_handler(event):
    try:
        await bot(GetParticipantRequest(channel=CHANNEL_USERNAME, participant=event.sender_id))
        await event.answer("✅ Terima kasih! Akses bot Anda aktif.", alert=True)
        await callback_start_handler(event)
    except UserNotParticipantError:
        await event.answer("❌ Anda belum bergabung ke channel!", alert=True)
    except Exception:
        await event.answer("✅ Akses aktif.", alert=True)
        await callback_start_handler(event)


# ─────────────────────────────────────────
# Helper: Buat URL Mini App
# ─────────────────────────────────────────
async def get_web_app_url(user_id: int) -> str:
    total_broadcast = total_lpm = total_userbots = 0
    user_bot_status = 'disconnected'
    user_package = 'Tidak Aktif'
    user_lpm = 0
    user_days = 0
    try:
        async with get_db() as db:
            cur = await db.execute("SELECT COUNT(*) FROM forward_logs WHERE status='success'")
            total_broadcast = (await cur.fetchone())[0]
            cur = await db.execute("SELECT COUNT(*) FROM lpm_lists WHERE is_active=1 AND is_blacklisted=0")
            total_lpm = (await cur.fetchone())[0]
            cur = await db.execute("SELECT COUNT(*) FROM userbots WHERE status='connected'")
            total_userbots = (await cur.fetchone())[0]
            cur = await db.execute("SELECT status FROM userbots WHERE user_id=?", (user_id,))
            row = await cur.fetchone()
            if row:
                user_bot_status = row[0]
            cur = await db.execute("""
                SELECT package_name, capacity_lpm, end_date FROM subscriptions
                WHERE user_id=? AND status='active' AND end_date > datetime('now','localtime')
                ORDER BY end_date DESC LIMIT 1
            """, (user_id,))
            row = await cur.fetchone()
            if row:
                user_package = row[0]
                user_lpm = row[1]
                try:
                    clean_date = row[2].split(".")[0]
                    end_dt = datetime.strptime(clean_date, "%Y-%m-%d %H:%M:%S")
                    user_days = max(0, (end_dt - datetime.now()).days)
                except Exception:
                    user_days = 0
    except Exception as e:
        logger.error(f"Error build WebApp URL: {e}")
    import urllib.parse
    pkg_encoded = urllib.parse.quote(str(user_package))
    ub_status_encoded = urllib.parse.quote(str(user_bot_status))
    return (
        f"{MINI_APP_URL.rstrip('/')}/?"
        f"b={total_broadcast}&l={total_lpm}&u={total_userbots}"
        f"&ub={ub_status_encoded}&pkg={pkg_encoded}&ulpm={user_lpm}&days={user_days}"
    )


# ─────────────────────────────────────────
# /start & callback start
# ─────────────────────────────────────────
@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    if not await check_channel_join(event):
        return
    await clear_login_state(event.sender_id)
    await _show_start_menu(event, is_callback=False)


@bot.on(events.CallbackQuery(data=b"start"))
async def callback_start_handler(event):
    await clear_login_state(event.sender_id)
    await _show_start_menu(event, is_callback=True)


async def _show_start_menu(event, is_callback: bool = False):
    sender = await event.get_sender()
    user_id = event.sender_id
    full_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()

    # Pastikan user terdaftar di DB
    try:
        async with get_db() as db:
            await db.execute(
                "INSERT INTO users (user_id, username, full_name) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, full_name=excluded.full_name",
                (user_id, sender.username or "", full_name)
            )
            await db.commit()
    except Exception as e:
        logger.error(f"Error upsert user: {e}")

    web_app_url = await get_web_app_url(user_id)

    if user_id == ADMIN_ID:
        title = f"{EMOJI_UI['start']} PANEL ADMIN GEUNID-JASEB"
        content = (
            f"Halo **{full_name}** (Owner/Admin)!\n\n"
            f"{EMOJI_UI['rocket']} **Command Admin:**\n"
            "• `/admin` — Panel admin lengkap\n"
            "• `/setprice` — Edit harga paket\n"
            "• `/billing` — Kelola langganan client\n"
            "• `/ubots` — Kelola semua userbot\n"
            "• `/broadcast_all` — Trigger sebar semua\n"
            "• `/scan @grup` — Scan LPM\n"
            "• `/install` — Sambung ubot admin"
        )
        buttons = [
            [KeyboardButtonWebView(text=f"{EMOJI_UI['rocket']} Buka Mini App", url=web_app_url)],
            [KeyboardButtonCallback(text="🛡️ Panel Admin", data=b"admin_main"),
             KeyboardButtonCallback(text="📊 Statistik", data=b"admin_stats")],
            [KeyboardButtonCallback(text="💰 Edit Harga", data=b"admin_prices"),
             KeyboardButtonCallback(text="👥 Billing", data=b"admin_billing")],
            [KeyboardButtonCallback(text="🤖 Userbot", data=b"admin_ubots"),
             KeyboardButtonCallback(text="📋 Order", data=b"admin_orders")],
        ]
    else:
        title = f"{EMOJI_UI['start']} GEUNID-JASEB"
        content = (
            f"Halo **{full_name}**! Selamat datang di layanan **GEUNID-JASEB**.\n\n"
            "Sebar teks promosi Anda ke ribuan grup Telegram secara otomatis!\n\n"
            "📖 `/help` — Panduan lengkap & daftar harga\n"
            "🛒 Langsung order via tombol di bawah\n"
            "📊 `/mystatus` — Cek status jaseb Anda"
        )
        buttons = [
            [KeyboardButtonWebView(text=f"{EMOJI_UI['rocket']} Buka Mini App", url=web_app_url)],
            [KeyboardButtonCallback(text="📖 Bantuan & Harga", data=b"help_main"),
             KeyboardButtonWebView(text="🛒 Order Sekarang", url=web_app_url)],
            [KeyboardButtonCallback(text="📊 Status Jaseb Saya", data=b"my_status")],
            [KeyboardButtonUrl(text="📞 Hubungi Admin", url=f"https://t.me/{ADMIN_USERNAME.replace('@', '')}")],
        ]

    text = format_menu_text(title, content)
    if is_callback:
        try:
            await event.edit(text, buttons=buttons)
        except Exception:
            await event.respond(text, buttons=buttons)
    else:
        await event.respond(text, buttons=buttons)


# ─────────────────────────────────────────
# Profil User — Data Real dari DB
# ─────────────────────────────────────────
@bot.on(events.CallbackQuery(data=b"profile"))
async def profile_handler(event):
    user_id = event.sender_id
    sender = await event.get_sender()
    full_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
    username = f"@{sender.username}" if sender.username else f"ID: {sender.id}"

    async with get_db() as db:
        cur = await db.execute("""
            SELECT package_name, capacity_lpm, end_date, broadcast_interval_hours
            FROM subscriptions
            WHERE user_id=? AND status='active' AND end_date > datetime('now','localtime')
            ORDER BY end_date DESC LIMIT 1
        """, (user_id,))
        sub = await cur.fetchone()
        cur = await db.execute("SELECT status, phone_number FROM userbots WHERE user_id=?", (user_id,))
        ub_row = await cur.fetchone()
        cur = await db.execute("SELECT COUNT(*) FROM forward_logs WHERE user_id=? AND status='success'", (user_id,))
        total_sent = (await cur.fetchone())[0]

    ub_status = "Terhubung ✅" if (ub_row and ub_row[0] == "connected") else "Tidak terhubung ❌"

    if sub:
        pkg_name, capacity, end_date, interval = sub
        try:
            clean_end = end_date.split(".")[0]
            end_dt = datetime.strptime(clean_end, "%Y-%m-%d %H:%M:%S")
            days_left = max(0, (end_dt - datetime.now()).days)
        except Exception:
            days_left = 0
        pkg_info = (
            f"• **Paket:** {pkg_name}\n"
            f"• **Kapasitas:** {capacity} LPM\n"
            f"• **Sisa:** {days_left} hari\n"
            f"• **Jadwal Sebar:** Setiap {interval or 2} jam\n"
            f"• **Total Terkirim:** {total_sent} pesan"
        )
    else:
        pkg_info = "• **Paket:** Tidak ada paket aktif\n• Gunakan /help untuk order."

    title = f"{EMOJI_UI['profile']} PROFIL SAYA"
    content = (
        f"👤 **{full_name}**\n"
        f"• **Username:** {username}\n"
        f"• **ID Telegram:** `{sender.id}`\n\n"
        f"🤖 **Userbot:** {ub_status}\n\n"
        f"📦 **Status Langganan:**\n{pkg_info}"
    )
    text = format_menu_text(title, content)
    buttons = [
        [Button.inline("📊 Status Jaseb", b"my_status"),
         Button.inline("📜 Riwayat Kirim", b"view_logs")],
        [Button.inline(f"{EMOJI_UI['back']} Kembali", b"start")]
    ]
    await event.edit(text, buttons=buttons)


# ─────────────────────────────────────────
# Statistik Global
# ─────────────────────────────────────────
@bot.on(events.CallbackQuery(data=b"stats"))
async def stats_handler(event):
    async with get_db() as db:
        cur = await db.execute("SELECT COUNT(*) FROM forward_logs WHERE status='success'")
        total_broadcast = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM lpm_lists WHERE is_active=1 AND is_blacklisted=0")
        total_lpm = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM userbots WHERE status='connected'")
        total_userbots = (await cur.fetchone())[0]

    title = f"{EMOJI_UI['analytics']} STATISTIK GLOBAL"
    content = (
        f"• **Total Broadcast:** {total_broadcast:,} Pesan\n"
        f"• **Grup LPM Aktif:** {total_lpm} Grup\n"
        f"• **Kecepatan Kirim:** ~1.5s / grup\n"
        f"• **Userbot Aktif:** {total_userbots} Akun\n\n"
        "⚡ _Statistik real-time dari database cluster GeunID._"
    )
    await event.edit(format_menu_text(title, content), buttons=[[Button.inline(f"{EMOJI_UI['back']} Kembali", b"start")]])


# ─────────────────────────────────────────
# Panduan (redirect ke help baru)
# ─────────────────────────────────────────
@bot.on(events.CallbackQuery(data=b"guide"))
async def guide_handler(event):
    # Redirect ke help_main dari client_handlers
    await event.edit(data=b"help_main")


# ─────────────────────────────────────────
# Riwayat Kirim (Proof Hub)
# ─────────────────────────────────────────
@bot.on(events.CallbackQuery(data=b"view_logs"))
async def view_logs_handler(event):
    async with get_db() as db:
        cur = await db.execute("""
            SELECT l.group_name, f.msg_link, f.status, f.sent_at
            FROM forward_logs f
            LEFT JOIN lpm_lists l ON f.group_id = l.group_id
            WHERE f.user_id=? ORDER BY f.sent_at DESC LIMIT 10
        """, (event.sender_id,))
        logs = await cur.fetchall()

    if not logs:
        await event.answer("📭 Belum ada riwayat pengiriman.", alert=True)
        return

    text = "📜 **Proof Hub — 10 Pengiriman Terakhir**\n\n"
    for group_name, link, status, sent_at in logs:
        group_name = group_name or "Grup LPM"
        icon = "✅" if status == 'success' else "❌"
        time_str = sent_at.split()[1] if sent_at and " " in sent_at else "-"
        if link:
            text += f"{icon} [{group_name}]({link}) | 🕒 {time_str}\n"
        else:
            text += f"{icon} {group_name} (Gagal) | 🕒 {time_str}\n"

    text += "\n_Klik link untuk melihat pesan di grup._"
    await event.edit(text, buttons=[[Button.inline("⬅️ Kembali", b"profile")]])


# ─────────────────────────────────────────
# Login Userbot (Admin & Client)
# ─────────────────────────────────────────
@bot.on(events.CallbackQuery(data=b"login_userbot"))
async def login_userbot_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("⚠️ Fitur Userbot hanya untuk Admin.", alert=True)
        return
    await _show_userbot_menu(event)


async def _show_userbot_menu(event):
    user_id = event.sender_id
    async with get_db() as db:
        cur = await db.execute("SELECT phone_number, status FROM userbots WHERE user_id=?", (user_id,))
        ub = await cur.fetchone()

    title = f"{EMOJI_UI['shield']} MANAJEMEN USERBOT"
    if ub and ub[1] == 'connected':
        content = (
            f"📱 **Userbot Admin Aktif!**\n\n"
            f"• **Nomor HP:** `{ub[0]}`\n"
            f"• **Status:** Terhubung ✅\n\n"
            "Userbot admin digunakan untuk melayani jaseb Regular & Forward semua client."
        )
        buttons = [
            [Button.inline("❌ Putuskan Hubungan", b"disconnect_userbot")],
            [Button.inline(f"{EMOJI_UI['back']} Kembali", b"start")]
        ]
    else:
        content = (
            "Hubungkan akun Telegram Admin sebagai userbot.\n\n"
            "**Fungsi:**\n"
            "• Mengirim jaseb Regular & Forward untuk semua client\n"
            "• Berjalan otomatis 24/7\n\n"
            "⚠️ _Gunakan nomor yang tidak dipakai sehari-hari untuk keamanan._"
        )
        buttons = [
            [Button.inline("➕ Hubungkan Nomor Baru", b"add_number")],
            [Button.inline(f"{EMOJI_UI['back']} Kembali", b"start")]
        ]
    await event.edit(format_menu_text(title, content), buttons=buttons)


@bot.on(events.CallbackQuery(data=b"disconnect_userbot"))
async def disconnect_userbot_handler(event):
    async with get_db() as db:
        await db.execute("UPDATE userbots SET status='disconnected' WHERE user_id=?", (event.sender_id,))
        await db.commit()
    session_file = f"data/sessions/user_{event.sender_id}.session"
    if os.path.exists(session_file):
        try:
            os.remove(session_file)
        except Exception as e:
            logger.error(f"Gagal hapus session: {e}")
    await event.answer("🔌 Userbot Admin diputuskan.", alert=True)
    await _show_userbot_menu(event)


@bot.on(events.CallbackQuery(data=b"add_number"))
async def add_number_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("⚠️ Hanya Admin.", alert=True)
        return
    login_states[event.sender_id] = {"state": "waiting_for_phone"}
    await event.edit(
        "📱 **Kirimkan nomor HP Anda** (format internasional).\n\n"
        "Contoh: `+628123456789`\n\n"
        "⚠️ _Kode OTP akan dikirim ke Telegram Anda._"
    )


# ─────────────────────────────────────────
# /install — Shortcut install userbot admin
# ─────────────────────────────────────────
@bot.on(events.NewMessage(pattern='/install'))
async def install_command_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.respond(f"⚠️ Perintah `/install` hanya untuk Admin.")
        return
    login_states[event.sender_id] = {"state": "waiting_for_phone"}
    await event.respond(
        "📱 **Kirimkan nomor HP Anda** (format internasional).\n\n"
        "Contoh: `+628123456789`\n\n"
        "⚠️ _Kode OTP akan dikirim ke Telegram Anda._"
    )


# ─────────────────────────────────────────
# State Machine — Input User (Multi-langkah)
# ─────────────────────────────────────────
@bot.on(events.NewMessage)
async def user_input_handler(event):
    """Handler utama untuk semua state machine percakapan."""
    text = (event.text or "").strip()
    if text.startswith("/"):
        return

    if event.sender_id not in login_states:
        return

    state_data = login_states[event.sender_id]
    current_state = state_data.get("state", "")

    # Guard: jika state adalah state admin, biarkan admin_handlers yang tangani
    if current_state.startswith("admin_"):
        return

    text = (event.text or "").strip()

    # ── State: Menunggu bukti transfer manual ──
    if current_state == "waiting_for_proof":
        if not event.message.photo and not event.message.document:
            await event.respond("❌ Harap kirimkan bukti transfer berupa foto atau screenshot bukti pembayaran Anda.")
            return

        await event.respond("⏳ Mengunduh dan mengirimkan bukti transfer ke Owner untuk verifikasi...")
        media_path = ""
        try:
            os.makedirs("data/proofs", exist_ok=True)
            media_path = await event.message.download_media(file="data/proofs/")
        except Exception as e:
            logger.error(f"Gagal unduh bukti transfer: {e}")
            await event.respond("❌ Gagal memproses gambar bukti transfer. Silakan coba kirim ulang.")
            return

        trx_id = state_data.get("trx_id")
        amount = state_data.get("amount")
        package_name = state_data.get("package_name")

        async with get_db() as db:
            await db.execute(
                "UPDATE transactions SET status='waiting_approval', payment_url=? WHERE trx_id=?",
                (media_path, trx_id)
            )
            await db.commit()

        sender = await event.get_sender()
        full_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
        uname_str = f"@{sender.username}" if sender.username else f"ID: {event.sender_id}"

        admin_msg = (
            f"🔔 **PERMINTAAN PERSETUJUAN TRANSFER MANUAL**\n\n"
            f"👤 Client: **{full_name}** ({uname_str})\n"
            f"📦 Paket: `{package_name}`\n"
            f"💰 Nominal: Rp {amount:,}\n"
            f"🔖 Invoice: `{trx_id}`\n\n"
            f"Silakan periksa bukti transfer di atas lalu tekan tombol di bawah:"
        )

        buttons = [
            [
                Button.inline("Approve ✅", f"approve_man_{trx_id}".encode()),
                Button.inline("Reject ❌", f"reject_man_{trx_id}".encode())
            ]
        ]

        try:
            await bot.send_file(ADMIN_ID, file=media_path, caption=admin_msg, buttons=buttons)
        except Exception as e:
            logger.error(f"Gagal kirim bukti ke admin: {e}")
            await bot.send_message(ADMIN_ID, admin_msg, buttons=buttons)

        del login_states[event.sender_id]
        await event.respond(
            "⏳ **Bukti transfer Anda telah dikirim ke Owner.**\n\n"
            "Mohon tunggu beberapa saat selagi Owner melakukan verifikasi. "
            "Anda akan menerima notifikasi otomatis begitu pembayaran Anda disetujui."
        )
        return

    # ── State: Menunggu materi jaseb dari client ──
    elif current_state == "waiting_for_ad":
        content_text = event.message.message or ""
        media_path = ""

        await event.respond("⏳ Menyimpan materi jaseb Anda...")

        if event.message.media:
            try:
                os.makedirs("data/media", exist_ok=True)
                media_path = await event.message.download_media(file="data/media/")
            except Exception as e:
                logger.error(f"Gagal download media: {e}")
                await event.respond("⚠️ Gagal unduh media. Jaseb disimpan tanpa media.")

        async with get_db() as db:
            await db.execute("DELETE FROM user_ads WHERE user_id=?", (event.sender_id,))
            await db.execute(
                "INSERT INTO user_ads (user_id, title, content, media_path) VALUES (?, ?, ?, ?)",
                (event.sender_id, "Jaseb Utama", content_text, media_path)
            )
            await db.commit()

        login_states[event.sender_id]["state"] = "waiting_for_lpm_request"
        await notify_client_ad_saved(bot, event.sender_id)
        return

    # ── State: Menunggu daftar LPM kustom ──
    elif current_state == "waiting_for_lpm_request":
        lpm_list_str = ""

        if text.lower() != "/skip":
            links = re.findall(
                r'(?:https?://)?(?:t\.me/|@)?([a-zA-Z0-9_]{5,32}|joinchat/[a-zA-Z0-9_\-]+)', text
            )
            if not links:
                await event.respond(
                    "❌ Tidak ada link LPM valid!\n"
                    "Kirim daftar LPM kustom Anda (Contoh: `@lpm1 @lpm2`) atau ketik `/skip` untuk pakai LPM default."
                )
                return

            await event.respond(f"⏳ Sedang memvalidasi **{len(links[:10])} grup LPM** Anda secara otomatis...")

            valid_links = []
            success_count = 0
            failed_count = 0

            for link in links[:10]:  # Batasi maks 10 kustom
                full_link = f"@{link}" if not ("t.me" in link or "joinchat" in link) else link
                res = await JasebEngine.verify_lpm_group(bot, full_link)
                if res.get("success"):
                    valid_links.append(full_link)
                    success_count += 1
                    # Simpan otomatis ke lpm_lists global agar bisa digunakan sistem di masa depan!
                    try:
                        async with get_db() as db:
                            await db.execute(
                                "INSERT OR IGNORE INTO lpm_lists (group_link, group_id, group_name, member_count, is_active) VALUES (?, ?, ?, ?, ?)",
                                (full_link, res["group_id"], res["group_name"], res["member_count"], 1)
                            )
                            await db.commit()
                    except Exception as db_err:
                        logger.error(f"Gagal menyimpan LPM kustom ke database global: {db_err}")
                else:
                    failed_count += 1

            if not valid_links:
                await event.respond(
                    "❌ Tidak ada satu pun grup LPM yang Anda kirimkan terbukti valid di Telegram!\n"
                    "Silakan kirimkan kembali daftar LPM kustom yang valid atau ketik `/skip` untuk menggunakan LPM default."
                )
                return

            lpm_list_str = " ".join(valid_links)
            await event.respond(
                f"✅ **Verifikasi Selesai!**\n"
                f"• Berhasil disimpan: **{success_count} grup** (otomatis ditambahkan ke database global sistem)\n"
                f"• Gagal/Tidak Valid: **{failed_count} grup**"
            )

        async with get_db() as db:
            await db.execute(
                "UPDATE subscriptions SET request_lpm=? WHERE user_id=? AND status='active'",
                (lpm_list_str or None, event.sender_id)
            )
            await db.commit()

        del login_states[event.sender_id]

        await event.respond(
            "🎉 **Pendaftaran Jaseb Selesai!**\n\n"
            "Bot akan mulai menyebarkan teks Anda secara otomatis sekarang.\n"
            "Ketik /mystatus untuk memantau perkembangan."
        )
        # Trigger broadcast pertama
        asyncio.create_task(start_user_broadcast(event.sender_id))
        return

    # ── State: Menunggu nomor HP untuk login userbot ──
    elif current_state == "waiting_for_phone":
        phone_number = text.replace(" ", "").replace("-", "")
        if not phone_number.startswith("+"):
            await event.respond("❌ Format salah! Gunakan format: `+628123456789`")
            return

        await event.respond("⏳ Menghubungkan ke Telegram & mengirim OTP...")
        os.makedirs("data/sessions", exist_ok=True)
        session_path = f"data/sessions/user_{event.sender_id}"
        client = TelegramClient(session_path, API_ID, API_HASH, receive_updates=False)
        try:
            await client.connect()
            send_code_result = await client.send_code_request(phone_number)
            login_states[event.sender_id] = {
                "state": "waiting_for_otp",
                "phone": phone_number,
                "client": client,
                "phone_code_hash": send_code_result.phone_code_hash
            }
            await event.respond(
                "📨 **Kode OTP dikirim oleh Telegram!**\n\n"
                "Kirimkan kode OTP 5 digit di sini. Contoh: `12345`"
            )
        except Exception as e:
            logger.error(f"Gagal kirim OTP: {e}")
            await event.respond(f"❌ Gagal kirim OTP: {str(e)}")
            await clear_login_state(event.sender_id)

    # ── State: Menunggu OTP ──
    elif current_state == "waiting_for_otp":
        otp_code = text.replace(" ", "")
        client = state_data["client"]
        phone = state_data["phone"]
        phone_code_hash = state_data["phone_code_hash"]
        await event.respond("⏳ Memverifikasi OTP...")
        try:
            await client.sign_in(phone=phone, code=otp_code, phone_code_hash=phone_code_hash)
            await _save_userbot_session(event, client, phone)
        except Exception as sign_in_error:
            from telethon.errors import SessionPasswordNeededError
            if isinstance(sign_in_error, SessionPasswordNeededError):
                login_states[event.sender_id]["state"] = "waiting_for_password"
                await event.respond(
                    "🔒 **Akun dilindungi 2FA.**\n\nKirimkan password 2FA Anda:"
                )
            else:
                logger.error(f"Sign-in error: {sign_in_error}")
                await event.respond(f"❌ OTP salah atau expired: {str(sign_in_error)}")

    # ── State: Menunggu Password 2FA ──
    elif current_state == "waiting_for_password":
        password = text
        client = state_data["client"]
        phone = state_data["phone"]
        await event.respond("⏳ Memverifikasi password 2FA...")
        try:
            await client.sign_in(password=password)
            await _save_userbot_session(event, client, phone)
        except Exception as p_err:
            logger.error(f"2FA login error: {p_err}")
            await event.respond(f"❌ Password 2FA salah: {str(p_err)}")


async def _save_userbot_session(event, client, phone: str):
    """Simpan session userbot ke DB setelah login berhasil."""
    sender = await event.get_sender()
    async with get_db() as db:
        await db.execute(
            "INSERT INTO users (user_id, username, full_name) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, full_name=excluded.full_name",
            (event.sender_id, sender.username or "", f"{sender.first_name or ''} {sender.last_name or ''}".strip())
        )
        await db.execute(
            "INSERT OR REPLACE INTO userbots (user_id, phone_number, session_name, status) VALUES (?, ?, ?, ?)",
            (event.sender_id, phone, f"user_{event.sender_id}", "connected")
        )
        await db.commit()
    
    # Putuskan koneksi client sementara agar session terlepas dengan bersih
    try:
        await client.disconnect()
    except Exception as e:
        logger.error(f"Gagal memutuskan koneksi client sementara: {e}")

    del login_states[event.sender_id]
    await event.respond(
        "🎉 **Userbot Berhasil Terhubung!**\n\n"
        "Sekarang jaseb akan menggunakan akun Anda sendiri (Stealth Mode aktif).\n"
        "Ketik /start untuk kembali ke menu utama."
    )


# ─────────────────────────────────────────
# Auto-Invoice Parser (Format Order Admin)
# ─────────────────────────────────────────
@bot.on(events.NewMessage(incoming=True))
async def order_format_parser(event):
    """Parse format order teks dan buat invoice QRIS otomatis atau transfer manual."""
    if event.sender_id in login_states:
        return  # Jangan proses jika sedang di state machine

    text = event.text or ""
    is_jaseb_fmt = "𝗙𝗢𝗥𝗠𝗔𝗧 𝗝𝗔𝗦𝗘𝗕 𝗢𝗧𝗢𝗠𝗔𝗧𝗜𝗦" in text or "FORMAT JASEB OTOMATIS" in text
    is_ubot_fmt = "𝗙𝗢𝗥𝗠𝗔𝗧 𝗣𝗔𝗦𝗔𝗡𝗚 𝗨𝗦𝗘𝗥𝗕𝗢𝗧" in text or "FORMAT PASANG USERBOT" in text

    if not (is_jaseb_fmt or is_ubot_fmt):
        return

    if not await check_channel_join(event):
        return

    lines = text.split("\n")
    data = {}
    for line in lines:
        if ":" in line:
            k, v = line.split(":", 1)
            clean_key = k.strip().replace("–", "").strip().lower()
            data[clean_key] = v.strip().replace('"', '')

    paket = data.get("paket jaseb", "Paket Jaseb")
    if is_ubot_fmt:
        paket = f"Userbot - {data.get('durasi userbot', '30 Hari')}"

    total_harga_str = data.get("total harga", "0")
    amount = 0
    m = re.search(r'\d[\d\.]*', total_harga_str)
    if m:
        amount = int(m.group(0).replace(".", ""))

    if amount <= 0:
        await event.respond("❌ Gagal baca nominal harga. Periksa format pesanan Anda.")
        return

    payment_method = data.get("payment", "Belum Memilih").strip()
    is_manual = "manual" in payment_method.lower() or "transfer" in payment_method.lower()

    sender = await event.get_sender()
    full_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()

    if is_manual:
        import time
        import random
        trx_id = f"TRX-MAN-{int(time.time())}{random.randint(100, 999)}"
        
        async with get_db() as db:
            await db.execute(
                "INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)",
                (event.sender_id, sender.username or "", full_name)
            )
            await db.execute(
                "INSERT INTO transactions (user_id, trx_id, package_id, amount, payment_url, status) VALUES (?, ?, ?, ?, ?, ?)",
                (event.sender_id, trx_id, paket, amount, "manual", "pending_proof")
            )
            await db.commit()

        login_states[event.sender_id] = {
            "state": "waiting_for_proof",
            "trx_id": trx_id,
            "amount": amount,
            "package_name": paket
        }

        pay_text = (
            f"📥 **INSTRUKSI TRANSFER MANUAL**\n\n"
            f"📦 **Paket:** {paket}\n"
            f"💰 **Total Bayar:** Rp {amount:,}\n\n"
            f"Silakan transfer tepat sejumlah nominal di atas ke salah satu rekening berikut:\n\n"
            f"💳 **BCA:** `0512586056` (an. Gunami)\n"
            f"📱 **DANA:** `0895365540011` (an. geungaa)\n"
            f"📲 **Gopay:** `0859741784399` (an. Walked)\n\n"
            f"⚠️ **PENTING:** Setelah melakukan transfer, silakan **kirimkan foto/screenshot bukti transfer** ke chat bot ini."
        )
        await event.respond(pay_text)
    else:
        await event.respond("⏳ Memproses pesanan & membuat QRIS...")
        trx_data = await create_qris_transaction(amount, f"Jaseb - {paket}")
        if trx_data:
            async with get_db() as db:
                await db.execute(
                    "INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)",
                    (event.sender_id, sender.username or "", full_name)
                )
                await db.execute(
                    "INSERT INTO transactions (user_id, trx_id, package_id, amount, payment_url, status) VALUES (?, ?, ?, ?, ?, ?)",
                    (event.sender_id, trx_data['transaction_id'], paket, amount, trx_data['payment_url'], 'pending')
                )
                await db.commit()

            pay_text = (
                f"✅ **Invoice QRIS Berhasil Dibuat!**\n\n"
                f"📦 **Paket:** {paket}\n"
                f"💰 **Total Bayar:** Rp {trx_data['total_amount']:,}\n"
                f"⏰ **Expired:** {trx_data['expired_at']}\n\n"
                "Scan QRIS di atas dan klik **🔄 Cek Status Bayar** setelah transfer."
            )
            await bot.send_file(
                event.chat_id,
                file=trx_data['qris_url'],
                caption=pay_text,
                buttons=[
                    [Button.url("🔗 Bayar via Browser", trx_data['payment_url'])],
                    [Button.inline("🔄 Cek Status Bayar", f"check_{trx_data['transaction_id']}".encode())]
                ]
            )
        else:
            await event.respond(f"❌ Gagal buat QRIS. Hubungi admin: {ADMIN_USERNAME}")


# ─────────────────────────────────────────
# Cek Status Pembayaran
# ─────────────────────────────────────────
@bot.on(events.CallbackQuery(pattern=b"check_(.+)"))
async def check_payment_status_handler(event):
    trx_id = event.pattern_match.group(1).decode('utf-8')
    status_response = await check_transaction_status(trx_id)

    if not status_response or not status_response.get("success"):
        await event.answer("❌ Gagal cek status ke gateway. Coba lagi.", alert=True)
        return

    status = status_response.get("data", {}).get("status", "")

    if status == "success":
        async with get_db() as db:
            cur = await db.execute(
                "SELECT user_id, amount, package_id, status FROM transactions WHERE trx_id=?", (trx_id,)
            )
            trx_row = await cur.fetchone()

        if not trx_row:
            await event.answer("✅ Pembayaran sukses!", alert=True)
            return

        u_id, amount, package_name, old_status = trx_row

        if old_status != 'pending':
            await event.answer("⚠️ Transaksi ini sudah diproses sebelumnya.", alert=True)
            return

        # Update transaksi
        async with get_db() as db:
            await db.execute("UPDATE transactions SET status='success' WHERE trx_id=?", (trx_id,))
            package_name = str(package_name or "Paket Jaseb")
            capacity = get_capacity_from_package(package_name)
            days = get_package_duration_days(package_name, amount)
            now = datetime.now()

            cur = await db.execute(
                "SELECT id, end_date FROM subscriptions WHERE user_id=? AND status='active'", (u_id,)
            )
            sub_row = await cur.fetchone()

            if sub_row:
                sub_id, current_end_str = sub_row
                try:
                    current_end = datetime.strptime(current_end_str.split(".")[0], "%Y-%m-%d %H:%M:%S")
                except Exception:
                    current_end = now
                new_end = (current_end if current_end > now else now) + timedelta(days=days)
                new_end_str = new_end.strftime("%Y-%m-%d %H:%M:%S")
                await db.execute(
                    "UPDATE subscriptions SET package_name=?, capacity_lpm=?, end_date=? WHERE id=?",
                    (package_name, capacity, new_end_str, sub_id)
                )
            else:
                new_end = now + timedelta(days=days)
                new_end_str = new_end.strftime("%Y-%m-%d %H:%M:%S")
                await db.execute(
                    "INSERT INTO subscriptions (user_id, package_name, capacity_lpm, start_date, end_date, status) VALUES (?, ?, ?, ?, ?, ?)",
                    (u_id, package_name, capacity, now.strftime("%Y-%m-%d %H:%M:%S"), new_end_str, 'active')
                )
            await db.commit()

        # Set state sesuai paket
        is_userbot = "userbot" in package_name.lower()
        if is_userbot:
            login_states[u_id] = {
                "state": "waiting_for_phone"
            }
            await event.answer("✅ Pembayaran berhasil!", alert=True)
            await event.edit(
                f"🎉 **Pembayaran Sukses!**\n\n"
                f"📦 Paket: **{package_name}**\n"
                f"💰 Total: Rp {amount:,}\n"
                f"📅 Berlaku Hingga: **{new_end_str[:10]}**\n\n"
                f"🤖 **Sekarang kirimkan nomor HP akun Telegram Anda** (format internasional) yang ingin dijadikan Userbot.\n"
                f"Contoh: `+628123456789`"
            )
        else:
            login_states[u_id] = {
                "state": "waiting_for_ad",
                "package_name": package_name,
                "capacity": capacity
            }
            await event.answer("✅ Pembayaran berhasil!", alert=True)
            await event.edit(
                f"🎉 **Pembayaran Sukses!**\n\n"
                f"📦 Paket: **{package_name}**\n"
                f"💰 Total: Rp {amount:,}\n"
                f"📅 Berlaku Hingga: **{new_end_str[:10]}**\n\n"
                f"✍️ **Sekarang kirimkan teks yang mau di-promote** ke chat ini.\n"
                f"Bisa berupa teks, foto/video, atau pesan forward."
            )

        # Notif admin
        sender = await event.get_sender()
        full_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
        await notify_admin_payment_success(
            bot, ADMIN_ID, u_id, full_name, sender.username or "",
            package_name, amount, new_end_str[:10]
        )

    elif status == "pending":
        await event.answer("⏳ Pembayaran belum terdeteksi. Silakan transfer terlebih dahulu.", alert=True)
    else:
        await event.answer("❌ Transaksi dibatalkan atau kedaluwarsa.", alert=True)


# ─────────────────────────────────────────
# Manual Approval Handler (Untuk Admin/Owner)
# ─────────────────────────────────────────
@bot.on(events.CallbackQuery(pattern=b"approve_man_(.+)"))
async def approve_manual_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("⛔ Akses ditolak.", alert=True)
        return
    
    trx_id = event.pattern_match.group(1).decode('utf-8')
    
    async with get_db() as db:
        cur = await db.execute(
            "SELECT user_id, amount, package_id, status FROM transactions WHERE trx_id=?", (trx_id,)
        )
        trx_row = await cur.fetchone()
    
    if not trx_row:
        await event.answer("❌ Transaksi tidak ditemukan.", alert=True)
        return
    
    u_id, amount, package_name, current_status = trx_row
    
    if current_status == 'success':
        await event.answer("⚠️ Transaksi ini sudah disetujui sebelumnya.", alert=True)
        return
    
    package_name = str(package_name or "Paket Jaseb")
    capacity = get_capacity_from_package(package_name)
    days = get_package_duration_days(package_name, amount)
    now = datetime.now()
    
    async with get_db() as db:
        await db.execute("UPDATE transactions SET status='success' WHERE trx_id=?", (trx_id,))
        
        cur = await db.execute(
            "SELECT id, end_date FROM subscriptions WHERE user_id=? AND status='active'", (u_id,)
        )
        sub_row = await cur.fetchone()
        
        if sub_row:
            sub_id, current_end_str = sub_row
            try:
                current_end = datetime.strptime(current_end_str.split(".")[0], "%Y-%m-%d %H:%M:%S")
            except Exception:
                current_end = now
            new_end = (current_end if current_end > now else now) + timedelta(days=days)
            new_end_str = new_end.strftime("%Y-%m-%d %H:%M:%S")
            await db.execute(
                "UPDATE subscriptions SET package_name=?, capacity_lpm=?, end_date=? WHERE id=?",
                (package_name, capacity, new_end_str, sub_id)
            )
        else:
            new_end = now + timedelta(days=days)
            new_end_str = new_end.strftime("%Y-%m-%d %H:%M:%S")
            await db.execute(
                "INSERT INTO subscriptions (user_id, package_name, capacity_lpm, start_date, end_date, status) VALUES (?, ?, ?, ?, ?, ?)",
                (u_id, package_name, capacity, now.strftime("%Y-%m-%d %H:%M:%S"), new_end_str, 'active')
            )
        await db.commit()
    
    await event.edit(f"✅ **Transaksi `{trx_id}` Berhasil Disetujui!**\nPaket {package_name} diaktifkan untuk user ID {u_id}.")
    
    is_userbot = "userbot" in package_name.lower()
    if is_userbot:
        login_states[u_id] = {"state": "waiting_for_phone"}
        await bot.send_message(
            u_id,
            f"🎉 **Pembayaran Manual Anda Telah Disetujui oleh Owner!**\n\n"
            f"📦 Paket: **{package_name}**\n"
            f"💰 Total: Rp {amount:,}\n"
            f"📅 Berlaku Hingga: **{new_end_str[:10]}**\n\n"
            f"🤖 **Sekarang silakan kirimkan nomor HP akun Telegram Anda** (format internasional) yang ingin dijadikan Userbot.\n"
            f"Contoh: `+628123456789`"
        )
    else:
        login_states[u_id] = {
            "state": "waiting_for_ad",
            "package_name": package_name,
            "capacity": capacity
        }
        await bot.send_message(
            u_id,
            f"🎉 **Pembayaran Manual Anda Telah Disetujui oleh Owner!**\n\n"
            f"📦 Paket: **{package_name}**\n"
            f"💰 Total: Rp {amount:,}\n"
            f"📅 Berlaku Hingga: **{new_end_str[:10]}**\n\n"
            f"✍️ **Sekarang kirimkan teks yang mau di-promote** ke chat ini.\n"
            f"Bisa berupa teks, foto/video, atau pesan forward."
        )

@bot.on(events.CallbackQuery(pattern=b"reject_man_(.+)"))
async def reject_manual_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("⛔ Akses ditolak.", alert=True)
        return
    
    trx_id = event.pattern_match.group(1).decode('utf-8')
    
    async with get_db() as db:
        cur = await db.execute(
            "SELECT user_id, package_id, status FROM transactions WHERE trx_id=?", (trx_id,)
        )
        trx_row = await cur.fetchone()
    
    if not trx_row:
        await event.answer("❌ Transaksi tidak ditemukan.", alert=True)
        return
    
    u_id, package_name, current_status = trx_row
    
    if current_status != 'waiting_approval':
        await event.answer("⚠️ Transaksi ini tidak dalam status menunggu persetujuan.", alert=True)
        return
    
    async with get_db() as db:
        await db.execute("UPDATE transactions SET status='rejected' WHERE trx_id=?", (trx_id,))
        await db.commit()
    
    await event.edit(f"❌ **Transaksi `{trx_id}` Telah Ditolak!**")
    
    await bot.send_message(
        u_id,
        f"❌ **Bukti pembayaran transfer manual Anda ditolak oleh Owner.**\n\n"
        f"Pastikan bukti transfer Anda valid dan jumlah transfer sesuai. Silakan hubungi Owner jika ada kendala."
    )


# ─────────────────────────────────────────
# LPM Scanner (/scan) — Admin Only
# ─────────────────────────────────────────
@bot.on(events.NewMessage(pattern=r'/scan(?:\s+(.+))?'))
async def scan_lpm_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.respond(f"⚠️ Perintah `/scan` hanya untuk Admin.")
        return

    raw_args = event.pattern_match.group(1)
    if not raw_args:
        title = f"{EMOJI_UI['analytics']} GEUNID FREE LPM SCANNER"
        content = (
            "Verifikasi grup/channel Telegram sebagai LPM aktif.\n\n"
            "📋 **Cara Pakai:**\n"
            "• `/scan @username_grup`\n"
            "• `/scan @grup1 @grup2 @grup3`\n\n"
            "⚡ _Setiap LPM valid otomatis masuk database cluster._"
        )
        await event.respond(format_menu_text(title, content))
        return

    links = re.findall(
        r'(?:https?://)?(?:t\.me/|@)?([a-zA-Z0-9_]{5,32}|joinchat/[a-zA-Z0-9_\-]+)', raw_args
    )
    if not links:
        await event.respond("❌ Format salah! Kirim username atau link grup yang valid.")
        return

    # Ambil sesi ubot admin untuk memproses scan
    async with get_db() as db:
        cur = await db.execute("SELECT session_name, status FROM userbots WHERE user_id=?", (ADMIN_ID,))
        ub_row = await cur.fetchone()

    if not ub_row or ub_row[1] != 'connected':
        await event.respond("❌ Ubot Admin terputus! Sambungkan kembali terlebih dahulu via perintah `/install` agar bisa memindai LPM.")
        return

    session_name = f"data/sessions/{ub_row[0]}"
    engine = JasebEngine(session_name, API_ID, API_HASH)
    
    try:
        await engine.start()
        if not await engine.client.is_user_authorized():
            await event.respond("❌ Ubot Admin tidak terotorisasi! Jalankan `/install` ulang.")
            await engine.stop()
            return
    except Exception as e:
        await event.respond(f"❌ Gagal menghubungkan Ubot Admin untuk pemindaian: {e}")
        return

    await event.respond(f"⌛ Memindai **{len(links)} grup** menggunakan Ubot Admin...")

    success_scanned = []
    failed_scanned = []

    for link in links:
        full_link = f"@{link}" if not ("t.me" in link or "joinchat" in link) else link
        try:
            # Gunakan engine.client (Ubot Admin)
            res = await JasebEngine.verify_lpm_group(engine.client, full_link)
            if res.get("success"):
                success_scanned.append(res)
                async with get_db() as db:
                    await db.execute(
                        "INSERT OR IGNORE INTO lpm_lists (group_link, group_id, group_name, member_count, is_active) VALUES (?, ?, ?, ?, ?)",
                        (full_link, res["group_id"], res["group_name"], res["member_count"], 1)
                    )
                    # Jika grup sudah ada tapi tidak aktif, aktifkan kembali
                    await db.execute(
                        "UPDATE lpm_lists SET is_active=1 WHERE group_link=?",
                        (full_link,)
                    )
                    await db.commit()
            else:
                failed_scanned.append({"link": full_link, "error": res.get("error")})
        except Exception as e:
            logger.error(f"Error scanning link {full_link}: {e}")
            failed_scanned.append({"link": full_link, "error": str(e)})

    # Matikan client setelah pemindaian selesai
    try:
        await engine.stop()
    except Exception:
        pass

    content = ""
    if success_scanned:
        content += "🟢 **LPM Valid:**\n"
        for idx, item in enumerate(success_scanned, 1):
            content += f"{idx}. **{item['group_name']}** — {item['member_count']:,} member\n"
        content += "\n"
    if failed_scanned:
        content += "🔴 **Gagal:**\n"
        for idx, item in enumerate(failed_scanned, 1):
            content += f"{idx}. `{item['link']}` ({item['error']})\n"
    if not content:
        content = "❌ Tidak ada grup yang berhasil dipindai."

    content += "\n⚡ _LPM aktif sudah diindeks ke database._"
    await event.respond(format_menu_text(f"{EMOJI_UI['success']} HASIL SCAN LPM", content))


# Import LPM Massal (Admin Only)
# ─────────────────────────────────────────
@bot.on(events.NewMessage(pattern=r'/import_lpm(?:\s+([\s\S]+))?'))
async def import_lpm_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.respond("⚠️ Perintah ini hanya untuk Admin.")
        return

    raw_text = event.pattern_match.group(1)
    if not raw_text:
        await event.respond(
            "📋 **Cara Pakai /import_lpm:**\n\n"
            "Ketik `/import_lpm` diikuti dengan daftar link/username LPM yang panjang.\n"
            "Contoh:\n"
            "`/import_lpm @LPM_A @LPM_B https://t.me/LPM_C`"
        )
        return

    # Saring username/link
    links = re.findall(
        r'(?:https?://)?(?:t\.me/|@)?([a-zA-Z0-9_]{5,32}|joinchat/[a-zA-Z0-9_\-]+)', raw_text
    )
    if not links:
        await event.respond("❌ Tidak ditemukan link atau username LPM yang valid dalam teks tersebut.")
        return

    await event.respond(f"⏳ Mengekstrak dan mengimpor **{len(links)} item** ke database...")

    unique_links = []
    seen = set()
    for link in links:
        if "joinchat" in link:
            full_link = link
        else:
            full_link = f"@{link}"
        if full_link not in seen:
            seen.add(full_link)
            unique_links.append(full_link)

    success_count = 0
    async with get_db() as db:
        for link in unique_links:
            group_name = link.replace("@", "").replace("https://t.me/", "")
            try:
                # Masukkan ke DB, status default active (1)
                cursor = await db.execute(
                    "INSERT OR IGNORE INTO lpm_lists (group_link, group_name, member_count, is_active) VALUES (?, ?, ?, ?)",
                    (link, group_name, 0, 1)
                )
                if cursor.rowcount > 0:
                    success_count += 1
                # Pastikan status diaktifkan kembali jika sebelumnya sempat tidak aktif
                await db.execute(
                    "UPDATE lpm_lists SET is_active=1 WHERE group_link=?",
                    (link,)
                )
            except Exception as e:
                logger.error(f"Gagal mengimpor LPM {link}: {e}")
        await db.commit()

    await event.respond(
        f"✅ **Proses Impor Selesai!**\n\n"
        f"📊 **Hasil Statistik:**\n"
        f"• Total Ditemukan: **{len(unique_links)} grup unik**\n"
        f"• Berhasil Ditambahkan: **{success_count} grup baru**\n"
        f"• Duplikat / Sudah Ada: **{len(unique_links) - success_count} grup**\n\n"
        f"⚡ _Semua LPM baru berhasil terindeks di database cluster._"
    )


# Validate LPM Database (Admin Only)
# ─────────────────────────────────────────
@bot.on(events.NewMessage(pattern=r'/validate_lpm'))
async def validate_lpm_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.respond("⚠️ Perintah ini hanya untuk Admin.")
        return

    # Ambil sesi ubot admin untuk validasi
    async with get_db() as db:
        cur = await db.execute("SELECT session_name, status FROM userbots WHERE user_id=?", (ADMIN_ID,))
        ub_row = await cur.fetchone()

    if not ub_row or ub_row[1] != 'connected':
        await event.respond("❌ Ubot Admin terputus! Sambungkan kembali terlebih dahulu via perintah `/install` agar bisa melakukan validasi.")
        return

    session_name = f"data/sessions/{ub_row[0]}"

    await event.respond("⏳ Memulai validasi database LPM menggunakan Ubot Admin...")

    async with get_db() as db:
        # Ambil semua grup non-blacklist agar grup yang tidak sengaja dinonaktifkan tadi bisa divalidasi ulang
        cur = await db.execute("SELECT group_link FROM lpm_lists WHERE is_blacklisted=0")
        rows = await cur.fetchall()
        
    if not rows:
        await event.respond("❌ Tidak ada LPM di database untuk divalidasi.")
        return

    links = [r[0] for r in rows]
    total = len(links)
    await event.respond(f"📊 Menemukan **{total} grup LPM** di database. Proses validasi berjalan di latar belakang...")

    # Jalankan proses validasi di background task menggunakan JasebEngine dari Ubot Admin
    asyncio.create_task(run_lpm_validation_task(event.sender_id, links, session_name))


async def run_lpm_validation_task(admin_id: int, links: list, session_name: str):
    engine = JasebEngine(session_name, API_ID, API_HASH)
    try:
        await engine.start()
        if not await engine.client.is_user_authorized():
            await bot.send_message(admin_id, "❌ Ubot Admin tidak terotorisasi! Jalankan `/install` ulang.")
            return
    except Exception as e:
        await bot.send_message(admin_id, f"❌ Gagal menghubungkan Ubot Admin untuk validasi: {e}")
        return

    success_count = 0
    failed_count = 0
    total = len(links)
    
    for idx, link in enumerate(links, 1):
        try:
            # Gunakan engine.client (Ubot Admin) agar bisa me-resolve username publik
            res = await JasebEngine.verify_lpm_group(engine.client, link)
            async with get_db() as db:
                if res.get("success"):
                    # Update info asli dan aktifkan kembali
                    await db.execute(
                        "UPDATE lpm_lists SET group_name=?, member_count=?, is_active=1 WHERE group_link=?",
                        (res["group_name"], res["member_count"], link)
                    )
                    success_count += 1
                else:
                    # Nonaktifkan LPM jika rusak / tidak bisa diakses
                    await db.execute(
                        "UPDATE lpm_lists SET is_active=0 WHERE group_link=?",
                        (link,)
                    )
                    failed_count += 1
                await db.commit()
        except Exception as e:
            logger.error(f"Error validating {link} in task: {e}")
            failed_count += 1

        # Kirim update progres setiap 50 grup
        if idx % 50 == 0 or idx == total:
            try:
                await bot.send_message(
                    admin_id,
                    f"⏳ **Progres Validasi LPM:** `{idx}/{total}` grup diperiksa.\n"
                    f"• Valid: **{success_count}**\n"
                    f"• Rusak (Dinonaktifkan): **{failed_count}**"
                )
            except Exception:
                pass
            
        # Jeda tipis anti flood limit Telegram
        await asyncio.sleep(1)

    # Matikan client ubot admin setelah selesai
    try:
        await engine.stop()
    except Exception:
        pass

    try:
        await bot.send_message(
            admin_id,
            f"✅ **Validasi Massal LPM Selesai!**\n\n"
            f"📊 **Laporan Akhir:**\n"
            f"• Total Diperiksa: **{total} grup**\n"
            f"• Tetap Aktif (Valid): **{success_count}**\n"
            f"• Dinonaktifkan (Rusak/Mati): **{failed_count}**\n\n"
            f"⚡ _Database LPM Anda sekarang 100% terverifikasi dan bersih dari link rusak!_"
        )
    except Exception as e:
        logger.error(f"Error sending final validation report: {e}")


# Scrape LPM from Channel (Admin Only)
# ─────────────────────────────────────────
@bot.on(events.NewMessage(pattern=r'/scrape_lpm(?:\s+(.+))?'))
async def scrape_lpm_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.respond("⚠️ Perintah ini hanya untuk Admin.")
        return

    raw_args = event.pattern_match.group(1)
    if not raw_args:
        await event.respond(
            "📋 **Cara Pakai Scraper LPM:**\n"
            "Kirim perintah: `/scrape_lpm @channel_target [limit]`\n\n"
            "Contoh:\n"
            "• `/scrape_lpm @RUMAHLPM` (Bawaan membaca 100 pesan)\n"
            "• `/scrape_lpm @RUMAHLPM 500` (Membaca 500 pesan)\n\n"
            "Bot akan men-scrape pesan terakhir di channel tersebut dan mengekstrak grup LPM baru secara otomatis."
        )
        return

    parts = raw_args.strip().split()
    channel_username = parts[0]
    limit = 100
    if len(parts) > 1:
        try:
            limit = int(parts[1])
            # Batasi maksimal 1000 pesan agar tidak membebani memori server
            limit = min(max(1, limit), 1000)
        except ValueError:
            pass

    await event.respond(f"⏳ Mengakses channel **{channel_username}** untuk membaca **{limit} pesan** menggunakan Ubot Admin...")

    # Ambil sesi ubot admin
    async with get_db() as db:
        cur = await db.execute("SELECT session_name, status FROM userbots WHERE user_id=?", (ADMIN_ID,))
        ub_row = await cur.fetchone()

    if not ub_row or ub_row[1] != 'connected':
        await event.respond("❌ Ubot Admin terputus! Sambungkan kembali terlebih dahulu via perintah `/install`.")
        return

    session_name = f"data/sessions/{ub_row[0]}"
    engine = JasebEngine(session_name, API_ID, API_HASH)
    
    try:
        await engine.start()
        if not await engine.client.is_user_authorized():
            await event.respond("❌ Ubot Admin tidak terotorisasi! Jalankan `/install` ulang.")
            await engine.stop()
            return
    except Exception as e:
        await event.respond(f"❌ Gagal menghubungkan Ubot Admin: {e}")
        return

    await event.respond("🔍 Membaca riwayat pesan dan mencari username LPM...")

    found_usernames = set()
    try:
        async for msg in engine.client.iter_messages(channel_username, limit=limit):
            if msg.text:
                # Cari pola @username
                matches = re.findall(r'@([a-zA-Z0-9_]{5,32})', msg.text)
                for m in matches:
                    username = f"@{m}"
                    # Filter: hanya yang mengandung kata lpm
                    if "lpm" in username.lower():
                        found_usernames.add(username)
    except Exception as e:
        await event.respond(f"❌ Gagal membaca pesan dari {channel_username}: {e}")
        await engine.stop()
        return

    if not found_usernames:
        await event.respond(f"❌ Tidak ditemukan username bertema LPM di {limit} pesan terakhir channel **{channel_username}**.")
        await engine.stop()
        return

    await event.respond(f"📊 Ditemukan **{len(found_usernames)} username LPM unik**. Mulai memvalidasi dan memasukkan ke database...")

    # Jalankan validasi di latar belakang (background task) agar tidak memblock bot
    asyncio.create_task(run_lpm_scrape_validation_task(event.sender_id, list(found_usernames), engine))


async def run_lpm_scrape_validation_task(admin_id: int, usernames: list, engine):
    success_count = 0
    failed_count = 0
    total = len(usernames)
    
    for idx, username in enumerate(usernames, 1):
        try:
            # Validasi LPM
            res = await JasebEngine.verify_lpm_group(bot, username)
            async with get_db() as db:
                if res.get("success"):
                    # Cek apakah sudah ada di DB
                    cur = await db.execute("SELECT id FROM lpm_lists WHERE group_link=?", (username,))
                    exists = await cur.fetchone()
                    if not exists:
                        await db.execute(
                            "INSERT INTO lpm_lists (group_link, group_id, group_name, member_count, is_active) VALUES (?, ?, ?, ?, ?)",
                            (username, res["group_id"], res["group_name"], res["member_count"], 1)
                        )
                        success_count += 1
                    await db.commit()
                else:
                    failed_count += 1
        except Exception as e:
            logger.error(f"Error scraping validation for {username}: {e}")
            failed_count += 1
            
        if idx % 10 == 0 or idx == total:
            try:
                await bot.send_message(
                    admin_id,
                    f"⏳ **Progres Scrape & Validasi:** `{idx}/{total}` grup diperiksa.\n"
                    f"• Baru ditambahkan: **{success_count}**\n"
                    f"• Gagal/Duplikat: **{failed_count}**"
                )
            except Exception:
                pass
        
        await asyncio.sleep(1)

    # Stop engine
    try:
        await engine.stop()
    except Exception:
        pass

    try:
        await bot.send_message(
            admin_id,
            f"✅ **Proses Scrape Selesai!**\n\n"
            f"📊 **Statistik Scrape ({total} ditemukan):**\n"
            f"• Berhasil Ditambahkan: **{success_count}** grup baru\n"
            f"• Gagal / Sudah Ada di DB: **{failed_count}** grup\n\n"
            f"⚡ _Database LPM Anda sekarang semakin kaya!_"
        )
    except Exception as e:
        logger.error(f"Error sending scrape report: {e}")


# ─────────────────────────────────────────
# Broadcast Engine
# ─────────────────────────────────────────
async def start_user_broadcast(user_id: int):
    """Mulai broadcast jaseb otomatis untuk satu user."""
    logger.info(f"Memulai broadcast untuk user_id: {user_id}")
    async with get_db() as db:
        cur = await db.execute("""
            SELECT package_name, capacity_lpm, request_lpm, broadcast_interval_hours
            FROM subscriptions
            WHERE user_id=? AND status='active' AND end_date > datetime('now','localtime')
            ORDER BY end_date DESC LIMIT 1
        """, (user_id,))
        sub = await cur.fetchone()
        if not sub:
            logger.warning(f"Tidak ada sub aktif untuk user {user_id}")
            return

        package_name, capacity, request_lpm, interval_hours = sub

        cur = await db.execute(
            "SELECT id FROM user_ads WHERE user_id=? ORDER BY created_at DESC LIMIT 1", (user_id,)
        )
        ad_row = await cur.fetchone()
        if not ad_row:
            logger.warning(f"Tidak ada materi jaseb untuk user {user_id}")
            await bot.send_message(user_id, "⚠️ Belum ada teks jaseb. Kirim /edit_jaseb untuk mengisinya.")
            return
        ad_id = ad_row[0]

        # Tentukan session
        is_userbot = "userbot" in package_name.lower()
        if is_userbot:
            cur = await db.execute("SELECT session_name, status FROM userbots WHERE user_id=?", (user_id,))
            ub_row = await cur.fetchone()
            if not ub_row or ub_row[1] != 'connected':
                await bot.send_message(user_id, "⚠️ Sesi Userbot Anda terputus! Hubungkan kembali via menu /start.")
                return
            session_name = f"data/sessions/{ub_row[0]}"
        else:
            cur = await db.execute("SELECT session_name, status FROM userbots WHERE user_id=?", (ADMIN_ID,))
            ub_row = await cur.fetchone()
            if not ub_row or ub_row[1] != 'connected':
                await bot.send_message(ADMIN_ID, "⚠️ Sesi Ubot Admin terputus! Sambungkan kembali (/install).")
                return
            session_name = f"data/sessions/{ub_row[0]}"

        # Bangun daftar LPM target
        lpm_links = []
        if request_lpm:
            lpm_links = [l.strip() for l in request_lpm.split() if l.strip()]

        sisa = max(0, capacity - len(lpm_links))
        if sisa > 0:
            cur = await db.execute("""
                SELECT group_link FROM lpm_lists
                WHERE is_active=1 AND is_blacklisted=0
                ORDER BY member_count DESC LIMIT ?
            """, (sisa,))
            defaults = await cur.fetchall()
            lpm_links.extend(row[0] for row in defaults)

        if not lpm_links:
            logger.warning(f"Daftar LPM kosong untuk user {user_id}")
            return

    # Notif user broadcast mulai
    await notify_client_broadcast_start(bot, user_id, len(lpm_links), package_name)

    # Jalankan engine
    engine = JasebEngine(session_name, API_ID, API_HASH)
    await engine.start()
    delay_mode = 'slowly' if 'regular' in package_name.lower() else 'instant'
    asyncio.create_task(
        run_broadcast_task(engine, user_id, ad_id, lpm_links, delay_mode, True, interval_hours or 2)
    )


async def run_broadcast_task(engine, user_id: int, ad_id: int, lpm_links: list,
                              delay_mode: str, auto_join_leave: bool, interval_hours: int):
    """Task background untuk menjalankan broadcast dan mengirim laporan."""
    success_count = 0
    failed_count = 0
    try:
        result = await engine.broadcast_with_stealth(
            user_id=user_id,
            ad_id=ad_id,
            group_links=lpm_links,
            delay_mode=delay_mode,
            auto_join_leave=auto_join_leave
        )
        # Hitung hasil dari DB
        async with get_db() as db:
            cur = await db.execute(
                "SELECT COUNT(*) FROM forward_logs WHERE user_id=? AND status='success' AND sent_at > datetime('now','-1 day','localtime')",
                (user_id,)
            )
            success_count = (await cur.fetchone())[0]
            cur = await db.execute(
                "SELECT COUNT(*) FROM forward_logs WHERE user_id=? AND status='failed' AND sent_at > datetime('now','-1 day','localtime')",
                (user_id,)
            )
            failed_count = (await cur.fetchone())[0]
    except Exception as e:
        logger.error(f"Error broadcast task user {user_id}: {e}")
        failed_count = len(lpm_links)
    finally:
        await engine.stop()

    # Kirim laporan ke client
    await notify_client_broadcast_done(bot, user_id, success_count, failed_count, interval_hours)


# ─────────────────────────────────────────
# Scheduler Autopilot
# ─────────────────────────────────────────
async def run_jaseb_scheduler():
    """Scheduler utama — broadcast otomatis berdasarkan interval per-client."""
    logger.info("Scheduler Autopilot Aktif...")
    # Simpan waktu terakhir broadcast per user
    last_broadcast = {}

    while True:
        try:
            await asyncio.sleep(60)  # Cek tiap 1 menit
            now = datetime.now()

            async with get_db() as db:
                cur = await db.execute("""
                    SELECT DISTINCT user_id, broadcast_interval_hours
                    FROM subscriptions
                    WHERE status='active' AND end_date > datetime('now','localtime')
                """)
                active_users = await cur.fetchall()

            for user_id, interval_hours in active_users:
                interval = interval_hours or 2
                last_time = last_broadcast.get(user_id)

                if last_time is None or (now - last_time).total_seconds() >= interval * 3600:
                    last_broadcast[user_id] = now
                    asyncio.create_task(start_user_broadcast(user_id))

        except Exception as e:
            logger.error(f"Error scheduler loop: {e}")


async def run_expiry_reminder():
    """Kirim reminder ke client yang paketnya hampir habis (3 hari & 1 hari sebelum)."""
    logger.info("Expiry Reminder Service Aktif...")
    while True:
        try:
            await asyncio.sleep(3600)  # Cek setiap 1 jam
            async with get_db() as db:
                cur = await db.execute("""
                    SELECT user_id, package_name, end_date FROM subscriptions
                    WHERE status='active'
                """)
                subs = await cur.fetchall()

            now = datetime.now()
            for user_id, package_name, end_date in subs:
                try:
                    clean_end = end_date.split(".")[0]
                    end_dt = datetime.strptime(clean_end, "%Y-%m-%d %H:%M:%S")
                    delta = end_dt - now
                    days_left = delta.days

                    if days_left in [3, 1]:
                        await notify_client_subscription_expiring(
                            bot, user_id, days_left, package_name, ADMIN_USERNAME
                        )
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Error expiry reminder: {e}")


# ─────────────────────────────────────────
# HTTP Web API Server (Dinamis untuk Vercel)
# ─────────────────────────────────────────
from aiohttp import web

async def handle_prices_api(request):
    try:
        prices_path = os.path.join("frontend", "src", "prices.json")
        if os.path.exists(prices_path):
            with open(prices_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return web.json_response(data, headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            })
        return web.json_response({"error": "Prices file not found"}, status=404)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def handle_checkout_api(request):
    try:
        if request.method == "OPTIONS":
            return web.Response(headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization"
            })

        data = await request.json()
        user_id = data.get("user_id")
        username = data.get("username", "")
        first_name = data.get("first_name", "")
        last_name = data.get("last_name", "")
        package_name = data.get("package_name")
        amount = data.get("amount")
        request_lpm = data.get("request_lpm", "")

        if not user_id or not package_name or not amount:
            return web.json_response({"status": False, "error": "user_id, package_name, and amount are required"}, status=400, headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            })

        from src.payments import create_qris_transaction
        from src.database import get_db
        from src.notifications import notify_admin_new_order
        from telethon import Button

        # Bentuk deskripsi paket
        pkg_desc = package_name
        if request_lpm and request_lpm.strip():
            pkg_desc = f"{package_name} (LPM: {request_lpm.strip()})"

        logger.info(f"Memproses checkout QRIS dari Mini App: User={user_id}, Paket={pkg_desc}, Harga={amount}")

        # Buat QRIS transaksi
        trx_data = await create_qris_transaction(amount, pkg_desc)
        if not trx_data:
            return web.json_response({"status": False, "error": "Gagal membuat transaksi QRIS melalui Payment Gateway"}, status=500, headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            })

        full_name = f"{first_name} {last_name}".strip() or "Client MiniApp"

        # Simpan ke DB SQLite
        async with get_db() as db:
            await db.execute(
                "INSERT INTO users (user_id, username, full_name) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, full_name=excluded.full_name",
                (int(user_id), username, full_name)
            )
            await db.execute(
                "INSERT INTO transactions (user_id, trx_id, package_id, amount, payment_url, status) VALUES (?, ?, ?, ?, ?, ?)",
                (int(user_id), trx_data["transaction_id"], pkg_desc, int(amount), trx_data["payment_url"], "pending")
            )
            await db.commit()

        # Kirim notifikasi ke admin
        try:
            await notify_admin_new_order(
                bot, int(ADMIN_ID), int(user_id), full_name, username, pkg_desc, int(amount), trx_data["transaction_id"]
            )
        except Exception as e:
            logger.error(f"Gagal kirim notifikasi order baru ke admin: {e}")

        # Kirim QRIS ke chat Telegram user
        pay_text = (
            f"✅ **Invoice QRIS Berhasil Dibuat via Mini App!**\n\n"
            f"📦 Paket: **{pkg_desc}**\n"
            f"💰 Total Bayar: **Rp {trx_data['total_amount']:,}**\n"
            f"⏰ Berlaku: {trx_data['expired_at']}\n\n"
            f"Scan QRIS di atas dengan OVO / Gopay / Dana / m-Banking.\n"
            f"Setelah bayar, klik **🔄 Cek Status Bayar** di bawah."
        )

        sent = False
        try:
            await bot.send_file(
                int(user_id),
                file=trx_data["qris_url"],
                caption=pay_text,
                buttons=[
                    [Button.url("🔗 Bayar via Browser", trx_data["payment_url"])],
                    [Button.inline("🔄 Cek Status Bayar", f"check_{trx_data['transaction_id']}".encode())]
                ]
            )
            sent = True
        except Exception as e:
            logger.error(f"Gagal kirim file QRIS ke chat user {user_id}: {e}")
            try:
                await bot.send_message(
                    int(user_id),
                    pay_text,
                    buttons=[
                        [Button.url("🔗 Bayar via Browser", trx_data["payment_url"])],
                        [Button.inline("🔄 Cek Status Bayar", f"check_{trx_data['transaction_id']}".encode())]
                    ]
                )
                sent = True
            except Exception as e2:
                logger.error(f"Gagal kirim teks invoice ke chat user {user_id}: {e2}")

        return web.json_response({
            "status": True,
            "message": "QRIS berhasil dibuat dan dikirim ke bot Telegram Anda.",
            "sent_to_bot": sent,
            "data": trx_data
        }, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        })

    except Exception as e:
        logger.error(f"Error handle_checkout_api: {e}")
        return web.json_response({"status": False, "error": str(e)}, status=500, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        })

async def run_web_server():
    app = web.Application()
    app.router.add_get('/api/prices', handle_prices_api)
    app.router.add_options('/api/prices', lambda r: web.Response(headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    }))
    app.router.add_post('/api/checkout', handle_checkout_api)
    app.router.add_options('/api/checkout', lambda r: web.Response(headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    }))
    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    logger.info(f"Memulai API HTTP Server di port {port}...")
    await site.start()


# ─────────────────────────────────────────
# Main Entry Point
# ─────────────────────────────────────────
async def main():
    logger.info("Inisialisasi Database...")
    await init_db()

    logger.info("Memulai Bot Telegram...")
    await bot.start(bot_token=BOT_TOKEN)  # type: ignore
    me = await bot.get_me()
    import src.config
    src.config.BOT_USERNAME = me.username if me and me.username else "GeunID_bot"
    logger.info(f"Bot Username terdaftar: @{src.config.BOT_USERNAME}")

    # Inject dependencies ke modul handler
    from src.client_handlers import init_client_handlers, register_edit_jaseb_btn
    from src.admin_handlers import init_admin_handlers, register_broadcast_all_confirm

    init_client_handlers(bot, login_states, load_prices)
    register_edit_jaseb_btn(bot, login_states)
    init_admin_handlers(bot, login_states, load_prices, get_package_duration_days, start_user_broadcast)
    register_broadcast_all_confirm(bot, start_user_broadcast)

    # Jalankan semua background service
    logger.info("Memulai Scheduler & Services...")
    asyncio.create_task(run_jaseb_scheduler())
    asyncio.create_task(run_expiry_reminder())
    asyncio.create_task(run_web_server())

    logger.info("Bot GEUNID-JASEB siap! Semua sistem aktif.")
    await bot.run_until_disconnected()


if __name__ == '__main__':
    asyncio.run(main())
