"""
admin_handlers.py — Panel Admin Lengkap GEUNID JASEB

Command admin:
  /admin         — Buka panel admin utama
  /billing       — Kelola langganan client
  /ubots         — Kelola semua userbot
  /broadcast_all — Trigger broadcast manual semua client
  /setprice      — Shortcut edit harga
  /scan          — Scan LPM (tetap admin only, ada di main.py)
  /install       — Sambung userbot admin (ada di main.py)

Inline buttons admin:
  admin_stats      — Statistik global
  admin_billing    — Kelola billing
  admin_ubots      — Kelola userbot
  admin_orders     — Riwayat order
  admin_prices     — Edit harga
  admin_price_{id} — Edit harga spesifik
  admin_set_interval_{uid} — Set jadwal broadcast client
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timedelta

from telethon import events, Button

from src.config import ADMIN_ID, ADMIN_USERNAME
from src.database import get_db
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

    # ═══════════════════════════════════════════
    # /admin — Panel Utama
    # ═══════════════════════════════════════════
    @bot.on(events.NewMessage(pattern='/admin'))
    async def admin_command(event):
        if not await _admin_only_check(event):
            return
        _login_states.pop(event.sender_id, None)
        await _show_admin_panel(event)

    @bot.on(events.CallbackQuery(data=b"admin_main"))
    async def admin_main_callback(event):
        if not await _admin_only_check(event):
            return
        await _show_admin_panel(event)

    # ═══════════════════════════════════════════
    # STATISTIK GLOBAL
    # ═══════════════════════════════════════════
    @bot.on(events.CallbackQuery(data=b"admin_stats"))
    async def admin_stats_handler(event):
        if not await _admin_only_check(event):
            return

        async with get_db() as db:
            # Total users
            cur = await db.execute("SELECT COUNT(*) FROM users")
            total_users = (await cur.fetchone())[0]

            # Active subscriptions
            cur = await db.execute(
                "SELECT COUNT(*) FROM subscriptions WHERE status='active' AND end_date > datetime('now','localtime')"
            )
            active_subs = (await cur.fetchone())[0]

            # Revenue total (sum sukses)
            cur = await db.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE status='success'")
            total_revenue = (await cur.fetchone())[0]

            # Order per kategori
            cur = await db.execute(
                "SELECT package_id, COUNT(*) FROM transactions WHERE status='success' GROUP BY package_id ORDER BY COUNT(*) DESC LIMIT 5"
            )
            top_packages = await cur.fetchall()

            # Total broadcast sukses
            cur = await db.execute("SELECT COUNT(*) FROM forward_logs WHERE status='success'")
            total_sent = (await cur.fetchone())[0]

            # Userbot aktif
            cur = await db.execute("SELECT COUNT(*) FROM userbots WHERE status='connected'")
            total_ub = (await cur.fetchone())[0]

            # LPM aktif
            cur = await db.execute("SELECT COUNT(*) FROM lpm_lists WHERE is_active=1 AND is_blacklisted=0")
            total_lpm = (await cur.fetchone())[0]

            # Order 7 hari terakhir
            cur = await db.execute(
                "SELECT COUNT(*), COALESCE(SUM(amount),0) FROM transactions WHERE status='success' AND created_at > datetime('now','-7 days','localtime')"
            )
            week_row = await cur.fetchone()
            week_orders, week_rev = week_row[0], week_row[1]

        top_pkg_text = ""
        for i, (pkg, cnt) in enumerate(top_packages, 1):
            top_pkg_text += f"  {i}. {pkg} ({cnt}x)\n"

        text = (
            f"📊 **STATISTIK GLOBAL GEUNID-JASEB**\n{'━'*26}\n\n"
            f"👥 **Total User:** {total_users}\n"
            f"✅ **Langganan Aktif:** {active_subs}\n"
            f"💰 **Total Revenue:** Rp {total_revenue:,}\n\n"
            f"📅 **7 Hari Terakhir:**\n"
            f"  • Order: {week_orders} transaksi\n"
            f"  • Revenue: Rp {week_rev:,}\n\n"
            f"📤 **Total Terkirim:** {total_sent} pesan\n"
            f"🤖 **Userbot Aktif:** {total_ub}\n"
            f"🎯 **LPM Database:** {total_lpm} grup\n\n"
            f"🏆 **Top 5 Paket Terlaris:**\n{top_pkg_text or '  Belum ada data.'}"
        )
        await event.edit(text, buttons=[[Button.inline("⬅️ Panel Admin", b"admin_main")]])

    # ═══════════════════════════════════════════
    # KELOLA BILLING CLIENT
    # ═══════════════════════════════════════════
    @bot.on(events.NewMessage(pattern='/billing'))
    async def billing_command(event):
        if not await _admin_only_check(event):
            return
        await _show_billing(event)

    @bot.on(events.CallbackQuery(data=b"admin_billing"))
    async def admin_billing_callback(event):
        if not await _admin_only_check(event):
            return
        await _show_billing(event)

    @bot.on(events.CallbackQuery(pattern=b"admin_billing_detail_(\\d+)"))
    async def admin_billing_detail(event):
        if not await _admin_only_check(event):
            return
        uid = int(event.pattern_match.group(1).decode())
        await _show_client_billing_detail(event, uid)

    @bot.on(events.CallbackQuery(pattern=b"admin_extend_(\\d+)"))
    async def admin_extend_sub(event):
        if not await _admin_only_check(event):
            return
        uid = int(event.pattern_match.group(1).decode())
        _login_states[event.sender_id] = {"state": "admin_extend_days", "target_uid": uid}
        await event.edit(
            f"➕ **Perpanjang Langganan**\nUser ID: `{uid}`\n\n"
            "Ketik jumlah hari yang ingin ditambahkan (contoh: `7` atau `30`):"
        )

    @bot.on(events.CallbackQuery(pattern=b"admin_deactivate_(\\d+)"))
    async def admin_deactivate_sub(event):
        if not await _admin_only_check(event):
            return
        uid = int(event.pattern_match.group(1).decode())
        async with get_db() as db:
            await db.execute(
                "UPDATE subscriptions SET status='inactive' WHERE user_id=? AND status='active'", (uid,)
            )
            await db.commit()
        await event.answer(f"✅ Langganan user {uid} dinonaktifkan.", alert=True)
        await _show_billing(event)

    @bot.on(events.CallbackQuery(pattern=b"admin_set_interval_(\\d+)"))
    async def admin_set_interval(event):
        if not await _admin_only_check(event):
            return
        uid = int(event.pattern_match.group(1).decode())
        _login_states[event.sender_id] = {"state": "admin_set_interval", "target_uid": uid}
        await event.edit(
            f"⏰ **Set Interval Broadcast**\nUser ID: `{uid}`\n\n"
            "Ketik interval broadcast dalam jam (contoh: `2`, `4`, atau `6`):"
        )

    # ═══════════════════════════════════════════
    # KELOLA USERBOT
    # ═══════════════════════════════════════════
    @bot.on(events.NewMessage(pattern='/ubots'))
    async def ubots_command(event):
        if not await _admin_only_check(event):
            return
        await _show_ubots(event)

    @bot.on(events.CallbackQuery(data=b"admin_ubots"))
    async def admin_ubots_callback(event):
        if not await _admin_only_check(event):
            return
        await _show_ubots(event)

    @bot.on(events.CallbackQuery(pattern=b"admin_dc_ubot_(\\d+)"))
    async def admin_disconnect_ubot(event):
        if not await _admin_only_check(event):
            return
        uid = int(event.pattern_match.group(1).decode())
        async with get_db() as db:
            await db.execute("UPDATE userbots SET status='disconnected' WHERE user_id=?", (uid,))
            await db.commit()
        session_file = f"data/sessions/user_{uid}.session"
        if os.path.exists(session_file):
            try:
                os.remove(session_file)
            except Exception as e:
                logger.error(f"Gagal hapus session {uid}: {e}")
        await event.answer(f"🔌 Userbot user {uid} diputuskan.", alert=True)
        await _show_ubots(event)

    # ═══════════════════════════════════════════
    # RIWAYAT ORDER
    # ═══════════════════════════════════════════
    @bot.on(events.CallbackQuery(data=b"admin_orders"))
    async def admin_orders_handler(event):
        if not await _admin_only_check(event):
            return

        async with get_db() as db:
            cur = await db.execute("""
                SELECT t.user_id, u.username, u.full_name, t.package_id, t.amount, t.status, t.created_at
                FROM transactions t
                LEFT JOIN users u ON t.user_id = u.user_id
                ORDER BY t.created_at DESC LIMIT 10
            """)
            orders = await cur.fetchall()

        if not orders:
            await event.edit("📋 Belum ada transaksi.", buttons=[[Button.inline("⬅️ Panel Admin", b"admin_main")]])
            return

        lines = ["📋 **10 TRANSAKSI TERAKHIR**\n"]
        for uid, uname, fname, pkg, amt, status, created_at in orders:
            icon = "✅" if status == "success" else ("⏳" if status == "pending" else "❌")
            name_str = f"@{uname}" if uname else (fname or str(uid))
            lines.append(f"{icon} {name_str} | {pkg} | Rp {amt:,}")
            lines.append(f"   🕐 {created_at[:16]}")

        await event.edit("\n".join(lines), buttons=[[Button.inline("⬅️ Panel Admin", b"admin_main")]])

    # ═══════════════════════════════════════════
    # KELOLA HARGA
    # ═══════════════════════════════════════════
    @bot.on(events.NewMessage(pattern='/setprice'))
    async def setprice_command(event):
        if not await _admin_only_check(event):
            return
        _login_states.pop(event.sender_id, None)
        await _show_price_categories(event)

    @bot.on(events.CallbackQuery(data=b"admin_prices"))
    async def admin_prices_callback(event):
        if not await _admin_only_check(event):
            return
        await _show_price_categories(event)

    @bot.on(events.CallbackQuery(pattern=b"admin_pcat_(.+)"))
    async def admin_price_category(event):
        if not await _admin_only_check(event):
            return
        cat = event.pattern_match.group(1).decode()
        prices = _load_prices()
        items = prices.get(cat, [])
        buttons = []
        for item in items:
            lpm_str = f"{item['lpm']} LPM - " if item["lpm"] > 0 else ""
            label = f"{lpm_str}{item['duration']} → Rp {item['promoPrice']:,}"
            data = f"admin_price_{item['id']}".encode()
            buttons.append([Button.inline(label, data)])
        buttons.append([Button.inline("⬅️ Kembali", b"admin_prices")])
        cat_label = {"regular": "REGULAR", "forward": "FORWARD", "userbot": "USERBOT"}.get(cat, cat.upper())
        await event.edit(
            f"💰 **Edit Harga — Paket {cat_label}**\nPilih paket yang ingin diedit:",
            buttons=buttons
        )

    @bot.on(events.CallbackQuery(pattern=b"admin_price_(.+)"))
    async def admin_price_edit_select(event):
        if not await _admin_only_check(event):
            return
        pkg_id = event.pattern_match.group(1).decode()
        prices = _load_prices()
        item = None
        for cat in ["regular", "forward", "userbot"]:
            item = next((i for i in prices.get(cat, []) if i.get("id") == pkg_id), None)
            if item:
                break
        if not item:
            await event.answer("❌ Paket tidak ditemukan.", alert=True)
            return

        _login_states[event.sender_id] = {"state": "admin_edit_price", "pkg_id": pkg_id}
        lpm_str = f"{item['lpm']} LPM - " if item["lpm"] > 0 else ""
        await event.edit(
            f"💰 **Edit Harga Paket**\n\n"
            f"📦 Paket: `{lpm_str}{item['duration']}`\n"
            f"💵 Harga Saat Ini: **Rp {item['promoPrice']:,}**\n\n"
            "Ketik harga baru dalam Rupiah (angka saja, tanpa titik/koma):\n"
            "Contoh: `15000`"
        )

    # ═══════════════════════════════════════════
    # /broadcast_all — Trigger broadcast manual
    # ═══════════════════════════════════════════
    @bot.on(events.NewMessage(pattern='/broadcast_all'))
    async def broadcast_all_command(event):
        if not await _admin_only_check(event):
            return
        await event.respond("⏳ Memulai broadcast manual untuk semua client aktif...")
        async with get_db() as db:
            cur = await db.execute(
                "SELECT DISTINCT user_id FROM subscriptions WHERE status='active' AND end_date > datetime('now','localtime')"
            )
            users = await cur.fetchall()
        count = 0
        for (uid,) in users:
            asyncio.create_task(_start_user_broadcast(uid))
            count += 1
        await event.respond(f"✅ Broadcast dimulai untuk **{count} client** aktif.")

    # ═══════════════════════════════════════════
    # Input handler untuk state admin
    # ═══════════════════════════════════════════
    @bot.on(events.NewMessage)
    async def admin_input_handler(event):
        if event.sender_id not in _login_states:
            return
        state_data = _login_states[event.sender_id]
        state = state_data.get("state", "")

        # ── Edit harga paket ──
        if state == "admin_edit_price":
            pkg_id = state_data.get("pkg_id")
            text = event.text.strip().replace(".", "").replace(",", "")
            if not text.isdigit():
                await event.respond("❌ Masukkan angka saja. Contoh: `15000`")
                return
            new_price = int(text)
            try:
                with open(_PRICES_PATH, "r", encoding="utf-8") as f:
                    prices_data = json.load(f)
                updated = False
                for cat in ["regular", "forward", "userbot"]:
                    for item in prices_data.get(cat, []):
                        if item.get("id") == pkg_id:
                            old_price = item["promoPrice"]
                            item["promoPrice"] = new_price
                            updated = True
                            break
                    if updated:
                        break
                if updated:
                    with open(_PRICES_PATH, "w", encoding="utf-8") as f:
                        json.dump(prices_data, f, ensure_ascii=False, indent=2)
                    del _login_states[event.sender_id]
                    await event.respond(
                        f"✅ Harga berhasil diperbarui!\n\n"
                        f"📦 ID: `{pkg_id}`\n"
                        f"💵 Harga Lama: Rp {old_price:,}\n"
                        f"💵 Harga Baru: **Rp {new_price:,}**"
                    )
                else:
                    await event.respond("❌ ID paket tidak ditemukan di prices.json.")
                    del _login_states[event.sender_id]
            except Exception as e:
                logger.error(f"Error update price: {e}")
                await event.respond(f"❌ Gagal update harga: {e}")
                del _login_states[event.sender_id]

        # ── Perpanjang langganan ──
        elif state == "admin_extend_days":
            target_uid = state_data.get("target_uid")
            text = event.text.strip()
            if not text.isdigit() or int(text) <= 0:
                await event.respond("❌ Masukkan angka hari yang valid. Contoh: `7`")
                return
            days = int(text)
            async with get_db() as db:
                cur = await db.execute(
                    "SELECT id, end_date FROM subscriptions WHERE user_id=? AND status='active' ORDER BY end_date DESC LIMIT 1",
                    (target_uid,)
                )
                sub = await cur.fetchone()
                if not sub:
                    await event.respond(f"❌ Tidak ada langganan aktif untuk user {target_uid}.")
                    del _login_states[event.sender_id]
                    return
                sub_id, end_date_str = sub
                try:
                    current_end = datetime.strptime(end_date_str.split(".")[0], "%Y-%m-%d %H:%M:%S")
                except Exception:
                    current_end = datetime.now()
                new_end = max(current_end, datetime.now()) + timedelta(days=days)
                new_end_str = new_end.strftime("%Y-%m-%d %H:%M:%S")
                await db.execute("UPDATE subscriptions SET end_date=? WHERE id=?", (new_end_str, sub_id))
                await db.commit()
            del _login_states[event.sender_id]
            await event.respond(
                f"✅ Langganan diperpanjang **{days} hari**.\n"
                f"👤 User: `{target_uid}`\n"
                f"📅 Aktif Hingga: `{new_end_str}`"
            )

        # ── Set interval broadcast ──
        elif state == "admin_set_interval":
            target_uid = state_data.get("target_uid")
            text = event.text.strip()
            if not text.isdigit() or int(text) < 1 or int(text) > 24:
                await event.respond("❌ Masukkan angka jam yang valid (1-24). Contoh: `2`")
                return
            hours = int(text)
            async with get_db() as db:
                await db.execute(
                    "UPDATE subscriptions SET broadcast_interval_hours=? WHERE user_id=? AND status='active'",
                    (hours, target_uid)
                )
                await db.commit()
            del _login_states[event.sender_id]
            await event.respond(
                f"✅ Interval broadcast diatur ke **setiap {hours} jam**.\n"
                f"👤 User: `{target_uid}`"
            )

    # ── Parser Format Pesanan Manual ──
    @bot.on(events.NewMessage)
    async def admin_paste_format_handler(event):
        if event.sender_id != ADMIN_ID:
            return

        text = event.text or ""
        
        # Bersihkan format HTML & Markdown agar deteksi substring lebih akurat
        import re
        text_clean = re.sub(r'<[^>]+>', '', text)
        text_clean = text_clean.replace('**', '').replace('__', '').replace('*', '').replace('_', '')
        
        is_userbot_fmt = "𝗙𝗢𝗥𝗠𝗔𝗧 𝗣𝗔𝗦𝗔𝗡𝗚 𝗨𝗦𝗘𝗥𝗕𝗢𝗧" in text_clean or "FORMAT PASANG USERBOT" in text_clean.upper()
        is_jaseb_fmt = "𝗙𝗢𝗥𝗠𝗔𝗧 𝗝𝗔𝗦𝗘𝗕 𝗢𝗧𝗢𝗠𝗔𝗧𝗜𝗦" in text_clean or "FORMAT JASEB OTOMATIS" in text_clean.upper()

        if not (is_userbot_fmt or is_jaseb_fmt):
            return

        lines = text_clean.split("\n")
        user_id = None
        username = ""
        duration = "1 Bulan"
        package_name = ""
        amount = 0

        for line in lines:
            line_clean = line.replace("–", "-").strip()
            if "ID Telegram" in line_clean:
                match = re.search(r"ID Telegram\s*[:\-]?\s*\"?(\d+)\"?", line_clean, re.IGNORECASE)
                if match:
                    user_id = int(match.group(1))
            elif "Username" in line_clean:
                match = re.search(r"Username(?:\s*akun)?\s*[:\-]?\s*\"?@?([^\"]+)\"?", line_clean, re.IGNORECASE)
                if match:
                    username = match.group(1).strip()
            elif "Durasi" in line_clean:
                match = re.search(r"Durasi(?:\s*userbot|\s*jaseb)?\s*[:\-]?\s*\"?([^\"]+)\"?", line_clean, re.IGNORECASE)
                if match:
                    duration = match.group(1).strip()
            elif "Paket" in line_clean:
                match = re.search(r"Paket(?:\s*jaseb)?\s*[:\-]?\s*\"?([^\"]+)\"?", line_clean, re.IGNORECASE)
                if match:
                    package_name = match.group(1).strip()
            elif "Harga" in line_clean or "Total" in line_clean or "Nominal" in line_clean:
                match = re.search(r"(?:Harga|Total|Nominal)\s*[:\-]?\s*(?:Rp\s*)?([\d\.,]+)", line_clean, re.IGNORECASE)
                if match:
                    amt_str = match.group(1).replace(".", "").replace(",", "").strip()
                    if amt_str.isdigit():
                        amount = int(amt_str)

        if not user_id:
            # Fallback search globally
            match = re.search(r"ID Telegram[^\d]*(\d{7,15})", text_clean, re.IGNORECASE)
            if match:
                user_id = int(match.group(1))

        if not user_id:
            await event.respond("❌ **Format Ditolak:** ID Telegram pembeli tidak ditemukan di dalam format pesanan.")
            return

        if not package_name:
            if is_userbot_fmt:
                package_name = f"Jaseb Userbot {duration}"
            else:
                package_name = f"Jaseb Jasa Pasang {duration}"

        if amount <= 0:
            amount = 39000

        await event.respond(
            f"⏳ **Format Terdeteksi! Memproses Aktivasi Manual...**\n\n"
            f"👤 Client ID: `{user_id}`\n"
            f"📦 Paket: **{package_name}**\n"
            f"💰 Nominal: Rp {amount:,}\n"
            f"📅 Durasi: {duration}"
        )

        import time, random
        dummy_trx_id = f"MAN-{int(time.time())}{random.randint(100, 999)}"

        from src.database import get_db
        async with get_db() as db:
            await db.execute(
                "INSERT INTO users (user_id, username, full_name) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username",
                (user_id, username, f"Client Manual {user_id}")
            )
            await db.execute(
                "INSERT INTO transactions (user_id, trx_id, package_id, amount, payment_url, status) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, dummy_trx_id, package_name, amount, "manual", "pending")
            )
            await db.commit()

        from src.main import process_successful_payment
        success, msg = await process_successful_payment(dummy_trx_id)

        if success:
            await event.respond(
                f"✅ **Aktivasi Manual Sukses!**\n\n"
                f"Obrolan konfirmasi sukses pembayaran & panduan setup otomatis telah dikirim ke chat bot pribadi pengguna (ID: `{user_id}`)."
            )
        else:
            await event.respond(f"❌ **Gagal melakukan aktivasi:** {msg}")


# ═══ Helper functions ═══════════════════════════

async def _show_admin_panel(event):
    text = format_menu_text(
        "🛡️ PANEL ADMIN GEUNID-JASEB",
        "Selamat datang di panel kontrol Admin.\nPilih menu yang ingin diakses:"
    )
    buttons = [
        [Button.inline("📊 Statistik Global", b"admin_stats"),
         Button.inline("📋 Riwayat Order", b"admin_orders")],
        [Button.inline("👥 Kelola Billing", b"admin_billing"),
         Button.inline("🤖 Kelola Userbot", b"admin_ubots")],
        [Button.inline("💰 Edit Harga Paket", b"admin_prices")],
        [Button.inline("📢 Broadcast Semua Client", b"admin_broadcast_all_confirm")],
        [Button.inline("⬅️ Menu Utama", b"start")]
    ]
    if hasattr(event, "edit"):
        try:
            await event.edit(text, buttons=buttons)
            return
        except Exception:
            pass
    await event.respond(text, buttons=buttons)


async def _show_billing(event):
    async with get_db() as db:
        cur = await db.execute("""
            SELECT s.user_id, u.username, u.full_name, s.package_name, s.end_date, s.broadcast_interval_hours
            FROM subscriptions s
            LEFT JOIN users u ON s.user_id = u.user_id
            WHERE s.status='active' AND s.end_date > datetime('now','localtime')
            ORDER BY s.end_date ASC
            LIMIT 10
        """)
        subs = await cur.fetchall()

    if not subs:
        text = "👥 Tidak ada langganan aktif saat ini."
        buttons = [[Button.inline("⬅️ Panel Admin", b"admin_main")]]
    else:
        lines = [f"👥 **BILLING AKTIF ({len(subs)} client)**\n"]
        buttons = []
        for uid, uname, fname, pkg, end_date, interval in subs:
            try:
                clean_end = end_date.split(".")[0]
                end_dt = datetime.strptime(clean_end, "%Y-%m-%d %H:%M:%S")
                days_left = max(0, (end_dt - datetime.now()).days)
            except Exception:
                days_left = 0
            name_str = f"@{uname}" if uname else (fname or str(uid))
            interval_str = f"{interval or 2}j"
            lines.append(f"• {name_str} | {pkg[:20]}... | {days_left}hari | ⏰{interval_str}")
            buttons.append([Button.inline(f"⚙️ {name_str}", f"admin_billing_detail_{uid}".encode())])

        buttons.append([Button.inline("⬅️ Panel Admin", b"admin_main")])
        text = "\n".join(lines)

    if hasattr(event, "edit") and isinstance(event, events.CallbackQuery.Event):
        try:
            await event.edit(text, buttons=buttons)
            return
        except Exception:
            pass
    await event.respond(text, buttons=buttons)


async def _show_client_billing_detail(event, uid: int):
    async with get_db() as db:
        cur = await db.execute(
            "SELECT username, full_name FROM users WHERE user_id=?", (uid,)
        )
        user_row = await cur.fetchone()
        cur = await db.execute(
            "SELECT package_name, capacity_lpm, start_date, end_date, broadcast_interval_hours FROM subscriptions WHERE user_id=? AND status='active' ORDER BY end_date DESC LIMIT 1",
            (uid,)
        )
        sub = await cur.fetchone()
        cur = await db.execute("SELECT COUNT(*) FROM forward_logs WHERE user_id=? AND status='success'", (uid,))
        sent_count = (await cur.fetchone())[0]

    uname = f"@{user_row[0]}" if user_row and user_row[0] else str(uid)
    fname = (user_row[1] if user_row else "") or "-"

    if not sub:
        text = f"❌ Tidak ada langganan aktif untuk user `{uid}`."
        buttons = [[Button.inline("⬅️ Billing", b"admin_billing")]]
    else:
        pkg, capacity, start_date, end_date, interval = sub
        try:
            clean_end = end_date.split(".")[0]
            end_dt = datetime.strptime(clean_end, "%Y-%m-%d %H:%M:%S")
            days_left = max(0, (end_dt - datetime.now()).days)
        except Exception:
            days_left = 0

        text = (
            f"⚙️ **Detail Billing Client**\n{'━'*24}\n\n"
            f"👤 Nama: **{fname}** ({uname})\n"
            f"🆔 ID: `{uid}`\n\n"
            f"📦 Paket: `{pkg}`\n"
            f"🎯 LPM: {capacity}\n"
            f"📅 Mulai: {start_date[:10] if start_date else '-'}\n"
            f"📅 Habis: {end_date[:10]}\n"
            f"⏳ Sisa: **{days_left} hari**\n"
            f"⏰ Interval: {interval or 2} jam\n"
            f"📤 Total Terkirim: {sent_count} pesan"
        )
        buttons = [
            [Button.inline("➕ Perpanjang", f"admin_extend_{uid}".encode()),
             Button.inline("❌ Nonaktifkan", f"admin_deactivate_{uid}".encode())],
            [Button.inline("⏰ Set Interval", f"admin_set_interval_{uid}".encode())],
            [Button.inline("⬅️ Kembali", b"admin_billing")]
        ]

    if hasattr(event, "edit") and isinstance(event, events.CallbackQuery.Event):
        try:
            await event.edit(text, buttons=buttons)
            return
        except Exception:
            pass
    await event.respond(text, buttons=buttons)


async def _show_ubots(event):
    async with get_db() as db:
        cur = await db.execute("""
            SELECT ub.user_id, u.username, u.full_name, ub.phone_number, ub.status
            FROM userbots ub
            LEFT JOIN users u ON ub.user_id = u.user_id
            ORDER BY ub.status DESC
        """)
        ubots = await cur.fetchall()

    if not ubots:
        text = "🤖 Belum ada userbot yang terdaftar."
        buttons = [[Button.inline("⬅️ Panel Admin", b"admin_main")]]
    else:
        lines = [f"🤖 **DAFTAR USERBOT ({len(ubots)} terdaftar)**\n"]
        buttons = []
        for uid, uname, fname, phone, status in ubots:
            icon = "🟢" if status == "connected" else "🔴"
            name_str = f"@{uname}" if uname else (fname or str(uid))
            lines.append(f"{icon} {name_str} | {phone or '-'} | {status}")
            if status == "connected":
                buttons.append([Button.inline(f"🔌 Putuskan {name_str}", f"admin_dc_ubot_{uid}".encode())])

        buttons.append([Button.inline("⬅️ Panel Admin", b"admin_main")])
        text = "\n".join(lines)

    if hasattr(event, "edit") and isinstance(event, events.CallbackQuery.Event):
        try:
            await event.edit(text, buttons=buttons)
            return
        except Exception:
            pass
    await event.respond(text, buttons=buttons)


async def _show_price_categories(event):
    text = format_menu_text(
        "💰 EDIT HARGA PAKET",
        "Pilih kategori paket yang ingin diedit harganya:"
    )
    buttons = [
        [Button.inline("📢 Regular", b"admin_pcat_regular"),
         Button.inline("🔵 Forward", b"admin_pcat_forward")],
        [Button.inline("🤖 Userbot", b"admin_pcat_userbot")],
        [Button.inline("⬅️ Panel Admin", b"admin_main")]
    ]
    if hasattr(event, "edit"):
        try:
            await event.edit(text, buttons=buttons)
            return
        except Exception:
            pass
    await event.respond(text, buttons=buttons)


# Callback broadcast all confirm
def register_broadcast_all_confirm(bot, start_broadcast_fn):
    @bot.on(events.CallbackQuery(data=b"admin_broadcast_all_confirm"))
    async def broadcast_all_confirm(event):
        if event.sender_id != ADMIN_ID:
            await event.answer("⛔ Hanya Admin.", alert=True)
            return
        await event.edit(
            "📢 **Konfirmasi Broadcast Manual**\n\nIni akan memulai broadcast jaseb untuk SEMUA client aktif.\nLanjutkan?",
            buttons=[
                [Button.inline("✅ Ya, Broadcast Semua!", b"admin_broadcast_all_go")],
                [Button.inline("❌ Batal", b"admin_main")]
            ]
        )

    @bot.on(events.CallbackQuery(data=b"admin_broadcast_all_go"))
    async def broadcast_all_go(event):
        if event.sender_id != ADMIN_ID:
            await event.answer("⛔ Hanya Admin.", alert=True)
            return
        await event.edit("⏳ Memulai broadcast semua client aktif...")
        async with get_db() as db:
            cur = await db.execute(
                "SELECT DISTINCT user_id FROM subscriptions WHERE status='active' AND end_date > datetime('now','localtime')"
            )
            users = await cur.fetchall()
        count = len(users)
        for (uid,) in users:
            asyncio.create_task(start_broadcast_fn(uid))
        await event.edit(
            f"✅ **Broadcast dimulai untuk {count} client aktif!**\n\nBot bekerja di background.",
            buttons=[[Button.inline("⬅️ Panel Admin", b"admin_main")]]
        )
