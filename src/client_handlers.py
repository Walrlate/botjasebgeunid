"""
client_handlers.py — Semua handler yang diakses oleh CLIENT (bukan admin)
"""

import asyncio
import logging
import os
import re
from datetime import datetime, timezone

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

    @bot.on(events.CallbackQuery(data=b"help_admin_only"))
    async def help_admin_only_callback(event):
        if event.sender_id != ADMIN_ID:
            await event.answer("⛔ Akses ditolak. Hanya Owner.", alert=True)
            return
        await _show_admin_step1_help(event)

    @bot.on(events.CallbackQuery(data=b"help_client_only"))
    async def help_client_only_callback(event): await _show_client_step1_help(event)

    @bot.on(events.CallbackQuery(data=b"help_client_step1"))
    async def help_client_step1_callback(event): await _show_client_step1_help(event)

    @bot.on(events.CallbackQuery(data=b"help_client_step2"))
    async def help_client_step2_callback(event): await _show_client_step2_help(event)

    @bot.on(events.CallbackQuery(data=b"help_client_step3"))
    async def help_client_step3_callback(event): await _show_client_step3_help(event)

    @bot.on(events.CallbackQuery(data=b"help_client_step4"))
    async def help_client_step4_callback(event): await _show_client_step4_help(event)

    @bot.on(events.CallbackQuery(data=b"help_client_step5"))
    async def help_client_step5_callback(event): await _show_client_step5_help(event)

    @bot.on(events.CallbackQuery(data=b"help_admin_step1"))
    async def help_admin_step1_callback(event):
        if event.sender_id != ADMIN_ID:
            await event.answer("⛔ Akses ditolak. Hanya Owner.", alert=True)
            return
        await _show_admin_step1_help(event)

    @bot.on(events.CallbackQuery(data=b"help_admin_step2"))
    async def help_admin_step2_callback(event):
        if event.sender_id != ADMIN_ID:
            await event.answer("⛔ Akses ditolak. Hanya Owner.", alert=True)
            return
        await _show_admin_step2_help(event)

    @bot.on(events.CallbackQuery(data=b"help_admin_step3"))
    async def help_admin_step3_callback(event):
        if event.sender_id != ADMIN_ID:
            await event.answer("⛔ Akses ditolak. Hanya Owner.", alert=True)
            return
        await _show_admin_step3_help(event)

    @bot.on(events.CallbackQuery(data=b"help_admin_step4"))
    async def help_admin_step4_callback(event):
        if event.sender_id != ADMIN_ID:
            await event.answer("⛔ Akses ditolak. Hanya Owner.", alert=True)
            return
        await _show_admin_step4_help(event)

    @bot.on(events.CallbackQuery(data=b"help_admin_step5"))
    async def help_admin_step5_callback(event):
        if event.sender_id != ADMIN_ID:
            await event.answer("⛔ Akses ditolak. Hanya Owner.", alert=True)
            return
        await _show_admin_step5_help(event)

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
        from src.database import db_get_active_subscription_status
        sub = db_get_active_subscription_status(uid)
        if sub and "userbot" in sub[0].lower():
            from src.database import db_get_active_subscriptions_of_user, db_get_userbots_by_subscription
            subs = db_get_active_subscriptions_of_user(uid)
            userbot_sub = next((s for s in subs if "userbot" in s["package_name"].lower()), None)
            if userbot_sub:
                ubots = db_get_userbots_by_subscription(userbot_sub["id"])
                connected_ubots = [u for u in ubots if u["status"] == "connected"]
                if not connected_ubots:
                    await event.answer("❌ Hubungkan userbot Anda terlebih dahulu di Panel sebelum mengedit materi!", alert=True)
                    return
        _login_states[uid] = {"state": "waiting_for_ad"}
        await event.edit("✍️ **Kirim teks/materi jaseb baru Anda sekarang:**\n(Teks, Foto+Caption, atau Forward)", buttons=[[Button.inline("❌ Batal", b"client_panel")]])

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
        logger.info(f"🔑 client_connect_session_callback: set uid={uid} (type={type(uid)}) to waiting_for_phone, _login_states={list(_login_states.keys())}")
        await event.edit(
            "📱 **SAMBUNGKAN USERBOT BARU**\n\n"
            "Silakan ketik nomor HP Anda (+628xxx) untuk login via OTP Telegram.\n\n"
            "💡 **Atau (Rekomendasi jika OTP Gagal/Limit):**\n"
            "Kirimkan berkas `.session` hasil login lokal Anda langsung ke chat ini.\n"
            "_(Nama file harus diawali nomor HP Anda, contoh: `+62895347734300.session`)_\n\n"
            "Untuk membuat file `.session` di komputer Anda, Anda dapat mengunduh dan menjalankan berkas pengaktif sesi lokal `create_user_session.py`.",
            buttons=[[Button.inline("❌ Batal", b"client_panel")]]
        )

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

    @bot.on(events.CallbackQuery(data=b"client_simulator_spintax"))
    async def client_simulator_spintax_callback(event):
        uid = event.sender_id
        _login_states[uid] = {"state": "waiting_for_spintax_sim"}
        text = (
            "⚡ **GEUNID SMART SPINTAX SIMULATOR** ⚡\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Silakan kirimkan teks iklan Anda yang menggunakan format spintax `{kata1|kata2|kata3}` ke chat bot ini sekarang.\n\n"
            "Sistem akan memproses dan menampilkan:\n"
            "1. **5 variasi teks acak** yang dihasilkan secara live.\n"
            "2. **Skor Keunikan (Spintax Uniqueness Score)** iklan Anda.\n"
            "3. Analisis & rekomendasi keamanan anti-spam Telegram.\n\n"
            "**Contoh spintax:**\n"
            "`{Halo|Permisi|Misi} Kak, kami menawarkan {jasa|layanan} sebar iklan kustom.`"
        )
        buttons = [[Button.inline("❌ Batal", b"client_panel")]]
        await event.edit(text, buttons=buttons)

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
        from src.database import db_get_active_subscriptions_of_user, db_get_userbots_by_subscription
        subs = db_get_active_subscriptions_of_user(uid)
        if not subs:
            await event.respond("❌ Anda tidak memiliki paket aktif.")
            return
            
        userbot_sub = next((s for s in subs if "userbot" in s["package_name"].lower()), None)
        if userbot_sub:
            ubots = db_get_userbots_by_subscription(userbot_sub["id"])
            connected_ubots = [u for u in ubots if u["status"] == "connected"]
            if not connected_ubots:
                await event.respond("❌ **Userbot Terputus/Belum Terhubung!**\n\nSilakan sambungkan userbot Anda terlebih dahulu melalui **Panel Kontrol** -> **Sambungkan Userbot** sebelum mengedit iklan.")
                return
                
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
    if event.sender_id == ADMIN_ID:
        await _show_admin_step1_help(event)
    else:
        await _show_client_step1_help(event)

async def _show_admin_help(event):
    if event.sender_id != ADMIN_ID:
        if hasattr(event, "answer"):
            await event.answer("⛔ Akses ditolak. Hanya Owner.", alert=True)
        return

    text = (
        "⚡ **DAFTAR PERINTAH SUPERADMIN**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "• `/admin` - Membuka Panel Admin interaktif (Kelola harga, billing, LPM pool, dll).\n"
        "• `/gentoken` - Cetak voucher aktivasi (kustom durasi/LPM/tipe atau sesuai pricelist).\n"
        "• `/promote` - Kelola iklan & sebar materi promosi resmi GeunID.\n"
        "• `/install` - Sambungkan/install akun userbot baru ke Admin Pool.\n"
        "• `/ubots` - Kelola & monitoring akun di Admin Pool.\n"
        "• `/clientubots` - Kelola & pantau status userbot milik pembeli.\n"
        "• `/billing` - Kelola langganan aktif user (perpanjang, cabut, ubah interval, lpm cap).\n"
        "• `/lpm` - Kelola pool grup LPM (lihat list, tambah, hapus, blacklist).\n"
        "• `/scrape_lpm <@target> [limit]` - Scrape link LPM dari channel target.\n"
        "• `/import_lpm <list>` - Impor massal link LPM dari teks.\n"
        "• `/join_pool` - Sinkronisasi gradual join bertahap untuk semua Admin Pool.\n"
        "• `/setprice` - Kelola & edit harga pricelist secara langsung."
    )
    buttons = [
        [Button.inline("➡️ Lanjut ke Panduan 1", b"help_admin_step1")],
        [Button.inline("⬅️ Kembali ke Start", b"start")]
    ]
    if hasattr(event, "edit"):
        try:
            await event.edit(text, buttons=buttons)
            return
        except Exception:
            pass
    try:
        await event.delete()
    except: pass
    await _bot.send_message(event.chat_id, text, buttons=buttons)

async def _show_client_help(event):
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
    buttons = [
        [KeyboardButtonWebView(text="🚀 Launch GEUNID JASEB", url=url)],
        [Button.inline("📖 Baca Panduan Lengkap", b"help_client_step1")],
        [Button.inline("📊 Status Saya", b"my_status"), Button.inline("⬅️ Kembali ke Start", b"start")]
    ]
    if event.sender_id == ADMIN_ID:
        buttons.insert(2, [Button.inline("⚡ Panduan Admin", b"help_admin_only")])
    
    if hasattr(event, "edit"):
        try:
            await event.edit(text, buttons=buttons)
            return
        except Exception:
            pass
    try:
        await event.delete()
    except: pass
    await _bot.send_message(event.chat_id, text, buttons=buttons)

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
        
        time_left_str = "Tidak diketahui"
        try:
            clean_end = end.replace("T", " ").split(".")[0].split("+")[0].strip()
            end_dt = datetime.strptime(clean_end, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            delta = end_dt - datetime.now(timezone.utc)
            
            if delta.total_seconds() <= 0:
                time_left_str = "Kedaluwarsa"
            elif delta.days > 0:
                time_left_str = f"{delta.days} hari lagi"
            else:
                hours_left = int(delta.total_seconds() // 3600)
                mins_left = int((delta.total_seconds() % 3600) // 60)
                if hours_left > 0:
                    time_left_str = f"{hours_left} jam {mins_left} menit lagi"
                else:
                    time_left_str = f"{mins_left} menit lagi"
        except Exception as e:
            logger.error(f"Gagal memformat sisa waktu trial: {e}")
            time_left_str = "Tidak diketahui"
                
        iv_label = f"{int(iv*60)}m" if iv < 1 else f"{iv}j"
        
        ub_line = ""
        if "userbot" in pkg.lower():
            ubots = db_get_userbots_by_subscription(sub_id)
            conn_count = len([u for u in ubots if u["status"] == "connected"])
            ub_line = f"\n🤖 Akun Userbot: **{conn_count}/{max_ub} Online**"
            
        text = f"📊 **STATUS JASEB**\n\n📦 Paket: {pkg}\n🎯 LPM: {cap}\n📅 Habis: {end[:16]} ({time_left_str})\n⏰ Jadwal: Setiap {iv_label}\n📤 Terkirim: {total_sent} grup{ub_line}"
        buttons = [[Button.inline("🔄 Sebar Ulang", b"resend_jaseb"), Button.inline("✍️ Edit Jaseb", b"edit_jaseb_btn")], [Button.inline("⬅️ Kembali", b"start")]]

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
        from src.database import db_get_active_subscriptions_of_user, db_get_userbots_by_subscription
        subs = db_get_active_subscriptions_of_user(uid)
        userbot_sub = next((s for s in subs if "userbot" in s["package_name"].lower()), None)
        if userbot_sub:
            ubots = db_get_userbots_by_subscription(userbot_sub["id"])
            connected_ubots = [u for u in ubots if u["status"] == "connected"]
            if not connected_ubots:
                await event.answer("❌ Sambungkan userbot terlebih dahulu!", alert=True)
                await event.respond("❌ **Userbot Terputus/Belum Terhubung!**\n\nSilakan sambungkan userbot Anda terlebih dahulu melalui **Panel Kontrol** -> **Sambungkan Userbot** sebelum mengedit iklan.")
                return
                
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

    @bot.on(events.NewMessage(pattern='/claimtrial'))
    async def claim_free_trial_handler(event):
        uid = event.sender_id
        from src.database import db_has_user_claimed_trial, db_add_subscription
        from datetime import datetime, timedelta, timezone
        
        if db_has_user_claimed_trial(uid):
            await event.respond(
                "❌ **BATAS KLAIM TERCAPAI**\n\n"
                "Anda sudah pernah menggunakan paket Trial gratis sebelumnya. "
                "Paket Trial hanya dapat diklaim **1 kali** per akun Telegram."
            )
            return
            
        start_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        end_date = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        
        success = db_add_subscription(
            user_id=uid,
            package_name="Trial Userbot",
            capacity_lpm=20,
            start_date=start_date,
            end_date=end_date
        )
        
        if success:
            await event.respond(
                "✅ **TRIAL USERBOT AKTIF!**\n\n"
                "Selamat! Paket **Trial Userbot (1 Hari, 20 LPM)** berhasil diaktifkan secara gratis untuk akun Anda.\n\n"
                "Silakan buka Mini App untuk mengaitkan akun Telegram Anda dan mulai menyebarkan promosi!"
            )
        else:
            await event.respond("❌ Gagal mengaktifkan paket trial. Silakan hubungi admin.")

    @bot.on(events.CallbackQuery(data=b"claim_token_menu"))
    async def claim_token_menu_callback(event):
        uid = event.sender_id
        login_states[uid] = {"state": "waiting_for_claim_token"}
        await event.edit(
            "🔑 **KLAIM TOKEN AKTIVASI**\n\n"
            "Silakan kirimkan kode token aktivasi Anda langsung ke chat ini:\n"
            "_(Contoh: `GEUNID-ABCD-1234`)_\n\n"
            "Atau Anda bisa menggunakan format: `/claim <KODE_TOKEN>`",
            buttons=[[Button.inline("❌ Batal", b"start")]]
        )

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
        
        from src.database import get_supabase
        from src.userbot_manager import stop_client_userbot
        
        phone_number = None
        try:
            supabase = get_supabase()
            res_ub = supabase.table("userbots").select("phone_number").eq("user_id", event.sender_id).execute()
            if res_ub.data:
                phone_number = res_ub.data[0]["phone_number"]
        except Exception as e:
            logger.error(f"Gagal mendapatkan nomor HP untuk transfer: {e}")
            
        if phone_number:
            logger.info(f"Menghentikan userbot {phone_number} sebelum transfer...")
            await stop_client_userbot(phone_number)
            
        success, msg = db_transfer_userbot_session(event.sender_id, target_uid)
        await event.edit(f"{'✅' if success else '❌'} {msg}")
        
        if success and phone_number:
            try:
                from src.userbot_manager import start_client_userbot
                phone_clean = phone_number.replace("+", "").replace(" ", "")
                session_name = f"user_{phone_clean}"
                import asyncio
                asyncio.create_task(start_client_userbot(target_uid, session_name, phone_number))
                logger.info(f"Userbot {phone_number} berhasil dinyalakan untuk pemilik baru {target_uid} secara realtime.")
            except Exception as start_err:
                logger.error(f"Gagal menyalakan userbot client hasil transfer secara realtime: {start_err}")

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
        text = (
            "⏰ **UBAH JAM OPERASIONAL SEBAR**\n\n"
            "Silakan pilih opsi rentang jam operasional di bawah ini secara instan, atau pilih Kustom untuk mengetik manual:"
        )
        buttons = [
            [Button.inline("🕒 24 Jam Penuh (00:00 - 23:00)", b"sch_set_24")],
            [Button.inline("💼 Jam Kerja (08:00 - 17:00)", b"sch_set_office")],
            [Button.inline("☀️ Pagi - Malam (08:00 - 22:00)", b"sch_set_day")],
            [Button.inline("🌙 Siang - Tengah Malam (12:00 - 23:00)", b"sch_set_night")],
            [Button.inline("✏️ Kustom Jam (Ketik Manual)", b"sch_set_custom")],
            [Button.inline("❌ Batal", b"schedule_main")]
        ]
        await event.edit(text, buttons=buttons)

    @bot.on(events.CallbackQuery(pattern=b"sch_set_(.+)"))
    async def sch_set_preset_callback(event):
        preset = event.pattern_match.group(1).decode()
        uid = event.sender_id
        from src.database import db_update_subscription_schedule
        
        if preset == "24":
            start_h, end_h = 0, 23
        elif preset == "office":
            start_h, end_h = 8, 17
        elif preset == "day":
            start_h, end_h = 8, 22
        elif preset == "night":
            start_h, end_h = 12, 23
        elif preset == "custom":
            login_states[event.sender_id] = {"state": "waiting_for_schedule_input"}
            await event.edit(
                "⏰ **UBAH JAM OPERASIONAL (KUSTOM)**\n\n"
                "Ketik rentang jam operasional (format: `jam_mulai | jam_selesai` dalam format 24 jam).\n\n"
                "_Contoh:_ `8 | 22` (sebar iklan dari jam 8 pagi s/d jam 10 malam).",
                buttons=[[Button.inline("❌ Batal", b"sch_edit")]]
            )
            return
        else:
            await event.answer("❌ Opsi tidak valid.", alert=True)
            return
            
        if db_update_subscription_schedule(uid, start_h, end_h):
            await event.answer("✅ Jam operasional berhasil diperbarui!", alert=True)
        else:
            await event.answer("❌ Gagal menyimpan ke database.", alert=True)
        await _show_schedule_menu(event)

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
        "👤 𝖯𝖠𝖭𝖤𝖫 𝖪𝖮𝖭𝖳𝖱𝖮𝖫 𝖯𝖤𝖬𝖡𝖤𝖫𝖨 𝖦𝖤𝖴𝖭𝖨𝖣\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 Paket : **{pkg}**\n"
        f"⏰ Jeda  : **Setiap {iv_label}**\n"
        f"⏳ Exp   : **{end[:10]}**\n"
        f"👥 Slot  : **{len(ubots)}/{max_ub} Userbot**\n\n"
        "💡 𝖥𝖨𝖳𝖴𝖱 𝖯𝖠𝖭𝖤𝖫:\n"
        "• ✍️ **Edit Jaseb** — Atur materi promosi\n"
        "• ⏰ **Jam Ops** — Batasi jam broadcast aktif\n"
        "• 🤖 **Auto Reply** — Balas chat masuk otomatis\n"
        "• 📋 **Target LPM** — Atur target grup kustom\n"
        "• 🔄 **Transfer** — Kirim paket ke user lain\n\n"
        "👇 𝖣𝖠𝖥𝖳𝖠𝖱 𝖴𝖲𝖤𝖱𝖡𝖮𝖳 (Klik nomor di bawah):"
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
        Button.inline("✍️ Edit Jaseb", b"client_edit_ad"),
        Button.inline("⏰ Jam Ops (Schedule)", b"schedule_main")
    ])
    buttons.append([
        Button.inline("🤖 Auto Reply WTB", b"autoreply_main"),
        Button.inline("📋 Target LPM", b"client_target_lpm")
    ])
    buttons.append([
        Button.inline("🔄 Transfer Paket", b"client_tf_pkg"),
        Button.inline("⚡ Simulator Spintax", b"client_simulator_spintax")
    ])
    buttons.append([
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
    try:
        res = supabase.table("userbots").select("status, pm_permit_status, custom_bio").eq("phone_number", phone).execute()
        if not res.data:
            await event.answer("❌ Userbot tidak ditemukan.", alert=True)
            return
        r = res.data[0]
        status = r.get("status", "disconnected")
        pm_status = r.get("pm_permit_status", False)
        custom_bio = r.get("custom_bio") or "(belum di-set)"
    except Exception as e_select:
        logger.warning(f"Gagal select status/pm_permit_status/custom_bio untuk {phone}: {e_select}. Menggunakan fallback.")
        res = supabase.table("userbots").select("status").eq("phone_number", phone).execute()
        if not res.data:
            await event.answer("❌ Userbot tidak ditemukan.", alert=True)
            return
        r = res.data[0]
        status = r.get("status", "disconnected")
        pm_status = False
        custom_bio = "(belum di-set/kolom DB belum ada)"
    
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
        "1️⃣ **Auto-Ban Redirect & Smart Safeguard**\n"
        "🟢 Status: **Aktif (Siaga)**\n"
        "💡 Sistem memantau respons server Telegram secara real-time. Jika akun mengalami FloodWait (limit), target LPM akan langsung dialihkan ke bot cadangan agar promosi Anda tetap jalan tanpa henti!\n\n"
        "2️⃣ **Humanoid Stealth Delay & Typing Simulator**\n"
        "🟢 Jeda Waktu: **30 - 150 detik (Dinamis)**\n"
        "💡 Userbot kami menirukan perilaku manusia asli dengan mengetik (typing status) selama 2-5 detik sebelum mengirim pesan. Dikombinasikan dengan delay acak dinamis, hal ini meminimalisir risiko ban hingga 99%.\n\n"
        "3️⃣ **Shadow Clone Smart Allocator**\n"
        "🟢 Alokasi LPM: **Bebas Tumpang Tindih**\n"
        "💡 Jika Anda mengaktifkan lebih dari 1 userbot, sistem secara otomatis membagi target LPM agar tidak ada grup yang dikirimi iklan ganda oleh akun berbeda secara bersamaan.\n\n"
        "4️⃣ **Smart Wording Spintax Rotator**\n"
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


# ─────────────────────────────────────────
# DETIL SUB-PANDUAN KLIEN
# ─────────────────────────────────────────

async def _show_client_step1_help(event):
    text = (
        "📱 **PANDUAN 1: AKTIVASI & SAMBUNG USERBOT**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣ **Aktivasi Paket**\n"
        "• Buka menu utama dan klik **Launch GEUNID JASEB**.\n"
        "• Pilih paket yang Anda inginkan (Regular / Forward / Userbot).\n"
        "• Selesaikan pembayaran otomatis via QRIS (aktif seketika) atau secara manual. Kirim foto bukti transfer ke bot untuk verifikasi admin.\n\n"
        "2️⃣ **Menghubungkan Akun (Khusus Paket Userbot)**\n"
        "• Setelah paket aktif, masuk to **Panel Kontrol** -> **Hubungkan Userbot**.\n"
        "• Masukkan nomor HP akun Telegram Anda dengan kode negara.\n"
        "  *Contoh:* `+628123456789`\n"
        "• Masukkan 5 digit kode OTP resmi dari Telegram yang dikirim ke aplikasi Telegram Anda.\n"
        "• Jika akun Anda dilindungi Verifikasi 2-Langkah (2FA), masukkan password Anda saat diminta bot.\n"
        "• Akun Anda berhasil online di server!"
    )
    buttons = [[Button.inline("➡️ Lanjut ke Panduan 2", b"help_client_step2")], [Button.inline("⬅️ Kembali ke Start", b"start")]]
    await event.edit(text, buttons=buttons)

async def _show_client_step2_help(event):
    text = (
        "✍️ **PANDUAN 2: MATERI IKLAN & SMART SPINTAX**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣ **Mengatur Materi Iklan**\n"
        "• Masuk to **Panel Kontrol** -> **Edit Iklan**, atau gunakan command `/edit_jaseb`.\n"
        "• **Paket Regular**: Kirim materi berupa teks biasa atau foto + teks.\n"
        "• **Paket Forward**: Kirim iklan dengan cara **Forward (teruskan)** pesan asli dari channel/grup lain. Cocok untuk mempertahankan format tombol link, media, atau format teks asli.\n\n"
        "2️⃣ **Fitur Spintax Rotator (Anti-Spam)**\n"
        "• Gunakan format `{pilihan1|pilihan2|pilihan3}` agar kata-kata dalam iklan Anda diputar secara otomatis di setiap grup LPM.\n"
        "• *Contoh:* `{Halo|Permisi} Kak, kami menawarkan {jasa|layanan} sebar iklan...`\n"
        "• Setiap grup akan menerima variasi teks yang unik sehingga akun Anda aman dari deteksi spam Telegram."
    )
    buttons = [
        [Button.inline("⬅️ Panduan 1", b"help_client_step1"), Button.inline("➡️ Panduan 3", b"help_client_step3")],
        [Button.inline("⬅️ Kembali ke Start", b"start")]
    ]
    await event.edit(text, buttons=buttons)

async def _show_client_step3_help(event):
    text = (
        "📋 **PANDUAN 3: LPM CUSTOM & JADWAL OPERASIONAL**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣ **Mengatur Target LPM Custom**\n"
        "• Secara default, iklan disebarkan ke ratusan grup LPM bawaan pool bot.\n"
        "• Jika ingin memakai grup target sendiri, masuk to **Panel Kontrol** -> **Target LPM**.\n"
        "• Kirimkan daftar link/username grup target Anda (satu per baris).\n"
        "  *Contoh:*\n"
        "  `https://t.me/grupjual1`\n"
        "  `@grupjual2`\n"
        "• Ketik `/skip` atau kosongkan jika ingin kembali memakai LPM bawaan pool bot.\n\n"
        "2️⃣ **Jadwal Operasional (Schedule)**\n"
        "• Batasi jam aktif sebar iklan agar bot tidak mengirim pesan di tengah malam.\n"
        "• Masuk to **Panel Kontrol** -> **Jam Ops (Schedule)**.\n"
        "• Ketik rentang jam dengan format `jam_mulai | jam_selesai`.\n"
        "  *Contoh:* `8 | 22` (sebar iklan hanya berjalan dari pukul 08.00 pagi sampai 22.00 malam waktu server)."
    )
    buttons = [
        [Button.inline("⬅️ Panduan 2", b"help_client_step2"), Button.inline("➡️ Panduan 4", b"help_client_step4")],
        [Button.inline("⬅️ Kembali ke Start", b"start")]
    ]
    await event.edit(text, buttons=buttons)

async def _show_client_step4_help(event):
    text = (
        "🛡️ **PANDUAN 4: AUTO REPLY & PM PERMIT**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣ **Auto Reply WTB (WTB Funnel)**\n"
        "• Membalas chat masuk secara otomatis berdasarkan kata kunci tertentu.\n"
        "• Gunakan command `/autoreply` -> klik **Tambah Kata Kunci**.\n"
        "• Masukkan kata kunci (misal: `order`) lalu masukkan teks balasan (misal: `Halo! Hubungi admin di @Geun_ID`).\n\n"
        "2️⃣ **PM Permit (Funnel Pengaman)**\n"
        "• Mengamankan akun userbot Anda dengan memandu otomatis chat masuk orang asing ke PM agar menuju ke bot utama. Ini mencegah akun Anda dilaporkan sebagai spam.\n"
        "• Aktifkan/nonaktifkan via **Panel Kontrol** -> klik nomor HP -> klik **PM Permit**.\n\n"
        "3️⃣ **Kustom Bio & Transfer Paket**\n"
        "• **Kustom Bio**: Ganti bio akun userbot Anda secara otomatis langsung lewat bot. Maksimal 70 karakter.\n"
        "• **Transfer Paket**: Pindahkan sisa lisensi paket beserta sesi userbot aktif ke User ID Telegram lain. Gunakan format: `/transfer <ID_TUJUAN>` (contoh: `/transfer 8844645901`)."
    )
    buttons = [
        [Button.inline("⬅️ Panduan 3", b"help_client_step3"), Button.inline("➡️ Panduan 5", b"help_client_step5")],
        [Button.inline("⬅️ Kembali ke Start", b"start")]
    ]
    await event.edit(text, buttons=buttons)

async def show_features_geunid(event, edit=True):
    uid = event.sender_id
    from src.database import get_supabase, db_get_user_loyalty
    
    # Ambil data loyalty user
    loy_data = db_get_user_loyalty(uid)
    points = loy_data.get("points", 0)
    tier = loy_data.get("tier", "bronze").upper()
    discount = loy_data.get("discount_percent", 0)
    
    # Ambil ad client untuk info iklan
    supabase = get_supabase()
    res_ad = supabase.table("user_ads").select("content").eq("user_id", uid).eq("title", "Iklan Utama").limit(1).execute()
    ad_content = res_ad.data[0].get("content") if res_ad.data else ""
    
    tier_icons = {"BRONZE": "🥉", "SILVER": "🥈", "GOLD": "🥇", "LOYALTY": "💎"}
    tier_icon = tier_icons.get(tier, "🏆")

    text = (
        "🏆 **KEUNGGULAN PREMIUM GEUNID JASEB**\n"
        f"{'━'*30}\n\n"
        "1️⃣ **Auto-Ban Redirect & Smart Safeguard**\n"
        "🟢 Status: **Aktif (Siaga)**\n"
        "💡 Sistem memantau respons server Telegram secara real-time. Jika akun mengalami FloodWait (limit), target LPM akan langsung dialihkan ke bot cadangan agar promosi Anda tetap jalan tanpa henti!\n\n"
        "2️⃣ **Humanoid Stealth Delay & Typing Simulator**\n"
        "🟢 Jeda Waktu: **30 - 150 detik (Dinamis)**\n"
        "💡 Userbot kami menirukan perilaku manusia asli dengan mengetik (typing status) selama 2-5 detik sebelum mengirim pesan. Jeda acak dinamis meminimalisir risiko ban hingga 99%.\n\n"
        "3️⃣ **Shadow Clone Smart Allocator**\n"
        "🟢 Alokasi LPM: **Bebas Tumpang Tindih**\n"
        "💡 Jika Anda mengaktifkan lebih dari 1 userbot, sistem otomatis membagi target LPM agar tidak ada grup yang dikirimi iklan ganda oleh akun berbeda secara bersamaan.\n\n"
        "4️⃣ **Points & Tier Loyalty System (Sistem Loyalitas) — [NEW]**\n"
        f"🟢 Status: **{tier_icon} {tier} ({points:,} Poin - Diskon {discount}%)**\n"
        "💡 Fitur loyalitas eksklusif GeunID! Dapatkan poin belanja (Rp 100 = 1 poin), streak bonus 2x lipat (belanja dalam 35 hari), dan rating bonus +50 poin. Tier Anda permanen memberikan diskon hingga 15% otomatis saat checkout di Mini App!\n\n"
        "5️⃣ **Smart Wording Spintax Rotator**\n"
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

async def _show_client_step5_help(event):
    text = (
        "🏆 **PANDUAN 5: SISTEM LOYALTY & TIER POIN**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "GeunID menghargai setiap pembelian Anda. Dapatkan poin otomatis dari setiap transaksi sukses dan naikkan tier Anda untuk diskon belanja permanen!\n\n"
        "📈 **Daftar Tingkatan Tier & Keuntungan:**\n"
        "• 🥉 **Bronze Member** (0 - 499 Poin)\n"
        "  - Diskon: 0%\n"
        "  - Badge keren di profil Mini App Anda.\n\n"
        "• 🥈 **Silver Member** (500 - 1.499 Poin)\n"
        "  - Diskon: **5% otomatis** untuk semua pembelian paket!\n\n"
        "• 🥇 **Gold Member** (1.500 - 4.999 Poin)\n"
        "  - Diskon: **10% otomatis** untuk semua pembelian paket!\n\n"
        "• 💎 **Loyalty Member** (5.000+ Poin)\n"
        "  - Diskon: **15% otomatis** (Maksimal diskon) untuk semua paket!\n"
        "  - Efek badge animasi berputar & glowing premium di Mini App Anda!\n\n"
        "🪙 **Cara Mengumpulkan Poin:**\n"
        "1. **Pembelian Paket**: Setiap **Rp 100** belanja sukses = **1 Poin** (contoh: beli paket Rp 7.500 dapat 75 poin).\n"
        "2. **Streak Pembelian (2x Poin)**: Beli/perpanjang paket dalam **35 hari** terakhir untuk mengaktifkan streak, poin yang didapatkan dari pembelian dikalikan 2! (contoh: paket Rp 7.500 jadi 150 poin).\n"
        "3. **Rating Bonus (+50 Poin)**: Berikan rating **5 Bintang ⭐⭐⭐⭐⭐** setelah aktivasi paket selesai untuk klaim instan bonus 50 poin.\n\n"
        "ℹ️ *Diskon tier loyalitas akan langsung memotong harga paket Anda secara otomatis saat checkout di Mini App.*"
    )
    buttons = [
        [Button.inline("⬅️ Panduan 4", b"help_client_step4")],
        [Button.inline("⬅️ Kembali ke Start", b"start")]
    ]
    await event.edit(text, buttons=buttons)

# ─────────────────────────────────────────
# DETIL SUB-PANDUAN ADMIN
# ─────────────────────────────────────────

async def _show_admin_step1_help(event):
    if event.sender_id != ADMIN_ID:
        if hasattr(event, "answer"):
            await event.answer("⛔ Akses ditolak. Hanya Owner.", alert=True)
        return

    text = (
        "🔑 **ADMIN 1: CETAK TOKEN & EDIT HARGA**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣ **Cetak Voucher / Token Aktivasi**\n"
        "• Gunakan command `/gentoken` untuk mencetak kode aktivasi bagi pembeli.\n"
        "• **Format Pricelist (Paket Terdaftar):**\n"
        "  `/gentoken <paket_id> [jumlah]`\n"
        "  *Contoh:* `/gentoken reg_20_3d 5` (mencetak 5 voucher paket regular 20 LPM 3 Hari).\n"
        "• **Format Kustom / Trial Bebas:**\n"
        "  `/gentoken <tipe_paket> <durasi> <kapasitas_lpm> [jumlah]`\n"
        "  *Suffix Durasi:* `d` (hari), `h` (jam).\n"
        "  *Contoh:* `/gentoken regular 12h 35 2` (mencetak 2 voucher regular kustom, 12 Jam, 35 LPM).\n"
        "  *Contoh Trial Userbot:* `/gentoken userbot 2h 0 1` (mencetak 1 voucher trial userbot, 2 Jam, 0 LPM).\n\n"
        "2️⃣ **Mengatur Harga Pricelist**\n"
        "• Gunakan command `/setprice` untuk mengubah daftar harga paket di Mini App secara interaktif. Anda dapat mengedit harga promo, harga asli, durasi, LPM, dan bonus paket."
    )
    buttons = [[Button.inline("➡️ Lanjut ke Panduan 2", b"help_admin_step2")], [Button.inline("⬅️ Kembali ke Start", b"start")]]
    await event.edit(text, buttons=buttons)

async def _show_admin_step2_help(event):
    if event.sender_id != ADMIN_ID:
        if hasattr(event, "answer"):
            await event.answer("⛔ Akses ditolak. Hanya Owner.", alert=True)
        return

    text = (
        "🤖 **ADMIN 2: MANAJEMEN POOL & USERBOT KLIEN**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣ **Instalasi Pool Admin Userbot**\n"
        "• Sambungkan akun Telegram baru ke pool bot admin menggunakan command `/install`.\n"
        "• Masukkan nomor HP pool admin (`+628xxx`), masukkan OTP, dan masukkan password 2FA (jika ada). Akun ini akan digunakan untuk menyebarkan iklan paket Regular/Forward milik pembeli.\n\n"
        "2️⃣ **Kelola Pool Admin (`/ubots`)**\n"
        "• Buka menu `/ubots` untuk memantau status online/offline akun pool admin.\n"
        "• Anda dapat mengubah deskripsi slot LPM (misal: \"Khusus Grup Crypto\") atau memutuskan koneksi (`DC`) akun pool admin dari server.\n\n"
        "3️⃣ **Kelola Userbot Pembeli (`/clientubots`)**\n"
        "• Buka menu `/clientubots` untuk memantau userbot milik pembeli yang aktif.\n"
        "• Anda dapat memaksa disconnect (`DC`) nomor tertentu atau menghapus sesi secara permanen (`Reset`) guna membebaskan kuota slot paket pembeli."
    )
    buttons = [
        [Button.inline("⬅️ Panduan 1", b"help_admin_step1"), Button.inline("➡️ Panduan 3", b"help_admin_step3")],
        [Button.inline("⬅️ Kembali ke Start", b"start")]
    ]
    await event.edit(text, buttons=buttons)

async def _show_admin_step3_help(event):
    if event.sender_id != ADMIN_ID:
        if hasattr(event, "answer"):
            await event.answer("⛔ Akses ditolak. Hanya Owner.", alert=True)
        return

    text = (
        "📋 **ADMIN 3: MANAJEMEN LPM POOL & SCRAPER**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣ **Scrape LPM Massal (`/scrape_lpm`)**\n"
        "• Ekstrak link grup LPM secara otomatis dari channel/grup referensi ke dalam database pool.\n"
        "• Format: `/scrape_lpm <@username_target> [limit]`\n"
        "  *Contoh:* `/scrape_lpm @LPMSharingChannel 150` (mengambil hingga 150 link grup dari channel tersebut).\n\n"
        "2️⃣ **Impor LPM Massal (`/import_lpm`)**\n"
        "• Memasukkan daftar link LPM dari teks mentah ke database.\n"
        "• Format: `/import_lpm <teks_daftar_link>`\n"
        "  *Contoh:* `/import_lpm @lpm1 @lpm2 https://t.me/lpm3`\n\n"
        "3️⃣ **Kelola LPM Pool (`/lpm`)**\n"
        "• Buka menu `/lpm` untuk memantau total grup LPM, menambah link satu per satu, mengedit nama grup & jumlah member, atau mem-blacklist grup mati.\n\n"
        "4️⃣ **Gradual Join (`/join_pool`)**\n"
        "• Memerintahkan seluruh akun pool admin untuk bergabung ke grup-grup LPM baru di database secara bertahap (gradual) guna menghindari deteksi spam dan ban dari Telegram."
    )
    buttons = [
        [Button.inline("⬅️ Panduan 2", b"help_admin_step2"), Button.inline("➡️ Panduan 4", b"help_admin_step4")],
        [Button.inline("⬅️ Kembali ke Start", b"start")]
    ]
    await event.edit(text, buttons=buttons)

async def _show_admin_step4_help(event):
    if event.sender_id != ADMIN_ID:
        if hasattr(event, "answer"):
            await event.answer("⛔ Akses ditolak. Hanya Owner.", alert=True)
        return

    text = (
        "📤 **ADMIN 4: KELOLA BILLING & PROMOSI ADMIN**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣ **Manajemen Billing Klien (`/billing`)**\n"
        "• Cari dan pilih User ID aktif untuk melakukan tindakan:\n"
        "  - **Perpanjang**: Menambah durasi aktif langganan klien (dalam hari).\n"
        "  - **Ubah Jeda**: Mengubah interval waktu broadcast klien (misal dari 0.5 jam menjadi 2 jam).\n"
        "  - **Ubah LPM**: Mengubah kapasitas batas LPM klien.\n"
        "  - **Cabut Paket**: Memaksa masa aktif berakhir seketika.\n\n"
        "2️⃣ **Materi Promosi Admin (`/promote`)**\n"
        "• Kelola sebar materi promosi resmi milik GeunID ke seluruh database grup LPM.\n"
        "• Masuk ke `/promote` untuk:\n"
        "  - **Edit Teks**: Mengubah materi iklan promosi admin (HTML didukung).\n"
        "  - **Edit Tombol**: Mengubah tombol inline link (format: `Teks | URL`).\n"
        "  - **Mulai/Hentikan**: Menjalankan atau menghentikan sebar iklan promosi admin secara massal."
    )
    buttons = [
        [Button.inline("⬅️ Panduan 3", b"help_admin_step3"), Button.inline("➡️ Panduan 5", b"help_admin_step5")],
        [Button.inline("⬅️ Kembali ke Start", b"start")]
    ]
    await event.edit(text, buttons=buttons)

async def _show_admin_step5_help(event):
    if event.sender_id != ADMIN_ID:
        if hasattr(event, "answer"):
            await event.answer("⛔ Akses ditolak. Hanya Owner.", alert=True)
        return

    text = (
        "💎 **ADMIN 5: TEKNIS DATABASE & SISTEM LOYALITAS**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Sistem Loyalitas diatur sepenuhnya via database Supabase PostgreSQL. Berikut adalah struktur, aturan kalkulasi, dan manajemen manual:\n\n"
        "📊 **Kolom Tabel `users` di Database:**\n"
        "• `loyalty_points` (INTEGER): Jumlah total poin terkumpul saat ini.\n"
        "• `loyalty_tier` (TEXT): Tier user aktif (`bronze`, `silver`, `gold`, `loyalty`).\n"
        "• `purchase_streak` (INTEGER): Jumlah transaksi berturut-turut yang memenuhi syarat.\n"
        "• `last_purchase_at` (TIMESTAMPTZ): Waktu transaksi sukses terakhir.\n\n"
        "⚙️ **Aturan Penghitungan Poin:**\n"
        "• **Base Points**: `amount // 100` (Rp 100 = 1 poin). Dihitung dari nominal tagihan akhir.\n"
        "• **Multiplier Streak (x2)**: Jika `last_purchase_at` tidak kosong dan selisihnya dengan waktu transaksi baru `≤ 35 hari`, maka `is_streak = True` → `points_earned = base_points * 2`, dan streak bertambah 1. Jika tidak, streak di-reset ke 1.\n"
        "• **Rating Bonus**: Jika pembeli mengirim feedback rating 5 bintang, fungsi backend `db_add_rating_bonus_points(user_id, rating)` langsung dipanggil untuk menambah **+50 Poin** bonus instan.\n\n"
        "🛠️ **Manajemen & Intervensi Poin Manual (SQL):**\n"
        "Untuk menambah, mengurangi, atau mereset poin pembeli secara manual, jalankan perintah SQL berikut di Supabase SQL Editor:\n"
        "• *Update poin & tier user:*\n"
        "  `UPDATE users SET loyalty_points = 5500, loyalty_tier = 'loyalty' WHERE user_id = 123456789;`\n"
        "• *Reset streak & points:*\n"
        "  `UPDATE users SET loyalty_points = 0, loyalty_tier = 'bronze', purchase_streak = 0, last_purchase_at = NULL WHERE user_id = 123456789;`"
    )
    buttons = [
        [Button.inline("⬅️ Panduan 4", b"help_admin_step4")],
        [Button.inline("⬅️ Kembali ke Start", b"start")]
    ]
    await event.edit(text, buttons=buttons)
