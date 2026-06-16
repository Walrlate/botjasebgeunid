"""
main.py — Core Bot GEUNID JASEB (AUDITED BY JARVIS - FINAL MASTER VERSION)
========================================================================
"""

import asyncio
import logging
import re
import os
import json
import urllib.parse
from datetime import datetime, timedelta
from aiohttp import web

from telethon import TelegramClient, events, Button
from telethon.errors import UserNotParticipantError, FloodWaitError
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.tl.types import KeyboardButtonWebView, KeyboardButtonCallback, KeyboardButtonUrl, PeerChannel, PeerUser, PeerChat
from telethon.extensions import html

# Import internal modules
from src.config import (
    API_ID, API_HASH, BOT_TOKEN, ADMIN_ID, 
    CHANNEL_USERNAME, ADMIN_USERNAME, MINI_APP_URL, BOT_USERNAME
)
from src.database import init_db, get_db
from src.ui_styles import EMOJI_UI, format_menu_text
from src.payments import create_qris_transaction, check_transaction_status
from src.jaseb_engine import JasebEngine
from src.notifications import (
    notify_admin_payment_success,
    notify_client_broadcast_start,
    notify_client_broadcast_done,
    notify_client_subscription_expiring,
    notify_client_ad_saved,
    notify_admin_new_order
)
from src.admin_handlers import init_admin_handlers
from src.client_handlers import init_client_handlers, register_edit_jaseb_btn

# ─────────────────────────────────────────
# Konfigurasi Logging
# ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

os.makedirs("data/sessions", exist_ok=True)
os.makedirs("data/proofs", exist_ok=True)
os.makedirs("data/media", exist_ok=True)

bot = TelegramClient('data/bot_session', API_ID, API_HASH)
login_states = {}

# ─────────────────────────────────────────
# Utility Functions (Timezone & Logic)
# ─────────────────────────────────────────
async def clear_login_state(user_id):
    state_data = login_states.pop(user_id, None)
    if state_data and "client" in state_data:
        try:
            client = state_data["client"]
            if client and client.is_connected():
                await client.disconnect()
        except: pass

def load_prices():
    try:
        path = os.path.join("frontend", "src", "prices.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except: pass
    return {}

def get_package_duration_days(package_name: str, amount: int) -> int:
    prices = load_prices()
    if not prices: return 30
    amount = int(amount)
    for category in ['regular', 'forward', 'userbot']:
        for item in prices.get(category, []):
            if int(item.get('promoPrice', 0)) == amount or int(item.get('price', 0)) == amount:
                dur = item.get('duration', '')
                m = re.search(r'(\d+)', dur)
                days = int(m.group(1)) if m else 30
                bonus = re.search(r'\+(\d+)', item.get('bonus', ''))
                if bonus: days += int(bonus.group(1))
                return days
    return 30

def get_capacity_from_package(package_name: str) -> int:
    for lpm in [50, 30, 20]:
        if str(lpm) in package_name: return lpm
    return 20

async def check_channel_join(event) -> bool:
    user_id = event.sender_id
    if not user_id or user_id == ADMIN_ID: return True
    if not CHANNEL_USERNAME: return True
    try:
        await bot(GetParticipantRequest(channel=CHANNEL_USERNAME, participant=user_id))
        return True
    except UserNotParticipantError:
        invite_link = f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"
        text = format_menu_text("WAJIB JOIN CHANNEL", f"Harap bergabung ke channel resmi {CHANNEL_USERNAME} untuk menggunakan bot.")
        buttons = [[Button.url("🚀 Gabung Sekarang", invite_link)], [Button.inline("🔄 Cek Status", b"check_join_status")]]
        await event.respond(text, buttons=buttons)
        return False
    except: return True

@bot.on(events.CallbackQuery(data=b"check_join_status"))
async def check_join_status_handler(event):
    if await check_channel_join(event):
        await event.answer("✅ Akses aktif.", alert=True)
        await start_handler(event)

async def get_web_app_url(user_id: int) -> str:
    user_id = int(user_id)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with get_db() as db:
        cur = await db.execute("SELECT COUNT(*) FROM forward_logs WHERE user_id=? AND status='success'", (user_id,))
        succ_user = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM lpm_lists WHERE is_active=1 AND is_blacklisted=0")
        total_lpm = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM userbots WHERE status='connected'")
        total_ub = (await cur.fetchone())[0]
        cur = await db.execute("SELECT status FROM userbots WHERE user_id=?", (user_id,))
        ub_row = await cur.fetchone()
        ub_status = ub_row[0] if ub_row else 'disconnected'
        cur = await db.execute("""
            SELECT package_name, capacity_lpm, end_date, broadcast_interval_hours FROM subscriptions 
            WHERE user_id=? AND status='active' AND TRIM(end_date) > ? 
            ORDER BY end_date DESC LIMIT 1
        """, (user_id, now_str))
        sub_row = await cur.fetchone()
        pkg_name = sub_row[0] if sub_row else "Tidak Aktif"
        cap = sub_row[1] if sub_row else 0
        iv = float(sub_row[3] or 0.5) if sub_row else 0.5
        days = 0
        if sub_row:
            try:
                end_dt = datetime.strptime(sub_row[2].split(".")[0].strip(), "%Y-%m-%d %H:%M:%S")
                delta = end_dt - datetime.now()
                days = max(0, delta.days)
                if days == 0 and delta.total_seconds() > 0: days = 1
            except: pass

    params = {"b": succ_user, "l": total_lpm, "u": total_ub, "ub": ub_status, "pkg": pkg_name, "ulpm": cap, "days": days, "int": iv}
    return f"{MINI_APP_URL.rstrip('/')}/?{urllib.parse.urlencode(params)}"

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    await clear_login_state(event.sender_id)
    url = await get_web_app_url(event.sender_id)
    text = format_menu_text("GEUNID-JASEB", "Solusi sebar iklan otomatis di ribuan grup LPM.")
    buttons = [[KeyboardButtonWebView(text="🚀 Buka Mini App", url=url)]]
    if event.sender_id == ADMIN_ID:
        buttons.append([KeyboardButtonCallback(text="🛡️ Admin Panel", data=b"admin_main"), KeyboardButtonCallback(text="🤖 Pool Admin", data=b"admin_ubots")])
    else: buttons.append([KeyboardButtonCallback(text="📊 My Status", data=b"my_status")])
    await event.respond(text, buttons=buttons)

@bot.on(events.CallbackQuery(data=b"start"))
async def callback_start_handler(event):
    await _show_start_menu(event, is_callback=True)

async def _show_start_menu(event, is_callback=False):
    user_id = event.sender_id
    url = await get_web_app_url(user_id)
    text = format_menu_text("GEUNID-JASEB", "Sistem sebar iklan otomatis.")
    buttons = [[KeyboardButtonWebView(text="🚀 Buka Mini App", url=url)]]
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButtonCallback(text="🛡️ Admin Panel", data=b"admin_main"), KeyboardButtonCallback(text="🤖 Pool Admin", data=b"admin_ubots")])
    else: buttons.append([KeyboardButtonCallback(text="📊 My Status", data=b"my_status")])
    if is_callback: await event.edit(text, buttons=buttons)
    else: await event.respond(text, buttons=buttons)

@bot.on(events.NewMessage(pattern='/install'))
async def install_handler(event):
    if event.sender_id != ADMIN_ID: return
    login_states[event.sender_id] = {"state": "waiting_for_phone"}
    await event.respond("📱 **INSTALL ADMIN USERBOT**\n\nMasukkan nomor HP yang ingin dijadikan pool pengirim (format: `+628xxx`):")

@bot.on(events.NewMessage(pattern=r'/scan\s+(.+)'))
async def scan_lpm_handler(event):
    if event.sender_id != ADMIN_ID: return
    link = event.pattern_match.group(1).strip()
    await event.respond(f"⏳ Sedang memindai grup: {link}...")
    async with get_db() as db:
        cur = await db.execute("SELECT session_name FROM admin_userbots WHERE status='connected' LIMIT 1")
        row = await cur.fetchone()
    if row:
        eng = JasebEngine(f"data/sessions/{row[0]}", API_ID, API_HASH)
        await eng.start()
        res = await JasebEngine.verify_lpm_group(eng.client, link)
        if res.get("success"):
            async with get_db() as db:
                await db.execute("INSERT OR IGNORE INTO lpm_lists (group_link, group_id, group_name, member_count, is_active) VALUES (?, ?, ?, ?, 1)", (link, res["group_id"], res["group_name"], res["member_count"]))
                await db.commit()
            await event.respond(f"✅ **Grup Valid!**\nNama: {res['group_name']}\nMember: {res['member_count']}")
        else: await event.respond(f"❌ Gagal: {res.get('error')}")
        await eng.stop()
    else: await event.respond("❌ Tidak ada Ubot Admin aktif untuk scanning.")

@bot.on(events.NewMessage)
async def user_input_handler(event):
    user_id = event.sender_id
    if user_id not in login_states: return
    state_data = login_states[user_id]
    current_state = state_data.get("state")
    text = (event.text or "").strip()
    if text.startswith("/") and text.lower() != "/skip": return

    if current_state == "waiting_for_proof":
        if not event.message.photo and not event.message.document:
            await event.respond("❌ Harap kirimkan **FOTO BUKTI TRANSFER** Anda.")
            return
        await event.respond("⏳ Mengirim bukti ke admin untuk verifikasi...")
        media = await event.message.download_media(file="data/proofs/")
        trx_id, pkg, amt = state_data["trx_id"], state_data["package_name"], state_data["amount"]
        admin_msg = f"🔔 **BUKTI TRANSFER BARU**\n\n👤 User: `{user_id}`\n📦 Paket: {pkg}\n💰 Nominal: Rp {amt:,}\n🆔 Order: `{trx_id}`"
        buttons = [[Button.inline("Approve ✅", f"approve_man_{trx_id}".encode()), Button.inline("Reject ❌", f"reject_man_{trx_id}".encode())]]
        await bot.send_file(ADMIN_ID, file=media, caption=admin_msg, buttons=buttons)
        await event.respond("✅ **Bukti Terkirim!** Mohon tunggu verifikasi admin.")
        del login_states[user_id]

    elif current_state == "waiting_for_phone":
        phone = text.replace(" ", "")
        if not phone.startswith("+"):
            await event.respond("❌ Format salah! Gunakan: `+628xxx`")
            return
        is_admin = (user_id == ADMIN_ID)
        session = f"admin_{phone[1:]}" if is_admin else f"user_{user_id}"
        client = TelegramClient(f"data/sessions/{session}", API_ID, API_HASH)
        await client.connect()
        try:
            res = await client.send_code_request(phone)
            login_states[user_id].update({"state": "waiting_for_otp", "phone": phone, "client": client, "hash": res.phone_code_hash})
            await event.respond("📨 **OTP dikirim!** Masukkan kode 5 digit:")
        except Exception as e: await event.respond(f"❌ Gagal: {e}"); await clear_login_state(user_id)

    elif current_state == "waiting_for_otp":
        try:
            client = state_data["client"]
            await client.sign_in(state_data["phone"], text, phone_code_hash=state_data["hash"])
            await _save_userbot_session(event, client, state_data["phone"])
        except Exception as e: await event.respond(f"❌ OTP Salah: {e}")

    elif current_state == "waiting_for_ad":
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        async with get_db() as db:
            cur = await db.execute("SELECT package_name FROM subscriptions WHERE user_id=? AND status='active' AND TRIM(end_date) > ? ORDER BY end_date DESC LIMIT 1", (user_id, now_str))
            sub = await cur.fetchone()
        if not sub: await event.respond("❌ Paket tidak aktif."); del login_states[user_id]; return
        is_fwd = "forward" in sub[0].lower()
        if is_fwd and not event.message.forward:
            await event.respond("❌ Paket FORWARD wajib forward pesan asli."); return
        if not is_fwd and event.message.forward:
            await event.respond("❌ Paket REGULAR dilarang forward."); return
        await event.respond("⏳ Menyimpan materi iklan..."); content = html.unparse(event.message.message or "", event.message.entities or [])
        media = await event.message.download_media(file="data/media/") if event.message.media else ""
        async with get_db() as db:
            await db.execute("DELETE FROM user_ads WHERE user_id=?", (user_id,))
            await db.execute("INSERT INTO user_ads (user_id, title, content, media_path) VALUES (?, 'Iklan Utama', ?, ?)", (user_id, content, media))
            await db.commit()
        login_states[user_id]["state"] = "waiting_for_lpm_request"
        await event.respond("✅ Materi Tersimpan! Kirim daftar link LPM kustom atau ketik `/skip`:")

    elif current_state == "waiting_for_lpm_request":
        lpm_list_str = ""
        if text.lower() != "/skip":
            links = re.findall(r'(?:https?://)?(?:t\.me/|@)?([a-zA-Z0-9_]{5,32}|joinchat/[a-zA-Z0-9_\-]+)', text)
            if not links: await event.respond("❌ Kirim daftar LPM atau /skip."); return
            lpm_list_str = " ".join([f"@{l}" if not ("t.me" in l or "joinchat" in l) else l for l in links[:10]])
        async with get_db() as db:
            await db.execute("UPDATE subscriptions SET request_lpm=? WHERE user_id=? AND status='active'", (lpm_list_str or None, user_id))
            await db.commit()
        del login_states[user_id]
        await event.respond("🎉 **Pendaftaran Selesai!** Bot mulai menyebar sekarang.")
        asyncio.create_task(start_user_broadcast(user_id))

async def _save_userbot_session(event, client, phone):
    user_id = event.sender_id
    is_admin = (user_id == ADMIN_ID)
    session = f"admin_{phone.replace('+','')}" if is_admin else f"user_{user_id}"
    async with get_db() as db:
        if is_admin: await db.execute("INSERT OR REPLACE INTO admin_userbots (phone_number, session_name, status) VALUES (?, ?, 'connected')", (phone, session))
        else: await db.execute("INSERT OR REPLACE INTO userbots (user_id, phone_number, session_name, status) VALUES (?, ?, ?, 'connected')", (user_id, phone, session))
        await db.commit()
    await client.disconnect(); del login_states[user_id]
    await event.respond("✅ **Userbot Berhasil Terhubung!**")

@bot.on(events.NewMessage(incoming=True))
async def order_format_parser(event):
    if event.sender_id in login_states: return
    text = event.text or ""
    if "𝗙𝗢𝗥𝗠𝗔𝗧 𝗝𝗔𝗦𝗘𝗕 𝗢𝗧𝗢𝗠𝗔𝗧𝗜𝗦" not in text and "𝗙𝗢𝗥𝗠𝗔𝗧 𝗣𝗔𝗦𝗔𝗡𝗚 𝗨𝗦𝗘𝗥𝗕𝗢𝗧" not in text: return
    
    # Hanya ADMIN yang bisa auto-aktivasi via paste format untuk keamanan
    if event.sender_id != ADMIN_ID: return
    
    lines = text.split("\n")
    data = {}
    for line in lines:
        if ":" in line:
            k, v = line.split(":", 1)
            data[k.strip().lower().replace("–","").strip()] = v.strip()
    m = re.search(r'\d+', data.get("total harga", "0").replace(".", ""))
    amount = int(m.group(0)) if m else 0
    paket = data.get("paket jaseb", data.get("durasi userbot", "Paket Manual"))
    trx_id = f"MAN-{int(datetime.now().timestamp())}"
    
    # Ambil ID target dari format (ID Telegram: xxxxx)
    target_uid = int(data.get("id telegram", event.sender_id))
    
    async with get_db() as db:
        await db.execute("INSERT INTO transactions (user_id, trx_id, package_id, amount, payment_url, status) VALUES (?, ?, ?, ?, 'manual', 'pending')", (target_uid, trx_id, paket, amount))
        await db.commit()
    await process_successful_payment(trx_id)
    await event.respond(f"✅ **Aktivasi Manual Sukses!** (ID: {trx_id} untuk User: {target_uid})")

async def process_successful_payment(trx_id: str):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with get_db() as db:
        cur = await db.execute("SELECT user_id, amount, package_id, status FROM transactions WHERE trx_id=?", (trx_id,))
        row = await cur.fetchone()
        if not row or row[3] == 'success': return
        uid, amt, pkg, _ = row
        days, cap = get_package_duration_days(pkg, amt), get_capacity_from_package(pkg)
        cur = await db.execute("SELECT end_date FROM subscriptions WHERE user_id=? AND status='active' AND TRIM(end_date) > ? ORDER BY end_date DESC LIMIT 1", (uid, now_str))
        sub = await cur.fetchone()
        if sub:
            curr_end = datetime.strptime(sub[0].split(".")[0].strip(), "%Y-%m-%d %H:%M:%S")
            new_end = (max(curr_end, datetime.now()) + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
            await db.execute("UPDATE subscriptions SET end_date=?, capacity_lpm=? WHERE user_id=? AND status='active'", (new_end, cap, uid))
        else:
            new_end = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
            await db.execute("INSERT INTO subscriptions (user_id, package_name, capacity_lpm, start_date, end_date, status, broadcast_interval_hours) VALUES (?, ?, ?, ?, ?, 'active', 0.5)", (uid, pkg, cap, now_str, new_end))
        await db.execute("UPDATE transactions SET status='success' WHERE trx_id=?", (trx_id,))
        await db.commit()
    is_ub = "userbot" in pkg.lower()
    msg = f"🎉 **Paket {pkg} Aktif!**\n" + ("🤖 Kirim nomor HP Ubot:" if is_ub else "✍️ Kirim materi iklan:")
    login_states[uid] = {"state": "waiting_for_phone" if is_ub else "waiting_for_ad"}
    await bot.send_message(uid, msg)

@bot.on(events.CallbackQuery(pattern=b"check_(.+)"))
async def check_payment_status_handler(event):
    trx_id = event.pattern_match.group(1).decode()
    res = await check_transaction_status(trx_id)
    if res and res.get("data", {}).get("status") == "success":
        await process_successful_payment(trx_id)
        await event.answer("✅ Sukses!", alert=True)
    else: await event.answer("⏳ Belum ada pembayaran.", alert=True)

# ─────────────────────────────────────────
# API Handlers
# ─────────────────────────────────────────
async def handle_prices_api(request):
    """Ambil data harga terbaru untuk Mini App."""
    return web.json_response(load_prices(), headers={"Access-Control-Allow-Origin": "*"})

async def handle_checkout_api(request):
    """Proses pembuatan transaksi (QRIS atau Manual)."""
    try:
        data = await request.json()
        user_id = int(data['user_id'])
        amount = int(data['amount'])
        package_name = data['package_name']
        method = data.get('payment_method', 'qris')
        
        if method == 'manual':
            import time
            trx_id = f"MAN-{int(time.time())}"
            async with get_db() as db:
                await db.execute(
                    "INSERT INTO transactions (user_id, trx_id, package_id, amount, payment_url, status) VALUES (?, ?, ?, ?, 'manual', 'pending')",
                    (user_id, trx_id, package_name, amount)
                )
                await db.commit()
            
            # Aktifkan state menunggu bukti di bot
            login_states[user_id] = {
                "state": "waiting_for_proof",
                "trx_id": trx_id,
                "amount": amount,
                "package_name": package_name
            }
            
            await bot.send_message(
                user_id, 
                f"📥 **INSTRUKSI MANUAL**\n\nID Order: `{trx_id}`\nPaket: {package_name}\nTotal: Rp {amount:,}\n\n"
                "Silakan kirim **FOTO BUKTI TRANSFER** ke chat ini sekarang!"
            )
            return web.json_response({"status": True, "data": {"transaction_id": trx_id, "payment_url": "manual"}}, headers={"Access-Control-Allow-Origin": "*"})
        
        # QRIS Flow
        trx = await create_qris_transaction(amount, package_name)
        if trx:
            async with get_db() as db:
                await db.execute(
                    "INSERT INTO transactions (user_id, trx_id, package_id, amount, payment_url, status) VALUES (?, ?, ?, ?, ?, 'pending')",
                    (user_id, trx["transaction_id"], package_name, amount, trx["payment_url"])
                )
                await db.commit()
            return web.json_response({"status": True, "data": trx}, headers={"Access-Control-Allow-Origin": "*"})
            
    except Exception as e:
        logger.error(f"Checkout API Error: {e}")
    return web.json_response({"status": False, "error": "Internal Error"}, status=400, headers={"Access-Control-Allow-Origin": "*"})

async def handle_user_stats_api(request):
    """API untuk auto-update statistik di Mini App."""
    try:
        uid = int(request.match_info['user_id'])
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        async with get_db() as db:
            # Hitung sukses milik user
            cur = await db.execute("SELECT COUNT(*) FROM forward_logs WHERE user_id=? AND status='success'", (uid,))
            succ = (await cur.fetchone())[0]
            
            # Cek paket aktif (Gunakan TRIM dan now_str)
            cur = await db.execute("""
                SELECT package_name, capacity_lpm, end_date, broadcast_interval_hours 
                FROM subscriptions 
                WHERE user_id=? AND status='active' AND TRIM(end_date) > ? 
                ORDER BY end_date DESC LIMIT 1
            """, (uid, now_str))
            sub = await cur.fetchone()
            
            # Cek status userbot
            cur = await db.execute("SELECT status FROM userbots WHERE user_id=?", (uid,))
            ub = await cur.fetchone()
        
        res = {
            "total_sent": succ,
            "package_name": "Tidak Aktif",
            "days_left": 0,
            "seconds_left": 0,
            "userbot_status": ub[0] if ub else "disconnected"
        }
        
        if sub:
            try:
                end_dt = datetime.strptime(sub[2].split(".")[0].strip(), "%Y-%m-%d %H:%M:%S")
                delta = end_dt - datetime.now()
                res.update({
                    "package_name": sub[0],
                    "capacity_lpm": sub[1],
                    "days_left": max(0, delta.days),
                    "seconds_left": max(0, int(delta.total_seconds())),
                    "interval": sub[3]
                })
                if res["days_left"] == 0 and res["seconds_left"] > 0:
                    res["days_left"] = 1
            except: pass
            
        return web.json_response({"status": True, "data": res}, headers={"Access-Control-Allow-Origin": "*"})
    except:
        return web.json_response({"status": False}, status=500, headers={"Access-Control-Allow-Origin": "*"})

async def handle_history_api(request):
    """API riwayat jaseb terisolasi per user."""
    try:
        uid = int(request.match_info['user_id'])
        async with get_db() as db:
            cur = await db.execute("""
                SELECT l.group_name, f.msg_link, f.status, f.error_msg, f.sent_at 
                FROM forward_logs f 
                LEFT JOIN lpm_lists l ON f.group_id = l.group_id 
                WHERE f.user_id=? 
                ORDER BY f.sent_at DESC LIMIT 50
            """, (uid,))
            rows = await cur.fetchall()
            
        history = []
        for r in rows:
            history.append({
                "group_name": r[0] or "Grup LPM",
                "msg_link": r[1],
                "status": r[2],
                "error_msg": r[3],
                "sent_at": r[4]
            })
        return web.json_response({"status": True, "data": history}, headers={"Access-Control-Allow-Origin": "*"})
    except:
        return web.json_response({"status": False}, status=500, headers={"Access-Control-Allow-Origin": "*"})

async def handle_check_status_api(request):
    """Gateway check status QRIS."""
    trx_id = request.match_info.get('trx_id')
    res = await check_transaction_status(trx_id)
    if res and res.get("data", {}).get("status") == "success":
        await process_successful_payment(trx_id)
    return web.json_response(res, headers={"Access-Control-Allow-Origin": "*"})

# ─────────────────────────────────────────
# Engine & Orchestration
# ─────────────────────────────────────────
async def start_user_broadcast(user_id: int):
    """Trigger pengiriman iklan untuk satu user."""
    user_id = int(user_id)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with get_db() as db:
        cur = await db.execute("""
            SELECT package_name, capacity_lpm, request_lpm, broadcast_interval_hours 
            FROM subscriptions 
            WHERE user_id=? AND status='active' AND TRIM(end_date) > ? 
            ORDER BY end_date DESC LIMIT 1
        """, (user_id, now_str))
        sub = await cur.fetchone()
        if not sub: return
        
        pkg, cap, req_lpm, iv = sub
        cur = await db.execute("SELECT id FROM user_ads WHERE user_id=? ORDER BY created_at DESC LIMIT 1", (user_id,))
        ad = await cur.fetchone()
        if not ad:
            await bot.send_message(user_id, "⚠️ Materi Jaseb Anda kosong! Ketik /edit_jaseb untuk mengisi.")
            return
        ad_id = ad[0]
    
    # Bangun list LPM
    links = [l.strip() for l in (req_lpm or "").split() if l.strip()]
    sisa = max(0, cap - len(links))
    if sisa > 0:
        async with get_db() as db:
            cur = await db.execute("SELECT group_link FROM lpm_lists WHERE is_active=1 AND is_blacklisted=0 ORDER BY member_count DESC LIMIT ?", (sisa,))
            links.extend(r[0] for r in await cur.fetchall())

    if "userbot" in pkg.lower():
        # Mode Stealth (Akun Pembeli)
        async with get_db() as db:
            cur = await db.execute("SELECT session_name, status FROM userbots WHERE user_id=?", (user_id,))
            ub = await cur.fetchone()
        if ub and ub[1] == 'connected':
            eng = JasebEngine(f"data/sessions/{ub[0]}", API_ID, API_HASH)
            await eng.start()
            asyncio.create_task(run_broadcast_task(eng, user_id, ad_id, links, 'slowly', True, iv or 0.5))
        else:
            await bot.send_message(user_id, "⚠️ Userbot Anda terputus. Harap hubungkan kembali via /start.")
    else:
        # Mode Pool (Admin Cadangan)
        async with get_db() as db:
            cur = await db.execute("""
                SELECT session_name, phone_number, id FROM admin_userbots 
                WHERE status='connected' AND (cooldown_until IS NULL OR TRIM(cooldown_until) < ?) 
                ORDER BY RANDOM()
            """, (now_str,))
            admins = await cur.fetchall()
        if admins:
            asyncio.create_task(run_admin_pool_broadcast_task(user_id, ad_id, links, pkg, admins, iv or 0.5))
        else:
            logger.error("CRITICAL: All Admin Pool offline/FloodWait!")

async def run_admin_pool_broadcast_task(user_id, ad_id, links, pkg, admins, iv):
    """Protokol Fallback: Jika Admin A limit, Admin B melanjutkan."""
    unprocessed = links.copy()
    succ = fail = 0
    for sess, phone, aid in admins:
        if not unprocessed: break
        eng = JasebEngine(f"data/sessions/{sess}", API_ID, API_HASH)
        try:
            await eng.start()
            res = await eng.broadcast_with_stealth(user_id, ad_id, unprocessed, 'slowly' if 'regular' in pkg.lower() else 'instant')
            succ += res.get("success_count", 0)
            fail += res.get("failed_count", 0)
            unprocessed = res.get("unprocessed_links", [])
            
            if res.get("floodwait_seconds", 0) > 300:
                until = (datetime.now() + timedelta(seconds=res["floodwait_seconds"])).strftime("%Y-%m-%d %H:%M:%S")
                async with get_db() as db:
                    await db.execute("UPDATE admin_userbots SET cooldown_until=? WHERE id=?", (until, aid))
                    await db.commit()
                continue # Gunakan admin berikutnya
            break
        except Exception as e:
            logger.error(f"Fallback Error ({phone}): {e}")
        finally:
            await eng.stop()
    
    await notify_client_broadcast_done(bot, user_id, succ, fail, iv)

async def run_broadcast_task(eng, user_id, ad_id, links, delay, join, iv):
    """Task tunggal untuk Userbot pembeli."""
    try:
        res = await eng.broadcast_with_stealth(user_id, ad_id, links, delay, join)
        await notify_client_broadcast_done(bot, user_id, res.get("success_count", 0), res.get("failed_count", 0), iv)
    finally:
        await eng.stop()

# ─────────────────────────────────────────
# Background Schedulers
# ─────────────────────────────────────────
async def run_jaseb_scheduler():
    """Jantung otomatisasi GeunID."""
    last_run = {}
    while True:
        try:
            await asyncio.sleep(60)
            now = datetime.now()
            now_str = now.strftime("%Y-%m-%d %H:%M:%S")
            async with get_db() as db:
                cur = await db.execute("""
                    SELECT DISTINCT user_id, broadcast_interval_hours 
                    FROM subscriptions WHERE status='active' AND TRIM(end_date) > ?
                """, (now_str,))
                users = await cur.fetchall()
                
            for uid, iv_h in users:
                iv = float(iv_h or 0.5)
                if uid not in last_run or (now - last_run[uid]).total_seconds() >= iv * 3600:
                    last_run[uid] = now
                    asyncio.create_task(start_user_broadcast(uid))
        except Exception as e:
            logger.error(f"Scheduler Error: {e}")

async def run_expiry_reminder():
    """Pengingat masa aktif (setiap 6 jam)."""
    while True:
        try:
            await asyncio.sleep(3600 * 6)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            limit_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
            async with get_db() as db:
                cur = await db.execute("""
                    SELECT user_id, package_name, end_date FROM subscriptions 
                    WHERE status='active' AND TRIM(end_date) BETWEEN ? AND ?
                """, (now_str, limit_str))
                exp = await cur.fetchall()
            for u, p, e in exp:
                await notify_client_subscription_expiring(bot, u, p, e)
        except: pass

# ─────────────────────────────────────────
# Web Server Entry Point
# ─────────────────────────────────────────
async def run_web_server():
    app = web.Application()
    app.router.add_get('/api/prices', handle_prices_api)
    app.router.add_post('/api/checkout', handle_checkout_api)
    app.router.add_get('/api/user-stats/{user_id}', handle_user_stats_api)
    app.router.add_get('/api/history/{user_id}', handle_history_api)
    app.router.add_get('/api/check-status/{trx_id}', handle_check_status_api)
    
    async def options_handler(request):
        return web.Response(headers={
            "Access-Control-Allow-Origin": "*", 
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS", 
            "Access-Control-Allow-Headers": "Content-Type"
        })
    
    # Daftarkan OPTIONS secara manual dan aman
    paths = ['/api/prices', '/api/checkout', '/api/user-stats/{user_id}', '/api/history/{user_id}', '/api/check-status/{trx_id}']
    for p in paths: app.router.add_options(p, options_handler)

    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', port).start()
    logger.info(f"API Server Online di port {port}")

async def main():
    logger.info("Jarvis: Memulai inisialisasi sistem...")
    await init_db()
    await bot.start(bot_token=BOT_TOKEN)
    
    # Injeksi Handlers
    init_admin_handlers(bot, login_states, load_prices, get_package_duration_days, start_user_broadcast)
    init_client_handlers(bot, login_states, load_prices)
    register_edit_jaseb_btn(bot, login_states)
    
    # Jalankan Tugas Background
    asyncio.create_task(run_jaseb_scheduler())
    asyncio.create_task(run_expiry_reminder())
    asyncio.create_task(run_web_server())
    
    logger.info("Sistem GEUNID JASEB Beroperasi Penuh.")
    await bot.run_until_disconnected()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
