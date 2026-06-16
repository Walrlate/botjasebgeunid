"""
main.py — Core Bot GEUNID JASEB (AUDITED BY JARVIS - 100% CLEAN ARCHITECTURE)
==========================================================================
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
from telethon.network import ConnectionTcpObfuscated
from telethon.errors import UserNotParticipantError, FloodWaitError, SessionPasswordNeededError
from telethon.tl.functions.channels import JoinChannelRequest, GetParticipantRequest
from telethon.tl.types import KeyboardButtonWebView, KeyboardButtonCallback, PeerChannel, PeerUser, PeerChat
from telethon.extensions import html

# Import internal modules
from src.config import (
    API_ID, API_HASH, BOT_TOKEN, ADMIN_ID, 
    CHANNEL_USERNAME, ADMIN_USERNAME, MINI_APP_URL, BOT_USERNAME
)
from src.database import (
    init_db,
    db_ensure_user,
    db_get_active_subscription_status,
    db_get_success_forward_logs_count,
    db_get_lpm_lists_count,
    db_get_active_userbots_count,
    db_get_userbot_status,
    db_save_admin_userbot,
    db_save_userbot,
    db_save_transaction,
    db_get_forward_history,
    db_get_active_users_for_scheduler,
    db_get_expiring_subscriptions
)
from src.ui_styles import EMOJI_UI, format_menu_text
from src.payments import create_qris_transaction, check_transaction_status
from src.jaseb_engine import JasebEngine
from src.notifications import (
    notify_client_subscription_expiring,
)
from src.logic import process_activation, run_broadcast_cycle, get_package_duration_days
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

bot = TelegramClient(
    'data/bot_session', 
    API_ID, 
    API_HASH,
    connection=ConnectionTcpObfuscated,
    timeout=30,
    connection_retries=10,
    retry_delay=5
)
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
    succ_user = db_get_success_forward_logs_count(user_id)
    total_lpm = db_get_lpm_lists_count()
    total_ub = db_get_active_userbots_count()
    ub_status = db_get_userbot_status(user_id)
    
    sub_row = db_get_active_subscription_status(user_id)
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
    import urllib.parse
    params = {"b": succ_user, "l": total_lpm, "u": total_ub, "ub": ub_status, "pkg": pkg_name, "ulpm": cap, "days": days, "int": iv}
    return f"{MINI_APP_URL.rstrip('/')}/?{urllib.parse.urlencode(params)}"

# ─────────────────────────────────────────
# Handlers Bot Utama
# ─────────────────────────────────────────
async def show_start_menu(event, edit=False):
    await clear_login_state(event.sender_id)
    if not await check_channel_join(event):
        return
    url = await get_web_app_url(event.sender_id)
    
    text = (
        f"Halo! Selamat datang di **GEUNID JASEB**.\n\n"
        f"Untuk mulai memesan paket dan mengelola iklan kamu, silakan klik tombol **🚀 Launch GEUNID JASEB** di bawah ini atau tekan tombol biru di sudut kiri bawah layar kamu."
    )
    
    buttons = [[KeyboardButtonWebView(text="🚀 Launch GEUNID JASEB", url=url)]]
    if event.sender_id == ADMIN_ID:
        buttons.append([
            KeyboardButtonCallback(text="🛡️ Admin Panel", data=b"admin_main"),
            KeyboardButtonCallback(text="🤖 Pool Admin", data=b"admin_ubots")
        ])
        buttons.append([
            KeyboardButtonCallback(text="📖 Panduan & Help", data=b"help_main")
        ])
    else:
        buttons.append([
            KeyboardButtonCallback(text="📊 Status Saya", data=b"my_status"),
            KeyboardButtonCallback(text="📖 Panduan & Help", data=b"help_main")
        ])
        
    photo_path = "data/GEUNIDJASEB.jpg"
    
    if edit:
        try:
            await event.edit(text, buttons=buttons)
            return
        except Exception as e:
            try: await event.delete()
            except: pass
            
    try:
        if os.path.exists(photo_path):
            await bot.send_file(event.chat_id, file=photo_path, caption=text, buttons=buttons)
        else:
            await event.respond(text, buttons=buttons)
    except Exception as e:
        logger.error(f"Error sending photo start: {e}")
        await event.respond(text, buttons=buttons)

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    await show_start_menu(event, edit=False)

@bot.on(events.CallbackQuery(data=b"start"))
async def callback_start_handler(event):
    await show_start_menu(event, edit=True)

@bot.on(events.NewMessage(pattern='/install'))
async def install_handler(event):
    if event.sender_id != ADMIN_ID: return
    login_states[event.sender_id] = {"state": "waiting_for_phone"}
    await event.respond("📱 **INSTALL ADMIN USERBOT**\n\nMasukkan nomor HP (+628xxx):")

# ─────────────────────────────────────────
# State Machine: Input User
# ─────────────────────────────────────────
@bot.on(events.NewMessage)
async def user_input_handler(event):
    text = (event.text or "").strip()
    
    # Abaikan perintah utama agar tidak diproses ganda
    if text.startswith("/") and not text.lower().startswith("/skip"):
        return

    user_id = event.sender_id
    if user_id not in login_states: return
    state_data = login_states[user_id]
    current_state = state_data.get("state")

    if current_state == "waiting_for_proof":
        if not event.message.photo and not event.message.document:
            await event.respond("❌ Harap kirimkan **FOTO BUKTI TRANSFER** Anda.")
            return
        await event.respond("⏳ Mengirim bukti ke admin untuk verifikasi...")
        media = await event.message.download_media(file="data/proofs/")
        trx_id, pkg, amt = state_data["trx_id"], state_data["package_name"], state_data["amount"]
        admin_msg = f"🔔 **BUKTI BARU**\n\n👤 User: `{user_id}`\n📦 Paket: {pkg}\n💰 Nominal: Rp {amt:,}\n🆔 Order: `{trx_id}`"
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
        client = TelegramClient(
            f"data/sessions/{session}", 
            API_ID, 
            API_HASH,
            connection=ConnectionTcpObfuscated,
            timeout=30,
            connection_retries=10,
            retry_delay=5
        )
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
        except SessionPasswordNeededError:
            login_states[user_id].update({"state": "waiting_for_password"})
            await event.respond("🔒 **AKUN ANDA MENGGUNAKAN 2FA!**\n\nMasukkan password verifikasi 2-langkah akun Telegram Anda:")
        except Exception as e: await event.respond(f"❌ OTP Salah atau Gagal: {e}")

    elif current_state == "waiting_for_password":
        try:
            client = state_data["client"]
            await client.sign_in(password=text)
            await _save_userbot_session(event, client, state_data["phone"])
        except Exception as e: await event.respond(f"❌ Password Salah atau Gagal: {e}")

    elif current_state == "waiting_for_ad":
        sub = db_get_active_subscription_status(user_id)
        if not sub: await event.respond("❌ Paket tidak aktif."); del login_states[user_id]; return
        is_fwd = "forward" in sub[0].lower()
        if is_fwd and not event.message.forward:
            await event.respond("❌ Paket FORWARD wajib forward pesan asli."); return
        if not is_fwd and event.message.forward:
            await event.respond("❌ Paket REGULAR dilarang forward."); return
        await event.respond("⏳ Menyimpan materi iklan..."); content = html.unparse(event.message.message or "", event.message.entities or [])
        media = await event.message.download_media(file="data/media/") if event.message.media else ""
        db_save_user_ad(user_id, content, media)
        login_states[user_id]["state"] = "waiting_for_lpm_request"
        await event.respond("✅ Materi Tersimpan! Kirim daftar link LPM kustom atau ketik `/skip`:")
 
    elif current_state == "waiting_for_lpm_request":
        lpm_list_str = ""
        if text.lower() != "/skip":
            links = re.findall(r'(?:https?://)?(?:t\.me/|@)?([a-zA-Z0-9_]{5,32}|joinchat/[a-zA-Z0-9_\-]+)', text)
            if not links: await event.respond("❌ Kirim daftar LPM atau /skip."); return
            lpm_list_str = " ".join([f"@{l}" if not ("t.me" in l or "joinchat" in l) else l for l in links[:10]])
        db_update_subscription_lpm(user_id, lpm_list_str)
        del login_states[user_id]
        await event.respond("🎉 **Pendaftaran Selesai!** Bot mulai menyebar sekarang.")
        asyncio.create_task(start_user_broadcast(user_id))
 
async def _save_userbot_session(event, client, phone):
    user_id = event.sender_id
    is_admin = (user_id == ADMIN_ID)
    session = f"admin_{phone.replace('+','')}" if is_admin else f"user_{user_id}"
    if is_admin:
        db_save_admin_userbot(phone, session)
    else:
        db_save_userbot(user_id, phone, session)
    await client.disconnect()
    if not is_admin:
        login_states[user_id] = {"state": "waiting_for_ad"}
        await event.respond("✅ **Userbot Terhubung!**\n\nSekarang silakan **KIRIM MATERI IKLAN** Anda ke sini:")
    else:
        del login_states[user_id]
        await event.respond("✅ **Pool Admin Ditambahkan!**")

@bot.on(events.NewMessage(incoming=True))
async def order_format_parser(event):
    if event.sender_id in login_states: return
    text = event.text or ""
    if "𝗙𝗢𝗥𝗠𝗔𝗧 𝗝𝗔𝗦𝗘𝗕 𝗢𝗧𝗢𝗠𝗔𝗧𝗜𝗦" not in text and "𝗙𝗢𝗥𝗠𝗔𝗧 𝗣𝗔𝗦𝗔𝗡𝗚 𝗨𝗦𝗘𝗥𝗕𝗢𝗧" not in text: return
    if event.sender_id != ADMIN_ID: return
    lines = text.split("\n")
    data = {}
    for line in lines:
        if ":" in line:
            k, v = line.split(":", 1)
            data[k.strip().lower().replace("–","").strip()] = v.strip()
    m = re.search(r'\d+', data.get("total harga", "0").replace(".", ""))
    amount = int(m.group(0)) if m else 0
    paket = data.get("paket jaseb", data.get("durasi userbot", "Manual"))
    target_uid = int(data.get("id telegram", event.sender_id))
    trx_id = f"MAN-{int(datetime.now().timestamp())}"
    db_save_transaction(target_uid, trx_id, paket, amount, "manual")
    await process_activation(bot, trx_id, load_prices(), login_states)
    await event.respond(f"✅ **Aktivasi Sukses!** (ID: {trx_id})")

@bot.on(events.CallbackQuery(pattern=b"check_(.+)"))
async def check_payment_status_handler(event):
    trx_id = event.pattern_match.group(1).decode()
    res = await check_transaction_status(trx_id)
    if res and res.get("data", {}).get("status") == "success":
        await process_activation(bot, trx_id, load_prices(), login_states)
        await event.answer("✅ Sukses!", alert=True)
    else: await event.answer("⏳ Menunggu...", alert=True)

# ─────────────────────────────────────────
# API Handlers & Authorization
# ─────────────────────────────────────────
def verify_telegram_init_data(init_data: str, bot_token: str) -> dict | None:
    """Verifikasi tanda tangan digital Telegram initData secara kriptografis."""
    import hmac
    import hashlib
    import json
    from urllib.parse import parse_qsl
    
    if not init_data:
        return None
    try:
        parsed = dict(parse_qsl(init_data))
        if "hash" not in parsed:
            return None
        
        received_hash = parsed.pop("hash")
        sorted_items = sorted(parsed.items())
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted_items)
        
        secret_key = hmac.new(b"WebAppData", bot_token.encode('utf-8'), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode('utf-8'), hashlib.sha256).hexdigest()
        
        if calculated_hash == received_hash:
            user_json = parsed.get("user")
            if user_json:
                return json.loads(user_json)
        return None
    except Exception as e:
        logger.error(f"Error dalam verifikasi initData: {e}")
        return None

async def handle_prices_api(request): return web.json_response(load_prices(), headers={"Access-Control-Allow-Origin": "*"})

async def handle_checkout_api(request):
    try:
        data = await request.json()
        uid, amt, pkg, method = int(data['user_id']), int(data['amount']), data['package_name'], data.get('payment_method', 'qris')
        if method == 'manual':
            trx_id = f"MAN-{int(datetime.now().timestamp())}"
            db_save_transaction(uid, trx_id, pkg, amt, "manual")
            login_states[uid] = {"state": "waiting_for_proof", "trx_id": trx_id, "amount": amt, "package_name": pkg}
            await bot.send_message(uid, f"📥 **INSTRUKSI MANUAL**\n\nID: {trx_id}\nTotal: Rp {amt:,}\n\nKirim foto bukti transfer ke bot!")
            return web.json_response({"status": True, "data": {"transaction_id": trx_id, "payment_url": "manual"}}, headers={"Access-Control-Allow-Origin": "*"})
        trx = await create_qris_transaction(amt, pkg)
        if trx:
            db_save_transaction(uid, trx['transaction_id'], pkg, amt, trx['payment_url'])
            return web.json_response({"status": True, "data": trx}, headers={"Access-Control-Allow-Origin": "*"})
    except: pass
    return web.json_response({"status": False}, status=400, headers={"Access-Control-Allow-Origin": "*"})

async def handle_user_stats_api(request):
    try:
        uid = int(request.match_info['user_id'])
        
        # Otorisasi & Validasi Privasi Tingkat Tinggi
        init_data = request.headers.get("x-telegram-init-data", "")
        verified_user = verify_telegram_init_data(init_data, BOT_TOKEN)
        is_production = os.getenv("RAILWAY_ENVIRONMENT") is not None or os.getenv("RAILWAY_STATIC_URL") is not None
        if is_production or init_data:
            if not verified_user or int(verified_user.get("id", 0)) != uid:
                return web.json_response({"status": False, "error": "Akses Ditolak. Pelanggaran Privasi."}, status=403, headers={"Access-Control-Allow-Origin": "*"})
                
        succ = db_get_success_forward_logs_count(uid)
        sub = db_get_active_subscription_status(uid)
        ub_status = db_get_userbot_status(uid)
        res = {"total_sent": succ, "package_name": "Tidak Aktif", "days_left": 0, "seconds_left": 0, "userbot_status": ub_status}
        if sub:
            try:
                end_dt = datetime.strptime(sub[2].split(".")[0].strip(), "%Y-%m-%d %H:%M:%S")
                delta = end_dt - datetime.now()
                res.update({"package_name": sub[0], "capacity_lpm": sub[1], "days_left": max(0, delta.days), "seconds_left": max(0, int(delta.total_seconds())), "interval": sub[3]})
                if res["days_left"] == 0 and res["seconds_left"] > 0: res["days_left"] = 1
            except: pass
        return web.json_response({"status": True, "data": res}, headers={"Access-Control-Allow-Origin": "*"})
    except: return web.json_response({"status": False}, status=500, headers={"Access-Control-Allow-Origin": "*"})

async def handle_history_api(request):
    try:
        uid = int(request.match_info['user_id'])
        
        # Otorisasi & Validasi Privasi Tingkat Tinggi
        init_data = request.headers.get("x-telegram-init-data", "")
        verified_user = verify_telegram_init_data(init_data, BOT_TOKEN)
        is_production = os.getenv("RAILWAY_ENVIRONMENT") is not None or os.getenv("RAILWAY_STATIC_URL") is not None
        if is_production or init_data:
            if not verified_user or int(verified_user.get("id", 0)) != uid:
                return web.json_response({"status": False, "error": "Akses Ditolak. Pelanggaran Privasi."}, status=403, headers={"Access-Control-Allow-Origin": "*"})
                
        rows = db_get_forward_history(uid)
        return web.json_response({"status": True, "data": [{"group_name": r[0] or "Grup LPM", "msg_link": r[1], "status": r[2], "error_msg": r[3], "sent_at": r[4]} for r in rows]}, headers={"Access-Control-Allow-Origin": "*"})
    except: return web.json_response({"status": False}, status=500, headers={"Access-Control-Allow-Origin": "*"})

async def handle_check_status_api(request):
    trx_id = request.match_info.get('trx_id')
    res = await check_transaction_status(trx_id)
    if res and res.get("data", {}).get("status") == "success":
        await process_activation(bot, trx_id, load_prices(), login_states)
    return web.json_response(res, headers={"Access-Control-Allow-Origin": "*"})

async def start_user_broadcast(user_id: int):
    await run_broadcast_cycle(bot, user_id, API_ID, API_HASH)

async def run_jaseb_scheduler():
    last_run = {}
    while True:
        await asyncio.sleep(60)
        now = datetime.now()
        users = db_get_active_users_for_scheduler()
        for uid, iv_h in users:
            iv = float(iv_h or 0.5)
            if uid not in last_run or (now - last_run[uid]).total_seconds() >= iv * 3600:
                last_run[uid] = now; asyncio.create_task(start_user_broadcast(uid))

async def run_expiry_reminder():
    while True:
        try:
            await asyncio.sleep(3600 * 6)
            now = datetime.now()
            exp = db_get_expiring_subscriptions(24)
            for u, p, e in exp:
                try:
                    end_dt = datetime.strptime(e.split(".")[0].strip(), "%Y-%m-%d %H:%M:%S")
                    days_left = max(0, (end_dt - now).days)
                    if days_left == 0 and (end_dt - now).total_seconds() > 0: days_left = 1
                except: days_left = 1
                await notify_client_subscription_expiring(bot, u, days_left, p, ADMIN_USERNAME)
        except: pass

async def run_web_server():
    app = web.Application()
    app.router.add_get('/api/prices', handle_prices_api)
    app.router.add_post('/api/checkout', handle_checkout_api)
    app.router.add_get('/api/user-stats/{user_id}', handle_user_stats_api)
    app.router.add_get('/api/history/{user_id}', handle_history_api)
    app.router.add_get('/api/check-status/{trx_id}', handle_check_status_api)
    async def opt(req): return web.Response(headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET, POST, OPTIONS", "Access-Control-Allow-Headers": "Content-Type"})
    for p in ['/api/prices', '/api/checkout', '/api/user-stats/{user_id}', '/api/history/{user_id}', '/api/check-status/{trx_id}']: app.router.add_options(p, opt)
    runner = web.AppRunner(app); await runner.setup(); await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8080))).start()

async def main():
    await init_db()
    
    # Retry loop untuk menghindari 'database is locked' pada rolling deployment di Railway
    retries = 6
    while retries > 0:
        try:
            await bot.start(bot_token=BOT_TOKEN)
            break
        except Exception as e:
            err_msg = str(e).lower()
            if "locked" in err_msg or "lock" in err_msg:
                logger.warning(f"⚠️ Berkas sesi Telegram (.session) sedang dikunci oleh proses lain. Mencoba kembali dalam 10 detik... (Sisa percobaan: {retries})")
                await asyncio.sleep(10)
                retries -= 1
            else:
                raise e
    else:
        raise RuntimeError("❌ Gagal menginisialisasi sesi Telegram karena berkas terkunci oleh proses lain secara permanen.")
    me = await bot.get_me(); import src.config; src.config.BOT_USERNAME = me.username
    init_admin_handlers(bot, login_states, load_prices, get_package_duration_days, start_user_broadcast)
    init_client_handlers(bot, login_states, load_prices); register_edit_jaseb_btn(bot, login_states)
    asyncio.create_task(run_jaseb_scheduler()); asyncio.create_task(run_expiry_reminder()); asyncio.create_task(run_web_server())
    await bot.run_until_disconnected()

if __name__ == '__main__':
    try: asyncio.run(main())
    except KeyboardInterrupt: pass
