"""
main.py — Core Bot GEUNID JASEB
================================
"""

import asyncio
import logging
import re
import os
import json
from datetime import datetime, timedelta

from telethon import TelegramClient, events, Button
from telethon.errors import UserNotParticipantError
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.tl.types import KeyboardButtonWebView, KeyboardButtonCallback, KeyboardButtonUrl, PeerChannel, PeerUser, PeerChat
from telethon.extensions import html

from src.config import API_ID, API_HASH, BOT_TOKEN, ADMIN_ID, CHANNEL_USERNAME, ADMIN_USERNAME, MINI_APP_URL
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

# ─────────────────────────────────────────
# Konfigurasi Logging
# ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

os.makedirs("data/sessions", exist_ok=True)
bot = TelegramClient('data/bot_session', API_ID, API_HASH)

login_states = {}

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
    for category in ['regular', 'forward', 'userbot']:
        for item in prices.get(category, []):
            if int(item.get('promoPrice', 0)) == int(amount):
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
        text = format_menu_text("WAJIB BERGABUNG CHANNEL", f"Harap bergabung ke {CHANNEL_USERNAME} untuk menggunakan bot.")
        buttons = [[Button.url("🚀 Gabung Channel", invite_link)], [Button.inline("🔄 Cek Status", b"check_join_status")]]
        await event.respond(text, buttons=buttons)
        return False
    except: return True

@bot.on(events.CallbackQuery(data=b"check_join_status"))
async def check_join_status_handler(event):
    if await check_channel_join(event):
        await event.answer("✅ Akses aktif.", alert=True)
        await _show_start_menu(event, is_callback=True)

# ─────────────────────────────────────────
# API Handlers
# ─────────────────────────────────────────
from aiohttp import web

async def handle_user_stats_api(request):
    user_id = None
    try:
        raw_user_id = request.match_info.get('user_id')
        if not raw_user_id: return web.json_response({"status": False, "error": "ID required"}, status=400)
        user_id = int(raw_user_id)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        async with get_db() as db:
            cur = await db.execute("SELECT COUNT(*) FROM forward_logs WHERE user_id=? AND status='success'", (user_id,))
            total_sent = (await cur.fetchone())[0]
            cur = await db.execute("SELECT COUNT(*) FROM forward_logs WHERE user_id=? AND status='failed'", (user_id,))
            total_failed = (await cur.fetchone())[0]
            cur = await db.execute("SELECT package_name, capacity_lpm, end_date, broadcast_interval_hours FROM subscriptions WHERE user_id=? AND status='active' AND TRIM(end_date) > ? ORDER BY end_date DESC LIMIT 1", (user_id, now_str))
            sub = await cur.fetchone()
            cur = await db.execute("SELECT status FROM userbots WHERE user_id=?", (user_id,))
            ub_row = await cur.fetchone()
            ub_status = ub_row[0] if ub_row else 'disconnected'

        user_package, user_lpm, user_days, user_seconds_left, user_interval = 'Tidak Aktif', 0, 0, 0, 0.5
        if sub:
            user_package, user_lpm, end_date, interval = sub
            user_interval = float(interval or 0.5)
            try:
                end_dt = datetime.strptime(end_date.split(".")[0].strip(), "%Y-%m-%d %H:%M:%S")
                delta = end_dt - datetime.now()
                user_seconds_left = max(0, int(delta.total_seconds()))
                user_days = max(0, delta.days)
                if user_seconds_left > 0 and user_days == 0: user_days = 1
            except: pass

        return web.json_response({"status": True, "data": {"total_sent": total_sent, "total_failed": total_failed, "package_name": user_package, "capacity_lpm": user_lpm, "days_left": user_days, "seconds_left": user_seconds_left, "interval": user_interval, "userbot_status": ub_status}}, headers={"Access-Control-Allow-Origin": "*"})
    except Exception as e: return web.json_response({"status": False, "error": str(e)}, status=500, headers={"Access-Control-Allow-Origin": "*"})

async def handle_history_api(request):
    try:
        user_id = int(request.match_info.get('user_id'))
        async with get_db() as db:
            cur = await db.execute("SELECT l.group_name, f.msg_link, f.status, f.error_msg, f.sent_at FROM forward_logs f LEFT JOIN lpm_lists l ON f.group_id = l.group_id WHERE f.user_id=? ORDER BY f.sent_at DESC LIMIT 50", (user_id,))
            rows = await cur.fetchall()
        history = [{"group_name": r[0] or "Grup LPM", "msg_link": r[1], "status": r[2], "error_msg": r[3], "sent_at": r[4]} for r in rows]
        return web.json_response({"status": True, "data": history}, headers={"Access-Control-Allow-Origin": "*"})
    except Exception as e: return web.json_response({"status": False, "error": str(e)}, status=500, headers={"Access-Control-Allow-Origin": "*"})

async def handle_prices_api(request):
    try:
        prices = load_prices()
        return web.json_response(prices, headers={"Access-Control-Allow-Origin": "*"})
    except: return web.json_response({"error": "server error"}, status=500, headers={"Access-Control-Allow-Origin": "*"})

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
                days = max(0, (end_dt - datetime.now()).days)
                if days == 0 and (end_dt - datetime.now()).total_seconds() > 0: days = 1
            except: pass
    import urllib.parse
    return f"{MINI_APP_URL.rstrip('/')}/?b={total_sent_user}&l={total_lpm_global}&u=0&ub={urllib.parse.quote(ub_row[0] if ub_row else 'disconnected')}&pkg={urllib.parse.quote(pkg_name)}&ulpm={cap}&days={days}&int={iv}"

# ─────────────────────────────────────────
# Handlers Bot Utama
# ─────────────────────────────────────────
@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    await clear_login_state(event.sender_id)
    await _show_start_menu(event)

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

@bot.on(events.CallbackQuery(data=b"profile"))
async def profile_handler(event):
    user_id = int(event.sender_id)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with get_db() as db:
        cur = await db.execute("SELECT package_name, capacity_lpm, end_date, broadcast_interval_hours FROM subscriptions WHERE user_id=? AND status='active' AND TRIM(end_date) > ? ORDER BY end_date DESC LIMIT 1", (user_id, now_str))
        sub = await cur.fetchone()
        cur = await db.execute("SELECT COUNT(*) FROM forward_logs WHERE user_id=? AND status='success'", (user_id,))
        total_sent = (await cur.fetchone())[0]
    
    text = f"👤 **PROFIL ANDA**\n\nID: `{user_id}`\n"
    if sub:
        text += f"📦 Paket: {sub[0]}\n🎯 Kapasitas: {sub[1]} LPM\n📅 Habis: {sub[2][:10]}\n📤 Terkirim: {total_sent} pesan"
    else: text += "❌ Tidak ada paket aktif."
    await event.edit(text, buttons=[[Button.inline("⬅️ Kembali", b"start")]])

# ─────────────────────────────────────────
# State Machine & Login
# ─────────────────────────────────────────
@bot.on(events.NewMessage)
async def user_input_handler(event):
    if event.sender_id not in login_states: return
    state_data = login_states[event.sender_id]
    current_state = state_data.get("state", "")
    text = (event.text or "").strip()
    if text.startswith("/") and text.lower() != "/skip": return

    if current_state == "waiting_for_phone":
        phone = text.replace(" ", "")
        is_admin = (event.sender_id == ADMIN_ID)
        session = f"admin_{phone[1:]}" if is_admin else f"user_{event.sender_id}"
        client = TelegramClient(f"data/sessions/{session}", API_ID, API_HASH)
        await client.connect()
        try:
            res = await client.send_code_request(phone)
            login_states[event.sender_id].update({"state": "waiting_for_otp", "phone": phone, "client": client, "hash": res.phone_code_hash})
            await event.respond("📨 Masukkan OTP:")
        except Exception as e: await event.respond(f"❌ Error: {e}"); await clear_login_state(event.sender_id)

    elif current_state == "waiting_for_otp":
        try:
            await state_data["client"].sign_in(state_data["phone"], text, phone_code_hash=state_data["hash"])
            await _save_userbot_session(event, state_data["client"], state_data["phone"])
        except Exception as e: await event.respond(f"❌ Error: {e}")

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
# Order Parser & Manual
# ─────────────────────────────────────────
@bot.on(events.NewMessage(incoming=True))
async def order_format_parser(event):
    if event.sender_id in login_states: return
    text = event.text or ""
    if not ("𝗙𝗢𝗥𝗠𝗔𝗧 𝗝𝗔𝗦𝗘𝗕 𝗢𝗧𝗢𝗠𝗔𝗧𝗜𝗦" in text or "𝗙𝗢𝗥𝗠𝗔𝗧 𝗣𝗔𝗦𝗔𝗡𝗚 𝗨𝗦𝗘𝗥𝗕𝗢𝗧" in text): return
    # Basic Parser
    lines = text.split("\n")
    data = {}
    for line in lines:
        if ":" in line:
            k, v = line.split(":", 1)
            data[k.strip().replace("–","").lower()] = v.strip()
    
    amount = 0
    m = re.search(r'\d+', data.get("total harga", "0"))
    if m: amount = int(m.group(0).replace(".",""))
    paket = data.get("paket jaseb", "Paket Jaseb")
    
    import time, random
    trx_id = f"MAN-{int(time.time())}"
    async with get_db() as db:
        await db.execute("INSERT INTO transactions (user_id, trx_id, package_id, amount, payment_url, status) VALUES (?, ?, ?, ?, 'manual', 'pending')", (event.sender_id, trx_id, paket, amount))
        await db.commit()
    await process_successful_payment(trx_id)
    await event.respond(f"✅ Pesanan manual diaktifkan: `{trx_id}`")

async def process_successful_payment(trx_id: str):
    async with get_db() as db:
        cur = await db.execute("SELECT user_id, amount, package_id FROM transactions WHERE trx_id=?", (trx_id,))
        row = await cur.fetchone()
        if not row: return
        uid, amt, pkg = row
        days = get_package_duration_days(pkg, amt)
        cap = get_capacity_from_package(pkg)
        end = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        await db.execute("UPDATE transactions SET status='success' WHERE trx_id=?", (trx_id,))
        await db.execute("INSERT INTO subscriptions (user_id, package_name, capacity_lpm, start_date, end_date, status, broadcast_interval_hours) VALUES (?, ?, ?, datetime('now'), ?, 'active', 0.5)", (uid, pkg, cap, end))
        await db.commit()
    await bot.send_message(uid, f"🎉 Paket **{pkg}** Anda telah AKTIF!")

@bot.on(events.CallbackQuery(pattern=b"check_(.+)"))
async def check_payment_status_handler(event):
    trx_id = event.pattern_match.group(1).decode()
    res = await check_transaction_status(trx_id)
    if res and res.get("data", {}).get("status") == "success":
        await process_successful_payment(trx_id)
        await event.answer("✅ Pembayaran Terverifikasi!", alert=True)
    else: await event.answer("⏳ Belum ada pembayaran.", alert=True)

# ─────────────────────────────────────────
# Orchestration Jaseb
# ─────────────────────────────────────────
async def start_user_broadcast(user_id: int):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with get_db() as db:
        cur = await db.execute("SELECT package_name, capacity_lpm, request_lpm, broadcast_interval_hours FROM subscriptions WHERE user_id=? AND status='active' AND TRIM(end_date) > ? ORDER BY end_date DESC LIMIT 1", (user_id, now_str))
        sub = await cur.fetchone()
        if not sub: return
        pkg, cap, req_lpm, iv = sub
        cur = await db.execute("SELECT id FROM user_ads WHERE user_id=? ORDER BY created_at DESC LIMIT 1", (user_id,))
        ad = await cur.fetchone()
        if not ad: return
        ad_id = ad[0]
    
    lpm_links = [l.strip() for l in (req_lpm or "").split()]
    sisa = max(0, cap - len(lpm_links))
    if sisa > 0:
        async with get_db() as db:
            cur = await db.execute("SELECT group_link FROM lpm_lists WHERE is_active=1 AND is_blacklisted=0 ORDER BY member_count DESC LIMIT ?", (sisa,))
            lpm_links.extend(r[0] for r in await cur.fetchall())

    if "userbot" in pkg.lower():
        async with get_db() as db:
            cur = await db.execute("SELECT session_name, status FROM userbots WHERE user_id=?", (user_id,))
            ub = await cur.fetchone()
        if ub and ub[1] == 'connected':
            engine = JasebEngine(f"data/sessions/{ub[0]}", API_ID, API_HASH)
            await engine.start()
            asyncio.create_task(run_broadcast_task(engine, user_id, ad_id, lpm_links, 'slowly', True, iv or 0.5))
    else:
        async with get_db() as db:
            cur = await db.execute("SELECT session_name, phone_number, id FROM admin_userbots WHERE status='connected' AND (cooldown_until IS NULL OR cooldown_until < ?) ORDER BY RANDOM()", (now_str,))
            admins = await cur.fetchall()
        if admins: asyncio.create_task(run_admin_pool_broadcast_task(user_id, ad_id, lpm_links, pkg, admins, iv or 0.5))

async def run_admin_pool_broadcast_task(user_id, ad_id, links, pkg, admins, iv):
    unprocessed = links.copy(); succ = fail = 0
    for sess, phone, aid in admins:
        if not unprocessed: break
        engine = JasebEngine(f"data/sessions/{sess}", API_ID, API_HASH)
        try:
            await engine.start()
            res = await engine.broadcast_with_stealth(user_id, ad_id, unprocessed, 'slowly' if 'regular' in pkg.lower() else 'instant')
            succ += res.get("success_count", 0); fail += res.get("failed_count", 0); unprocessed = res.get("unprocessed_links", [])
            if res.get("floodwait_seconds", 0) > 300:
                until = (datetime.now() + timedelta(seconds=res["floodwait_seconds"])).strftime("%Y-%m-%d %H:%M:%S")
                async with get_db() as db: await db.execute("UPDATE admin_userbots SET cooldown_until=? WHERE id=?", (until, aid)); await db.commit()
                continue
            break
        finally: await engine.stop()
    await notify_client_broadcast_done(bot, user_id, succ, fail, iv)

async def run_broadcast_task(engine, user_id, ad_id, links, delay, join, iv):
    try:
        res = await engine.broadcast_with_stealth(user_id, ad_id, links, delay, join)
        await notify_client_broadcast_done(bot, user_id, res.get("success_count", 0), res.get("failed_count", 0), iv)
    finally: await engine.stop()

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

async def run_web_server():
    app = web.Application()
    app.router.add_get('/api/prices', handle_prices_api)
    app.router.add_post('/api/checkout', handle_checkout_api)
    app.router.add_get('/api/user-stats/{user_id}', handle_user_stats_api)
    app.router.add_get('/api/history/{user_id}', handle_history_api)
    for route in list(app.router.routes()):
        app.router.add_options(route.resource.canonical, lambda r: web.Response(headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET, POST, OPTIONS", "Access-Control-Allow-Headers": "Content-Type"}))
    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(app); await runner.setup(); site = web.TCPSite(runner, '0.0.0.0', port); await site.start()

async def main():
    await init_db()
    await bot.start(bot_token=BOT_TOKEN)
    me = await bot.get_me(); import src.config; src.config.BOT_USERNAME = me.username
    from src.admin_handlers import init_admin_handlers
    init_admin_handlers(bot, login_states, load_prices, get_package_duration_days, start_user_broadcast)
    asyncio.create_task(run_jaseb_scheduler()); asyncio.create_task(run_web_server())
    await bot.run_until_disconnected()

if __name__ == '__main__': asyncio.run(main())
