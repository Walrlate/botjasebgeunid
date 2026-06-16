"""
client_handlers.py — Semua handler yang diakses oleh CLIENT (bukan admin)

Command yang tersedia untuk client:
  /start    — Menu utama
  /help     — Panduan fitur + daftar harga
  /mystatus — Cek status jaseb aktif
  /edit_jaseb — Ganti teks jaseb
  /skip     — Skip input LPM kustom
  
Inline buttons:
  help_*       — Sub-menu help
  order_cat_*  — Pilih kategori (regular/forward/userbot)
  order_lpm_*  — Pilih LPM
  order_dur_*  — Pilih durasi & buat QRIS
  resend_jaseb — Minta jaseb disebar ulang sekarang
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
from src.notifications import notify_admin_new_order

logger = logging.getLogger(__name__)

# Referensi ke bot dan login_states akan di-inject dari main.py
_bot = None
_login_states = None
_load_prices = None


def init_client_handlers(bot, login_states, load_prices_fn):
    """Dipanggil dari main.py saat startup untuk inject dependencies."""
    global _bot, _login_states, _load_prices
    _bot = bot
    _login_states = login_states
    _load_prices = load_prices_fn
    _register_handlers(bot)


def _register_handlers(bot):
    """Register semua event handler client ke bot instance."""

    # ─────────────────────────────────────────
    # /help — Menu Bantuan & Daftar Harga
    # ─────────────────────────────────────────
    @bot.on(events.NewMessage(pattern='/help'))
    async def help_command_handler(event):
        await _show_help_main(event)

    @bot.on(events.CallbackQuery(data=b"help_main"))
    async def help_main_callback(event):
        await _show_help_main(event)

    @bot.on(events.CallbackQuery(data=b"help_prices"))
    async def help_prices_handler(event):
        prices = _load_prices()
        lines = ["💰 **DAFTAR HARGA PAKET JASEB**\n"]

        for lpm in [20, 30, 50]:
            reg = [i for i in prices.get("regular", []) if i.get("lpm") == lpm]
            if reg:
                lines.append(f"━ **REGULAR {lpm} LPM**")
                for item in reg:
                    bonus = f" {item['bonus']}" if item.get("bonus") else ""
                    lines.append(f"  • {item['duration']}{bonus} → Rp {item['promoPrice']:,}")
                lines.append("")

        for lpm in [20, 30, 50]:
            fwd = [i for i in prices.get("forward", []) if i.get("lpm") == lpm]
            if fwd:
                lines.append(f"━ **FORWARD {lpm} LPM**")
                for item in fwd:
                    bonus = f" {item['bonus']}" if item.get("bonus") else ""
                    lines.append(f"  • {item['duration']}{bonus} → Rp {item['promoPrice']:,}")
                lines.append("")

        ub = prices.get("userbot", [])
        if ub:
            lines.append("━ **USERBOT AUTOPILOT**")
            for item in ub:
                lines.append(f"  • {item['duration']} → Rp {item['promoPrice']:,}")

        lines.append("\n🛒 Ketuk tombol di bawah untuk order sekarang!")
        text = "\n".join(lines)
        from src.main import get_web_app_url
        from telethon.tl.types import KeyboardButtonWebView, KeyboardButtonCallback
        web_app_url = await get_web_app_url(event.sender_id)
        await event.edit(text, buttons=[
            [KeyboardButtonWebView(text="🛒 Order Sekarang", url=web_app_url)],
            [KeyboardButtonCallback(text="⬅️ Kembali", data=b"help_main")]
        ])

    @bot.on(events.CallbackQuery(data=b"help_howto"))
    async def help_howto_handler(event):
        text = format_menu_text(
            "📖 CARA PAKAI JASEB",
            "**Langkah-langkah Order Jaseb:**\n\n"
            "1️⃣ Ketuk tombol **🛒 Order** atau `/help`\n"
            "2️⃣ Pilih jenis paket: Regular / Forward / Userbot\n"
            "3️⃣ Pilih kapasitas LPM (20 / 30 / 50)\n"
            "4️⃣ Pilih durasi paket\n"
            "5️⃣ Scan **QRIS** yang muncul & bayar\n"
            "6️⃣ Klik tombol **🔄 Cek Status Bayar**\n"
            "7️⃣ Kirim **teks yang mau di-promote** ke bot ini\n"
            "8️⃣ Kirim **link grup LPM kustom** (opsional, maks 10)\n"
            "9️⃣ Selesai! Bot akan menyebarkan otomatis 🎉\n\n"
            "**Perbedaan Regular vs Forward:**\n"
            "• **Regular** — Teks saja, ada watermark\n"
            "• **Forward** — Support foto/video, tanpa watermark, lebih stealth\n"
            "• **Userbot** — Pakai nomor Telegram Anda sendiri (paling stealth)\n\n"
            "💡 _Ketik /mystatus untuk cek status jaseb kapan saja._"
        )
        from src.main import get_web_app_url
        from telethon.tl.types import KeyboardButtonWebView, KeyboardButtonCallback
        web_app_url = await get_web_app_url(event.sender_id)
        await event.edit(text, buttons=[
            [KeyboardButtonWebView(text="🛒 Order Sekarang", url=web_app_url)],
            [KeyboardButtonCallback(text="⬅️ Kembali", data=b"help_main")]
        ])

    # ─────────────────────────────────────────
    # Order Flow — Client bisa order mandiri
    # ─────────────────────────────────────────
    @bot.on(events.CallbackQuery(data=b"order_start"))
    async def order_start_handler(event):
        text = format_menu_text(
            "🛒 PILIH JENIS PAKET",
            "Pilih jenis layanan jaseb yang Anda inginkan:\n\n"
            "📢 **Regular** — Sebar teks, ada watermark GeunID\n"
            "🔵 **Forward** — Support foto & video, tanpa watermark\n"
            "🤖 **Userbot** — Pakai nomor Telegram Anda sendiri"
        )
        await event.edit(text, buttons=[
            [Button.inline("📢 Regular", b"order_cat_regular"),
             Button.inline("🔵 Forward", b"order_cat_forward")],
            [Button.inline("🤖 Userbot Autopilot", b"order_cat_userbot")],
            [Button.inline("⬅️ Kembali", b"help_main")]
        ])

    @bot.on(events.CallbackQuery(pattern=b"order_cat_(.+)"))
    async def order_category_handler(event):
        category = event.pattern_match.group(1).decode()
        prices = _load_prices()

        if category == "userbot":
            items = prices.get("userbot", [])
            buttons = []
            for item in items:
                label = f"{item['duration']} — Rp {item['promoPrice']:,}"
                data = f"order_buy_{category}_0_{item['id']}".encode()
                buttons.append([Button.inline(label, data)])
            buttons.append([Button.inline("⬅️ Kembali", b"order_start")])

            text = format_menu_text("🤖 PILIH DURASI USERBOT", "Pilih paket durasi userbot:")
            await event.edit(text, buttons=buttons)
            return

        # Regular / Forward — pilih LPM dulu
        lpms = sorted(set(i["lpm"] for i in prices.get(category, [])))
        buttons = [[Button.inline(f"{lpm} LPM", f"order_lpm_{category}_{lpm}".encode())] for lpm in lpms]
        buttons.append([Button.inline("⬅️ Kembali", b"order_start")])

        cat_label = "Regular" if category == "regular" else "Forward"
        text = format_menu_text(
            f"📋 PILIH KAPASITAS LPM ({cat_label.upper()})",
            "LPM (Link Per Menit) = jumlah grup yang akan mendapat kiriman jaseb Anda.\n\n"
            "Pilih kapasitas yang sesuai:"
        )
        await event.edit(text, buttons=buttons)

    @bot.on(events.CallbackQuery(pattern=b"order_lpm_(.+)_(\\d+)"))
    async def order_lpm_handler(event):
        parts = event.data.decode().split("_")
        category = parts[2]
        lpm = int(parts[3])
        prices = _load_prices()

        items = [i for i in prices.get(category, []) if i.get("lpm") == lpm]
        buttons = []
        for item in items:
            bonus = f" {item['bonus']}" if item.get("bonus") else ""
            label = f"{item['duration']}{bonus} — Rp {item['promoPrice']:,}"
            data = f"order_buy_{category}_{lpm}_{item['id']}".encode()
            buttons.append([Button.inline(label, data)])
        buttons.append([Button.inline("⬅️ Kembali", f"order_cat_{category}".encode())])

        cat_label = "Regular" if category == "regular" else "Forward"
        text = format_menu_text(
            f"📅 PILIH DURASI ({cat_label} {lpm} LPM)",
            "Pilih durasi paket yang diinginkan:"
        )
        await event.edit(text, buttons=buttons)

    @bot.on(events.CallbackQuery(pattern=b"order_buy_(.+)_(\\d+)_(.+)"))
    async def order_buy_handler(event):
        raw = event.data.decode()
        parts = raw.split("_", 4)  # order_buy_{cat}_{lpm}_{id}
        category = parts[2]
        lpm = int(parts[3])
        pkg_id = parts[4]

        prices = _load_prices()
        item = next((i for i in prices.get(category, []) if i.get("id") == pkg_id), None)
        if not item:
            await event.answer("❌ Paket tidak ditemukan.", alert=True)
            return

        amount = item["promoPrice"]
        lpm_label = f"{item['lpm']} LPM" if item["lpm"] > 0 else ""
        pkg_desc = f"Jaseb {category.capitalize()} {lpm_label} {item['duration']}".strip()
        bonus = f" {item['bonus']}" if item.get("bonus") else ""
        
        await event.answer("⏳ Membuat QRIS pembayaran...", alert=False)

        trx_data = await create_qris_transaction(amount, pkg_desc)
        if not trx_data:
            await event.answer("❌ Gagal membuat pembayaran. Hubungi admin.", alert=True)
            return

        # Simpan ke DB
        sender = await event.get_sender()
        full_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
        username = sender.username or ""

        async with get_db() as db:
            # Upsert user
            await db.execute(
                "INSERT INTO users (user_id, username, full_name) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, full_name=excluded.full_name",
                (event.sender_id, username, full_name)
            )
            await db.execute(
                "INSERT INTO transactions (user_id, trx_id, package_id, amount, payment_url, status) VALUES (?, ?, ?, ?, ?, ?)",
                (event.sender_id, trx_data["transaction_id"], pkg_desc, amount, trx_data["payment_url"], "pending")
            )
            await db.commit()

        # Notif admin ada order baru
        await notify_admin_new_order(
            _bot, ADMIN_ID, event.sender_id, full_name, username, pkg_desc, amount, trx_data["transaction_id"]
        )

        pay_text = (
            f"✅ **Invoice QRIS Berhasil Dibuat!**\n\n"
            f"📦 Paket: **{pkg_desc}**{bonus}\n"
            f"💰 Total Bayar: **Rp {trx_data['total_amount']:,}**\n"
            f"⏰ Berlaku: {trx_data['expired_at']}\n\n"
            f"Scan QRIS di atas dengan OVO / Gopay / Dana / m-Banking.\n"
            f"Setelah bayar, klik **🔄 Cek Status Bayar** di bawah."
        )
        # Konstruksi tombol secara dinamis
        buttons = []
        payment_url = trx_data.get("payment_url")
        if payment_url and isinstance(payment_url, str) and payment_url.startswith("http"):
            buttons.append([Button.url("🔗 Bayar via Browser", payment_url)])
        
        buttons.append([Button.inline("🔄 Cek Status Bayar", f"check_{trx_data['transaction_id']}".encode())])

        try:
            await _bot.send_file(
                event.chat_id,
                file=trx_data["qris_url"],
                caption=pay_text,
                buttons=buttons
            )
        except Exception as e:
            logger.error(f"Gagal kirim QRIS image: {e}")
            await event.respond(pay_text, buttons=buttons)

    # ─────────────────────────────────────────
    # /mystatus — Cek status jaseb real-time
    # ─────────────────────────────────────────
    @bot.on(events.NewMessage(pattern='/mystatus'))
    async def mystatus_command_handler(event):
        await _show_mystatus(event, event.sender_id)

    @bot.on(events.CallbackQuery(data=b"my_status"))
    async def mystatus_callback(event):
        await _show_mystatus(event, event.sender_id)

    # ─────────────────────────────────────────
    # /edit_jaseb — Ganti teks jaseb
    # ─────────────────────────────────────────
    @bot.on(events.NewMessage(pattern='/edit_jaseb'))
    async def edit_jaseb_command_handler(event):
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT id FROM subscriptions WHERE user_id = ? AND status = 'active' AND end_date > datetime('now', 'localtime')",
                (event.sender_id,)
            )
            sub = await cursor.fetchone()

        if not sub:
            await event.respond("❌ Anda tidak memiliki paket aktif. Gunakan /help untuk order.")
            return

        _login_states[event.sender_id] = {"state": "waiting_for_ad"}
        await event.respond(
            "✍️ **Silakan kirim teks jaseb baru Anda.**\n\n"
            "Bisa berupa:\n"
            "• Teks biasa\n"
            "• Foto / Video dengan caption\n"
            "• Pesan forward dari channel toko Anda\n\n"
            "_Teks lama akan digantikan dengan yang baru._"
        )

    # ─────────────────────────────────────────
    # Tombol Kirim Ulang Jaseb
    # ─────────────────────────────────────────
    @bot.on(events.CallbackQuery(data=b"resend_jaseb"))
    async def resend_jaseb_handler(event):
        from src.main import start_user_broadcast
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT id FROM subscriptions WHERE user_id = ? AND status = 'active' AND end_date > datetime('now', 'localtime')",
                (event.sender_id,)
            )
            sub = await cursor.fetchone()
            cursor = await db.execute(
                "SELECT id FROM user_ads WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
                (event.sender_id,)
            )
            ad = await cursor.fetchone()

        if not sub:
            await event.answer("❌ Paket Anda tidak aktif!", alert=True)
            return
        if not ad:
            await event.answer("❌ Belum ada teks jaseb. Kirim /edit_jaseb dulu.", alert=True)
            return

        await event.answer("🚀 Sedang memulai ulang broadcast...", alert=False)
        asyncio.create_task(start_user_broadcast(event.sender_id))

    @bot.on(events.CallbackQuery(data=b"client_set_interval"))
    async def client_set_interval_callback(event):
        _login_states[event.sender_id] = {"state": "client_set_interval"}
        await event.respond(
            "⏰ **Atur Jeda Sebar Userbot**\n\n"
            "Ketik interval sebar otomatis yang Anda inginkan dalam jam.\n"
            "Masukkan angka jam saja (contoh: `1` untuk setiap jam, `2` untuk setiap 2 jam, dll. Maksimal 24 jam):"
        )

    @bot.on(events.CallbackQuery(data=b"client_reset_userbot"))
    async def client_reset_userbot_handler(event):
        uid = event.sender_id
        session_file = f"data/sessions/user_{uid}.session"
        if os.path.exists(session_file):
            try:
                os.remove(session_file)
            except Exception as e:
                logger.error(f"Gagal hapus session file user {uid}: {e}")
        
        async with get_db() as db:
            await db.execute(
                "UPDATE userbots SET status='disconnected' WHERE user_id=?", (uid,)
            )
            await db.commit()
            
        _login_states[uid] = {"state": "waiting_for_phone"}
        await event.respond(
            "🔌 **Koneksi Userbot Berhasil Direset!**\n\n"
            "Silakan kirimkan nomor HP akun Telegram Anda kembali untuk melakukan pairing ulang (format internasional).\n"
            "Contoh: `+628123456789`"
        )


async def _show_help_main(event):
    """Tampilkan menu help utama."""
    title = f"📖 BANTUAN & FITUR GEUNID-JASEB"
    content = (
        "Selamat datang! Berikut fitur-fitur yang tersedia:\n\n"
        f"{'━'*22}\n"
        "🛒 **Order Paket** — Beli paket jaseb, bayar via QRIS, bot langsung proses otomatis\n\n"
        "📊 **Status Real-time** — Cek berapa grup sudah terkirim, sisa hari paket, dll\n\n"
        "✍️ **Edit Teks Jaseb** — Ganti teks yang disebar kapan saja tanpa order ulang\n\n"
        "🔄 **Kirim Ulang** — Minta jaseb disebarkan ulang langsung tanpa tunggu jadwal\n\n"
        "🎯 **LPM Kustom** — Request grup LPM spesifik (maks 10) setelah order\n\n"
        "📜 **Riwayat Kirim** — Lihat log pengiriman ke setiap grup\n\n"
        f"{'━'*22}\n\n"
        "Gunakan tombol di bawah untuk navigasi:"
    )
    text = format_menu_text(title, content)
    from src.main import get_web_app_url
    from telethon.tl.types import KeyboardButtonWebView, KeyboardButtonCallback, KeyboardButtonUrl
    web_app_url = await get_web_app_url(event.sender_id)
    buttons = [
        [KeyboardButtonCallback(text="💰 Lihat Daftar Harga", data=b"help_prices"),
         KeyboardButtonCallback(text="📖 Cara Pakai", data=b"help_howto")],
        [KeyboardButtonWebView(text="🛒 Order Sekarang", url=web_app_url)],
        [KeyboardButtonCallback(text="📊 Status Jaseb Saya", data=b"my_status")],
        [KeyboardButtonUrl(text="📞 Hubungi Admin", url=f"https://t.me/{ADMIN_USERNAME.replace('@', '')}")],
        [KeyboardButtonCallback(text="⬅️ Menu Utama", data=b"start")]
    ]
    if hasattr(event, "edit"):
        try:
            await event.edit(text, buttons=buttons)
            return
        except Exception:
            pass
    await event.respond(text, buttons=buttons)


async def _show_mystatus(event, user_id: int):
    """Tampilkan status jaseb real-time dari database."""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT package_name, capacity_lpm, start_date, end_date, broadcast_interval_hours
            FROM subscriptions
            WHERE user_id = ? AND status = 'active' AND end_date > datetime('now', 'localtime')
            ORDER BY end_date DESC LIMIT 1
        """, (user_id,))
        sub = await cursor.fetchone()

        cursor = await db.execute(
            "SELECT content, media_path, created_at FROM user_ads WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
            (user_id,)
        )
        ad = await cursor.fetchone()

        cursor = await db.execute(
            "SELECT COUNT(*) FROM forward_logs WHERE user_id = ? AND status = 'success'",
            (user_id,)
        )
        total_sent = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT COUNT(*) FROM forward_logs WHERE user_id = ? AND status = 'failed'",
            (user_id,)
        )
        total_failed = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT status FROM userbots WHERE user_id = ?", (user_id,)
        )
        ub_row = await cursor.fetchone()
        ub_status = (ub_row[0] if ub_row else "disconnected")

    if not sub:
        text = (
            "📊 **Status Jaseb Anda**\n\n"
            "❌ Tidak ada paket aktif.\n\n"
            "Gunakan /help untuk melihat daftar harga dan order."
        )
        buttons = [[Button.inline("🛒 Order Sekarang", b"order_start")]]
    else:
        pkg_name, capacity, start_date, end_date, interval_hours = sub
        # Hitung sisa hari
        try:
            clean_end = end_date.split(".")[0]
            end_dt = datetime.strptime(clean_end, "%Y-%m-%d %H:%M:%S")
            delta = end_dt - datetime.now()
            days_left = max(0, delta.days)
        except Exception:
            days_left = 0

        ad_status = "✅ Ada" if ad else "❌ Belum dikirim (ketik /edit_jaseb)"
        ub_icon = "🟢" if ub_status == "connected" else "🔴"
        interval_label = f"Setiap {interval_hours} jam" if interval_hours else "Setiap 2 jam"

        text = (
            f"📊 **Status Jaseb Real-time**\n{'━'*22}\n\n"
            f"📦 **Paket:** {pkg_name}\n"
            f"🎯 **Kapasitas:** {capacity} LPM\n"
            f"📅 **Aktif Hingga:** {end_date[:10]}\n"
            f"⏳ **Sisa:** {days_left} hari\n"
            f"⏰ **Jadwal Sebar:** {interval_label}\n\n"
            f"✍️ **Teks Jaseb:** {ad_status}\n"
            f"{ub_icon} **Userbot:** {ub_status.capitalize()}\n\n"
            f"📈 **Statistik Pengiriman:**\n"
            f"  ✅ Berhasil: {total_sent} grup\n"
            f"  ❌ Gagal: {total_failed} grup"
        )
        
        is_userbot_package = "userbot" in pkg_name.lower()
        if is_userbot_package:
            buttons = [
                [Button.inline("🔄 Kirim Ulang Sekarang", b"resend_jaseb"),
                 Button.inline("✍️ Edit Teks", b"edit_jaseb_btn")],
                [Button.inline("⏰ Atur Jeda Sebar", b"client_set_interval"),
                 Button.inline("🔌 Reset Koneksi", b"client_reset_userbot")],
                [Button.inline("📜 Riwayat Kirim", b"view_logs"),
                 Button.inline("⬅️ Menu Utama", b"start")]
            ]
        else:
            buttons = [
                [Button.inline("🔄 Kirim Ulang Sekarang", b"resend_jaseb"),
                 Button.inline("✍️ Edit Teks", b"edit_jaseb_btn")],
                [Button.inline("📜 Riwayat Kirim", b"view_logs"),
                 Button.inline("⬅️ Menu Utama", b"start")]
            ]

    if hasattr(event, "edit"):
        try:
            await event.edit(text, buttons=buttons)
            return
        except Exception:
            pass
    await event.respond(text, buttons=buttons)


# ─────────────────────────────────────────
# Callback untuk tombol edit teks jaseb
# ─────────────────────────────────────────
def register_edit_jaseb_btn(bot, login_states):
    @bot.on(events.CallbackQuery(data=b"edit_jaseb_btn"))
    async def edit_jaseb_btn_handler(event):
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT id FROM subscriptions WHERE user_id = ? AND status = 'active' AND end_date > datetime('now', 'localtime')",
                (event.sender_id,)
            )
            sub = await cursor.fetchone()

        if not sub:
            await event.answer("❌ Paket tidak aktif!", alert=True)
            return

        login_states[event.sender_id] = {"state": "waiting_for_ad"}
        await event.edit(
            "✍️ **Silakan kirim teks jaseb baru Anda.**\n\n"
            "Bisa berupa teks, foto/video dengan caption, atau pesan forward.\n"
            "_Teks lama akan digantikan._"
        )
