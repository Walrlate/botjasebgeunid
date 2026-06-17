"""
admin_handlers.py — Panel Admin GEUNID JASEB - Full Management Suite
====================================================================
Fitur:
  - /setprice  : Edit harga, durasi, LPM, bonus per paket (Regular/Forward/Userbot)
  - /lpm       : Kelola pool grup LPM (tambah, hapus, lihat, bulk import)
  - /billing   : Kelola langganan user (perpanjang, cabut, ubah interval, ubah LPM)
  - /ubots     : Kelola userbot pembeli dan admin pool
  - /admin     : Panel utama
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
    db_get_admin_userbots,
    # LPM Management
    db_get_lpm_lists_paginated,
    db_add_lpm_entry,
    db_bulk_add_lpm_entries,
    db_delete_lpm_entry,
    db_toggle_lpm_status,
    db_blacklist_lpm,
    db_clear_all_lpm,
    db_get_lpm_lists_count,
    db_get_lpm_entry,
    db_update_lpm_details,
    # Billing Management
    db_get_all_subscriptions_detail,
    db_get_subscription_by_user,
    db_extend_subscription,
    db_set_subscription_interval,
    db_revoke_subscription,
    db_set_subscription_lpm_capacity,
    # Userbot Management
    db_get_all_client_userbots,
    db_admin_disconnect_client_userbot,
    db_admin_delete_client_userbot,
)
from src.ui_styles import EMOJI_UI, format_menu_text

logger = logging.getLogger(__name__)

_bot = None
_login_states = None
_load_prices = None
_get_package_duration_days = None
_start_user_broadcast = None
_PRICES_PATH = os.path.join("data", "prices.json")


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


# ══════════════════════════════════════════════════
# HARGA HELPER
# ══════════════════════════════════════════════════

def _load_prices_json() -> dict:
    try:
        default_path = os.path.join("frontend", "src", "prices.json")
        if not os.path.exists(_PRICES_PATH):
            if os.path.exists(default_path):
                import shutil
                os.makedirs(os.path.dirname(_PRICES_PATH), exist_ok=True)
                shutil.copy(default_path, _PRICES_PATH)
                logger.info("ℹ️ prices.json default disalin ke penyimpanan persisten data/prices.json")
        if os.path.exists(_PRICES_PATH):
            with open(_PRICES_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Gagal baca prices.json: {e}")
    return {}


def _save_prices_json(data: dict) -> bool:
    try:
        os.makedirs(os.path.dirname(_PRICES_PATH), exist_ok=True)
        with open(_PRICES_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Gagal simpan prices.json: {e}")
        return False


def _format_price_list_text(prices: dict) -> str:
    lines = ["💰 **PRICELIST SAAT INI**\n"]
    icons = {"regular": "📢", "forward": "📤", "userbot": "🤖"}
    for ptype, icon in icons.items():
        items = prices.get(ptype, [])
        if not items:
            continue
        lines.append(f"\n{icon} **{ptype.upper()}**")
        for item in items:
            lpm_str = f" {item['lpm']} LPM" if item.get("lpm", 0) > 0 else ""
            bonus_str = f" (+{item['bonus']})" if item.get("bonus") else ""
            promo = f"Rp {item['promoPrice']:,}"
            coret = f"~~Rp {item['originalPrice']:,}~~" if item.get("originalPrice") else ""
            lines.append(f"  • `{item['id']}` — {item['duration']}{lpm_str}{bonus_str} | {coret} **{promo}**")
    return "\n".join(lines)


async def validate_and_add_lpm(bot, raw_link: str) -> tuple:
    """
    Normalisasi, validasi, dan tambahkan grup LPM ke database.
    Mengambil nama grup dan jumlah member jika memungkinkan.
    Returns: (success, group_name, member_count)
    """
    from src.database import db_add_lpm_entry
    import re
    from telethon.errors import FloodWaitError
    from telethon.tl.functions.channels import GetFullChannelRequest
    
    # Normalisasi
    link = raw_link.strip()
    if not link:
        return False, "", 0
        
    username_or_link = link
    if username_or_link.startswith("@"):
        username_or_link = username_or_link[1:]
        
    # Standardize DB link format
    db_link = link
    if not db_link.startswith("https://t.me/") and not db_link.startswith("http"):
        db_link = f"https://t.me/{db_link.lstrip('@')}"

    group_name = link
    member_count = 0
    validated = False

    try:
        # Ganti ke username jika public link t.me/username
        entity_target = username_or_link
        if "t.me/" in username_or_link and "joinchat" not in username_or_link:
            entity_target = username_or_link.split("t.me/")[-1].split("/")[0]

        # Coba get entity jika bukan private join link
        if "joinchat" not in username_or_link:
            entity = await bot.get_entity(entity_target)
            if hasattr(entity, 'title'):
                group_name = entity.title
            
            # Coba ambil full channel untuk dapat participant count
            try:
                full_info = await bot(GetFullChannelRequest(entity))
                if full_info and hasattr(full_info, 'full_chat') and hasattr(full_info.full_chat, 'participants_count'):
                    member_count = full_info.full_chat.participants_count or 0
            except:
                # Fallback ke participants_count jika ada di entity
                if hasattr(entity, 'participants_count'):
                    member_count = entity.participants_count or 0
            validated = True
    except FloodWaitError as e:
        logger.warning(f"FloodWait saat validasi {link}: harus menunggu {e.seconds} detik. Menyimpan default.")
    except Exception as e:
        logger.debug(f"Gagal memvalidasi {link}: {e}")

    # Simpan ke database
    db_add_lpm_entry(db_link, group_name=group_name, member_count=member_count)
    return validated, group_name, member_count


# ══════════════════════════════════════════════════
# REGISTER SEMUA HANDLER
# ══════════════════════════════════════════════════

def _register_admin_handlers(bot):

    # ─── PANEL UTAMA ───
    @bot.on(events.NewMessage(pattern='/admin'))
    async def admin_command(event):
        if not await _admin_only_check(event): return
        _login_states.pop(event.sender_id, None)
        await _show_admin_panel(event)

    @bot.on(events.CallbackQuery(data=b"admin_main"))
    async def admin_main_callback(event):
        if not await _admin_only_check(event): return
        _login_states.pop(event.sender_id, None)
        await _show_admin_panel(event)

    # ─── STATS ───
    @bot.on(events.CallbackQuery(data=b"admin_stats"))
    async def admin_stats_handler(event):
        if not await _admin_only_check(event): return
        total_users, total_revenue, total_sent, total_admin_ub = db_get_admin_stats()
        total_lpm = db_get_lpm_lists_count()
        text = (
            f"📊 **STATISTIK GEUNID**\n{'━'*24}\n\n"
            f"👥 Total User Terdaftar: **{total_users}**\n"
            f"💰 Total Revenue: **Rp {total_revenue:,}**\n"
            f"📤 Total Iklan Terkirim: **{total_sent:,}**\n"
            f"🤖 Admin Pool Aktif: **{total_admin_ub} nomor**\n"
            f"📋 LPM Pool: **{total_lpm} grup**\n"
        )
        await event.edit(text, buttons=[[Button.inline("⬅️ Kembali", b"admin_main")]])

    # ─── APPROVAL ───
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

    # ════════════════════════════════════════════
    # ADMIN USERBOT POOL
    # ════════════════════════════════════════════
    @bot.on(events.NewMessage(pattern='/ubots'))
    async def ubots_command(event):
        if not await _admin_only_check(event): return
        await _show_ubots(event)

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

    # ════════════════════════════════════════════
    # MANAJEMEN USERBOT PEMBELI
    # ════════════════════════════════════════════
    @bot.on(events.NewMessage(pattern='/clientubots'))
    async def client_ubots_command(event):
        if not await _admin_only_check(event): return
        await _show_client_ubots(event)

    @bot.on(events.CallbackQuery(data=b"admin_client_ubots"))
    async def admin_client_ubots_callback(event):
        if not await _admin_only_check(event): return
        await _show_client_ubots(event)

    @bot.on(events.CallbackQuery(pattern=b"cub_dc_(\\d+)"))
    async def client_ubot_dc_callback(event):
        if not await _admin_only_check(event): return
        uid = int(event.pattern_match.group(1).decode())
        if db_admin_disconnect_client_userbot(uid):
            await event.answer(f"✅ Userbot {uid} di-disconnect.", alert=True)
        else:
            await event.answer("❌ Gagal disconnect.", alert=True)
        await _show_client_ubots(event)

    @bot.on(events.CallbackQuery(pattern=b"cub_del_(\\d+)"))
    async def client_ubot_del_callback(event):
        if not await _admin_only_check(event): return
        uid = int(event.pattern_match.group(1).decode())
        ok, session = db_admin_delete_client_userbot(uid)
        if ok:
            if session:
                for ext in [".session", ".session-journal"]:
                    path = f"data/sessions/{session}{ext}"
                    if os.path.exists(path):
                        try: os.remove(path)
                        except: pass
            await event.answer(f"✅ Userbot {uid} dihapus.", alert=True)
        else:
            await event.answer("❌ Gagal hapus.", alert=True)
        await _show_client_ubots(event)

    # ════════════════════════════════════════════
    # MANAJEMEN BILLING (SUBSCRIPTIONS)
    # ════════════════════════════════════════════
    @bot.on(events.NewMessage(pattern='/billing'))
    async def billing_command(event):
        if not await _admin_only_check(event): return
        _login_states.pop(event.sender_id, None)
        await _show_billing_list(event)

    @bot.on(events.CallbackQuery(data=b"admin_billing"))
    async def admin_billing_callback(event):
        if not await _admin_only_check(event): return
        _login_states.pop(event.sender_id, None)
        await _show_billing_list(event)

    @bot.on(events.CallbackQuery(pattern=b"bill_detail_(\\d+)"))
    async def billing_detail_callback(event):
        if not await _admin_only_check(event): return
        uid = int(event.pattern_match.group(1).decode())
        await _show_billing_detail(event, uid)

    @bot.on(events.CallbackQuery(pattern=b"bill_revoke_(\\d+)"))
    async def billing_revoke_callback(event):
        if not await _admin_only_check(event): return
        uid = int(event.pattern_match.group(1).decode())
        if db_revoke_subscription(uid):
            await event.answer(f"✅ Langganan {uid} dicabut.", alert=True)
        else:
            await event.answer("❌ Gagal mencabut langganan.", alert=True)
        await _show_billing_list(event)

    @bot.on(events.CallbackQuery(pattern=b"bill_extend_(\\d+)"))
    async def billing_extend_start_callback(event):
        if not await _admin_only_check(event): return
        uid = int(event.pattern_match.group(1).decode())
        _login_states[event.sender_id] = {"state": "admin_extend_sub", "target_uid": uid}
        await event.edit(
            f"📅 **PERPANJANG LANGGANAN**\n\n"
            f"👤 User ID: `{uid}`\n\n"
            f"Ketik jumlah hari perpanjangan:\n_Contoh: `7` (untuk perpanjang 7 hari)_",
            buttons=[[Button.inline("❌ Batal", b"admin_billing")]]
        )

    @bot.on(events.CallbackQuery(pattern=b"bill_interval_(\\d+)"))
    async def billing_interval_start_callback(event):
        if not await _admin_only_check(event): return
        uid = int(event.pattern_match.group(1).decode())
        _login_states[event.sender_id] = {"state": "admin_set_interval", "target_uid": uid}
        await event.edit(
            f"⏰ **UBAH INTERVAL BROADCAST**\n\n"
            f"👤 User ID: `{uid}`\n\n"
            f"Ketik interval dalam jam:\n"
            f"_Contoh: `0.5` (30 menit) | `1` (1 jam) | `2` (2 jam)_",
            buttons=[[Button.inline("❌ Batal", b"admin_billing")]]
        )

    @bot.on(events.CallbackQuery(pattern=b"bill_lpmcap_(\\d+)"))
    async def billing_lpmcap_start_callback(event):
        if not await _admin_only_check(event): return
        uid = int(event.pattern_match.group(1).decode())
        _login_states[event.sender_id] = {"state": "admin_set_lpmcap", "target_uid": uid}
        await event.edit(
            f"🎯 **UBAH KAPASITAS LPM**\n\n"
            f"👤 User ID: `{uid}`\n\n"
            f"Ketik jumlah LPM baru:\n_Contoh: `20` | `30` | `50`_",
            buttons=[[Button.inline("❌ Batal", b"admin_billing")]]
        )

    # ════════════════════════════════════════════
    # MANAJEMEN LPM POOL
    # ════════════════════════════════════════════
    @bot.on(events.NewMessage(pattern='/lpm'))
    async def lpm_command(event):
        if not await _admin_only_check(event): return
        _login_states.pop(event.sender_id, None)
        await _show_lpm_menu(event)

    @bot.on(events.CallbackQuery(data=b"lpm_main"))
    async def lpm_main_callback(event):
        if not await _admin_only_check(event): return
        _login_states.pop(event.sender_id, None)
        await _show_lpm_menu(event)

    @bot.on(events.CallbackQuery(data=b"lpm_view"))
    async def lpm_view_callback(event):
        if not await _admin_only_check(event): return
        await _show_lpm_list(event, offset=0)

    @bot.on(events.CallbackQuery(pattern=b"lpm_page_(\\d+)"))
    async def lpm_page_callback(event):
        if not await _admin_only_check(event): return
        offset = int(event.pattern_match.group(1).decode())
        await _show_lpm_list(event, offset=offset)

    @bot.on(events.CallbackQuery(pattern=b"lpm_del_(\\d+)"))
    async def lpm_del_callback(event):
        if not await _admin_only_check(event): return
        lpm_id = int(event.pattern_match.group(1).decode())
        if db_delete_lpm_entry(lpm_id):
            await event.answer("✅ LPM dihapus.", alert=True)
        else:
            await event.answer("❌ Gagal hapus.", alert=True)
        await _show_lpm_list(event, offset=0)

    @bot.on(events.CallbackQuery(pattern=b"lpm_bl_(\\d+)"))
    async def lpm_blacklist_callback(event):
        if not await _admin_only_check(event): return
        lpm_id = int(event.pattern_match.group(1).decode())
        if db_blacklist_lpm(lpm_id):
            await event.answer("🚫 LPM di-blacklist.", alert=True)
        else:
            await event.answer("❌ Gagal.", alert=True)
        await _show_lpm_list(event, offset=0)

    @bot.on(events.CallbackQuery(pattern=b"lpm_edit_(\\d+)"))
    async def lpm_edit_callback(event):
        if not await _admin_only_check(event): return
        lpm_id = int(event.pattern_match.group(1).decode())
        item = db_get_lpm_entry(lpm_id)
        if not item:
            await event.answer("❌ LPM tidak ditemukan.", alert=True); return

        text = (
            f"✏️ **EDIT LPM GROUP**\n{'━'*20}\n\n"
            f"🔗 Link: `{item['group_link']}`\n"
            f"📛 Judul: **{item['group_name']}**\n"
            f"👥 Member: **{item['member_count']:,}**\n\n"
            f"Pilih field yang ingin diubah:"
        )
        buttons = [
            [Button.inline("📛 Ubah Judul LPM", f"lpm_edtitle_{lpm_id}".encode()),
             Button.inline("👥 Ubah Jumlah Member", f"lpm_edmem_{lpm_id}".encode())],
            [Button.inline("⬅️ Kembali ke List", b"lpm_view")]
        ]
        await event.edit(text, buttons=buttons)

    @bot.on(events.CallbackQuery(pattern=b"lpm_edtitle_(\\d+)"))
    async def lpm_edit_title_callback(event):
        if not await _admin_only_check(event): return
        lpm_id = int(event.pattern_match.group(1).decode())
        _login_states[event.sender_id] = {"state": "admin_edit_lpm_title", "target_id": lpm_id}
        await event.edit(
            f"✏️ **UBAH JUDUL LPM**\n\n"
            f"Ketik judul/nama baru untuk grup LPM ini:",
            buttons=[[Button.inline("❌ Batal", f"lpm_edit_{lpm_id}".encode())]]
        )

    @bot.on(events.CallbackQuery(pattern=b"lpm_edmem_(\\d+)"))
    async def lpm_edit_member_callback(event):
        if not await _admin_only_check(event): return
        lpm_id = int(event.pattern_match.group(1).decode())
        _login_states[event.sender_id] = {"state": "admin_edit_lpm_member", "target_id": lpm_id}
        await event.edit(
            f"✏️ **UBAH JUMLAH MEMBER LPM**\n\n"
            f"Ketik jumlah member baru (hanya angka):",
            buttons=[[Button.inline("❌ Batal", f"lpm_edit_{lpm_id}".encode())]]
        )

    @bot.on(events.CallbackQuery(data=b"lpm_add"))
    async def lpm_add_callback(event):
        if not await _admin_only_check(event): return
        _login_states[event.sender_id] = {"state": "admin_add_lpm"}
        await event.edit(
            "➕ **TAMBAH LPM BARU**\n\n"
            "Kirim satu atau banyak link/username grup (satu per baris):\n\n"
            "_Contoh:_\n"
            "`@grupjual1`\n"
            "`@grupjual2`\n"
            "`https://t.me/grupjual3`\n\n"
            "✅ Bisa kirim hingga ratusan sekaligus!",
            buttons=[[Button.inline("❌ Batal", b"lpm_main")]]
        )

    @bot.on(events.CallbackQuery(data=b"lpm_clear_confirm"))
    async def lpm_clear_confirm_callback(event):
        if not await _admin_only_check(event): return
        await event.edit(
            "⚠️ **KONFIRMASI HAPUS SEMUA LPM**\n\n"
            "Apakah kamu yakin ingin **menghapus SEMUA** grup LPM dari pool?\n"
            "Tindakan ini **tidak bisa dibatalkan**!",
            buttons=[
                [Button.inline("🗑 Ya, Hapus Semua!", b"lpm_clear_do")],
                [Button.inline("❌ Batal", b"lpm_main")]
            ]
        )

    @bot.on(events.CallbackQuery(data=b"lpm_clear_do"))
    async def lpm_clear_do_callback(event):
        if not await _admin_only_check(event): return
        if db_clear_all_lpm():
            await event.answer("✅ Semua LPM berhasil dihapus.", alert=True)
        else:
            await event.answer("❌ Gagal hapus semua.", alert=True)
        await _show_lpm_menu(event)

    # ════════════════════════════════════════════
    # /setprice — MANAJEMEN HARGA
    # ════════════════════════════════════════════
    @bot.on(events.NewMessage(pattern='/setprice'))
    async def setprice_command(event):
        if not await _admin_only_check(event): return
        _login_states.pop(event.sender_id, None)
        await _show_setprice_menu(event)

    @bot.on(events.CallbackQuery(data=b"sp_main"))
    async def setprice_main_callback(event):
        if not await _admin_only_check(event): return
        _login_states.pop(event.sender_id, None)
        await _show_setprice_menu(event)

    @bot.on(events.CallbackQuery(data=b"sp_view"))
    async def setprice_view_callback(event):
        if not await _admin_only_check(event): return
        prices = _load_prices_json()
        text = _format_price_list_text(prices)
        await event.edit(text, buttons=[[Button.inline("⬅️ Kembali", b"sp_main")]], parse_mode="md")

    @bot.on(events.CallbackQuery(data=b"sp_edit_qris_tax"))
    async def sp_edit_qris_tax_callback(event):
        if not await _admin_only_check(event): return
        prices = _load_prices_json()
        qris_tax = prices.get("qris_tax_percent", 0.7)
        _login_states[event.sender_id] = {
            "state": "setprice_edit_qris_tax"
        }
        await event.edit(
            "⚡ **EDIT PAJAK KLIKQRIS**\n\n"
            f"Pajak Saat Ini: **{qris_tax}%**\n\n"
            "Ketik persentase pajak baru (angka desimal/float menggunakan titik, contoh: `0.7` atau `1.5`):",
            buttons=[[Button.inline("❌ Batal", b"sp_main")]]
        )

    @bot.on(events.CallbackQuery(pattern=b"sp_type_(.+)"))
    async def setprice_type_callback(event):
        if not await _admin_only_check(event): return
        ptype = event.pattern_match.group(1).decode()
        if ptype not in ("regular", "forward", "userbot"):
            await event.answer("Tipe tidak valid.", alert=True); return
        await _show_setprice_package_list(event, ptype)

    @bot.on(events.CallbackQuery(pattern=b"sp_pkg_(.+)"))
    async def setprice_pkg_callback(event):
        if not await _admin_only_check(event): return
        pkg_id = event.pattern_match.group(1).decode()
        prices = _load_prices_json()
        found_item, found_type = None, None
        for ptype, items in prices.items():
            for item in items:
                if item.get("id") == pkg_id:
                    found_item, found_type = item, ptype
                    break
            if found_item: break
        if not found_item:
            await event.answer("❌ Paket tidak ditemukan.", alert=True); return

        _login_states[event.sender_id] = {
            "state": "setprice_waiting_field",
            "pkg_id": pkg_id,
            "pkg_type": found_type,
            "pkg_item": found_item,
        }

        lpm_str = f" {found_item['lpm']} LPM" if found_item.get("lpm", 0) > 0 else ""
        bonus_str = f" | Bonus: {found_item['bonus']}" if found_item.get("bonus") else ""
        text = (
            f"✏️ **EDIT PAKET**\n\n"
            f"📦 ID: `{pkg_id}`\n"
            f"⏰ Durasi: **{found_item['duration']}**{lpm_str}{bonus_str}\n"
            f"💰 Harga Promo: **Rp {found_item.get('promoPrice', 0):,}**\n"
            f"🏷 Harga Coret: Rp {found_item.get('originalPrice', 0):,}\n\n"
            f"Pilih **field yang ingin diubah:**"
        )
        buttons = [
            [Button.inline("💰 Ubah Harga Promo", f"sp_edit_promo_{pkg_id}".encode()),
             Button.inline("🏷 Ubah Harga Coret", f"sp_edit_orig_{pkg_id}".encode())],
            [Button.inline("⏰ Ubah Durasi", f"sp_edit_dur_{pkg_id}".encode()),
             Button.inline("🎯 Ubah LPM", f"sp_edit_lpm_{pkg_id}".encode())],
            [Button.inline("🎁 Ubah Bonus", f"sp_edit_bonus_{pkg_id}".encode())],
            [Button.inline("⬅️ Kembali", f"sp_type_{found_type}".encode())]
        ]
        await event.edit(text, buttons=buttons)

    # Edit field spesifik
    for _field in ["promo", "orig", "dur", "lpm", "bonus"]:
        @bot.on(events.CallbackQuery(pattern=f"sp_edit_{_field}_(.+)".encode()))
        async def _sp_edit_field_cb(event, field=_field):
            if not await _admin_only_check(event): return
            pkg_id = event.pattern_match.group(1).decode()
            prices = _load_prices_json()
            found_item, found_type = None, None
            for ptype, items in prices.items():
                for item in items:
                    if item.get("id") == pkg_id:
                        found_item, found_type = item, ptype
                        break
                if found_item: break
            if not found_item:
                await event.answer("❌ Paket tidak ditemukan.", alert=True); return

            field_labels = {
                "promo": ("💰 Harga Promo", f"Rp {found_item.get('promoPrice',0):,}", "angka nominal, contoh: `9900`"),
                "orig":  ("🏷 Harga Coret", f"Rp {found_item.get('originalPrice',0):,}", "angka nominal, contoh: `25000`"),
                "dur":   ("⏰ Durasi", found_item.get("duration",""), "teks durasi, contoh: `7 Hari`"),
                "lpm":   ("🎯 Kapasitas LPM", str(found_item.get("lpm",0)), "angka LPM, contoh: `20` (isi `0` untuk userbot)"),
                "bonus": ("🎁 Bonus", found_item.get("bonus","(kosong)"), "teks bonus, contoh: `+2 Hari` (ketik `-` untuk hapus bonus)"),
            }
            label, current, hint = field_labels[field]
            _login_states[event.sender_id] = {
                "state": f"setprice_edit_{field}",
                "pkg_id": pkg_id,
                "pkg_type": found_type,
                "pkg_item": found_item,
            }
            await event.edit(
                f"✏️ **EDIT {label.upper()}**\n\n"
                f"📦 Paket: `{pkg_id}`\n"
                f"🔢 Nilai Saat Ini: **{current}**\n\n"
                f"Ketik nilai baru ({hint}):",
                buttons=[[Button.inline("❌ Batal", f"sp_pkg_{pkg_id}".encode())]]
            )

    @bot.on(events.CallbackQuery(pattern=b"sp_add_(.+)"))
    async def setprice_add_callback(event):
        if not await _admin_only_check(event): return
        ptype = event.pattern_match.group(1).decode()
        if ptype not in ("regular", "forward", "userbot"):
            await event.answer("Tipe tidak valid.", alert=True); return
        _login_states[event.sender_id] = {"state": "setprice_add_waiting_input", "pkg_type": ptype}
        await event.edit(
            f"➕ **TAMBAH PAKET {ptype.upper()} BARU**\n\n"
            f"Format: `durasi | lpm | harga_coret | harga_promo`\n\n"
            f"**Contoh:**\n"
            f"`14 Hari | 20 | 30000 | 12000`\n\n"
            f"_• Untuk Userbot, isi lpm = 0_\n"
            f"_• Semua angka tanpa titik/koma_\n"
            f"_• Tambahkan bonus dengan: `14 Hari | 20 | 30000 | 12000 | +2 Hari`_",
            buttons=[[Button.inline("❌ Batal", f"sp_type_{ptype}".encode())]]
        )

    @bot.on(events.CallbackQuery(pattern=b"sp_del_(.+)"))
    async def setprice_del_callback(event):
        if not await _admin_only_check(event): return
        pkg_id = event.pattern_match.group(1).decode()
        prices = _load_prices_json()
        deleted, found_type = False, None
        for ptype, items in prices.items():
            new_items = [i for i in items if i.get("id") != pkg_id]
            if len(new_items) < len(items):
                prices[ptype] = new_items
                deleted, found_type = True, ptype
                break
        if deleted and _save_prices_json(prices):
            await event.answer(f"✅ Paket dihapus!", alert=True)
            await _show_setprice_package_list(event, found_type)
        else:
            await event.answer("❌ Gagal hapus.", alert=True)

    # ─── SCRAPE LPM ───
    @bot.on(events.NewMessage(pattern=r'/scrape_lpm(?:\s+(.+))?'))
    async def scrape_lpm_command(event):
        if not await _admin_only_check(event): return
        
        args_str = event.pattern_match.group(1)
        if not args_str:
            await event.respond("❌ Format salah. Gunakan: `/scrape_lpm <@username_atau_link> [limit]`\nContoh: `/scrape_lpm @RUMAHLPM 1000`")
            return
            
        parts = args_str.strip().split()
        target = parts[0]
        limit = 100
        if len(parts) > 1 and parts[1].isdigit():
            limit = int(parts[1])
            
        status_msg = await event.respond(f"🔍 **Mulai men-scrape dari {target} (limit: {limit} pesan)...**")
        
        # Ambil salah satu admin userbot yang aktif
        from src.database import db_get_active_admin_userbots
        admins = db_get_active_admin_userbots()
        
        if not admins:
            await status_msg.edit(
                "❌ **Gagal:** Fitur scraping membutuhkan minimal 1 akun Admin Pool (Userbot) yang terhubung.\n\n"
                "Silakan hubungkan akun admin terlebih dahulu dengan menggunakan perintah `/install` di bot."
            )
            return
            
        # Gunakan admin userbot pertama yang aktif
        sess, phone, aid = admins[0]
        from telethon import TelegramClient
        from telethon.network import ConnectionTcpObfuscated
        from src.config import API_ID, API_HASH
        
        client = TelegramClient(
            f"data/sessions/{sess}",
            API_ID,
            API_HASH,
            receive_updates=False,
            connection=ConnectionTcpObfuscated,
            timeout=30,
            connection_retries=10,
            retry_delay=5
        )
        
        try:
            await client.connect()
            if not await client.is_user_authorized():
                await status_msg.edit(f"❌ **Gagal:** Akun admin pool `{phone}` tidak terotorisasi. Silakan hubungkan ulang dengan `/install`.")
                await client.disconnect()
                return
                
            try:
                entity = await client.get_entity(target)
            except Exception as e:
                await status_msg.edit(f"❌ Gagal menemukan chat {target}: {e}")
                await client.disconnect()
                return
                
            found_links = set()
            
            try:
                async for message in client.iter_messages(entity, limit=limit):
                    msg_text = message.text or ""
                    if not msg_text:
                        continue
                    # Extract usernames
                    usernames = re.findall(r'@[a-zA-Z0-9_]{5,32}', msg_text)
                    for u in usernames:
                        found_links.add(u)
                    # Extract links
                    links = re.findall(r'(?:https?://)?t\.me/(?:joinchat/[a-zA-Z0-9_\-]+|[a-zA-Z0-9_]{5,32})', msg_text)
                    for l in links:
                        found_links.add(l)
            except Exception as e:
                await status_msg.edit(f"❌ Terjadi kesalahan saat membaca pesan via Userbot: {e}")
                await client.disconnect()
                return
                
            if not found_links:
                await status_msg.edit(f"❌ Tidak ditemukan username/link grup LPM di {target}.")
                await client.disconnect()
                return
                
            total_found = len(found_links)
            await status_msg.edit(f"📥 **Menemukan {total_found} tautan. Memvalidasi & menyimpan...**\n_(Proses berjalan asinkron via Userbot, mohon tunggu)_")
            
            success_count = 0
            validated_count = 0
            
            for link in found_links:
                try:
                    # Lewati target itu sendiri agar tidak rekursif
                    if target.lower().replace("@","") in link.lower():
                        continue
                    validated, gname, mcount = await validate_and_add_lpm(client, link)
                    if validated:
                        validated_count += 1
                    success_count += 1
                    await asyncio.sleep(0.3)
                except Exception as e:
                    logger.error(f"Error scraping link {link}: {e}")
                    
            await status_msg.edit(
                f"✅ **SCRAPE SELESAI VIA USERBOT!**\n{'━'*26}\n\n"
                f"👤 Target: {target}\n"
                f"📥 Total link ditemukan: **{total_found}**\n"
                f"✅ Berhasil ditambahkan: **{success_count}**\n"
                f"🔍 Terverifikasi detail: **{validated_count}**"
            )
            
        except Exception as e:
            await status_msg.edit(f"❌ Terjadi kesalahan koneksi sesi admin userbot: {e}")
        finally:
            if client.is_connected():
                await client.disconnect()

    # ─── IMPORT LPM ───
    @bot.on(events.NewMessage(pattern=r'/import_lpm(?:\s+(.+))?'))
    async def import_lpm_command(event):
        if not await _admin_only_check(event): return
        
        args_str = event.pattern_match.group(1) or ""
        
        # Cek apakah membalas pesan (reply)
        reply_text = ""
        if event.message.is_reply:
            reply_msg = await event.get_reply_message()
            if reply_msg and reply_msg.text:
                reply_text = reply_msg.text
                
        # Bersihkan command dari teks args_str jika didapat dari event.text
        if not args_str and event.text:
            args_str = re.sub(r'^/import_lpm', '', event.text, flags=re.IGNORECASE).strip()
        
        # Cek apakah ada file terlampir
        file_content = ""
        if event.message.media and event.message.file and event.message.file.name and event.message.file.name.endswith(".txt"):
            try:
                buffer = await event.message.download_media(file=bytes)
                if buffer:
                    file_content = buffer.decode('utf-8', errors='ignore')
            except Exception as fe:
                logger.error(f"Gagal mendownload file import_lpm: {fe}")
                await event.respond(f"❌ Gagal membaca file lampiran: {fe}")
                return
                
        # Gabungkan teks input manual, isi file, dan teks dari pesan yang direply
        combined_text = args_str + "\n" + file_content + "\n" + reply_text
        
        # Cari semua username atau link
        usernames = re.findall(r'@[a-zA-Z0-9_]{5,32}', combined_text)
        links = re.findall(r'(?:https?://)?t\.me/(?:joinchat/[a-zA-Z0-9_\-]+|[a-zA-Z0-9_]{5,32})', combined_text)
        
        all_targets = set(usernames + links)
        if not all_targets:
            await event.respond("❌ Tidak ditemukan tautan LPM yang valid. Gunakan format:\n`/import_lpm @LPM1 @LPM2 ...` atau lampirkan file .txt berisi daftar LPM.")
            return
            
        total_targets = len(all_targets)
        status_msg = await event.respond(f"📥 **Mulai mengimpor {total_targets} grup LPM...**\n_(Mohon tunggu, sedang memvalidasi)_")
        
        success_count = 0
        validated_count = 0
        
        for link in all_targets:
            try:
                validated, gname, mcount = await validate_and_add_lpm(bot, link)
                if validated:
                    validated_count += 1
                success_count += 1
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.error(f"Error importing link {link}: {e}")
                
        await status_msg.edit(
            f"✅ **IMPORT SELESAI!**\n{'━'*18}\n\n"
            f"📥 Total link diimpor: **{total_targets}**\n"
            f"✅ Berhasil dimasukkan: **{success_count}**\n"
            f"🔍 Terverifikasi detail: **{validated_count}**"
        )

    # ─── GRADUAL JOIN POOL ───
    @bot.on(events.NewMessage(pattern='/join_pool'))
    async def join_pool_command(event):
        if not await _admin_only_check(event): return
        
        asyncio.create_task(run_admin_pool_gradual_join(bot, event.chat_id))
        await event.respond(
            "⏳ **Memulai proses gradual join untuk semua Admin Pool...**\n"
            "Setiap akun admin akan mencoba bergabung ke maksimal 5 grup LPM baru yang belum diikuti dengan jeda aman 20-35 detik per join.\n\n"
            "Laporan progress akan dikirimkan di sini."
        )


async def run_admin_pool_gradual_join(bot, status_chat_id):
    from src.database import db_get_active_admin_userbots, db_get_active_lpm_links_with_ids, db_get_lpm_lists_count
    from src.jaseb_engine import JasebEngine
    from telethon import TelegramClient
    from telethon.network import ConnectionTcpObfuscated
    from telethon.tl.functions.channels import JoinChannelRequest
    import random
    
    # 1. Api-ID & Api-Hash
    from src.config import API_ID, API_HASH
    
    # 2. Ambil semua link LPM dari database
    total_lpm = db_get_lpm_lists_count()
    if total_lpm == 0:
        await bot.send_message(status_chat_id, "❌ **Gagal:** Pool LPM di database kosong.")
        return
        
    lpm_data = db_get_active_lpm_links_with_ids(limit=total_lpm)
    if not lpm_data:
        await bot.send_message(status_chat_id, "❌ **Gagal:** Tidak ada LPM aktif di database.")
        return

    # 3. Ambil semua admin userbots yang terhubung
    admins = db_get_active_admin_userbots()
    if not admins:
        await bot.send_message(status_chat_id, "❌ **Gagal:** Tidak ada akun Admin Pool yang terhubung.")
        return

    await bot.send_message(status_chat_id, f"📢 **Gradual Join dimulai:**\n👤 Total Admin: **{len(admins)}**\n📋 Total LPM Pool: **{len(lpm_data)}**")
    
    for sess, phone, aid in admins:
        await bot.send_message(status_chat_id, f"⏳ **Memproses akun admin: {phone}...**")
        client = TelegramClient(
            f"data/sessions/{sess}",
            API_ID,
            API_HASH,
            receive_updates=False,
            connection=ConnectionTcpObfuscated,
            timeout=30,
            connection_retries=10,
            retry_delay=5
        )
        try:
            await client.connect()
            if not await client.is_user_authorized():
                await bot.send_message(status_chat_id, f"⚠️ Akun {phone} tidak terotorisasi (butuh login ulang). Melewati.")
                continue
                
            # Ambil daftar chat/grup yang sudah diikuti oleh admin ini
            joined_ids = set()
            try:
                async for dialog in client.iter_dialogs(limit=None):
                    if dialog.is_group or dialog.is_channel:
                        joined_ids.add(dialog.entity.id)
            except Exception as ex:
                logger.error(f"Error iter_dialogs untuk {phone}: {ex}")
                
            # Cari LPM mana saja yang belum diikuti
            to_join = []
            for link, db_group_id in lpm_data:
                # 1. Cek ID di joined_ids (instan & tanpa network request)
                if db_group_id and int(db_group_id) in joined_ids:
                    continue
                    
                # 2. Fallback jika group_id di DB kosong (None/0)
                if not db_group_id:
                    try:
                        target_entity = link.strip().replace("https://t.me/", "").replace("t.me/", "").replace("@", "")
                        entity = await client.get_entity(target_entity)
                        if entity.id in joined_ids:
                            continue
                        to_join.append(entity)
                    except:
                        continue
                else:
                    # Simpan string link untuk di-resolve nanti saat akan di-join
                    to_join.append(link)
                    
            if not to_join:
                await bot.send_message(status_chat_id, f"✅ Akun {phone} sudah bergabung ke semua grup LPM yang valid. (Sisa target: 0)")
                continue
                
            # Batasi hanya 5 join baru per siklus per akun untuk menghindari ban
            limit_join = min(5, len(to_join))
            await bot.send_message(status_chat_id, f"🔄 Akun {phone} akan bergabung ke **{limit_join}** grup baru...\n🎯 Sisa target LPM belum diikuti akun ini: **{len(to_join)}** grup")
            
            joined_count = 0
            for item in to_join[:limit_join]:
                try:
                    # Resolve ke entity jika string
                    if isinstance(item, str):
                        target_entity = item.strip().replace("https://t.me/", "").replace("t.me/", "").replace("@", "")
                        entity = await client.get_entity(target_entity)
                    else:
                        entity = item
                        
                    await client(JoinChannelRequest(entity))
                    joined_count += 1
                    # Jeda waktu aman yang panjang
                    await asyncio.sleep(random.uniform(20, 35))
                except Exception as ex:
                    # Mengambil info identitas error untuk log
                    target_name = item if isinstance(item, str) else (entity.title if hasattr(entity, 'title') else "grup")
                    logger.error(f"Admin {phone} gagal join {target_name}: {ex}")
                    if "flood" in str(ex).lower():
                        await bot.send_message(status_chat_id, f"⚠️ Akun {phone} terkena FloodWait. Menghentikan join untuk akun ini.")
                        break
                        
            await bot.send_message(status_chat_id, f"✅ Akun {phone} berhasil bergabung ke **{joined_count}** grup baru. (Sisa target akun ini: **{len(to_join) - joined_count}**)")
            
        except Exception as e:
            logger.error(f"Error processing admin join for {phone}: {e}")
            await bot.send_message(status_chat_id, f"❌ Terjadi kesalahan pada akun {phone}: {e}")
        finally:
            try: await client.disconnect()
            except: pass
            
    await bot.send_message(status_chat_id, "🎯 **Proses Gradual Join selesai untuk seluruh Admin Pool!**\nJalankan kembali perintah `/join_pool` secara berkala (misal 1-2 jam sekali) hingga semua akun admin bergabung ke semua LPM.")


# ══════════════════════════════════════════════════
# INPUT HANDLER UTAMA (State Machine)
# ══════════════════════════════════════════════════

async def handle_admin_input(event, state_data: dict):
    """
    Dipanggil dari main.py untuk semua state admin_* dan setprice_*.
    """
    user_id = event.sender_id
    text = (event.text or "").strip()
    state = state_data.get("state", "")

    # ──────────────── BILLING STATES ────────────────
    if state == "admin_extend_sub":
        if not text.isdigit():
            await event.respond("❌ Masukkan angka hari saja. Contoh: `7`")
            return
        uid = state_data["target_uid"]
        days = int(text)
        if db_extend_subscription(uid, days):
            del _login_states[user_id]
            await event.respond(
                f"✅ **Langganan `{uid}` diperpanjang {days} hari!**",
                buttons=[[Button.inline("📋 Lihat Billing", b"admin_billing")]]
            )
        else:
            await event.respond("❌ Gagal perpanjang. User mungkin tidak punya langganan aktif.")

    elif state == "admin_set_interval":
        try:
            iv = float(text)
            if iv <= 0: raise ValueError
        except ValueError:
            await event.respond("❌ Masukkan angka desimal positif. Contoh: `0.5` atau `1` atau `2`")
            return
        uid = state_data["target_uid"]
        if db_set_subscription_interval(uid, iv):
            del _login_states[user_id]
            iv_label = f"{int(iv*60)} menit" if iv < 1 else f"{iv} jam"
            await event.respond(
                f"✅ **Interval broadcast `{uid}` diubah ke {iv_label}!**",
                buttons=[[Button.inline("📋 Lihat Billing", b"admin_billing")]]
            )
        else:
            await event.respond("❌ Gagal ubah interval.")

    elif state == "admin_set_lpmcap":
        if not text.isdigit():
            await event.respond("❌ Masukkan angka LPM saja. Contoh: `20` | `30` | `50`")
            return
        uid = state_data["target_uid"]
        cap = int(text)
        if db_set_subscription_lpm_capacity(uid, cap):
            del _login_states[user_id]
            await event.respond(
                f"✅ **Kapasitas LPM `{uid}` diubah ke {cap} LPM!**",
                buttons=[[Button.inline("📋 Lihat Billing", b"admin_billing")]]
            )
        else:
            await event.respond("❌ Gagal ubah kapasitas LPM.")

    # ──────────────── LPM STATES ────────────────
    elif state == "admin_add_lpm":
        import re
        usernames = re.findall(r'@[a-zA-Z0-9_]{5,32}', text)
        links = re.findall(r'(?:https?://)?t\.me/(?:joinchat/[a-zA-Z0-9_\-]+|[a-zA-Z0-9_]{5,32})', text)
        all_targets = list(set(usernames + links))
        
        if not all_targets:
            await event.respond("❌ Tidak ada link LPM atau username yang valid. Coba lagi.")
            return
            
        count = db_bulk_add_lpm_entries(all_targets)
        del _login_states[user_id]
        total_now = db_get_lpm_lists_count()
        await event.respond(
            f"✅ **{count} dari {len(all_targets)} LPM berhasil ditambahkan!**\n"
            f"📋 Total LPM pool sekarang: **{total_now} grup**",
            buttons=[[Button.inline("📋 Lihat LPM Pool", b"lpm_view"), Button.inline("⬅️ Menu LPM", b"lpm_main")]]
        )

    elif state == "admin_edit_lpm_title":
        if not text:
            await event.respond("❌ Judul tidak boleh kosong.")
            return
        lid = state_data["target_id"]
        if db_update_lpm_details(lid, group_name=text):
            del _login_states[user_id]
            await event.respond(
                f"✅ **Judul LPM berhasil diubah ke:**\n`{text}`",
                buttons=[[Button.inline("📋 Detail LPM", f"lpm_edit_{lid}".encode())]]
            )
        else:
            await event.respond("❌ Gagal mengubah judul LPM.")

    elif state == "admin_edit_lpm_member":
        if not text.isdigit():
            await event.respond("❌ Masukkan angka saja.")
            return
        lid = state_data["target_id"]
        members = int(text)
        if db_update_lpm_details(lid, member_count=members):
            del _login_states[user_id]
            await event.respond(
                f"✅ **Jumlah member LPM berhasil diubah ke:**\n`{members:,}`",
                buttons=[[Button.inline("📋 Detail LPM", f"lpm_edit_{lid}".encode())]]
            )
        else:
            await event.respond("❌ Gagal mengubah jumlah member LPM.")

    # ──────────────── SETPRICE STATES ────────────────
    elif state == "setprice_edit_qris_tax":
        try:
            clean_text = text.replace(",", ".")
            val = float(clean_text)
            if val < 0: raise ValueError
        except ValueError:
            await event.respond("❌ Masukkan angka desimal/float non-negatif. Contoh: `0.7` atau `1.5` atau `0`:")
            return
        prices = _load_prices_json()
        prices["qris_tax_percent"] = val
        if _save_prices_json(prices):
            del _login_states[user_id]
            await event.respond(
                f"✅ **Pajak KlikQRIS berhasil diubah!**\n\n"
                f"🔄 Nilai baru: **{val}%**\n\n"
                "✨ Mini App auto-update!",
                buttons=[[Button.inline("💰 Menu Harga", b"sp_main")]]
            )
        else:
            await event.respond("❌ Gagal menyimpan data.")

    elif state.startswith("setprice_edit_"):
        field = state.replace("setprice_edit_", "")
        await _handle_setprice_field_edit(event, state_data, field, text)

    elif state == "setprice_add_waiting_input":
        await _handle_setprice_add(event, state_data, text)


async def _handle_setprice_field_edit(event, state_data, field, text):
    """Edit satu field spesifik pada sebuah paket harga."""
    user_id = event.sender_id
    pkg_id = state_data["pkg_id"]
    pkg_type = state_data["pkg_type"]
    pkg_item = state_data["pkg_item"]

    prices = _load_prices_json()

    # Validasi & konversi nilai
    field_map = {
        "promo": ("promoPrice", "int"),
        "orig":  ("originalPrice", "int"),
        "dur":   ("duration", "str"),
        "lpm":   ("lpm", "int"),
        "bonus": ("bonus", "str_or_empty"),
    }

    if field not in field_map:
        await event.respond("❌ Field tidak dikenal."); del _login_states[user_id]; return

    db_key, val_type = field_map[field]

    if val_type == "int":
        if not text.isdigit():
            await event.respond("❌ Harus angka saja. Coba lagi."); return
        new_val = int(text)
    elif val_type == "str":
        if not text:
            await event.respond("❌ Nilai tidak boleh kosong."); return
        new_val = text
    elif val_type == "str_or_empty":
        new_val = "" if text.strip() == "-" else text.strip()

    # Update di prices dict
    updated = False
    for item in prices.get(pkg_type, []):
        if item.get("id") == pkg_id:
            if new_val == "" and db_key == "bonus":
                item.pop("bonus", None)
            else:
                item[db_key] = new_val
            updated = True
            break

    del _login_states[user_id]

    if updated and _save_prices_json(prices):
        field_labels = {
            "promo": "Harga Promo", "orig": "Harga Coret",
            "dur": "Durasi", "lpm": "Kapasitas LPM", "bonus": "Bonus"
        }
        display = f"Rp {new_val:,}" if val_type == "int" else (new_val or "(dihapus)")
        await event.respond(
            f"✅ **{field_labels[field]} berhasil diubah!**\n\n"
            f"📦 Paket: `{pkg_id}`\n"
            f"🔄 Nilai baru: **{display}**\n\n"
            f"✨ Mini App auto-update!",
            buttons=[
                [Button.inline("✏️ Edit Lagi", f"sp_pkg_{pkg_id}".encode())],
                [Button.inline("📋 Lihat Paket", f"sp_type_{pkg_type}".encode()), Button.inline("💰 Menu Harga", b"sp_main")]
            ]
        )
    else:
        await event.respond("❌ Gagal menyimpan. Coba lagi.")


async def _handle_setprice_add(event, state_data, text):
    """Tambahkan paket baru dari format input."""
    user_id = event.sender_id
    ptype = state_data["pkg_type"]

    parts = [p.strip() for p in text.split("|")]
    if len(parts) < 4 or len(parts) > 5:
        await event.respond(
            "❌ Format salah! Harus 4 atau 5 kolom dipisah `|`:\n"
            "`durasi | lpm | harga_coret | harga_promo`\n"
            "atau dengan bonus:\n"
            "`durasi | lpm | harga_coret | harga_promo | bonus`\n\n"
            "_Contoh: `14 Hari | 20 | 30000 | 12000 | +2 Hari`_"
        )
        return

    duration_str = parts[0]
    lpm_str = parts[1]
    orig_str = parts[2]
    promo_str = parts[3]
    bonus_str = parts[4] if len(parts) == 5 else ""

    if not lpm_str.isdigit() or not orig_str.isdigit() or not promo_str.isdigit():
        await event.respond("❌ LPM, harga coret, dan harga promo harus angka."); return

    lpm = int(lpm_str)
    orig = int(orig_str)
    promo = int(promo_str)

    slug = re.sub(r'[^a-z0-9]', '', duration_str.lower())
    prefix_map = {"regular": "reg", "forward": "fwd", "userbot": "ub"}
    prefix = prefix_map.get(ptype, ptype[:3])
    new_id = f"{prefix}_{lpm}lpm_{slug}" if lpm > 0 else f"{prefix}_{slug}"

    new_item = {"id": new_id, "duration": duration_str, "lpm": lpm, "originalPrice": orig, "promoPrice": promo}
    if bonus_str:
        new_item["bonus"] = bonus_str

    prices = _load_prices_json()
    if ptype not in prices:
        prices[ptype] = []
    prices[ptype].append(new_item)

    del _login_states[user_id]

    if _save_prices_json(prices):
        lpm_info = f" {lpm} LPM" if lpm > 0 else ""
        bonus_info = f"\n🎁 Bonus: **{bonus_str}**" if bonus_str else ""
        await event.respond(
            f"✅ **PAKET BARU DITAMBAHKAN!**\n\n"
            f"📦 ID: `{new_id}`\n"
            f"📋 Tipe: {ptype.upper()}\n"
            f"⏰ Durasi: {duration_str}{lpm_info}{bonus_info}\n"
            f"💰 Harga Promo: **Rp {promo:,}**\n"
            f"🏷 Harga Coret: ~~Rp {orig:,}~~\n\n"
            f"✨ Mini App auto-update!",
            buttons=[[Button.inline("💰 Kelola Harga", b"sp_main"), Button.inline("📋 Lihat Paket", f"sp_type_{ptype}".encode())]]
        )
    else:
        await event.respond("❌ Gagal menyimpan.")


# ══════════════════════════════════════════════════
# FUNGSI ALIAS untuk backward compat
# ══════════════════════════════════════════════════

async def handle_setprice_input(event, state_data: dict):
    """Alias untuk backward compat - diarahkan ke handle_admin_input."""
    await handle_admin_input(event, state_data)


# ══════════════════════════════════════════════════
# UI HELPER FUNCTIONS
# ══════════════════════════════════════════════════

async def _show_admin_panel(event):
    text = (
        "🛡️ **GEUNID ADMIN PANEL**\n\n"
        "Pilih menu yang ingin dikelola:"
    )
    buttons = [
        [Button.inline("📊 Statistik", b"admin_stats"), Button.inline("👥 Billing", b"admin_billing")],
        [Button.inline("📋 Kelola LPM", b"lpm_main"), Button.inline("💰 Kelola Harga", b"sp_main")],
        [Button.inline("🤖 Admin Pool", b"admin_ubots"), Button.inline("👤 Userbot Client", b"admin_client_ubots")],
        [Button.inline("⬅️ Menu Utama", b"start")]
    ]
    if hasattr(event, "edit"):
        try:
            await event.edit(text, buttons=buttons); return
        except Exception:
            pass
    await event.respond(text, buttons=buttons)


async def _show_billing_list(event):
    subs = db_get_all_subscriptions_detail(15)
    if not subs:
        buttons = [[Button.inline("⬅️ Kembali", b"admin_main")]]
        if hasattr(event, "edit"):
            await event.edit("❌ Tidak ada langganan aktif.", buttons=buttons)
        else:
            await event.respond("❌ Tidak ada langganan aktif.", buttons=buttons)
        return

    text = "👥 **LANGGANAN AKTIF**\n\n"
    buttons = []
    for sub in subs:
        uid = sub["user_id"]
        pkg = sub["package_name"]
        end = sub.get("end_date", "")
        end_clean = normalize_end(end)
        cap = sub.get("capacity_lpm", 0)
        iv = sub.get("broadcast_interval_hours", 0.5)
        iv_label = f"{int(iv*60)}m" if iv < 1 else f"{iv}j"
        text += f"• `{uid}` | {pkg[:25]} | {end_clean[:10]} | {cap}LPM/{iv_label}\n"
        buttons.append([Button.inline(f"🔧 Kelola {uid}", f"bill_detail_{uid}".encode())])

    buttons.append([Button.inline("⬅️ Kembali", b"admin_main")])
    if hasattr(event, "edit"):
        try:
            await event.edit(text, buttons=buttons); return
        except Exception:
            pass
    await event.respond(text, buttons=buttons)


async def _show_billing_detail(event, uid: int):
    sub = db_get_subscription_by_user(uid)
    if not sub:
        await event.answer("❌ User tidak punya langganan aktif.", alert=True)
        await _show_billing_list(event)
        return

    pkg = sub.get("package_name", "-")
    end = normalize_end(sub.get("end_date", ""))
    cap = sub.get("capacity_lpm", 0)
    iv = sub.get("broadcast_interval_hours", 0.5)
    iv_label = f"{int(iv*60)} menit" if iv < 1 else f"{iv} jam"
    req_lpm = sub.get("request_lpm") or "(default pool)"

    text = (
        f"🔧 **KELOLA USER `{uid}`**\n{'━'*22}\n\n"
        f"📦 Paket: **{pkg}**\n"
        f"🎯 Kapasitas: **{cap} LPM**\n"
        f"📅 Expired: **{end[:10]}**\n"
        f"⏰ Interval: **{iv_label}**\n"
        f"📋 LPM Custom: `{req_lpm[:50]}`\n"
    )
    buttons = [
        [Button.inline("📅 Perpanjang", f"bill_extend_{uid}".encode()),
         Button.inline("⏰ Ubah Interval", f"bill_interval_{uid}".encode())],
        [Button.inline("🎯 Ubah LPM Cap", f"bill_lpmcap_{uid}".encode()),
         Button.inline("🚫 Cabut Langganan", f"bill_revoke_{uid}".encode())],
        [Button.inline("⬅️ Kembali", b"admin_billing")]
    ]
    if hasattr(event, "edit"):
        try:
            await event.edit(text, buttons=buttons); return
        except Exception:
            pass
    await event.respond(text, buttons=buttons)


async def _show_lpm_menu(event):
    total = db_get_lpm_lists_count()
    text = (
        f"📋 **MANAJEMEN LPM POOL**\n\n"
        f"Total Aktif: **{total} grup LPM**\n\n"
        f"Kelola pool grup LPM yang digunakan untuk broadcast:"
    )
    buttons = [
        [Button.inline(f"👁 Lihat Pool ({total})", b"lpm_view"), Button.inline("➕ Tambah LPM", b"lpm_add")],
        [Button.inline("🗑 Hapus Semua (⚠️)", b"lpm_clear_confirm")],
        [Button.inline("⬅️ Kembali", b"admin_main")]
    ]
    if hasattr(event, "edit"):
        try:
            await event.edit(text, buttons=buttons); return
        except Exception:
            pass
    await event.respond(text, buttons=buttons)


async def _show_lpm_list(event, offset: int = 0):
    PAGE = 5
    items = db_get_lpm_lists_paginated(offset=offset, limit=PAGE, active_only=False)
    total = db_get_lpm_lists_count()

    text = f"📋 **LPM POOL** (hal {offset//PAGE + 1})\n\n"
    buttons = []

    if not items:
        text += "_Pool kosong._"
    else:
        for item in items:
            status = "🟢" if item.get("is_active") else ("🚫" if item.get("is_blacklisted") else "🔴")
            name = (item.get("group_name") or item.get("group_link") or "-")
            members = item.get("member_count", 0)
            text += f"{status} **{name[:28]}** ({members:,} member)\n`{item.get('group_link')}`\n\n"
            buttons.append([
                Button.inline("✏️ Edit", f"lpm_edit_{item['id']}".encode()),
                Button.inline("🗑 Hapus", f"lpm_del_{item['id']}".encode()),
                Button.inline("🚫 BL", f"lpm_bl_{item['id']}".encode())
            ])

    # Navigasi halaman
    nav = []
    if offset > 0:
        nav.append(Button.inline("◀️ Prev", f"lpm_page_{max(0, offset - PAGE)}".encode()))
    if offset + PAGE < total:
        nav.append(Button.inline("Next ▶️", f"lpm_page_{offset + PAGE}".encode()))
    if nav:
        buttons.append(nav)

    buttons.append([Button.inline("➕ Tambah LPM", b"lpm_add"), Button.inline("⬅️ Menu LPM", b"lpm_main")])

    if hasattr(event, "edit"):
        try:
            await event.edit(text, buttons=buttons); return
        except Exception:
            pass
    await event.respond(text, buttons=buttons)


async def _show_setprice_menu(event):
    prices = _load_prices_json()
    qris_tax = prices.get("qris_tax_percent", 0.7)
    text = (
        "💰 **MANAJEMEN HARGA GEUNID**\n\n"
        "Pilih tipe paket yang ingin dikelola:\n\n"
        "• Edit harga, durasi, LPM, bonus per paket\n"
        "• Tambah paket baru\n"
        "• Hapus paket\n\n"
        f"⚡ **Pajak KlikQRIS Saat Ini:** `{qris_tax}%`"
    )
    buttons = [
        [Button.inline("📢 Regular", b"sp_type_regular"), Button.inline("📤 Forward", b"sp_type_forward")],
        [Button.inline("🤖 Userbot", b"sp_type_userbot")],
        [Button.inline(f"⚡ Set Pajak QRIS ({qris_tax}%)", b"sp_edit_qris_tax")],
        [Button.inline("📋 Lihat Semua Pricelist", b"sp_view")],
        [Button.inline("⬅️ Kembali ke Admin", b"admin_main")]
    ]
    if hasattr(event, "edit"):
        try:
            await event.edit(text, buttons=buttons); return
        except Exception:
            pass
    await event.respond(text, buttons=buttons)


async def _show_setprice_package_list(event, ptype: str):
    prices = _load_prices_json()
    items = prices.get(ptype, [])
    icon = {"regular": "📢", "forward": "📤", "userbot": "🤖"}.get(ptype, "📦")

    text = f"{icon} **PAKET {ptype.upper()}**\n\n"
    buttons = []

    if not items:
        text += "_Belum ada paket._\n"
    else:
        for item in items:
            lpm_str = f" {item['lpm']} LPM" if item.get("lpm", 0) > 0 else ""
            bonus_str = f" (+{item['bonus']})" if item.get("bonus") else ""
            text += (
                f"• `{item['id']}`\n"
                f"  ⏰ {item['duration']}{lpm_str}{bonus_str}\n"
                f"  💰 **Rp {item.get('promoPrice', 0):,}** ~~(Rp {item.get('originalPrice', 0):,})~~\n\n"
            )
            buttons.append([
                Button.inline(f"✏️ Edit {item['duration']}{lpm_str}", f"sp_pkg_{item['id']}".encode()),
                Button.inline("🗑", f"sp_del_{item['id']}".encode())
            ])

    buttons.append([Button.inline(f"➕ Tambah {ptype.upper()}", f"sp_add_{ptype}".encode())])
    buttons.append([Button.inline("⬅️ Kembali", b"sp_main")])

    if hasattr(event, "edit"):
        try:
            await event.edit(text, buttons=buttons, parse_mode="md"); return
        except Exception:
            pass
    await event.respond(text, buttons=buttons, parse_mode="md")


async def _show_ubots(event):
    admins = db_get_admin_userbots()
    text = "🤖 **ADMIN POOL**\n\n"
    buttons = []
    if not admins:
        text += "_Belum ada nomor admin._"
    else:
        for aid, phone, status, cooldown in admins:
            icon = "🟢" if status == 'connected' else "🔴"
            cd_str = f" (cooldown s/d {cooldown[:10]})" if cooldown else ""
            text += f"{icon} {phone}{cd_str}\n"
            if status == 'connected':
                buttons.append([Button.inline(f"🔌 Disconnect {phone}", f"admin_dc_pool_{aid}".encode())])
    buttons.append([Button.inline("⬅️ Kembali", b"admin_main")])
    if hasattr(event, "edit"):
        try:
            await event.edit(text, buttons=buttons); return
        except Exception:
            pass
    await event.respond(text, buttons=buttons)


async def _show_client_ubots(event):
    ubots = db_get_all_client_userbots(15)
    text = "👤 **USERBOT PEMBELI**\n\n"
    buttons = []
    if not ubots:
        text += "_Belum ada userbot pembeli._"
    else:
        for ub in ubots:
            uid = ub["user_id"]
            phone = ub.get("phone_number", "-")
            status = ub.get("status", "disconnected")
            icon = "🟢" if status == "connected" else "🔴"
            text += f"{icon} `{uid}` | {phone} | {status}\n"
            buttons.append([
                Button.inline(f"🔌 DC {uid}", f"cub_dc_{uid}".encode()),
                Button.inline(f"🗑 Del {uid}", f"cub_del_{uid}".encode())
            ])
    buttons.append([Button.inline("⬅️ Kembali", b"admin_main")])
    if hasattr(event, "edit"):
        try:
            await event.edit(text, buttons=buttons); return
        except Exception:
            pass
    await event.respond(text, buttons=buttons)


def normalize_end(date_str: str) -> str:
    if not date_str:
        return "-"
    try:
        date_str = date_str.replace("T", " ")
        if "+" in date_str:
            date_str = date_str.split("+")[0]
        if "." in date_str:
            date_str = date_str.split(".")[0]
        return date_str.strip()
    except:
        return date_str


def register_broadcast_all_confirm(bot, start_broadcast_fn):
    pass  # Reserved
