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
    db_get_userbot_status,
    db_redeem_activation_token,
    db_get_auto_replies,
    db_add_auto_reply,
    db_delete_auto_reply,
    db_update_subscription_schedule,
    db_transfer_userbot_session
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

    @bot.on(events.NewMessage(pattern='/panel'))
    async def panel_command_handler(event):
        await show_client_panel(event, edit=False)

    @bot.on(events.NewMessage(pattern='/client'))
    async def client_command_handler(event):
        await show_client_panel(event, edit=False)

    @bot.on(events.CallbackQuery(data=b"client_panel"))
    async def client_panel_callback(event):
        await show_client_panel(event, edit=True)

    @bot.on(events.CallbackQuery(data=b"client_start_share"))
    async def client_start_share_callback(event):
        uid = event.sender_id
        from src.database import db_get_active_subscription_status
        sub = db_get_active_subscription_status(uid)
        if not sub:
            await event.answer("❌ Anda tidak memiliki paket aktif.", alert=True)
            return
            
        from src.main import start_user_broadcast
        await event.answer("🚀 Memulai broadcast iklan jaseb Anda!", alert=True)
        asyncio.create_task(start_user_broadcast(uid))

    @bot.on(events.CallbackQuery(data=b"client_stop_share"))
    async def client_stop_share_callback(event):
        uid = event.sender_id
        from src.logic import active_broadcasts
        active_broadcasts.discard(uid)
        await event.answer("🛑 Broadcast iklan dihentikan.", alert=True)

    @bot.on(events.CallbackQuery(data=b"client_edit_ad"))
    async def client_edit_ad_callback(event):
        uid = event.sender_id
        _login_states[uid] = {"state": "waiting_for_ad"}
        await event.edit("✍️ **Kirim teks/materi jaseb baru Anda sekarang:**\n(Teks, Foto+Caption, atau Forward)")

    @bot.on(events.CallbackQuery(pattern=b"manage_ub_(.+)"))
    async def manage_ub_callback(event):
        phone = event.pattern_match.group(1).decode()
        await show_single_userbot_menu(event, phone)

    @bot.on(events.CallbackQuery(pattern=b"toggle_pm_(.+)"))
    async def toggle_pm_callback(event):
        phone = event.pattern_match.group(1).decode()
        from src.database import db_toggle_pm_permit
        success, new_status = db_toggle_pm_permit(phone)
        if success:
            from src.userbot_manager import update_single_online_userbot_pm_permit
            await update_single_online_userbot_pm_permit(phone, new_status)
            status_text = "diaktifkan" if new_status else "dinonaktifkan"
            await event.answer(f"✅ PM Permit untuk {phone} berhasil {status_text}!", alert=True)
        else:
            await event.answer("❌ Gagal mengubah status PM Permit.", alert=True)
        await show_single_userbot_menu(event, phone)

    @bot.on(events.CallbackQuery(pattern=b"edit_bio_(.+)"))
    async def edit_bio_callback(event):
        phone = event.pattern_match.group(1).decode()
        uid = event.sender_id
        _login_states[uid] = {"state": "waiting_for_bio_input", "phone": phone}
        await event.edit(
            f"✍️ **KUSTOM BIO USERBOT (`{phone}`)**\n\n"
            f"Bio saat ini akan diubah. Kirimkan bio Telegram baru Anda (maksimal 70 karakter):", 
            buttons=[[Button.inline("❌ Batal", f"manage_ub_{phone}".encode())]]
        )

    @bot.on(events.CallbackQuery(pattern=b"conn_toggle_(.+)"))
    async def conn_toggle_callback(event):
        phone = event.pattern_match.group(1).decode()
        from src.database import get_supabase
        supabase = get_supabase()
        res = supabase.table("userbots").select("status, session_name").eq("phone_number", phone).execute()
        if not res.data:
            await event.answer("❌ Data tidak ditemukan.", alert=True)
            return
        
        status = res.data[0]["status"]
        session_name = res.data[0]["session_name"]
        
        if status == "connected":
            from src.userbot_manager import stop_client_userbot
            await stop_client_userbot(phone)
            from src.database import db_update_userbot_status
            db_update_userbot_status(phone, "disconnected")
            await event.answer(f"🔌 Sesi {phone} berhasil diputuskan.", alert=True)
        else:
            # Reconnect
            from src.userbot_manager import start_client_userbot
            await event.answer("⏳ Menghubungkan sesi...", alert=False)
            ok = await start_client_userbot(event.sender_id, session_name, phone)
            if ok:
                await event.answer(f"🟢 Sesi {phone} berhasil dihubungkan kembali!", alert=True)
            else:
                await event.answer(f"❌ Gagal menghubungkan sesi {phone}. Pastikan sesi belum hangus.", alert=True)
        await show_single_userbot_menu(event, phone)

    @bot.on(events.CallbackQuery(pattern=b"del_session_(.+)"))
    async def del_session_callback(event):
        phone = event.pattern_match.group(1).decode()
        
        buttons = [
            [Button.inline("⚠️ Ya, Hapus Permanen!", f"confirm_del_session_{phone}".encode())],
            [Button.inline("❌ Batal", f"manage_ub_{phone}".encode())]
        ]
        await event.edit(
            f"⚠️ **KONFIRMASI HAPUS SESI USERBOT ({phone})**\n\n"
            f"Tindakan ini akan menghentikan userbot secara fisik dari server dan menghapus data sesinya secara permanen.\n"
            f"Ini akan **mengosongkan 1 slot kuota** di paket Anda agar nomor lain bisa didaftarkan.\n\n"
            f"Apakah Anda yakin?",
            buttons=buttons
        )

    @bot.on(events.CallbackQuery(pattern=b"confirm_del_session_(.+)"))
    async def confirm_del_session_callback(event):
        phone = event.pattern_match.group(1).decode()
        from src.userbot_manager import stop_client_userbot
        await stop_client_userbot(phone)
        
        from src.database import db_admin_delete_client_userbot
        ok, session = db_admin_delete_client_userbot(phone)
        if ok:
            if session:
                for ext in [".session", ".session-journal"]:
                    path = f"data/sessions/{session}{ext}"
                    if os.path.exists(path):
                        try: os.remove(path)
                        except: pass
            await event.answer(f"🗑️ Sesi {phone} berhasil dihapus. 1 Slot kuota dibebaskan!", alert=True)
            await show_client_panel(event, edit=True)
        else:
            await event.answer("❌ Gagal menghapus sesi.", alert=True)

    @bot.on(events.CallbackQuery(pattern=b"client_connect_session_(.+)"))
    async def client_connect_session_callback(event):
        uid = event.sender_id
        _login_states[uid] = {"state": "waiting_for_phone"}
        await event.edit("📱 **SAMBUNGKAN USERBOT BARU**\n\nMasukkan nomor HP akun Telegram Anda (+628xxx):", buttons=[[Button.inline("❌ Batal", b"client_panel")]])

    @bot.on(events.CallbackQuery(data=b"client_target_lpm"))
    async def client_target_lpm_callback(event):
        uid = event.sender_id
        _login_states[uid] = {"state": "waiting_for_lpm_request"}
        await event.edit("📋 **TARGET LPM CUSTOM**\n\nKirimkan daftar link grup LPM kustom Anda (satu per baris) atau ketik `/skip` untuk kembali menggunakan LPM bawaan:", buttons=[[Button.inline("❌ Batal", b"client_panel")]])

    @bot.on(events.CallbackQuery(data=b"client_tf_pkg"))
    async def client_tf_pkg_callback(event):
        await event.edit(
            "🚀 **TRANSFER USERBOT**\n\n"
            "Untuk mentransfer userbot beserta sisa paket ke pengguna lain, silakan ketik perintah transfer di kolom chat bot:\n\n"
            "`/transfer <ID_TELEGRAM_TUJUAN>`\n\n"
            "_Contoh: `/transfer 8844645901`_",
            buttons=[[Button.inline("⬅️ Kembali ke Panel", b"client_panel")]]
        )

    @bot.on(events.CallbackQuery(data=b"client_features_geunid"))
    async def client_features_geunid_callback(event):
        await show_features_geunid(event, edit=True)

    @bot.on(events.CallbackQuery(data=b"client_panel_back"))
    async def client_panel_back_callback(event):
        await show_client_panel(event, edit=True)

    @bot.on(events.CallbackQuery(data=b"client_test_spintax"))
    async def client_test_spintax_callback(event):
        uid = event.sender_id
        from src.database import get_supabase
        supabase = get_supabase()
        res_ad = supabase.table("user_ads").select("content").eq("user_id", uid).eq("title", "Iklan Utama").limit(1).execute()
        content = res_ad.data[0].get("content") if res_ad.data else ""
        
        if not content:
            content = "{Halo|Permisi|Selamat pagi} bos, {kapan|hari apa} kita {mulai|sebar} iklan?"
            
        from src.jaseb_engine import resolve_spintax
        result = resolve_spintax(content)
        
        alert_text = (
            "🔄 **HASIL PUTAR SPINTAX INSTAN**\n"
            f"{'━'*30}\n\n"
            f"📝 **Teks Asli:**\n`{content}`\n\n"
            f"🎯 **Hasil Rotasi Acak:**\n`{result}`"
        )
        await event.answer("🔄 Berhasil Memutar Spintax!", alert=True)
        await event.respond(alert_text)

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
    from src.database import db_get_active_subscriptions_of_user, db_get_userbots_by_subscription, db_get_success_forward_logs_count
    subs = db_get_active_subscriptions_of_user(user_id)
    total_sent = db_get_success_forward_logs_count(user_id)

    if not subs:
        text = "📊 **Status Jaseb**\n\n❌ Tidak ada paket aktif."
        buttons = [[Button.inline("⬅️ Kembali", b"start")]]
    else:
        sub_active = subs[0]
        pkg = sub_active["package_name"]
        cap = sub_active["capacity_lpm"]
        end = sub_active["end_date"]
        iv = sub_active["broadcast_interval_hours"]
        max_ub = sub_active.get("max_userbots", 1) or 1
        sub_id = sub_active["id"]
        
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
        
        ub_line = ""
        if "userbot" in pkg.lower():
            ubots = db_get_userbots_by_subscription(sub_id)
            conn_count = len([u for u in ubots if u["status"] == "connected"])
            ub_line = f"\n🤖 Akun Userbot: **{conn_count}/{max_ub} Online**"
            
        text = f"📊 **STATUS JASEB**\n\n📦 Paket: {pkg}\n🎯 LPM: {cap}\n📅 Habis: {end[:10]} ({days} hari lagi)\n⏰ Jadwal: Setiap {iv_label}\n📤 Terkirim: {total_sent} grup{ub_line}"
        buttons = [[Button.inline("🔄 Sebar Ulang", b"resend_jaseb"), Button.inline("✍️ Edit Iklan", b"edit_jaseb_btn")], [Button.inline("⬅️ Kembali", b"start")]]

    if hasattr(event, "edit"):
        try:
            await event.edit(text, buttons=buttons)
            return
        except Exception:
            pass
    await _bot.send_message(event.chat_id, text, buttons=buttons)

def register_edit_jaseb_btn(bot, login_states):
    @bot.on(events.CallbackQuery(data=b"edit_jaseb_btn"))
    async def handler(event):
        uid = int(event.sender_id)
        login_states[uid] = {"state": "waiting_for_ad"}
        await event.edit("✍️ **Kirim teks jaseb baru Anda sekarang:**")

    # ─── FITUR BARU KLIEN ───
    
    @bot.on(events.NewMessage(pattern='/claim'))
    async def claim_token_handler(event):
        text = event.text or ""
        parts = text.split()
        if len(parts) < 2:
            await event.respond("🔑 **KLAIM TOKEN AKTIVASI**\n\nGunakan format: `/claim <KODE_TOKEN>`\n_Contoh: `/claim GEUNID-ABCD-1234`_")
            return
        token = parts[1].strip()
        success, msg = db_redeem_activation_token(token, event.sender_id)
        await event.respond(f"{'✅' if success else '❌'} {msg}")

    @bot.on(events.NewMessage(pattern='/transfer'))
    async def transfer_userbot_handler(event):
        text = event.text or ""
        parts = text.split()
        if len(parts) < 2 or not parts[1].isdigit():
            await event.respond("🚀 **TRANSFER USERBOT**\n\nGunakan format: `/transfer <ID_TELEGRAM_TUJUAN>`\n_Contoh: `/transfer 8844645901`_")
            return
        target_uid = int(parts[1])
        
        buttons = [
            [Button.inline("⚠️ Ya, Transfer Sekarang!", f"confirm_tf_{target_uid}".encode())],
            [Button.inline("❌ Batal", b"start")]
        ]
        await event.respond(
            f"⚠️ **KONFIRMASI TRANSFER USERBOT**\n\n"
            f"Apakah Anda yakin ingin memindahkan userbot dan seluruh sisa paket aktif Anda ke User ID `{target_uid}`?\n"
            f"Tindakan ini **tidak dapat dibatalkan**!",
            buttons=buttons
        )

    @bot.on(events.CallbackQuery(pattern=b"confirm_tf_(.+)"))
    async def confirm_transfer_callback(event):
        target_uid = int(event.pattern_match.group(1).decode())
        success, msg = db_transfer_userbot_session(event.sender_id, target_uid)
        if success:
            from src.userbot_manager import stop_client_userbot
            await stop_client_userbot(event.sender_id)
        await event.edit(f"{'✅' if success else '❌'} {msg}")

    @bot.on(events.NewMessage(pattern='/autoreply'))
    async def autoreply_command_handler(event):
        await _show_autoreply_menu(event)

    @bot.on(events.CallbackQuery(data=b"autoreply_main"))
    async def autoreply_main_callback(event):
        await _show_autoreply_menu(event)

    @bot.on(events.CallbackQuery(data=b"ar_add"))
    async def ar_add_callback(event):
        login_states[event.sender_id] = {"state": "waiting_for_ar_keyword"}
        await event.edit("✍️ **TAMBAH AUTO REPLY**\n\nKetik kata kunci yang ingin ditangkap (contoh: `order`):", buttons=[[Button.inline("❌ Batal", b"autoreply_main")]])

    @bot.on(events.CallbackQuery(pattern=b"ar_del_(.+)"))
    async def ar_del_callback(event):
        reply_id = int(event.pattern_match.group(1).decode())
        if db_delete_auto_reply(event.sender_id, reply_id):
            await event.answer("✅ Auto reply berhasil dihapus.", alert=True)
        else:
            await event.answer("❌ Gagal menghapus.", alert=True)
        await _show_autoreply_menu(event)

    @bot.on(events.NewMessage(pattern='/schedule'))
    async def schedule_command_handler(event):
        await _show_schedule_menu(event)

    @bot.on(events.CallbackQuery(data=b"schedule_main"))
    async def schedule_main_callback(event):
        await _show_schedule_menu(event)

    @bot.on(events.CallbackQuery(data=b"sch_edit"))
    async def sch_edit_callback(event):
        login_states[event.sender_id] = {"state": "waiting_for_schedule_input"}
        await event.edit(
            "⏰ **UBAH JAM OPERASIONAL SEBAR**\n\n"
            "Ketik rentang jam operasional (format: `jam_mulai | jam_selesai` dalam format 24 jam).\n\n"
            "_Contoh:_ `8 | 22` (sebar iklan hanya akan berjalan dari jam 8 pagi sampai jam 10 malam lokal server).",
            buttons=[[Button.inline("❌ Batal", b"schedule_main")]]
        )

async def _show_autoreply_menu(event):
    uid = event.sender_id
    replies = db_get_auto_replies(uid)
    text = "🤖 **MANAJEMEN AUTO REPLY (WTB)**\n\n"
    buttons = []
    
    if not replies:
        text += "❌ Anda belum membuat kata kunci balasan otomatis."
    else:
        text += "Daftar WTB aktif saat ini:\n\n"
        for rep in replies:
            status_emoji = "🟢" if rep["is_active"] else "🔴"
            text += f"{status_emoji} **Kata Kunci:** `{rep['keyword']}`\n💬 **Balasan:** {rep['reply_text'][:50]}...\n\n"
            buttons.append([Button.inline(f"🗑 Hapus '{rep['keyword']}'", f"ar_del_{rep['id']}".encode())])
            
    buttons.append([Button.inline("➕ Tambah Kata Kunci", b"ar_add")])
    buttons.append([Button.inline("⬅️ Kembali", b"start")])
    
    if hasattr(event, "edit"):
        await event.edit(text, buttons=buttons)
    else:
        await _bot.send_message(event.chat_id, text, buttons=buttons)

async def _show_schedule_menu(event):
    uid = event.sender_id
    sub = db_get_active_subscription_status(uid)
    if not sub:
        await event.respond("❌ Anda tidak memiliki paket aktif."); return
        
    from src.database import get_supabase
    supabase = get_supabase()
    res = supabase.table("subscriptions").select("schedule_start_hour, schedule_end_hour").eq("user_id", uid).eq("status", "active").execute()
    start_h, end_h = 0, 23
    if res.data:
        start_h = res.data[0].get("schedule_start_hour", 0)
        end_h = res.data[0].get("schedule_end_hour", 23)
        
    text = (
        "⏰ **JADWAL OPERASIONAL BROADCAST**\n\n"
        f"🟢 Jam Mulai: **{start_h:02d}:00**\n"
        f"🔴 Jam Selesai: **{end_h:02d}:00**\n\n"
        "_Iklan hanya akan disebarkan di dalam rentang waktu operasional di atas._"
    )
    buttons = [
        [Button.inline("✏️ Ubah Jam Operasional", b"sch_edit")],
        [Button.inline("⬅️ Kembali", b"start")]
    ]
    if hasattr(event, "edit"):
        await event.edit(text, buttons=buttons)
    else:
        await _bot.send_message(event.chat_id, text, buttons=buttons)

async def show_client_panel(event, edit=False):
    uid = event.sender_id
    from src.database import db_get_active_subscriptions_of_user, db_get_userbots_by_subscription
    
    subs = db_get_active_subscriptions_of_user(uid)
    
    if not subs:
        text = (
            "👤 **PANEL KONTROL PEMBELI**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "❌ **Anda belum memiliki paket sebar iklan aktif.**\n"
            "Silakan lakukan pembelian paket promosi terlebih dahulu melalui Mini App."
        )
        buttons = [[Button.inline("⬅️ Kembali", b"start")]]
        if edit and hasattr(event, "edit"):
            await event.edit(text, buttons=buttons)
        else:
            await _bot.send_message(event.chat_id, text, buttons=buttons)
        return

    # Ambil paket aktif pertama (biasanya hanya ada 1 paket aktif, atau rendernya per paket)
    sub_active = subs[0]
    sub_id = sub_active["id"]
    pkg = sub_active["package_name"]
    cap = sub_active["capacity_lpm"]
    end = sub_active["end_date"]
    iv = sub_active["broadcast_interval_hours"]
    max_ub = sub_active.get("max_userbots", 1) or 1
    
    # Ambil semua userbot yang terhubung dengan subscription ini
    ubots = db_get_userbots_by_subscription(sub_id)
    
    # Format jeda broadcast
    iv_label = f"{int(iv*60)} menit" if iv < 1 else f"{iv} jam"
    
    text = (
        "👤 **PANEL KONTROL PEMBELI GEUNID**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 Paket Aktif: **{pkg}**\n"
        f"⏰ Jeda Broadcast: **Setiap {iv_label}**\n"
        f"📅 Tanggal Expired: **{end[:10]}**\n"
        f"👥 Akun Terhubung: **{len(ubots)}/{max_ub} Userbot**\n\n"
        "**💡 PANDUAN PANEL KONTROL:**\n"
        "• **✍️ Edit Iklan**: Mengubah materi (teks/foto/forward) iklan yang disebar.\n"
        "• **⏰ Jam Ops (Schedule)**: Membatasi jam broadcast berjalan (misal: 08:00 - 22:00).\n"
        "• **🤖 Auto Reply WTB**: Kata kunci reply otomatis saat ada prospek chat masuk.\n"
        "• **📋 Target LPM**: Menentukan daftar grup LPM target Anda secara kustom.\n"
        "• **🔄 Transfer Paket**: Memindahkan sisa lisensi paket ke User ID lain.\n\n"
        "👇 **DAFTAR USERBOT ANDA** (Klik nomor untuk mengatur PM Permit/Bio/Koneksi):"
    )
    
    buttons = []
    
    # Render tombol userbot yang ada
    for ub in ubots:
        phone = ub["phone_number"]
        status = ub["status"]
        icon = "🟢" if status == "connected" else "🔴"
        buttons.append([Button.inline(f"{icon} {phone} ({status.upper()})", f"manage_ub_{phone}".encode())])
        
    # Render tombol tambah userbot jika slot masih tersedia
    if len(ubots) < max_ub:
        buttons.append([Button.inline("🔌 Sambungkan Userbot Baru", f"client_connect_session_{sub_id}".encode())])
        
    buttons.append([
        Button.inline("✍️ Edit Iklan", b"client_edit_ad"),
        Button.inline("⏰ Jam Ops (Schedule)", b"schedule_main")
    ])
    buttons.append([
        Button.inline("🤖 Auto Reply WTB", b"autoreply_main"),
        Button.inline("📋 Target LPM", b"client_target_lpm")
    ])
    buttons.append([
        Button.inline("🔄 Transfer Paket", b"client_tf_pkg"),
        Button.inline("🏆 Keunggulan GeunID", b"client_features_geunid")
    ])
    buttons.append([Button.inline("⬅️ Kembali ke Status Saya", b"my_status")])
    
    if edit and hasattr(event, "edit"):
        try:
            await event.edit(text, buttons=buttons)
            return
        except Exception:
            pass
    await _bot.send_message(event.chat_id, text, buttons=buttons)

async def show_single_userbot_menu(event, phone: str):
    """Menampilkan detail kontrol dan panduan untuk nomor userbot tertentu."""
    from src.database import get_supabase
    supabase = get_supabase()
    res = supabase.table("userbots").select("status, pm_permit_status, custom_bio").eq("phone_number", phone).execute()
    if not res.data:
        await event.answer("❌ Userbot tidak ditemukan.", alert=True)
        return
        
    r = res.data[0]
    status = r.get("status", "disconnected")
    pm_status = r.get("pm_permit_status", False)
    custom_bio = r.get("custom_bio") or "(belum di-set)"
    
    pm_label = "🟢 Aktif" if pm_status else "🔴 Nonaktif"
    status_icon = "🟢" if status == "connected" else "🔴"
    
    text = (
        f"🤖 **KONTROL USERBOT:** `{phone}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔌 Status Sesi: {status_icon} **{status.capitalize()}**\n"
        f"🛡️ PM Permit (Funnel): **{pm_label}**\n"
        f"✍️ Bio Kustom: `{custom_bio}`\n\n"
        "**💡 PANDUAN MENU KONTROL:**\n"
        "• **🛡️ PM Permit (Funnel)**: Memandu otomatis chat orang asing yang masuk ke PM ubot Anda untuk langsung menuju ke bot utama agar akun aman dari limit/ban.\n"
        "• **✍️ Kustom Bio**: Mengubah teks bio profil akun Telegram userbot ini secara otomatis.\n"
        "• **🔌 Sambung/Putuskan**: Hubungkan kembali sesi jika mati, atau logout secara fisik dari server.\n"
        "• **🗑️ Hapus Sesi (Reset)**: Menghapus data sesi selamanya dari database dan server lokal untuk membebaskan 1 slot kuota ubot agar Anda bisa mendaftarkan nomor HP lainnya."
    )
    
    status_toggle_btn = "🔌 Putuskan Koneksi" if status == "connected" else "🟢 Hubungkan Sesi"
    buttons = [
        [Button.inline("🛡️ PM Permit (Funnel)", f"toggle_pm_{phone}".encode())],
        [Button.inline("✍️ Kustom Bio", f"edit_bio_{phone}".encode())],
        [Button.inline(status_toggle_btn, f"conn_toggle_{phone}".encode()), Button.inline("🗑️ Hapus Sesi (Reset)", f"del_session_{phone}".encode())],
        [Button.inline("⬅️ Kembali ke Panel Utama", b"client_panel")]
    ]
    
    if hasattr(event, "edit"):
        try:
            await event.edit(text, buttons=buttons)
            return
        except Exception:
            pass
    await _bot.send_message(event.chat_id, text, buttons=buttons)

async def show_features_geunid(event, edit=True):
    uid = event.sender_id
    from src.database import get_supabase
    supabase = get_supabase()
    
    # Ambil ad client untuk demo spintax
    res_ad = supabase.table("user_ads").select("content").eq("user_id", uid).eq("title", "Iklan Utama").limit(1).execute()
    ad_content = res_ad.data[0].get("content") if res_ad.data else ""
    
    text = (
        "🏆 **KEUNGGULAN PREMIUM GEUNID JASEB**\n"
        f"{'━'*30}\n\n"
        "1️⃣ **AI Auto-Ban Redirect (Smart Safeguard)**\n"
        "🟢 Status: **Aktif (Siaga)**\n"
        "💡 Sistem memantau respons server Telegram secara real-time. Jika akun mengalami FloodWait (limit), target LPM akan langsung dialihkan ke bot cadangan agar promosi Anda tetap jalan tanpa henti!\n\n"
        "2️⃣ **Humanoid Stealth Delay & Typing Simulator**\n"
        "🟢 Jeda Waktu: **30 - 150 detik (Dinamis)**\n"
        "💡 Userbot kami menirukan perilaku manusia asli dengan mengetik (typing status) selama 2-5 detik sebelum mengirim pesan. Dikombinasikan dengan delay acak dinamis, hal ini meminimalisir risiko ban hingga 99%.\n\n"
        "3️⃣ **Shadow Clone Smart Allocator**\n"
        "🟢 Alokasi LPM: **Bebas Tumpang Tindih**\n"
        "💡 Jika Anda mengaktifkan lebih dari 1 userbot, sistem secara otomatis membagi target LPM agar tidak ada grup yang dikirimi iklan ganda oleh akun berbeda secara bersamaan.\n\n"
        "4️⃣ **AI Smart Wording Spintax Rotator**\n"
        "💡 Putar kata secara otomatis menggunakan format `{pilihan1|pilihan2}` pada iklan Anda untuk mencegah deteksi duplikasi pesan oleh Telegram.\n"
    )
    
    if ad_content:
        text += f"\n📝 **Iklan Anda saat ini:**\n`{ad_content[:100]}...`"
    else:
        text += "\n📝 _Anda belum menyimpan iklan untuk tes spintax._"
        
    buttons = [
        [Button.inline("🔄 Tes Putar Spintax", b"client_test_spintax")],
        [Button.inline("⬅️ Kembali ke Panel", b"client_panel_back")]
    ]
    
    if edit and hasattr(event, "edit"):
        await event.edit(text, buttons=buttons)
    else:
        await _bot.send_message(event.chat_id, text, buttons=buttons)
