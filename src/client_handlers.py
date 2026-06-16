"""
client_handlers.py — Semua handler yang diakses oleh CLIENT (bukan admin)
"""

import asyncio
import logging
import os
import re
from datetime import datetime

from telethon import events, Button

from src.config import ADMIN_ID, ADMIN_USERNAME
from src.database import (
    db_get_active_subscription_id,
    db_get_active_subscription_status,
    db_get_success_forward_logs_count,
    db_get_userbot_status
)
from src.payments import create_qris_transaction
from src.ui_styles import EMOJI_UI, format_menu_text

logger = logging.getLogger(__name__)

_bot = None
_login_states = None
_load_prices = None

def init_client_handlers(bot, login_states, load_prices_fn):
    global _bot, _login_states, _load_prices
    _bot = bot
    _login_states = login_states
    _load_prices = load_prices_fn
    _register_handlers(bot)

def _register_handlers(bot):
    @bot.on(events.NewMessage(pattern='/help'))
    async def help_command_handler(event): await _show_help_main(event)

    @bot.on(events.CallbackQuery(data=b"help_main"))
    async def help_main_callback(event): await _show_help_main(event)

    @bot.on(events.NewMessage(pattern='/mystatus'))
    async def mystatus_command_handler(event): await _show_mystatus(event, event.sender_id)

    @bot.on(events.CallbackQuery(data=b"my_status"))
    async def mystatus_callback(event): await _show_mystatus(event, event.sender_id)

    @bot.on(events.NewMessage(pattern='/edit_jaseb'))
    async def edit_jaseb_command_handler(event):
        uid = int(event.sender_id)
        sub = db_get_active_subscription_id(uid)
        if not sub: await event.respond("❌ Anda tidak memiliki paket aktif."); return
        _login_states[uid] = {"state": "waiting_for_ad"}
        await event.respond("✍️ **Kirim teks/materi jaseb baru Anda:**\n(Teks, Foto+Caption, atau Forward)")

    @bot.on(events.CallbackQuery(data=b"resend_jaseb"))
    async def resend_jaseb_handler(event):
        uid = int(event.sender_id)
        sub = db_get_active_subscription_id(uid)
        if not sub:
            await event.answer("❌ Anda tidak memiliki paket aktif yang dapat disebar ulang.", alert=True)
            return
        from src.main import start_user_broadcast
        await event.answer("🚀 Memulai broadcast ulang...", alert=False)
        asyncio.create_task(start_user_broadcast(uid))

async def _show_help_main(event):
    from src.main import get_web_app_url
    from telethon.tl.types import KeyboardButtonWebView
    url = await get_web_app_url(event.sender_id)
    text = (
        "📖 **PANDUAN & BANTUAN GEUNID JASEB**\n\n"
        "Cara mudah menggunakan bot ini:\n\n"
        "1️⃣ **Aktivasi Paket**\n"
        "• Klik tombol **Launch GEUNID JASEB** di menu utama.\n"
        "• Pilih paket yang kamu mau dan selesaikan pembayaran (bisa QRIS otomatis atau Transfer Manual).\n\n"
        "2️⃣ **Sambungkan Akun (Userbot)**\n"
        "• Kirim nomor HP akun Telegram kamu (+628xxx).\n"
        "• Masukkan kode OTP yang dikirim Telegram (dan password 2FA kamu jika ada).\n\n"
        "3️⃣ **Kirim Materi Promosi**\n"
        "• Kirim materi iklan kamu (bisa teks biasa, foto + teks, atau forward pesan).\n"
        "• Kirim daftar link grup LPM kustom kamu, atau ketik `/skip` untuk memakai ratusan grup LPM bawaan bot.\n\n"
        "4️⃣ **Kelola & Cek Status**\n"
        "• Masuk ke menu **Status Saya** untuk melihat log pengiriman, edit materi iklan, atau melakukan sebar ulang.\n\n"
        "Hubungi Admin di @Geun_ID jika butuh bantuan tambahan."
    )
    
    # Cek apakah pengakses adalah Admin
    if event.sender_id == ADMIN_ID:
        text += (
            "\n\n⚡ **PANDUAN PERINTAH ADMIN (Hanya Anda)**\n"
            f"{'━'*22}\n"
            "• `/admin` - Membuka Panel Admin interaktif (Kelola harga, billing, LPM pool, dll).\n"
            "• `/setprice` - Kelola & edit harga paket secara langsung.\n"
            "• `/lpm` - Kelola pool grup LPM (Lihat list, tambah, hapus, blacklist).\n"
            "• `/billing` - Kelola langganan aktif user (Perpanjang, cabut, ubah interval, lpm cap).\n"
            "• `/ubots` - Kelola akun Telegram di Admin Pool.\n"
            "• `/clientubots` - Kelola status userbot pembeli (Disconnect paksa, hapus sesi).\n"
            "• `/scrape_lpm <@target> [limit]` - Scrape username/link LPM massal dari channel referensi.\n"
            "• `/import_lpm <list>` - Impor massal username/link LPM dari teks secara langsung.\n"
            "• `/join_pool` - Sinkronisasi gradual join bertahap untuk semua Admin Pool agar aman dari ban."
        )

    buttons = [
        [KeyboardButtonWebView(text="🚀 Launch GEUNID JASEB", url=url)],
        [Button.inline("📊 Status Saya", b"my_status"), Button.inline("⬅️ Kembali", b"start")]
    ]
    if hasattr(event, "edit"):
        try:
            await event.edit(text, buttons=buttons)
        except Exception:
            # Jika gagal edit (misal pesan lama adalah foto, atau teks admin terlalu panjang), 
            # hapus pesan lama agar chat bersih dan kirim pesan teks baru.
            try:
                await event.delete()
            except: pass
            try:
                await _bot.send_message(event.chat_id, text, buttons=buttons)
            except Exception as e2:
                logger.error(f"Gagal mengirim help: {e2}")
                await event.respond(text, buttons=buttons)
    else:
        await event.respond(text, buttons=buttons)

async def _show_mystatus(event, user_id: int):
    user_id = int(user_id)
    sub = db_get_active_subscription_status(user_id)
    total_sent = db_get_success_forward_logs_count(user_id)
    ub_status = db_get_userbot_status(user_id)

    if not sub:
        text = "📊 **Status Jaseb**\n\n❌ Tidak ada paket aktif."
        buttons = [[Button.inline("⬅️ Kembali", b"start")]]
    else:
        pkg, cap, end, iv = sub
        try:
            end_dt = datetime.strptime(end.split(".")[0].strip(), "%Y-%m-%d %H:%M:%S")
            days = max(0, (end_dt - datetime.now()).days)
        except Exception:
            try:
                clean_end = end.replace("T", " ").split(".")[0].split("+")[0].strip()
                end_dt = datetime.strptime(clean_end, "%Y-%m-%d %H:%M:%S")
                days = max(0, (end_dt - datetime.now()).days)
            except Exception:
                days = 0
                
        iv_label = f"{int(iv*60)}m" if iv < 1 else f"{iv}j"
        text = f"📊 **STATUS JASEB**\n\n📦 Paket: {pkg}\n🎯 LPM: {cap}\n📅 Habis: {end[:10]} ({days} hari lagi)\n⏰ Jadwal: Setiap {iv_label}\n📤 Terkirim: {total_sent} grup\n🤖 Userbot: {ub_status.capitalize()}"
        buttons = [[Button.inline("🔄 Sebar Ulang", b"resend_jaseb"), Button.inline("✍️ Edit Iklan", b"edit_jaseb_btn")], [Button.inline("⬅️ Kembali", b"start")]]

    if hasattr(event, "edit"):
        try:
            await event.edit(text, buttons=buttons)
            return
        except Exception:
            pass
    await event.respond(text, buttons=buttons)

def register_edit_jaseb_btn(bot, login_states):
    @bot.on(events.CallbackQuery(data=b"edit_jaseb_btn"))
    async def handler(event):
        uid = int(event.sender_id)
        login_states[uid] = {"state": "waiting_for_ad"}
        await event.edit("✍️ **Kirim teks jaseb baru Anda sekarang:**")
