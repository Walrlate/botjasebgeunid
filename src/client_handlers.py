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
from src.database import get_db
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
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        async with get_db() as db:
            cur = await db.execute("SELECT id FROM subscriptions WHERE user_id=? AND status='active' AND TRIM(end_date) > ? ORDER BY end_date DESC LIMIT 1", (uid, now_str))
            sub = await cur.fetchone()
        if not sub: await event.respond("❌ Anda tidak memiliki paket aktif."); return
        _login_states[uid] = {"state": "waiting_for_ad"}
        await event.respond("✍️ **Kirim teks/materi jaseb baru Anda:**\n(Teks, Foto+Caption, atau Forward)")

    @bot.on(events.CallbackQuery(data=b"resend_jaseb"))
    async def resend_jaseb_handler(event):
        from src.main import start_user_broadcast
        await event.answer("🚀 Memulai broadcast ulang...", alert=False)
        asyncio.create_task(start_user_broadcast(event.sender_id))

async def _show_help_main(event):
    from src.main import get_web_app_url
    from telethon.tl.types import KeyboardButtonWebView
    url = await get_web_app_url(event.sender_id)
    text = format_menu_text("📖 BANTUAN GEUNID", "Pilih menu bantuan di bawah:")
    buttons = [[KeyboardButtonWebView(text="🛒 Buka Mini App", url=url)], [Button.inline("📊 Status Saya", b"my_status")], [Button.inline("⬅️ Kembali", b"start")]]
    if hasattr(event, "edit"): await event.edit(text, buttons=buttons)
    else: await event.respond(text, buttons=buttons)

async def _show_mystatus(event, user_id: int):
    user_id = int(user_id)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with get_db() as db:
        cur = await db.execute("SELECT package_name, capacity_lpm, end_date, broadcast_interval_hours FROM subscriptions WHERE user_id=? AND status='active' AND TRIM(end_date) > ? ORDER BY end_date DESC LIMIT 1", (user_id, now_str))
        sub = await cur.fetchone()
        cur = await db.execute("SELECT COUNT(*) FROM forward_logs WHERE user_id=? AND status='success'", (user_id,))
        total_sent = (await cur.fetchone())[0]
        cur = await db.execute("SELECT status FROM userbots WHERE user_id=?", (user_id,))
        ub_row = await cur.fetchone()
        ub_status = ub_row[0] if ub_row else "disconnected"

    if not sub:
        text = "📊 **Status Jaseb**\n\n❌ Tidak ada paket aktif."
        buttons = [[Button.inline("⬅️ Kembali", b"start")]]
    else:
        pkg, cap, end, iv = sub
        end_dt = datetime.strptime(end.split(".")[0].strip(), "%Y-%m-%d %H:%M:%S")
        days = max(0, (end_dt - datetime.now()).days)
        iv_label = f"{int(iv*60)}m" if iv < 1 else f"{iv}j"
        text = f"📊 **STATUS JASEB**\n\n📦 Paket: {pkg}\n🎯 LPM: {cap}\n📅 Habis: {end[:10]} ({days} hari lagi)\n⏰ Jadwal: Setiap {iv_label}\n📤 Terkirim: {total_sent} grup\n🤖 Userbot: {ub_status.capitalize()}"
        buttons = [[Button.inline("🔄 Sebar Ulang", b"resend_jaseb"), Button.inline("✍️ Edit Iklan", b"edit_jaseb_btn")], [Button.inline("⬅️ Kembali", b"start")]]

    if hasattr(event, "edit"): await event.edit(text, buttons=buttons)
    else: await event.respond(text, buttons=buttons)

def register_edit_jaseb_btn(bot, login_states):
    @bot.on(events.CallbackQuery(data=b"edit_jaseb_btn"))
    async def handler(event):
        uid = int(event.sender_id)
        login_states[uid] = {"state": "waiting_for_ad"}
        await event.edit("✍️ **Kirim teks jaseb baru Anda sekarang:**")
