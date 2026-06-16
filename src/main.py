"""
main.py — Core Bot GEUNID JASEB (AUDITED BY JARVIS)
==================================================
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
from telethon.tl.functions.channels import JoinChannelRequest, GetParticipantRequest
from telethon.tl.types import KeyboardButtonWebView, KeyboardButtonCallback
from telethon.extensions import html

# Import internal modules
from src.config import (
    API_ID, API_HASH, BOT_TOKEN, ADMIN_ID, 
    CHANNEL_USERNAME, MINI_APP_URL, BOT_USERNAME
)
from src.database import init_db, get_db
from src.ui_styles import EMOJI_UI, format_menu_text
from src.payments import create_qris_transaction, check_transaction_status
from src.jaseb_engine import JasebEngine
from src.notifications import (
    notify_admin_payment_success,
    notify_client_broadcast_done,
    notify_client_subscription_expiring,
    notify_client_ad_saved
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
bot = TelegramClient('data/bot_session', API_ID, API_HASH)

login_states = {}

# ─────────────────────────────────────────
# Utility Functions
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

async def get_web_app_url(user_id: int) -> str:
    user_id = int(user_id)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with get_db() as db:
        cur = await db.execute("SELECT COUNT(*) FROM forward_logs WHERE user_id=? AND status='success'", (user_id,))
        total_sent_user = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM lpm_lists WHERE is_active=1 AND is_blacklisted=0")
        total_lpm_global = (await cur.fetchone())[0]
        cur = await db.execute("SELECT status FROM userbots WHERE user_id=?", (user_id,))
        ub_row = await cur.fetchone()
        cur = await db.execute("SELECT package_name, capacity_lpm, end_date, broadcast_interval_hours FROM subscriptions WHERE user_id=? AND status='active' AND TRIM(end_date) > ? ORDER BY end_date DESC LIMIT 1", (user_id, now_str))
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

    params = {
        "b": total_sent_user,
        "l": total_lpm_global,
        "u": 0,
        "ub": ub_row[0] if ub_row else 'disconnected',
        "pkg": pkg_name,
        "ulpm": cap,
        "days": days,
        "int": iv
    }
    return f"{MINI_APP_URL.rstrip('/')}/?{urllib.parse.urlencode(params)}"

# ─────────────────────────────────────────
# Handlers Bot Utama
# ─────────────────────────────────────────
@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    await clear_login_state(event.sender_id)
    url = await get_web_app_url(event.sender_id)
    text = format_menu_text("GEUNID-JASEB", "Solusi sebar iklan otomatis di ribuan grup LPM.")
    buttons = [[KeyboardButtonWebView(text="🚀 Buka Mini App", url=url)], [KeyboardButtonCallback(text="📊 My Status", data=b"my_status")]]
    if event.sender_id == ADMIN_ID:
        buttons.append([KeyboardButtonCallback(text="🛡️ Admin Panel", data=b"admin_main")])
    await event.respond(text, buttons=buttons)

@bot.on(events.CallbackQuery(data=b"start"))
async def callback_start_handler(event):
    await clear_login_state(event.sender_id)
    url = await get_web_app_url(event.sender_id)
    text = format_menu_text("GEUNID-JASEB", "Sistem sebar iklan otomatis.")
    buttons = [[KeyboardButtonWebView(text="🚀 Buka Mini App", url=url)], [KeyboardButtonCallback(text="📊 My Status", data=b"my_status")]]
    if event.sender_id == ADMIN_ID:
        buttons.append([KeyboardButtonCallback(text="🛡️ Admin Panel", data=b"admin_main")])
    await event.edit(text, buttons=buttons)

# ─────────────────────────────────────────
# State Machine: Input User
# ─────────────────────────────────────────
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
        trx_id = state_data["trx_id"]
        pkg = state_data["package_name"]
        amt = state_data["amount"]
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
            await event.respond("📨 **OTP dikirim!** Masukkan kode:")
        except Exception as e:
            await event.respond(f"❌ Gagal: {e}")
            await clear_login_state(user_id)

    elif current_state == "waiting_for_otp":
        try:
            client = state_data["client"]
            await client.sign_in(state_data["phone"], text, phone_code_hash=state_data["hash"])
            await _save_userbot_session(event, client, state_data["phone"])
        except Exception as e: await event.respond(f"❌ OTP Salah: {e}")

async def _save_userbot_session(event, client, phone):
    is_admin = (event.sender_id == ADMIN_ID)
    session = f"admin_{phone.replace('+','')}" if is_admin else f"user_{event.sender_id}"
    async with get_db() as db:
        if is_admin: await db.execute("INSERT OR REPLACE INTO admin_userbots (phone_number, session_name, status) VALUES (?, ?, 'connected')", (phone, session))
        else: await db.execute("INSERT OR REPLACE INTO userbots (user_id, phone_number, session_name, status) VALUES (?, ?, ?, 'connected')", (event.sender_id, phone, session))
        await db.commit()
    await client.disconnect()
    del login_states[event.sender_id]
    await event.respond("✅ Userbot Berhasil Terhubung!")

# ─────────────────────────────────────────
# Order Parser & Activation
# ─────────────────────────────────────────
@bot.on(events.NewMessage(incoming=True))
async def order_format_parser(event):
    if event.sender_id in login_states: return
    text = event.text or ""
    if "𝗙𝗢𝗥𝗠𝗔𝗧 𝗝𝗔𝗦𝗘𝗕 𝗢𝗧𝗢𝗠𝗔𝗧𝗜𝗦" not in text and "𝗙𝗢𝗥𝗠𝗔𝗧 𝗣𝗔𝗦𝗔𝗡𝗚 𝗨𝗦𝗘𝗥𝗕𝗢𝗧" not in text: return
    lines = text.split("\n")
    data = {}
    for line in lines:
        if ":" in line:
            k, v = line.split(":", 1)
            data[k.strip().lower().replace("–","").strip()] = v.strip()
    
    amount = 0
    m = re.search(r'\d+', data.get("total harga", "0").replace(".", "").replace(",", ""))
    if m: amount = int(m.group(0))
    paket = data.get("paket jaseb", data.get("durasi userbot", "Paket Manual"))
    import time
    trx_id = f"MAN-{int(time.time())}"
    async with get_db() as db:
        await db.execute("INSERT INTO transactions (user_id, trx_id, package_id, amount, payment_url, status) VALUES (?, ?, ?, ?, 'manual', 'pending')", (event.sender_id, trx_id, paket, amount))
        await db.commit()
    await process_successful_payment(trx_id)
    await event.respond(f"✅ **Aktivasi Sukses!** (ID: {trx_id})")

async def process_successful_payment(trx_id: str):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with get_db() as db:
        cur = await db.execute("SELECT user_id, amount, package_id, status FROM transactions WHERE trx_id=?", (trx_id,))
        row = await cur.fetchone()
        if not row or row[3] == 'success': return
        uid, amt, pkg, _ = row
        days = get_package_duration_days(pkg, amt)
        cap = get_capacity_from_package(pkg)
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
    msg = "🎉 **Akses Jaseb Aktif!**\n\n" + ("🤖 Kirim nomor HP untuk Ubot:" if is_ub else "✍️ Kirim materi iklan Anda:")
    login_states[uid] = {"state": "waiting_for_phone" if is_ub else "waiting_for_ad"}
    await bot.send_message(uid, msg)

# ─────────────────────────────────────────
# API Endpoints
# ─────────────────────────────────────────
async def handle_prices_api(request):
    return web.json_response(load_prices(), headers={"Access-Control-Allow-Origin": "*"})

async def handle_checkout_api(request):
    try:
        data = await request.json()
        user_id, amount, pkg, method = int(data.get('user_id')), int(data.get('amount')), data.get('package_name'), data.get('payment_method', 'qris')
        if method == 'manual':
            import time, random
            trx_id = f"MAN-{int(time.time())}"
            async with get_db() as db:
                await db.execute("INSERT INTO transactions (user_id, trx_id, package_id, amount, payment_url, status) VALUES (?, ?, ?, ?, 'manual', 'pending')", (user_id, trx_id, pkg, amount))
                await db.commit()
            login_states[user_id] = {"state": "waiting_for_proof", "trx_id": trx_id, "amount": amount, "package_name": pkg}
            await bot.send_message(user_id, f"📥 **INSTRUKSI MANUAL**\n\nPaket: {pkg}\nTotal: Rp {amount:,}\n\n**KIRIM BUKTI TRANSFER SEKARANG!**")
            return web.json_response({"status": True, "data": {"transaction_id": trx_id, "payment_url": "manual"}}, headers={"Access-Control-Allow-Origin": "*"})
        
        trx = await create_qris_transaction(amount, pkg)
        if trx:
            async with get_db() as db:
                await db.execute("INSERT INTO transactions (user_id, trx_id, package_id, amount, payment_url, status) VALUES (?, ?, ?, ?, ?, 'pending')", (user_id, trx["transaction_id"], pkg, amount, trx["payment_url"]))
                await db.commit()
            return web.json_response({"status": True, "data": trx}, headers={"Access-Control-Allow-Origin": "*"})
    except: pass
    return web.json_response({"status": False}, status=400, headers={"Access-Control-Allow-Origin": "*"})

async def handle_user_stats_api(request):
    try:
        uid = int(request.match_info.get('user_id'))
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        async with get_db() as db:
            cur = await db.execute("SELECT COUNT(*) FROM forward_logs WHERE user_id=? AND status='success'", (uid,))
            succ = (await cur.fetchone())[0]
            cur = await db.execute("SELECT package_name, capacity_lpm, end_date, broadcast_interval_hours FROM subscriptions WHERE user_id=? AND status='active' AND TRIM(end_date) > ? ORDER BY end_date DESC LIMIT 1", (uid, now))
            sub = await cur.fetchone()
            cur = await db.execute("SELECT status FROM userbots WHERE user_id=?", (uid,))
            ub = await cur.fetchone()
        
        res = {"total_sent": succ, "package_name": "Tidak Aktif", "days_left": 0, "seconds_left": 0, "userbot_status": ub[0] if ub else "disconnected"}
        if sub:
            end_dt = datetime.strptime(sub[2].split(".")[0].strip(), "%Y-%m-%d %H:%M:%S")
            delta = end_dt - datetime.now()
            res.update({"package_name": sub[0], "capacity_lpm": sub[1], "days_left": max(0, delta.days), "seconds_left": max(0, int(delta.total_seconds())), "interval": sub[3]})
        return web.json_response({"status": True, "data": res}, headers={"Access-Control-Allow-Origin": "*"})
    except: return web.json_response({"status": False}, status=500, headers={"Access-Control-Allow-Origin": "*"})

async def handle_history_api(request):
    try:
        uid = int(request.match_info.get('user_id'))
        async with get_db() as db:
            cur = await db.execute("SELECT l.group_name, f.msg_link, f.status, f.error_msg, f.sent_at FROM forward_logs f LEFT JOIN lpm_lists l ON f.group_id = l.group_id WHERE f.user_id=? ORDER BY f.sent_at DESC LIMIT 50", (uid,))
            rows = await cur.fetchall()
        return web.json_response({"status": True, "data": [{"group_name": r[0] or "Grup LPM", "msg_link": r[1], "status": r[2], "error_msg": r[3], "sent_at": r[4]} for r in rows]}, headers={"Access-Control-Allow-Origin": "*"})
    except: return web.json_response({"status": False}, status=500, headers={"Access-Control-Allow-Origin": "*"})

async def handle_check_status_api(request):
    trx_id = request.match_info.get('trx_id')
    res = await check_transaction_status(trx_id)
    if res and res.get("data", {}).get("status") == "success": await process_successful_payment(trx_id)
    return web.json_response(res, headers={"Access-Control-Allow-Origin": "*"})

# ─────────────────────────────────────────
# Engine & Orchestration
# ─────────────────────────────────────────
async def start_user_broadcast(user_id: int):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with get_db() as db:
        cur = await db.execute("SELECT package_name, capacity_lpm, request_lpm, broadcast_interval_hours FROM subscriptions WHERE user_id=? AND status='active' AND TRIM(end_date) > ? ORDER BY end_date DESC LIMIT 1", (user_id, now))
        sub = await cur.fetchone()
        if not sub: return
        pkg, cap, req_lpm, iv = sub
        cur = await db.execute("SELECT id FROM user_ads WHERE user_id=? ORDER BY created_at DESC LIMIT 1", (user_id,))
        ad = await cur.fetchone()
        if not ad: return
        ad_id = ad[0]
    
    links = [l.strip() for l in (req_lpm or "").split() if l.strip()]
    sisa = max(0, cap - len(links))
    if sisa > 0:
        async with get_db() as db:
            cur = await db.execute("SELECT group_link FROM lpm_lists WHERE is_active=1 AND is_blacklisted=0 ORDER BY member_count DESC LIMIT ?", (sisa,))
            links.extend(r[0] for r in await cur.fetchall())

    if "userbot" in pkg.lower():
        async with get_db() as db:
            cur = await db.execute("SELECT session_name, status FROM userbots WHERE user_id=?", (user_id,))
            ub = await cur.fetchone()
        if ub and ub[1] == 'connected':
            eng = JasebEngine(f"data/sessions/{ub[0]}", API_ID, API_HASH)
            await eng.start()
            asyncio.create_task(run_broadcast_task(eng, user_id, ad_id, links, 'slowly', True, iv or 0.5))
    else:
        async with get_db() as db:
            cur = await db.execute("SELECT session_name, phone_number, id FROM admin_userbots WHERE status='connected' AND (cooldown_until IS NULL OR TRIM(cooldown_until) < ?) ORDER BY RANDOM()", (now,))
            admins = await cur.fetchall()
        if admins: asyncio.create_task(run_admin_pool_broadcast_task(user_id, ad_id, links, pkg, admins, iv or 0.5))

async def run_admin_pool_broadcast_task(user_id, ad_id, links, pkg, admins, iv):
    unprocessed = links.copy(); succ = fail = 0
    for sess, phone, aid in admins:
        if not unprocessed: break
        eng = JasebEngine(f"data/sessions/{sess}", API_ID, API_HASH)
        try:
            await eng.start()
            res = await eng.broadcast_with_stealth(user_id, ad_id, unprocessed, 'slowly' if 'regular' in pkg.lower() else 'instant')
            succ += res.get("success_count", 0); fail += res.get("failed_count", 0); unprocessed = res.get("unprocessed_links", [])
            if res.get("floodwait_seconds", 0) > 300:
                until = (datetime.now() + timedelta(seconds=res["floodwait_seconds"])).strftime("%Y-%m-%d %H:%M:%S")
                async with get_db() as db: await db.execute("UPDATE admin_userbots SET cooldown_until=? WHERE id=?", (until, aid)); await db.commit()
                continue
            break
        except: pass
        finally: await eng.stop()
    await notify_client_broadcast_done(bot, user_id, succ, fail, iv)

async def run_broadcast_task(eng, user_id, ad_id, links, delay, join, iv):
    try:
        res = await eng.broadcast_with_stealth(user_id, ad_id, links, delay, join)
        await notify_client_broadcast_done(bot, user_id, res.get("success_count", 0), res.get("failed_count", 0), iv)
    finally: await eng.stop()

async def run_jaseb_scheduler():
    last_run = {}
    while True:
        await asyncio.sleep(60)
        now = datetime.now(); now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        async with get_db() as db:
            cur = await db.execute("SELECT DISTINCT user_id, broadcast_interval_hours FROM subscriptions WHERE status='active' AND TRIM(end_date) > ?", (now_str,))
            users = await cur.fetchall()
        for uid, iv_h in users:
            iv = float(iv_h or 0.5)
            if uid not in last_run or (now - last_run[uid]).total_seconds() >= iv * 3600:
                last_run[uid] = now; asyncio.create_task(start_user_broadcast(uid))

async def main():
    await init_db()
    await bot.start(bot_token=BOT_TOKEN)
    from src.admin_handlers import init_admin_handlers
    from src.client_handlers import init_client_handlers, register_edit_jaseb_btn
    init_admin_handlers(bot, login_states, load_prices, get_package_duration_days, start_user_broadcast)
    init_client_handlers(bot, login_states, load_prices)
    register_edit_jaseb_btn(bot, login_states)
    asyncio.create_task(run_jaseb_scheduler())
    
    app = web.Application()
    app.router.add_get('/api/prices', handle_prices_api)
    app.router.add_post('/api/checkout', handle_checkout_api)
    app.router.add_get('/api/user-stats/{user_id}', handle_user_stats_api)
    app.router.add_get('/api/history/{user_id}', handle_history_api)
    app.router.add_get('/api/check-status/{trx_id}', handle_check_status_api)
    for route in list(app.router.routes()):
        app.router.add_options(route.resource.canonical, lambda r: web.Response(headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET, POST, OPTIONS", "Access-Control-Allow-Headers": "Content-Type"}))
    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(app); await runner.setup(); site = web.TCPSite(runner, '0.0.0.0', port); await site.start()
    
    await bot.run_until_disconnected()

if __name__ == '__main__': asyncio.run(main())
