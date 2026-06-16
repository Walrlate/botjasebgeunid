"""
admin_handlers.py — Panel Admin Lengkap GEUNID JASEB
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timedelta

from telethon import events, Button

from src.config import ADMIN_ID, ADMIN_USERNAME
from src.database import (
    db_get_admin_stats,
    db_update_transaction_status,
    db_get_admin_userbot_session,
    db_delete_admin_userbot,
    db_get_active_subscriptions_list,
    db_get_admin_userbots
)
from src.ui_styles import EMOJI_UI, format_menu_text

logger = logging.getLogger(__name__)

# Injected dari main.py
_bot = None
_login_states = None
_load_prices = None
_get_package_duration_days = None
_start_user_broadcast = None
_PRICES_PATH = os.path.join("frontend", "src", "prices.json")


def init_admin_handlers(bot, login_states, load_prices_fn, get_pkg_days_fn, start_broadcast_fn):
    global _bot, _login_states, _load_prices, _get_package_duration_days, _start_user_broadcast
    _bot = bot
    _login_states = login_states
    _load_prices = load_prices_fn
    _get_package_duration_days = get_pkg_days_fn
    _start_user_broadcast = start_broadcast_fn
    _register_admin_handlers(bot)


def _is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


async def _admin_only_check(event) -> bool:
    if not _is_admin(event.sender_id):
        if hasattr(event, "answer"):
            await event.answer("⛔ Akses ditolak. Hanya Admin.", alert=True)
        else:
            await event.respond("⛔ Akses ditolak. Hanya Admin.")
        return False
    return True


def _register_admin_handlers(bot):

    @bot.on(events.NewMessage(pattern='/admin'))
    async def admin_command(event):
        if not await _admin_only_check(event): return
        _login_states.pop(event.sender_id, None)
        await _show_admin_panel(event)

    @bot.on(events.CallbackQuery(data=b"admin_main"))
    async def admin_main_callback(event):
        if not await _admin_only_check(event): return
        await _show_admin_panel(event)

    @bot.on(events.CallbackQuery(data=b"admin_stats"))
    async def admin_stats_handler(event):
        if not await _admin_only_check(event): return
        total_users, total_revenue, total_sent, total_admin_ub = db_get_admin_stats()

        text = (
            f"📊 **STATISTIK ADMIN GEUNID**\n{'━'*22}\n\n"
            f"👥 Total User: {total_users}\n"
            f"💰 Revenue: Rp {total_revenue:,}\n"
            f"📤 Terkirim: {total_sent:,}\n"
            f"🤖 Admin Pool: {total_admin_ub} nomor\n"
        )
        await event.edit(text, buttons=[[Button.inline("⬅️ Kembali", b"admin_main")]])

    # ═══════════════════════════════════════════
    # MANUAL APPROVAL SYSTEM
    # ═══════════════════════════════════════════
    @bot.on(events.CallbackQuery(pattern=b"approve_man_(.+)"))
    async def approve_manual_handler(event):
        if not await _admin_only_check(event): return
        trx_id = event.pattern_match.group(1).decode()
        from src.logic import process_activation
        await process_activation(bot, trx_id, _load_prices(), _login_states)
        await event.edit(f"✅ **TRANSAKSI {trx_id} DISETUJUI!**")

    @bot.on(events.CallbackQuery(pattern=b"reject_man_(.+)"))
    async def reject_manual_handler(event):
        if not await _admin_only_check(event): return
        trx_id = event.pattern_match.group(1).decode()
        db_update_transaction_status(trx_id, "rejected")
        await event.edit(f"❌ **TRANSAKSI {trx_id} DITOLAK!**")

    # ═══════════════════════════════════════════
    # USERBOT MANAGEMENT
    # ═══════════════════════════════════════════
    @bot.on(events.CallbackQuery(data=b"admin_ubots"))
    async def admin_ubots_callback(event):
        if not await _admin_only_check(event): return
        await _show_ubots(event)

    @bot.on(events.CallbackQuery(pattern=b"admin_dc_pool_(\\d+)"))
    async def admin_disconnect_pool_callback(event):
        if not await _admin_only_check(event): return
        aid = int(event.pattern_match.group(1).decode())
        sess = db_get_admin_userbot_session(aid)
        if sess:
            db_delete_admin_userbot(aid)
            path = f"data/sessions/{sess}.session"
            if os.path.exists(path):
                try: os.remove(path)
                except: pass
        await event.answer("✅ Admin Ubot dihapus.", alert=True)
        await _show_ubots(event)

    # ═══════════════════════════════════════════
    # HARGA & BILLING (MINIMALIST)
    # ═══════════════════════════════════════════
    @bot.on(events.CallbackQuery(data=b"admin_prices"))
    async def admin_prices_callback(event):
        if not await _admin_only_check(event): return
        # ... logic ...
        await event.answer("Fitur edit harga via bot sedang dioptimalkan. Gunakan prices.json.", alert=True)

    @bot.on(events.CallbackQuery(data=b"admin_billing"))
    async def admin_billing_callback(event):
        if not await _admin_only_check(event): return
        await _show_billing(event)

# ═══ Helper functions ═══════════════════════════

async def _show_admin_panel(event):
    text = "🛡️ **GEUNID ADMIN PANEL**"
    buttons = [
        [Button.inline("📊 Stats", b"admin_stats"), Button.inline("👥 Billing", b"admin_billing")],
        [Button.inline("🤖 Admin Pool", b"admin_ubots")],
        [Button.inline("⬅️ Menu Utama", b"start")]
    ]
    await event.edit(text, buttons=buttons)

async def _show_billing(event):
    subs = db_get_active_subscriptions_list(10)
    if not subs:
        await event.edit("❌ Tidak ada billing aktif.", buttons=[[Button.inline("⬅️ Kembali", b"admin_main")]])
        return
    
    text = "👥 **LANGGANAN AKTIF**\n\n"
    for uid, pkg, end in subs:
        text += f"• `{uid}` | {pkg} | {end[:10]}\n"
    await event.edit(text, buttons=[[Button.inline("⬅️ Kembali", b"admin_main")]])

async def _show_ubots(event):
    admins = db_get_admin_userbots()
    text = "🤖 **MANAJEMEN ADMIN POOL**\n\n"
    buttons = []
    if not admins:
        text += "_Belum ada nomor admin._"
    else:
        for aid, phone, status, cooldown in admins:
            icon = "🟢" if status == 'connected' else "🔴"
            text += f"{icon} {phone} | {status}\n"
            if status == 'connected':
                buttons.append([Button.inline(f"🔌 DC {phone}", f"admin_dc_pool_{aid}".encode())])
    
    buttons.append([Button.inline("⬅️ Kembali", b"admin_main")])
    await event.edit(text, buttons=buttons)

def register_broadcast_all_confirm(bot, start_broadcast_fn):
    pass # Reserved
