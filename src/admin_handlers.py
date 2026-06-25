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
    db_update_admin_lpm_description,
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
    db_get_pending_transactions,
    db_get_transaction_detail,
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

async def show_promote_panel(event, edit=False):
    from src.database import db_get_admin_promote_ad
    content, buttons_json = db_get_admin_promote_ad()
    
    if not content:
        content = "🚀 **GEUNID JASEB** - Solusi Jasa Sebar Iklan Telegram Terbaik!"
        
    preview_text = f"📢 **PREVIEW PROMOSI GEUNID**\n{'━'*30}\n\n{content}"
    
    buttons = []
    if buttons_json:
        try:
            import json
            btn_data = json.loads(buttons_json)
            row = []
            for btn in btn_data:
                row.append(Button.url(btn["text"], btn["url"]))
                if len(row) == 2:
                    buttons.append(row)
                    row = []
            if row:
                buttons.append(row)
        except:
            pass
            
    from src.logic import active_broadcasts
    from src.config import ADMIN_ID
    is_running = ADMIN_ID in active_broadcasts
    
    action_btn = Button.inline("🛑 Hentikan Promosi", b"promo_stop_broadcast") if is_running else Button.inline("🚀 Mulai Sebar Promosi", b"promo_start_broadcast")
    
    control_buttons = [
        [Button.inline("📝 Edit Teks", b"promo_edit_text"), Button.inline("🔗 Edit Tombol", b"promo_edit_btns")],
        [action_btn],
        [Button.inline("⬅️ Kembali ke Admin", b"admin_main")]
    ]
    
    all_buttons = buttons + control_buttons
    
    if edit and hasattr(event, "edit"):
        try:
            await event.edit(preview_text, buttons=all_buttons, parse_mode="html")
            return
        except:
            pass
    await event.respond(preview_text, buttons=all_buttons, parse_mode="html")

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
        
        default_data = {}
        if os.path.exists(default_path):
            with open(default_path, "r", encoding="utf-8") as f:
                default_data = json.load(f)
                
        if not os.path.exists(_PRICES_PATH):
            if default_data:
                import shutil
                os.makedirs(os.path.dirname(_PRICES_PATH), exist_ok=True)
                shutil.copy(default_path, _PRICES_PATH)
                logger.info("ℹ️ prices.json default disalin ke penyimpanan persisten data/prices.json")
        else:
            try:
                with open(_PRICES_PATH, "r", encoding="utf-8") as f:
                    curr_data = json.load(f)
                
                def count_items(d):
                    return len(d.get("regular", [])) + len(d.get("forward", [])) + len(d.get("userbot", []))
                
                if count_items(default_data) > count_items(curr_data):
                    import shutil
                    os.makedirs(os.path.dirname(_PRICES_PATH), exist_ok=True)
                    shutil.copy(default_path, _PRICES_PATH)
                    logger.info("🔄 prices.json default lebih baru, menimpa data/prices.json")
            except Exception as cmp_err:
                logger.error(f"Gagal membandingkan prices.json: {cmp_err}")
                
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

    # ─── KOMANDO UTAMA ADMIN BARU ───
    @bot.on(events.NewMessage(pattern=r'/promote'))
    async def promote_command(event):
        if not await _admin_only_check(event): return
        _login_states.pop(event.sender_id, None)
        await show_promote_panel(event, edit=False)

    @bot.on(events.NewMessage(pattern=r'/restart'))
    async def restart_command(event):
        if not await _admin_only_check(event): return
        
        await event.respond("🔄 **Memulai Ulang Bot...**\n\nSistem akan memuat kembali seluruh modul dan kode terbaru. Silakan tunggu 5-10 detik.")
        
        # Jeda sejenak agar pesan selesai terkirim
        await asyncio.sleep(1.5)
        
        try:
            await bot.disconnect()
        except:
            pass
            
        import os
        import sys
        
        # Jalankan ulang interpreter python dengan process args yang sama
        os.execv(sys.executable, [sys.executable] + sys.argv)

    @bot.on(events.CallbackQuery(data=b"promo_panel"))
    async def promo_panel_callback(event):
        if not await _admin_only_check(event): return
        _login_states.pop(event.sender_id, None)
        await show_promote_panel(event, edit=True)

    @bot.on(events.CallbackQuery(data=b"promo_edit_text"))
    async def promo_edit_text_callback(event):
        if not await _admin_only_check(event): return
        _login_states[event.sender_id] = {"state": "admin_edit_promote_text"}
        await event.edit(
            "📝 **EDIT TEKS PROMOSI**\n\n"
            "Kirimkan teks materi promosi yang baru (HTML didukung):",
            buttons=[[Button.inline("❌ Batal", b"promo_panel")]]
        )

    @bot.on(events.CallbackQuery(data=b"promo_edit_btns"))
    async def promo_edit_btns_callback(event):
        if not await _admin_only_check(event): return
        _login_states[event.sender_id] = {"state": "admin_edit_promote_buttons"}
        await event.edit(
            "🔗 **EDIT TOMBOL PROMOSI**\n\n"
            "Kirimkan tombol promosi baru dengan format pipa (satu tombol per baris).\n\n"
            "Format:\n"
            "`Teks Tombol 1 | Tautan URL 1`\n"
            "`Teks Tombol 2 | Tautan URL 2`\n\n"
            "Ketik `-` untuk menghapus semua tombol.",
            buttons=[[Button.inline("❌ Batal", b"promo_panel")]]
        )

    @bot.on(events.CallbackQuery(data=b"promo_start_broadcast"))
    async def promo_start_broadcast_callback(event):
        if not await _admin_only_check(event): return
        from src.database import get_supabase
        supabase = get_supabase()
        res = supabase.table("user_ads").select("id").eq("user_id", ADMIN_ID).eq("title", "Promosi Admin").limit(1).execute()
        if res.data:
            ad_id = res.data[0]["id"]
            await event.answer("🚀 Memulai broadcast promosi!", alert=True)
            asyncio.create_task(run_promote_broadcast_task(bot, event.chat_id, ad_id))
        else:
            # Jika belum ada di DB, buat default dulu
            from src.database import db_save_admin_promote_ad
            db_save_admin_promote_ad("🚀 **GEUNID JASEB** - Solusi Jasa Sebar Iklan Telegram Terbaik!", "")
            res2 = supabase.table("user_ads").select("id").eq("user_id", ADMIN_ID).eq("title", "Promosi Admin").limit(1).execute()
            if res2.data:
                ad_id = res2.data[0]["id"]
                await event.answer("🚀 Memulai broadcast promosi!", alert=True)
                asyncio.create_task(run_promote_broadcast_task(bot, event.chat_id, ad_id))
            else:
                await event.answer("❌ Gagal memulai, materi promosi kosong.", alert=True)

    @bot.on(events.CallbackQuery(data=b"promo_stop_broadcast"))
    async def promo_stop_broadcast_callback(event):
        if not await _admin_only_check(event): return
        from src.logic import active_broadcasts
        if ADMIN_ID in active_broadcasts:
            active_broadcasts.discard(ADMIN_ID)
            await event.answer("🛑 Permintaan penghentian promosi dikirim!", alert=True)
        else:
            await event.answer("ℹ️ Promosi memang tidak sedang berjalan.", alert=True)
        await show_promote_panel(event, edit=True)

    @bot.on(events.NewMessage(pattern=r'/gentoken(?:\s+(.+))?'))
    async def gentoken_command(event):
        if not await _admin_only_check(event): return
        
        args = event.pattern_match.group(1) or ""
        parts = args.strip().split()
        if not parts:
            prices = _load_prices_json()
            lines = [
                "🔑 **PEMBUATAN VOUCHER AKTIVASI**\n",
                "Gunakan salah satu format berikut:\n",
                "1️⃣ **Format Pricelist (Paket Terdaftar):**",
                "Gunakan format: `/gentoken <paket_id> [jumlah]`\n",
                "Daftar `paket_id` yang tersedia:"
            ]
            for k in ['regular', 'forward', 'userbot']:
                for item in prices.get(k, []):
                    lines.append(f"• `{item['id']}` - {item['duration']}")
            
            lines.extend([
                "\n2️⃣ **Format Kustom (Bebas Atur / Trial):**",
                "Gunakan format: `/gentoken <tipe_paket> <durasi> <kapasitas_lpm> [jumlah]`\n",
                "• `<tipe_paket>` : `regular` / `forward` / `userbot` (atau `reg` / `fwd` / `ub`)",
                "• `<durasi>` : Angka dengan suffix `d` (hari) atau `h` (jam) (contoh: `30d`, `12h`, `6h`)",
                "• `<kapasitas_lpm>` : Angka LPM (contoh: `25` untuk 25 LPM, atau `0` jika userbot)",
                "• `[jumlah]` : Jumlah voucher yang dicetak (default `1`)\n",
                "_Contoh Kustom:_ `/gentoken regular 12h 35 5` (membuat 5 voucher regular, 12 jam, 35 LPM)"
            ])
            await event.respond("\n".join(lines))
            return
            
        first_arg = parts[0].lower()
        is_custom = first_arg in ['regular', 'forward', 'userbot', 'reg', 'fwd', 'ub']
        
        package_id = ""
        days = 30
        lpm_capacity = 20
        count = 1
        duration_label = ""
        package_label = ""
        
        if is_custom:
            import re
            duration_arg = parts[1].lower() if len(parts) > 1 else ""
            m_dur = re.match(r'^(\d+)(h|d)?$', duration_arg)
            
            if len(parts) < 3 or not m_dur or not parts[2].isdigit():
                await event.respond(
                    "❌ **Format Kustom Salah!**\n\n"
                    "Gunakan format: `/gentoken <tipe_paket> <durasi> <kapasitas_lpm> [jumlah]`\n"
                    "• `<durasi>` : Angka dengan suffix 'd' (hari) atau 'h' (jam). Contoh: `30d` atau `12h`\n"
                    "_Contoh:_ `/gentoken regular 12h 35 5`"
                )
                return
            
            tipe_paket = "regular"
            if first_arg in ['reg', 'regular']:
                tipe_paket = "regular"
            elif first_arg in ['fwd', 'forward']:
                tipe_paket = "forward"
            elif first_arg in ['ub', 'userbot']:
                tipe_paket = "userbot"
                
            val_dur = int(m_dur.group(1))
            unit_dur = m_dur.group(2) or 'd'
            
            if unit_dur == 'h':
                days = -val_dur # Simpan negatif untuk menandakan jam
                duration_label = f"{val_dur} Jam"
            else:
                days = val_dur
                duration_label = f"{val_dur} Hari"
                
            lpm_capacity = int(parts[2])
            if tipe_paket == "userbot":
                lpm_capacity = 0 # Paksa 0 untuk userbot
                
            if len(parts) > 3 and parts[3].isdigit():
                count = int(parts[3])
                
            # Bentuk package_id kustom agar ketika diklaim, package_name disimpan dengan benar
            package_id = f"{tipe_paket}_{lpm_capacity}_{val_dur}{unit_dur}_custom" if tipe_paket != "userbot" else f"{tipe_paket}_{val_dur}{unit_dur}_custom"
            package_label = f"{tipe_paket.upper()} (KUSTOM)"
            
        else:
            package_id = parts[0].strip()
            if len(parts) > 1 and parts[1].isdigit():
                count = int(parts[1])
                
            prices = _load_prices_json()
            target_item = None
            for category in ['regular', 'forward', 'userbot']:
                for item in prices.get(category, []):
                    if item.get('id') == package_id:
                        target_item = item
                        break
                if target_item: break
                
            if not target_item:
                await event.respond(f"❌ `paket_id` `{package_id}` tidak ditemukan di pricelist.")
                return
                
            duration_str = target_item.get('duration', '')
            import re
            days = int(re.search(r'(\d+)', duration_str).group(1)) if re.search(r'(\d+)', duration_str) else 30
            bonus = re.search(r'\+(\d+)', target_item.get('bonus', ''))
            if bonus:
                days += int(bonus.group(1))
                
            lpm_capacity = target_item.get('lpm', 20)
            duration_label = target_item.get('duration', f"{days} Hari")
            package_label = package_id.upper()
            
        import uuid
        from src.database import db_generate_activation_token
        
        generated_tokens = []
        for _ in range(count):
            token = f"GEUNID-{uuid.uuid4().hex[:4].upper()}-{uuid.uuid4().hex[4:8].upper()}"
            if db_generate_activation_token(token, package_id, lpm_capacity, days):
                generated_tokens.append(token)
                
        if not generated_tokens:
            await event.respond("❌ Gagal membuat token.")
            return
            
        token_lines = [f"`{tok}`" for tok in generated_tokens]
        
        # Format durasi teks yang rapi di output telegram
        detail_duration = f"{abs(days)} Jam" if days < 0 else f"{days} Hari"
        
        res_text = (
            f"🔑 **VOUCHER AKTIVASI SELESAI DICETAK**\n{'━'*30}\n\n"
            f"📦 Paket: **{package_label}**\n"
            f"🎯 Kapasitas: **{lpm_capacity} LPM**\n"
            f"⏳ Durasi: **{duration_label}** ({detail_duration})\n"
            f"🔢 Jumlah: **{len(generated_tokens)} voucher**\n\n"
            f"**Daftar Token:** (sentuh untuk copy)\n" + "\n".join(token_lines)
        )
        await event.respond(res_text)

    # ─── CALLBACK PENGATURAN MASSAL ───
    @bot.on(events.CallbackQuery(data=b"admin_mass"))
    async def admin_mass_callback(event):
        if not await _admin_only_check(event): return
        _login_states.pop(event.sender_id, None)
        await _show_mass_settings_panel(event)

    @bot.on(events.CallbackQuery(data=b"mass_start"))
    async def mass_start_handler(event):
        if not await _admin_only_check(event): return
        from src.database import db_get_active_users_for_scheduler
        users = db_get_active_users_for_scheduler()
        
        if not users:
            await event.answer("❌ Tidak ada klien aktif saat ini.", alert=True)
            return
            
        success_triggered = 0
        from src.logic import active_broadcasts
        for uid, iv in users:
            if uid not in active_broadcasts:
                asyncio.create_task(_start_user_broadcast(uid))
                success_triggered += 1
                
        await event.answer(f"🚀 Memulai broadcast massal untuk {success_triggered} klien!", alert=True)
        await _show_mass_settings_panel(event)

    @bot.on(events.CallbackQuery(data=b"mass_stop"))
    async def mass_stop_handler(event):
        if not await _admin_only_check(event): return
        from src.logic import active_broadcasts
        total_active = len(active_broadcasts)
        active_broadcasts.clear()
        
        await event.answer(f"🛑 Menghentikan paksa {total_active} proses broadcast aktif!", alert=True)
        await _show_mass_settings_panel(event)

    @bot.on(events.CallbackQuery(data=b"mass_interval"))
    async def mass_interval_handler(event):
        if not await _admin_only_check(event): return
        _login_states[event.sender_id] = {"state": "admin_mass_interval"}
        await event.edit(
            "⏰ **UBAH JEDA BROADCAST MASSAL**\n\n"
            "Ketik interval baru dalam jam untuk **SEMUA** subskripsi aktif:\n"
            "_Contoh: `0.5` (30 menit) | `1` (1 jam) | `2` (2 jam)_",
            buttons=[[Button.inline("❌ Batal", b"admin_mass")]]
        )

    @bot.on(events.CallbackQuery(pattern=b"mass_pm_(on|off)"))
    async def mass_pm_handler(event):
        if not await _admin_only_check(event): return
        status_str = event.pattern_match.group(1).decode()
        status_bool = (status_str == "on")
        
        from src.database import db_update_userbot_mass_settings
        if db_update_userbot_mass_settings(pm_permit_status=status_bool):
            try:
                from src.userbot_manager import reload_all_userbot_settings
                await reload_all_userbot_settings()
            except Exception as e:
                logger.error(f"Gagal reload settings: {e}")
                
            await event.answer(f"✅ PM Permit massal berhasil di{'aktifkan' if status_bool else 'nonaktifkan'}!", alert=True)
        else:
            await event.answer("❌ Gagal merubah status PM Permit massal.", alert=True)
        await _show_mass_settings_panel(event)

    @bot.on(events.CallbackQuery(data=b"mass_bio"))
    async def mass_bio_handler(event):
        if not await _admin_only_check(event): return
        _login_states[event.sender_id] = {"state": "admin_mass_bio"}
        await event.edit(
            "✍️ **UBAH BIO TELEGRAM MASSAL**\n\n"
            "Ketik biografi Telegram baru untuk **SEMUA** userbot klien (maks 70 karakter):\n"
            "_Contoh:_ `Promote by GEUNID JASEB`",
            buttons=[[Button.inline("❌ Batal", b"admin_mass")]]
        )

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
        # Guard: cek apakah transaksi masih pending (cegah double-approve)
        from src.database import db_get_transaction
        trx_data = db_get_transaction(trx_id)
        if not trx_data:
            await event.answer("❌ Transaksi tidak ditemukan!", alert=True)
            return
        if trx_data[3] != "pending":
            await event.answer(f"⚠️ Transaksi sudah diproses (status: {trx_data[3]})", alert=True)
            return
        from src.logic import process_activation
        await process_activation(bot, trx_id, _load_prices(), _login_states)
        await event.edit(f"✅ **TRANSAKSI {trx_id} DISETUJUI!**")

    @bot.on(events.CallbackQuery(pattern=b"reject_man_(.+)"))
    async def reject_manual_handler(event):
        if not await _admin_only_check(event): return
        trx_id = event.pattern_match.group(1).decode()
        # Guard: cek apakah transaksi masih pending
        from src.database import db_get_transaction
        trx_data = db_get_transaction(trx_id)
        if not trx_data:
            await event.answer("❌ Transaksi tidak ditemukan!", alert=True)
            return
        if trx_data[3] != "pending":
            await event.answer(f"⚠️ Transaksi sudah diproses (status: {trx_data[3]})", alert=True)
            return
        db_update_transaction_status(trx_id, "rejected")
        await event.edit(f"❌ **TRANSAKSI {trx_id} DITOLAK!**")
        # Kirim notifikasi penolakan ke user
        try:
            user_id = trx_data[0]
            pkg = trx_data[2]
            await bot.send_message(
                user_id,
                f"❌ **Pembayaran Anda Ditolak**\n\n"
                f"🔖 Order: `{trx_id}`\n"
                f"📦 Paket: `{pkg}`\n\n"
                f"Silakan hubungi admin jika merasa ini kesalahan: @{ADMIN_USERNAME}"
            )
        except Exception as notif_err:
            logger.error(f"Gagal kirim notif rejection ke user {trx_data[0]}: {notif_err}")

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

    @bot.on(events.CallbackQuery(pattern=b"admin_edit_desc_(\\d+)"))
    async def admin_edit_desc_callback(event):
        if not await _admin_only_check(event): return
        aid = int(event.pattern_match.group(1).decode())
        _login_states[event.sender_id] = {
            "state": "admin_editing_lpm_desc",
            "target_admin_id": aid
        }
        await event.edit(
            f"📝 **GANTI DESKRIPSI SLOT LPM**\n\n"
            f"Kirimkan teks deskripsi baru untuk Admin Pool ID `{aid}`:\n\n"
            f"Contoh: `Total LPM 100 Campur` atau `Khusus Grup Crypto`.\n"
            f"Maksimal 60 karakter.",
            buttons=[[Button.inline("❌ Batal", b"admin_ubots")]]
        )

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
        phone = "+" + event.pattern_match.group(1).decode()
        from src.userbot_manager import stop_client_userbot
        await stop_client_userbot(phone)
        if db_admin_disconnect_client_userbot(phone):
            await event.answer(f"✅ Userbot {phone} di-disconnect.", alert=True)
        else:
            await event.answer("❌ Gagal disconnect.", alert=True)
        await _show_client_ubots(event)

    @bot.on(events.CallbackQuery(pattern=b"cub_del_(\\d+)"))
    async def client_ubot_del_callback(event):
        if not await _admin_only_check(event): return
        phone = "+" + event.pattern_match.group(1).decode()
        from src.userbot_manager import stop_client_userbot
        await stop_client_userbot(phone)
        ok, session = db_admin_delete_client_userbot(phone)
        if ok:
            if session:
                for ext in [".session", ".session-journal"]:
                    path = f"data/sessions/{session}{ext}"
                    if os.path.exists(path):
                        try: os.remove(path)
                        except: pass
            await event.answer(f"✅ Userbot {phone} dihapus.", alert=True)
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
        await _show_billing_menu(event)

    @bot.on(events.CallbackQuery(data=b"admin_billing"))
    async def admin_billing_callback(event):
        if not await _admin_only_check(event): return
        _login_states.pop(event.sender_id, None)
        await _show_billing_menu(event)

    @bot.on(events.CallbackQuery(data=b"admin_billing_active"))
    async def admin_billing_active_callback(event):
        if not await _admin_only_check(event): return
        await _show_billing_list(event)

    @bot.on(events.CallbackQuery(data=b"admin_billing_pending"))
    async def admin_billing_pending_callback(event):
        if not await _admin_only_check(event): return
        await _show_pending_transactions(event)

    @bot.on(events.CallbackQuery(data=b"admin_billing_search"))
    async def admin_billing_search_callback(event):
        if not await _admin_only_check(event): return
        _login_states[event.sender_id] = {"state": "admin_search_trx"}
        text = (
            "🔍 **CARI TRANSAKSI**\n\n"
            "Masukkan ID Transaksi / Invoice yang ingin dicari:\n"
            "_(Contoh: `INV-1782348021916` atau `USERBOT-MAN-xxx`)_\n\n"
            "Ketik langsung di kolom chat bot ini."
        )
        buttons = [[Button.inline("❌ Batal", b"admin_billing")]]
        if hasattr(event, "edit"):
            await event.edit(text, buttons=buttons)
        else:
            await event.respond(text, buttons=buttons)

    @bot.on(events.CallbackQuery(pattern=b"trx_manage_(.+)"))
    async def trx_manage_callback(event):
        if not await _admin_only_check(event): return
        trx_id = event.pattern_match.group(1).decode()
        from src.database import db_get_transaction_detail
        trx = db_get_transaction_detail(trx_id)
        if not trx:
            await event.answer("❌ Transaksi tidak ditemukan!", alert=True)
            await _show_pending_transactions(event)
            return
        await _show_transaction_detail_message(event, trx)

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
        from src.userbot_manager import get_session_lock
        
        async with get_session_lock(sess):
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
            "⏳ **Memulai proses perapian & gradual join/leave sharding untuk semua Admin Pool...**\n"
            "Setiap akun admin akan menyelaraskan grup LPM-nya:\n"
            "- Join maksimal 5 grup baru di jatah slotnya (jeda 20-35 detik).\n"
            "- Keluar maksimal 15 grup yang berada di luar jatah slotnya (jeda 4-8 detik).\n\n"
            "Laporan progress dikirim berkala di sini."
        )


async def run_admin_pool_gradual_join(bot, status_chat_id):
    from src.database import db_get_active_admin_userbots, db_get_lpm_lists_count
    from src.supabase_client import get_supabase
    from telethon import TelegramClient
    from telethon.network import ConnectionTcpObfuscated
    from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
    import random
    import asyncio
    
    # 1. Api-ID & Api-Hash
    from src.config import API_ID, API_HASH
    
    # 2. Ambil semua admin terdaftar diurutkan berdasarkan ID ascending untuk kestabilan indeks sharding
    try:
        supabase = get_supabase()
        res_all_admins = supabase.table("admin_userbots") \
            .select("id, phone_number") \
            .order("id", desc=False) \
            .execute()
        all_admins = res_all_admins.data or []
        all_admin_ids = [a["id"] for a in all_admins]
    except Exception as e:
        logger.error(f"Gagal mengambil daftar admin dari Supabase: {e}")
        await bot.send_message(status_chat_id, f"❌ **Gagal:** Tidak bisa memuat data admin dari database: {e}")
        return

    if not all_admin_ids:
        await bot.send_message(status_chat_id, "❌ **Gagal:** Tidak ada Admin Pool terdaftar di database.")
        return

    # 3. Ambil semua LPM aktif dari database diurutkan berdasarkan ID ascending
    try:
        res_all_lpm = supabase.table("lpm_lists") \
            .select("group_link, group_id") \
            .eq("is_active", True) \
            .eq("is_blacklisted", False) \
            .order("id", desc=False) \
            .execute()
        all_active_lpm = res_all_lpm.data or []
        total_lpm = len(all_active_lpm)
    except Exception as e:
        logger.error(f"Gagal mengambil daftar LPM dari Supabase: {e}")
        await bot.send_message(status_chat_id, f"❌ **Gagal:** Tidak bisa memuat data LPM dari database: {e}")
        return

    if total_lpm == 0:
        await bot.send_message(status_chat_id, "❌ **Gagal:** Pool LPM aktif di database kosong.")
        return

    # 4. Ambil semua admin userbots aktif (yang terkoneksi saat ini)
    admins = db_get_active_admin_userbots()
    if not admins:
        await bot.send_message(status_chat_id, "❌ **Gagal:** Tidak ada akun Admin Pool yang terhubung (status: connected).")
        return

    await bot.send_message(
        status_chat_id, 
        f"📢 **SHARDED JOIN & LEAVE POOL DIMULAI**\n"
        f"👤 Admin Aktif: **{len(admins)}**\n"
        f"📋 Total LPM Database: **{total_lpm}**\n"
        f"⚙️ Aturan: **1 Akun = Slot 100 LPM** (Statis by ID ASC)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    
    SLOT_SIZE = 100
    for sess, phone, aid in admins:
        # Tentukan posisi urutan sharding (index ke-N)
        if aid not in all_admin_ids:
            await bot.send_message(status_chat_id, f"⚠️ **Admin {phone}** tidak ditemukan di daftar utama. Lewati.")
            continue
            
        idx = all_admin_ids.index(aid)  # 0-based index
        start_offset = idx * SLOT_SIZE
        end_offset = start_offset + SLOT_SIZE - 1
        
        # Saring slot LPM jatah admin ini
        slot_lpm = all_active_lpm[start_offset:end_offset+1]
        
        # Kumpulkan LPM luar slot (yang ada di database tapi di luar rentang indeks jatahnya)
        out_of_slot_lpm = all_active_lpm[:start_offset] + all_active_lpm[end_offset+1:]
        
        await bot.send_message(
            status_chat_id, 
            f"⏳ **Menghubungkan Sesi Admin #{idx+1}: {phone}...**\n"
            f"🎯 Jatah Slot: **LPM #{start_offset+1} s/d #{start_offset+len(slot_lpm)}**"
        )
        
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
            # Hubungkan sesi dengan penanganan lock (retry loop)
            connected = False
            retries = 3
            while retries > 0:
                try:
                    await client.connect()
                    connected = True
                    break
                except Exception as conn_err:
                    err_str = str(conn_err).lower()
                    if "lock" in err_str or "locked" in err_str:
                        logger.warning(f"⚠️ Berkas sesi admin {phone} terkunci, mencoba kembali dalam 5 detik... (Sisa retry: {retries-1})")
                        await asyncio.sleep(5)
                        retries -= 1
                    else:
                        raise conn_err
            
            if not connected:
                await bot.send_message(status_chat_id, f"⚠️ **Gagal:** Sesi {phone} terkunci oleh proses lain. Melewati.")
                continue
                
            if not await client.is_user_authorized():
                await bot.send_message(status_chat_id, f"⚠️ Akun {phone} tidak terotorisasi (butuh login ulang). Melewati.")
                continue
                
            # Ambil daftar chat/grup yang sudah diikuti oleh admin ini (ID & Username)
            joined_ids = set()
            joined_usernames = set()
            try:
                async for dialog in client.iter_dialogs(limit=None):
                    if dialog.is_group or dialog.is_channel:
                        joined_ids.add(dialog.entity.id)
                        if hasattr(dialog.entity, 'username') and dialog.entity.username:
                            joined_usernames.add(dialog.entity.username.lower())
            except Exception as ex:
                logger.error(f"Error iter_dialogs untuk {phone}: {ex}")
                
            # 1. Cari LPM di dalam jatah slot yang BELUM diikuti (To Join)
            to_join = []
            for lpm in slot_lpm:
                link = lpm["group_link"]
                db_group_id = lpm["group_id"]
                target_entity = link.strip().replace("https://t.me/", "").replace("t.me/", "").replace("@", "").lower()
                
                is_joined = False
                if db_group_id and int(db_group_id) in joined_ids:
                    is_joined = True
                elif target_entity in joined_usernames:
                    is_joined = True
                    
                if not is_joined:
                    to_join.append(link)
                    
            # 2. Cari LPM luar slot yang SAAT INI diikuti (To Leave)
            to_leave = []
            for lpm in out_of_slot_lpm:
                link = lpm["group_link"]
                db_group_id = lpm["group_id"]
                target_entity = link.strip().replace("https://t.me/", "").replace("t.me/", "").replace("@", "").lower()
                
                is_joined = False
                matched_peer = None
                if db_group_id and int(db_group_id) in joined_ids:
                    is_joined = True
                    matched_peer = int(db_group_id)
                elif target_entity in joined_usernames:
                    is_joined = True
                    matched_peer = target_entity
                    
                if is_joined:
                    to_leave.append((link, matched_peer))
                    
            # Kirim laporan pemetaan awal untuk akun ini
            report_msg = (
                f"📊 **Analisis Sesi {phone}** (Admin #{idx+1}):\n"
                f"• Jatah Slot: **LPM #{start_offset+1}–#{start_offset+len(slot_lpm)}** ({len(slot_lpm)} grup)\n"
                f"• Sudah Gabung: **{len(slot_lpm) - len(to_join)}** / {len(slot_lpm)}\n"
                f"• Perlu Join (Slot): **{len(to_join)}** grup\n"
                f"• Perlu Leave (Luar Slot): **{len(to_leave)}** grup"
            )
            await bot.send_message(status_chat_id, report_msg)
            
            # --- EKSEKUSI LEAVE (Keluar Grup Luar Slot) ---
            left_count = 0
            limit_leave = min(15, len(to_leave))  # Batasi maks 15 keluar per siklus agar aman
            if limit_leave > 0:
                await bot.send_message(status_chat_id, f"🔄 {phone} sedang keluar dari **{limit_leave}** grup luar slot secara bertahap...")
                for link, matched_peer in to_leave[:limit_leave]:
                    try:
                        entity = await client.get_entity(matched_peer)
                        await client(LeaveChannelRequest(entity))
                        left_count += 1
                        await asyncio.sleep(random.uniform(4, 8))  # Jeda aman saat leave
                    except Exception as ex:
                        logger.error(f"Admin {phone} gagal leave dari {link}: {ex}")
                        if "flood" in str(ex).lower():
                            await bot.send_message(status_chat_id, f"⚠️ Akun {phone} terkena FloodWait saat leave. Menghentikan leave.")
                            break
                await bot.send_message(status_chat_id, f"✅ {phone} berhasil keluar dari **{left_count}** grup luar slot.")
                
            # --- EKSEKUSI JOIN (Masuk Grup Jatah Slot) ---
            joined_count = 0
            limit_join = min(5, len(to_join))  # Batasi maks 5 join baru per siklus agar anti-banned
            if limit_join > 0:
                await bot.send_message(status_chat_id, f"🔄 {phone} sedang bergabung ke **{limit_join}** grup jatah slot secara bertahap...")
                for link in to_join[:limit_join]:
                    try:
                        target_entity = link.strip().replace("https://t.me/", "").replace("t.me/", "").replace("@", "")
                        entity = await client.get_entity(target_entity)
                        await client(JoinChannelRequest(entity))
                        joined_count += 1
                        await asyncio.sleep(random.uniform(20, 35))  # Jeda aman yang panjang saat join
                    except Exception as ex:
                        logger.error(f"Admin {phone} gagal join ke {link}: {ex}")
                        if "flood" in str(ex).lower():
                            await bot.send_message(status_chat_id, f"⚠️ Akun {phone} terkena FloodWait saat join. Menghentikan join.")
                            break
                await bot.send_message(status_chat_id, f"✅ {phone} berhasil bergabung ke **{joined_count}** grup jatah slot.")
                
            # Kirim rangkuman akhir sesi untuk akun ini
            await bot.send_message(
                status_chat_id, 
                f"👤 **Rangkuman Sesi {phone}**:\n"
                f"👉 Berhasil Join: **+{joined_count}** (Sisa belum join: {len(to_join) - joined_count})\n"
                f"👉 Berhasil Leave: **-{left_count}** (Sisa di luar slot: {len(to_leave) - left_count})"
            )
            
        except Exception as e:
            logger.error(f"Error processing admin join for {phone}: {e}")
            await bot.send_message(status_chat_id, f"❌ Terjadi kesalahan pada akun {phone}: {e}")
        finally:
            try:
                await client.disconnect()
            except:
                pass
            
    await bot.send_message(
        status_chat_id, 
        "🎯 **Proses Sharded Join & Leave selesai untuk seluruh Admin Pool!**\n"
        "Silakan jalankan kembali `/join_pool` secara berkala (misal 1-2 jam sekali) hingga seluruh sisa join/leave bernilai 0."
    )


async def run_promote_broadcast_task(bot, status_chat_id, ad_id):
    from src.database import db_get_active_admin_userbots, db_get_lpm_sharded_for_admin
    from src.jaseb_engine import JasebEngine
    
    admins = db_get_active_admin_userbots()
    if not admins:
        await bot.send_message(status_chat_id, "❌ **Gagal:** Tidak ada akun Admin Pool yang terhubung.")
        return
        
    await bot.send_message(status_chat_id, f"📢 **Promosi GeunID Dimulai:**\n🤖 Total Admin Pool: **{len(admins)}**\n🎯 Menggunakan sistem sharding (maks 100 LPM berbeda per admin ubot).")
    
    from src.config import API_ID, API_HASH
    from src.logic import active_broadcasts
    active_broadcasts.add(ADMIN_ID)
    
    total_succ = 0
    total_fail = 0
    
    try:
        for sess, phone, aid in admins:
            if ADMIN_ID not in active_broadcasts:
                await bot.send_message(status_chat_id, "⏹ **Promosi internal dihentikan paksa oleh Admin.**")
                break
                
            links = db_get_lpm_sharded_for_admin(aid, limit=100)
            if not links:
                logger.info(f"Admin {phone} tidak memiliki LPM sharded.")
                continue
                
            await bot.send_message(status_chat_id, f"🔄 Bot `{phone}` mulai menyebar ke **{len(links)}** LPM sharded...")
            
            eng = JasebEngine(f"data/sessions/{sess}", API_ID, API_HASH)
            try:
                await eng.start()
                res = await eng.broadcast_with_stealth(ADMIN_ID, ad_id, links, 'instant', is_promote=True)
                succ = res.get("success_count", 0)
                fail = res.get("failed_count", 0)
                total_succ += succ
                total_fail += fail
                await bot.send_message(status_chat_id, f"✅ Bot `{phone}` selesai. Sukses: **{succ}** | Gagal: **{fail}**")
            except Exception as ex:
                logger.error(f"Error pada ubot admin {phone} saat promosi: {ex}")
                await bot.send_message(status_chat_id, f"⚠️ Bot `{phone}` mengalami error: {ex}")
            finally:
                await eng.stop()
                
        await bot.send_message(status_chat_id, f"🎯 **PROMOSI INTERNAL SELESAI!**\n{'━'*26}\n\n📤 Total Sukses: **{total_succ}** grup\n❌ Total Gagal: **{total_fail}** grup")
    finally:
        active_broadcasts.discard(ADMIN_ID)


async def _show_mass_settings_panel(event):
    text = (
        "⚡ **PENGATURAN MASSAL ADMIN**\n\n"
        "Kendalikan seluruh userbot klien secara massal dengan satu ketukan:"
    )
    buttons = [
        [Button.inline("🚀 Mulai Sebar Massal", b"mass_start"), Button.inline("🛑 Hentikan Sebar Massal", b"mass_stop")],
        [Button.inline("⏰ Ubah Jeda Massal", b"mass_interval")],
        [Button.inline("🟢 Aktifkan PM Permit Massal", b"mass_pm_on"), Button.inline("🔴 Matikan PM Permit Massal", b"mass_pm_off")],
        [Button.inline("✍️ Ganti Bio Massal", b"mass_bio")],
        [Button.inline("⬅️ Kembali ke Admin", b"admin_main")]
    ]
    if hasattr(event, "edit"):
        try:
            await event.edit(text, buttons=buttons); return
        except Exception:
            pass
    await event.respond(text, buttons=buttons)


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

    elif state == "admin_search_trx":
        trx_id = text.strip()
        from src.database import db_get_transaction_detail
        trx = db_get_transaction_detail(trx_id)
        if not trx:
            await event.respond(
                f"❌ **Transaksi `{trx_id}` tidak ditemukan!**\n\n"
                f"Silakan coba masukkan ID Transaksi / Invoice yang valid:",
                buttons=[[Button.inline("❌ Batal", b"admin_billing")]]
            )
            return
        # Hapus state setelah pencarian sukses
        del _login_states[user_id]
        await _show_transaction_detail_message(event, trx)

    elif state == "admin_editing_lpm_desc":
        aid = state_data["target_admin_id"]
        new_desc = text.strip()
        if len(new_desc) > 60:
            await event.respond("❌ **Deskripsi terlalu panjang!** Maksimal 60 karakter.")
            return
        if db_update_admin_lpm_description(aid, new_desc):
            del _login_states[user_id]
            await event.respond(f"✅ **Deskripsi untuk Admin Pool ID `{aid}` berhasil diubah menjadi:**\n`{new_desc}`")
            await _show_ubots(event)
        else:
            await event.respond("❌ Gagal memperbarui deskripsi di database.")

    elif state == "admin_edit_promote_text":
        from src.database import db_save_admin_promote_ad, db_get_admin_promote_ad
        # Ambil buttons_json yang sudah ada agar tidak terhapus
        _, buttons_json = db_get_admin_promote_ad()
        if db_save_admin_promote_ad(text, buttons_json):
            del _login_states[user_id]
            await event.respond("✅ **Teks promosi berhasil diperbarui!**")
            await show_promote_panel(event, edit=False)
        else:
            await event.respond("❌ Gagal menyimpan teks promosi.")

    elif state == "admin_edit_promote_buttons":
        from src.database import db_save_admin_promote_ad, db_get_admin_promote_ad
        content, _ = db_get_admin_promote_ad()
        
        if text.strip() == "-":
            buttons_json = ""
        else:
            # Parse format pipa
            lines = text.strip().split("\n")
            buttons = []
            for line in lines:
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 2:
                    btn_text = parts[0]
                    btn_url = parts[1]
                    if btn_url.startswith("t.me/"):
                        btn_url = "https://" + btn_url
                    buttons.append({"text": btn_text, "url": btn_url})
            import json
            buttons_json = json.dumps(buttons) if buttons else ""
            
        if db_save_admin_promote_ad(content, buttons_json):
            del _login_states[user_id]
            await event.respond("✅ **Tombol promosi berhasil diperbarui!**")
            await show_promote_panel(event, edit=False)
        else:
            await event.respond("❌ Gagal menyimpan tombol promosi.")

    elif state == "admin_mass_interval":
        try:
            iv = float(text)
            if iv <= 0: raise ValueError
        except ValueError:
            await event.respond("❌ Masukkan angka desimal positif. Contoh: `0.5` atau `1` atau `2`")
            return
        from src.database import db_mass_update_subscription_interval
        if db_mass_update_subscription_interval(iv):
            del _login_states[user_id]
            iv_label = f"{int(iv*60)} menit" if iv < 1 else f"{iv} jam"
            await event.respond(
                f"✅ **Interval broadcast seluruh klien diubah ke {iv_label}!**",
                buttons=[[Button.inline("⚡ Pengaturan Massal", b"admin_mass")]]
            )
        else:
            await event.respond("❌ Gagal mengubah interval massal.")

    elif state == "admin_mass_bio":
        if len(text) > 70:
            await event.respond(f"❌ Bio terlalu panjang ({len(text)} karakter). Maksimal 70 karakter.")
            return
        from src.database import db_update_userbot_mass_settings
        if db_update_userbot_mass_settings(custom_bio=text):
            try:
                from src.userbot_manager import update_all_online_userbot_bios
                asyncio.create_task(update_all_online_userbot_bios(text))
            except Exception as e:
                logger.error(f"Gagal update bio online: {e}")
                
            del _login_states[user_id]
            await event.respond(
                f"✅ **Bio Telegram seluruh klien berhasil diubah ke:**\n`{text}`\n\n_Bio akan otomatis diperbarui secara bertahap pada akun klien yang terhubung._",
                buttons=[[Button.inline("⚡ Pengaturan Massal", b"admin_mass")]]
            )
        else:
            await event.respond("❌ Gagal mengubah bio massal.")

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
        [Button.inline("⚡ Pengaturan Massal", b"admin_mass")],
        [Button.inline("⬅️ Menu Utama", b"start")]
    ]
    if hasattr(event, "edit"):
        try:
            await event.edit(text, buttons=buttons); return
        except Exception:
            pass
    await event.respond(text, buttons=buttons)


async def _show_billing_menu(event):
    text = (
        "📋 **MENU BILLING & TRANSAKSI**\n\n"
        "Silakan pilih submenu di bawah untuk mengelola:\n"
        "• **Langganan Aktif**: Kelola lisensi Jaseb & Userbot yang sedang aktif.\n"
        "• **Transaksi Pending**: Lihat & setujui pembayaran (QRIS/Manual) yang belum aktif.\n"
        "• **Cari Transaksi**: Cari detail transaksi/invoice berdasarkan ID (Contoh: `INV-...`)."
    )
    buttons = [
        [Button.inline("👥 Langganan Aktif", b"admin_billing_active"), Button.inline("⏳ Transaksi Pending", b"admin_billing_pending")],
        [Button.inline("🔍 Cari Transaksi", b"admin_billing_search")],
        [Button.inline("⬅️ Panel Admin", b"admin_main")]
    ]
    if hasattr(event, "edit"):
        try:
            await event.edit(text, buttons=buttons); return
        except Exception:
            pass
    await event.respond(text, buttons=buttons)


async def _show_billing_list(event):
    subs = db_get_all_subscriptions_detail(50)
    if not subs:
        buttons = [[Button.inline("⬅️ Kembali", b"admin_billing")]]
        if hasattr(event, "edit"):
            await event.edit("❌ Tidak ada langganan aktif.", buttons=buttons)
        else:
            await event.respond("❌ Tidak ada langganan aktif.", buttons=buttons)
        return

    text = "👥 **LANGGANAN AKTIF (JASEB & USERBOT)**\n\n"
    buttons = []
    for sub in subs:
        uid = sub["user_id"]
        pkg = sub["package_name"]
        end = sub.get("end_date", "")
        end_clean = normalize_end(end)
        if "userbot" in pkg.lower():
            max_ub = sub.get("max_userbots", 1) or 1
            text += f"• 🤖 `{uid}` | {pkg[:20]} | {end_clean[:10]} | {max_ub} Akun\n"
        else:
            cap = sub.get("capacity_lpm", 0)
            iv = sub.get("broadcast_interval_hours", 0.5)
            iv_label = f"{int(iv*60)}m" if iv < 1 else f"{iv}j"
            text += f"• 📢 `{uid}` | {pkg[:20]} | {end_clean[:10]} | {cap}LPM/{iv_label}\n"
        buttons.append([Button.inline(f"🔧 Kelola {uid}", f"bill_detail_{uid}".encode())])

    buttons.append([Button.inline("⬅️ Kembali", b"admin_billing")])
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
    is_ub = "userbot" in pkg.lower()
    end = normalize_end(sub.get("end_date", ""))
    
    if is_ub:
        max_ub = sub.get("max_userbots", 1) or 1
        text = (
            f"🔧 **KELOLA USER `{uid}` (USERBOT)**\n{'━'*22}\n\n"
            f"📦 Paket: **{pkg}**\n"
            f"🤖 Maksimal Akun: **{max_ub} Userbot**\n"
            f"📅 Expired: **{end[:10]}**\n"
        )
        buttons = [
            [Button.inline("📅 Perpanjang", f"bill_extend_{uid}".encode()),
             Button.inline("🚫 Cabut Langganan", f"bill_revoke_{uid}".encode())],
            [Button.inline("⬅️ Kembali", b"admin_billing_active")]
        ]
    else:
        cap = sub.get("capacity_lpm", 0)
        iv = sub.get("broadcast_interval_hours", 0.5)
        iv_label = f"{int(iv*60)} menit" if iv < 1 else f"{iv} jam"
        req_lpm = sub.get("request_lpm") or "(default pool)"
        text = (
            f"🔧 **KELOLA USER `{uid}` (JASEB)**\n{'━'*22}\n\n"
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
            [Button.inline("⬅️ Kembali", b"admin_billing_active")]
        ]
        
    if hasattr(event, "edit"):
        try:
            await event.edit(text, buttons=buttons); return
        except Exception:
            pass
    await event.respond(text, buttons=buttons)


async def _show_pending_transactions(event):
    trxs = db_get_pending_transactions(15)
    if not trxs:
        buttons = [[Button.inline("⬅️ Kembali", b"admin_billing")]]
        if hasattr(event, "edit"):
            await event.edit("❌ Tidak ada transaksi pending saat ini.", buttons=buttons)
        else:
            await event.respond("❌ Tidak ada transaksi pending saat ini.", buttons=buttons)
        return
        
    text = "⏳ **DAFTAR TRANSAKSI PENDING**\n\n"
    buttons = []
    for trx in trxs:
        trx_id = trx["trx_id"]
        pkg = trx["package_id"]
        amt = trx["amount"]
        text += f"• `{trx_id}` | {pkg[:20]} | Rp {amt:,}\n"
        buttons.append([Button.inline(f"⚙️ Kelola {trx_id}", f"trx_manage_{trx_id}".encode())])
        
    buttons.append([Button.inline("⬅️ Kembali", b"admin_billing")])
    if hasattr(event, "edit"):
        try:
            await event.edit(text, buttons=buttons); return
        except Exception:
            pass
    await event.respond(text, buttons=buttons)


async def _show_transaction_detail_message(event, trx: dict):
    trx_id = trx["trx_id"]
    uid = trx["user_id"]
    pkg = trx["package_id"]
    amt = trx["amount"]
    status = trx["status"]
    created_at = trx["created_at"]
    
    # Format created_at to WIB
    try:
        from datetime import datetime, timezone, timedelta
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00").split("+")[0])
        dt_wib = dt.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=7)))
        date_str = dt_wib.strftime("%d/%m/%Y %H:%M WIB")
    except Exception:
        date_str = str(created_at)
        
    text = (
        f"🆔 **DETAIL TRANSAKSI**\n"
        f"{'━'*22}\n\n"
        f"Invoice: `{trx_id}`\n"
        f"User ID: `{uid}`\n"
        f"Paket: **{pkg}**\n"
        f"Nominal: **Rp {amt:,}**\n"
        f"Status: `{status.upper()}`\n"
        f"Tanggal: {date_str}\n"
    )
    
    buttons = []
    if status == "pending":
        buttons.append([
            Button.inline("Approve ✅", f"approve_man_{trx_id}".encode()),
            Button.inline("Reject ❌", f"reject_man_{trx_id}".encode())
        ])
    buttons.append([Button.inline("⬅️ Kembali ke Billing", b"admin_billing")])
    
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
    admins = db_get_admin_userbots()  # Semua admin diurutkan by ID ascending
    from src.database import db_get_lpm_lists_count
    total_lpm = db_get_lpm_lists_count()
    SLOT_SIZE = 100  # Slot LPM per admin (harus konsisten dengan db_get_lpm_sharded_for_admin)

    text = "🤖 **ADMIN POOL — DISTRIBUSI LPM**\n"
    text += f"{'━' * 30}\n\n"
    text += f"📋 Total LPM Pool: **{total_lpm} grup**\n"
    text += f"🤖 Total Admin Terdaftar: **{len(admins)} akun**\n\n"

    buttons = []
    if not admins:
        text += "_Belum ada nomor admin. Gunakan /install untuk menambahkan._\n"
    else:
        for i, (aid, phone, status, cooldown, lpm_description) in enumerate(admins):
            # Hitung slot LPM statis berdasarkan posisi urutan (0-based index = i)
            slot_start = i * SLOT_SIZE + 1
            slot_end   = (i + 1) * SLOT_SIZE
            # Cek apakah slot ini benar-benar ada di pool
            if slot_start > total_lpm:
                slot_label = f"⚠️ #{slot_start}–#{slot_end} _(slot kosong, pool LPM kurang)_"
            elif slot_end > total_lpm:
                actual_end = total_lpm
                slot_label = f"⚠️ #{slot_start}–#{actual_end} _(hanya {actual_end - slot_start + 1} LPM, kurang dari 100)_"
            else:
                slot_label = f"✅ #{slot_start}–#{slot_end} (100 LPM)"

            # Status icon
            icon = "🟢" if status == "connected" else "🔴"
            cd_str = f"\n      ⏸ Cooldown s/d `{cooldown[:10]}`" if cooldown else ""

            text += (
                f"{icon} **Admin #{i+1}** — `{phone}`\n"
                f"      📝 Deskripsi Slot: `{lpm_description}`\n"
                f"      🗂 Jangkauan LPM: {slot_label}{cd_str}\n\n"
            )
            
            row_btns = []
            if status == "connected":
                row_btns.append(Button.inline(f"🔌 DC {phone}", f"admin_dc_pool_{aid}".encode()))
            row_btns.append(Button.inline("📝 Edit Deskripsi", f"admin_edit_desc_{aid}".encode()))
            buttons.append(row_btns)

    # Ringkasan coverage LPM
    if admins:
        covered = min(len(admins) * SLOT_SIZE, total_lpm)
        uncovered = max(0, total_lpm - covered)
        text += f"{'━' * 30}\n"
        text += f"📊 **Coverage:** {covered}/{total_lpm} LPM tercakup\n"
        if uncovered > 0:
            admins_needed = -(-uncovered // SLOT_SIZE)  # ceiling division
            text += f"ℹ️ {uncovered} LPM belum tercakup. Tambah **{admins_needed} admin** lagi untuk full coverage.\n"
        else:
            text += "🎯 Semua LPM telah tercakup oleh admin pool!\n"

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
            phone_clean = phone.replace("+", "")
            text += f"{icon} `{uid}` | {phone} | {status}\n"
            buttons.append([
                Button.inline(f"🔌 DC {phone}", f"cub_dc_{phone_clean}".encode()),
                Button.inline(f"🗑 Del {phone}", f"cub_del_{phone_clean}".encode())
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
