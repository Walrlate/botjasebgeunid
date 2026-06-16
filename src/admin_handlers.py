"""
admin_handlers.py — Panel Admin Lengkap GEUNID JASEB
Termasuk /setprice interaktif via state machine
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

# Label tipe paket
_TYPE_LABELS = {
    "regular": "📢 Regular",
    "forward": "📤 Forward",
    "userbot": "🤖 Userbot"
}


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


def _load_prices_json() -> dict:
    """Load prices.json dari filesystem."""
    try:
        if os.path.exists(_PRICES_PATH):
            with open(_PRICES_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Gagal baca prices.json: {e}")
    return {}


def _save_prices_json(data: dict) -> bool:
    """Simpan prices.json ke filesystem."""
    try:
        os.makedirs(os.path.dirname(_PRICES_PATH), exist_ok=True)
        with open(_PRICES_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Gagal simpan prices.json: {e}")
        return False


def _format_price_list_text(prices: dict) -> str:
    """Format pricelist menjadi teks yang rapi."""
    lines = ["💰 **PRICELIST SAAT INI**\n"]
    type_icons = {"regular": "📢", "forward": "📤", "userbot": "🤖"}
    for ptype, icon in type_icons.items():
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


def _register_admin_handlers(bot):

    # ───────────────────────────────────────────
    # PERINTAH & CALLBACK UTAMA ADMIN
    # ───────────────────────────────────────────
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
    # BILLING
    # ═══════════════════════════════════════════
    @bot.on(events.CallbackQuery(data=b"admin_billing"))
    async def admin_billing_callback(event):
        if not await _admin_only_check(event): return
        await _show_billing(event)

    # ═══════════════════════════════════════════
    # /setprice — SISTEM EDIT HARGA INTERAKTIF
    # ═══════════════════════════════════════════
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

    # Pilih tipe paket
    @bot.on(events.CallbackQuery(pattern=b"sp_type_(.+)"))
    async def setprice_type_callback(event):
        if not await _admin_only_check(event): return
        ptype = event.pattern_match.group(1).decode()
        if ptype not in ("regular", "forward", "userbot"):
            await event.answer("Tipe tidak valid.", alert=True)
            return
        await _show_setprice_package_list(event, ptype)

    # Pilih paket spesifik untuk diedit
    @bot.on(events.CallbackQuery(pattern=b"sp_pkg_(.+)"))
    async def setprice_pkg_callback(event):
        if not await _admin_only_check(event): return
        pkg_id = event.pattern_match.group(1).decode()
        prices = _load_prices_json()
        
        # Cari paket berdasarkan ID
        found_item = None
        found_type = None
        for ptype, items in prices.items():
            for item in items:
                if item.get("id") == pkg_id:
                    found_item = item
                    found_type = ptype
                    break
            if found_item:
                break

        if not found_item:
            await event.answer("❌ Paket tidak ditemukan.", alert=True)
            return

        # Simpan state untuk input harga
        _login_states[event.sender_id] = {
            "state": "setprice_waiting_promo",
            "pkg_id": pkg_id,
            "pkg_type": found_type,
            "pkg_item": found_item,
        }

        lpm_str = f" {found_item['lpm']} LPM" if found_item.get("lpm", 0) > 0 else ""
        bonus_str = f" (+{found_item['bonus']})" if found_item.get("bonus") else ""
        promo_now = found_item.get("promoPrice", 0)
        orig_now = found_item.get("originalPrice", 0)

        text = (
            f"✏️ **EDIT HARGA PAKET**\n\n"
            f"📦 Paket: `{pkg_id}`\n"
            f"⏰ Durasi: {found_item['duration']}{lpm_str}{bonus_str}\n"
            f"💰 Harga Promo Sekarang: **Rp {promo_now:,}**\n"
            f"🏷 Harga Coret Sekarang: Rp {orig_now:,}\n\n"
            f"Ketik **harga promo baru** (angka saja):\n"
            f"_Contoh: `9900`_"
        )
        await event.edit(text, buttons=[[Button.inline("❌ Batal", b"sp_main")]])

    # Tambah paket baru ke tipe tertentu
    @bot.on(events.CallbackQuery(pattern=b"sp_add_(.+)"))
    async def setprice_add_callback(event):
        if not await _admin_only_check(event): return
        ptype = event.pattern_match.group(1).decode()
        if ptype not in ("regular", "forward", "userbot"):
            await event.answer("Tipe tidak valid.", alert=True)
            return

        _login_states[event.sender_id] = {
            "state": "setprice_add_waiting_input",
            "pkg_type": ptype,
        }

        text = (
            f"➕ **TAMBAH PAKET {ptype.upper()} BARU**\n\n"
            f"Kirim detail paket dalam 1 baris dengan format:\n\n"
            f"`durasi | lpm | harga_coret | harga_promo`\n\n"
            f"**Contoh:**\n"
            f"{'`14 Hari | 20 | 30000 | 12000`' if ptype != 'userbot' else '`14 Hari | 0 | 30000 | 12000`'}\n\n"
            f"_• Untuk Userbot, isi lpm = 0_\n"
            f"_• Semua angka tanpa titik/koma_"
        )
        await event.edit(text, buttons=[[Button.inline("❌ Batal", b"sp_main")]])

    # Hapus paket
    @bot.on(events.CallbackQuery(pattern=b"sp_del_(.+)"))
    async def setprice_del_callback(event):
        if not await _admin_only_check(event): return
        pkg_id = event.pattern_match.group(1).decode()
        prices = _load_prices_json()

        deleted = False
        found_type = None
        for ptype, items in prices.items():
            new_items = [i for i in items if i.get("id") != pkg_id]
            if len(new_items) < len(items):
                prices[ptype] = new_items
                deleted = True
                found_type = ptype
                break

        if deleted and _save_prices_json(prices):
            await event.answer(f"✅ Paket `{pkg_id}` berhasil dihapus!", alert=True)
            await _show_setprice_package_list(event, found_type)
        else:
            await event.answer("❌ Gagal menghapus paket.", alert=True)


# ═══════════════════════════════════════════════
# INPUT HANDLER HARGA (State Machine via NewMessage)
# ═══════════════════════════════════════════════
async def handle_setprice_input(event, state_data: dict):
    """
    Dipanggil dari main.py user_input_handler saat state setprice_* aktif.
    """
    user_id = event.sender_id
    text = (event.text or "").strip()
    current_state = state_data.get("state")

    # ─── STATE: Menunggu harga promo baru ───
    if current_state == "setprice_waiting_promo":
        if not text.isdigit():
            await event.respond("❌ Masukkan **angka saja** tanpa titik/koma.\n_Contoh: `9900`_")
            return

        new_promo = int(text)
        state_data["new_promo"] = new_promo
        state_data["state"] = "setprice_waiting_orig"
        _login_states[user_id] = state_data

        pkg_item = state_data["pkg_item"]
        orig_now = pkg_item.get("originalPrice", new_promo * 2)
        await event.respond(
            f"✅ Harga promo baru: **Rp {new_promo:,}**\n\n"
            f"Sekarang ketik **harga coret** (harga asli sebelum promo):\n"
            f"_Harga coret saat ini: Rp {orig_now:,}_\n"
            f"_Kirim `/same` untuk pakai harga coret yang sama_"
        )
        return

    # ─── STATE: Menunggu harga coret ───
    elif current_state == "setprice_waiting_orig":
        if text.lower() == "/same":
            new_orig = state_data["pkg_item"].get("originalPrice", state_data["new_promo"] * 2)
        elif text.isdigit():
            new_orig = int(text)
        else:
            await event.respond("❌ Masukkan angka atau kirim `/same` untuk tetap pakai harga coret lama.")
            return

        # Simpan ke prices.json
        prices = _load_prices_json()
        pkg_id = state_data["pkg_id"]
        ptype = state_data["pkg_type"]
        new_promo = state_data["new_promo"]

        updated = False
        for item in prices.get(ptype, []):
            if item.get("id") == pkg_id:
                item["promoPrice"] = new_promo
                item["originalPrice"] = new_orig
                updated = True
                break

        del _login_states[user_id]

        if updated and _save_prices_json(prices):
            lpm_str = f" {state_data['pkg_item']['lpm']} LPM" if state_data['pkg_item'].get("lpm", 0) > 0 else ""
            await event.respond(
                f"✅ **HARGA BERHASIL DIPERBARUI!**\n\n"
                f"📦 Paket: `{pkg_id}`\n"
                f"⏰ Durasi: {state_data['pkg_item']['duration']}{lpm_str}\n"
                f"💰 Harga Baru: **Rp {new_promo:,}**\n"
                f"🏷 Harga Coret: ~~Rp {new_orig:,}~~\n\n"
                f"✨ Mini App akan auto-update dalam hitungan detik!",
                buttons=[[Button.inline("💰 Edit Harga Lain", b"sp_main"), Button.inline("📋 Lihat Semua", b"sp_view")]]
            )
        else:
            await event.respond("❌ Gagal menyimpan. Coba lagi dengan `/setprice`.")

    # ─── STATE: Menunggu input paket baru ───
    elif current_state == "setprice_add_waiting_input":
        parts = [p.strip() for p in text.split("|")]
        if len(parts) != 4:
            await event.respond(
                "❌ Format salah! Kirim 4 kolom dipisah `|`:\n"
                "`durasi | lpm | harga_coret | harga_promo`\n\n"
                "_Contoh: `14 Hari | 20 | 30000 | 12000`_"
            )
            return

        duration_str, lpm_str, orig_str, promo_str = parts

        if not lpm_str.isdigit() or not orig_str.isdigit() or not promo_str.isdigit():
            await event.respond("❌ LPM, harga coret, dan harga promo harus angka semua.")
            return

        ptype = state_data["pkg_type"]
        lpm = int(lpm_str)
        orig = int(orig_str)
        promo = int(promo_str)

        # Generate ID unik
        slug = re.sub(r'[^a-z0-9]', '', duration_str.lower().replace(" ", ""))
        new_id = f"{ptype[:3]}_{lpm}lpm_{slug}" if lpm > 0 else f"{ptype[:2]}_{slug}"

        new_item = {
            "id": new_id,
            "duration": duration_str,
            "lpm": lpm,
            "originalPrice": orig,
            "promoPrice": promo
        }

        prices = _load_prices_json()
        if ptype not in prices:
            prices[ptype] = []
        prices[ptype].append(new_item)

        del _login_states[user_id]

        if _save_prices_json(prices):
            lpm_info = f" {lpm} LPM" if lpm > 0 else ""
            await event.respond(
                f"✅ **PAKET BARU DITAMBAHKAN!**\n\n"
                f"📦 ID: `{new_id}`\n"
                f"📋 Tipe: {ptype.upper()}\n"
                f"⏰ Durasi: {duration_str}{lpm_info}\n"
                f"💰 Harga Promo: **Rp {promo:,}**\n"
                f"🏷 Harga Coret: ~~Rp {orig:,}~~\n\n"
                f"✨ Mini App auto-update sekarang!",
                buttons=[[Button.inline("💰 Kelola Harga Lain", b"sp_main"), Button.inline("📋 Lihat Semua", b"sp_view")]]
            )
        else:
            await event.respond("❌ Gagal menyimpan. Coba lagi dengan `/setprice`.")


# ═══════════════════════════════════════════════
# HELPER UI FUNCTIONS
# ═══════════════════════════════════════════════

async def _show_admin_panel(event):
    text = "🛡️ **GEUNID ADMIN PANEL**"
    buttons = [
        [Button.inline("📊 Stats", b"admin_stats"), Button.inline("👥 Billing", b"admin_billing")],
        [Button.inline("💰 Kelola Harga", b"sp_main"), Button.inline("🤖 Admin Pool", b"admin_ubots")],
        [Button.inline("⬅️ Menu Utama", b"start")]
    ]
    if hasattr(event, "edit"):
        try:
            await event.edit(text, buttons=buttons)
            return
        except Exception:
            pass
    await event.respond(text, buttons=buttons)


async def _show_setprice_menu(event):
    """Tampilkan menu utama setprice: pilih tipe paket."""
    text = (
        "💰 **MANAJEMEN HARGA GEUNID**\n\n"
        "Pilih tipe paket yang ingin dikelola:\n\n"
        "• Edit harga promo & harga coret per paket\n"
        "• Tambah paket baru\n"
        "• Hapus paket yang tidak diinginkan"
    )
    buttons = [
        [Button.inline("📢 Regular", b"sp_type_regular"), Button.inline("📤 Forward", b"sp_type_forward")],
        [Button.inline("🤖 Userbot", b"sp_type_userbot")],
        [Button.inline("📋 Lihat Semua Pricelist", b"sp_view")],
        [Button.inline("⬅️ Kembali ke Admin", b"admin_main")]
    ]
    if hasattr(event, "edit"):
        try:
            await event.edit(text, buttons=buttons)
            return
        except Exception:
            pass
    await event.respond(text, buttons=buttons)


async def _show_setprice_package_list(event, ptype: str):
    """Tampilkan daftar paket dalam satu tipe beserta tombol edit/hapus/tambah."""
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
                Button.inline("🗑 Hapus", f"sp_del_{item['id']}".encode())
            ])

    buttons.append([Button.inline(f"➕ Tambah Paket {ptype.upper()}", f"sp_add_{ptype}".encode())])
    buttons.append([Button.inline("⬅️ Kembali", b"sp_main")])

    if hasattr(event, "edit"):
        try:
            await event.edit(text, buttons=buttons, parse_mode="md")
            return
        except Exception:
            pass
    await event.respond(text, buttons=buttons, parse_mode="md")


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
    pass  # Reserved
