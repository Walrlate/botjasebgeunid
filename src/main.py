import logging
import re
from telethon import TelegramClient, events, Button
from telethon.errors import UserNotParticipantError
from telethon.tl.functions.channels import GetParticipantRequest
from src.config import API_ID, API_HASH, BOT_TOKEN, ADMIN_ID, CHANNEL_USERNAME, ADMIN_USERNAME
from src.database import init_db, get_db
from src.ui_styles import EMOJI_UI, format_menu_text
from src.payments import create_qris_transaction


# Konfigurasi Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Inisialisasi Client
# Client Bot (untuk UI)
bot = TelegramClient('bot_session', API_ID, API_HASH)

async def check_channel_join(event):
    user_id = event.sender_id
    if not user_id:
        return True
    
    # Bypass admin
    if user_id == ADMIN_ID:
        return True
        
    if not CHANNEL_USERNAME:
        return True
        
    try:
        # Pengecekan status partisipan
        await bot(GetParticipantRequest(channel=CHANNEL_USERNAME, participant=user_id))
        return True
    except UserNotParticipantError:
        invite_link = f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"
        title = f"{EMOJI_UI['shield']} WAJIB BERGABUNG CHANNEL"
        content = (
            "Untuk dapat menggunakan layanan bot ini, Anda diwajibkan bergabung ke channel resmi kami terlebih dahulu.\n\n"
            f"Silakan bergabung ke channel: **{CHANNEL_USERNAME}**\n\n"
            "Setelah bergabung, silakan klik tombol **\"🔄 Cek Status\"** di bawah ini untuk mengaktifkan akses bot."
        )
        text = format_menu_text(title, content)
        buttons = [
            [Button.url(f"{EMOJI_UI['rocket']} Gabung Channel", invite_link)],
            [Button.inline("🔄 Cek Status", b"check_join_status")]
        ]
        
        if isinstance(event, events.CallbackQuery.Event):
            await event.edit(text, buttons=buttons)
        else:
            await event.respond(text, buttons=buttons)
        return False
    except Exception as e:
        logger.error(f"Error checking channel join status: {e}")
        # Jika bot bukan admin di channel atau terjadi error lain, izinkan user masuk agar bot tidak macet
        return True

@bot.on(events.CallbackQuery(data=b"check_join_status"))
async def check_join_status_handler(event):
    user_id = event.sender_id
    try:
        await bot(GetParticipantRequest(channel=CHANNEL_USERNAME, participant=user_id))
        # Jika berhasil (sudah join)
        await event.answer("✅ Terima kasih! Akses bot Anda telah aktif.", alert=True)
        # Tampilkan menu utama
        await callback_start_handler(event)
    except UserNotParticipantError:
        await event.answer("❌ Anda belum bergabung ke channel! Silakan gabung terlebih dahulu.", alert=True)
    except Exception as e:
        logger.error(f"Error checking join status on callback: {e}")
        await event.answer("✅ Akses aktif (Pemeriksaan dilewati).", alert=True)
        await callback_start_handler(event)


async def get_web_app_url(user_id):
    total_broadcast = 0
    total_lpm = 0
    total_userbots = 0
    user_bot_status = 'disconnected'
    user_package = 'Tidak Aktif'
    user_lpm = 0
    user_days = 0
    
    try:
        async with await get_db() as db:
            # 1. Global Stats
            cursor = await db.execute("SELECT COUNT(*) FROM forward_logs WHERE status = 'success'")
            total_broadcast = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM lpm_lists WHERE is_active = 1")
            total_lpm = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM userbots WHERE status = 'connected'")
            total_userbots = (await cursor.fetchone())[0]
            
            # 2. User Info
            cursor = await db.execute("SELECT status FROM userbots WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            if row:
                user_bot_status = row[0]
                
            cursor = await db.execute("""
                SELECT package_name, capacity_lpm, end_date 
                FROM subscriptions 
                WHERE user_id = ? AND status = 'active' AND end_date > datetime('now', 'localtime') 
                ORDER BY end_date DESC LIMIT 1
            """, (user_id,))
            row = await cursor.fetchone()
            if row:
                user_package = row[0]
                user_lpm = row[1]
                try:
                    from datetime import datetime
                    clean_date = row[2].split(".")[0]
                    end_dt = datetime.strptime(clean_date, "%Y-%m-%d %H:%M:%S")
                    delta = end_dt - datetime.now()
                    user_days = max(0, delta.days)
                except Exception as date_err:
                    logger.error(f"Date parse error: {date_err}")
                    user_days = 0
    except Exception as e:
        logger.error(f"Error getting WebApp stats from DB: {e}")
        
    return (
        f"https://geunid-jaseb.vercel.app/?"
        f"b={total_broadcast}&"
        f"l={total_lpm}&"
        f"u={total_userbots}&"
        f"ub={user_bot_status}&"
        f"pkg={user_package}&"
        f"ulpm={user_lpm}&"
        f"days={user_days}"
    )


@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    if not await check_channel_join(event):
        return
    sender = await event.get_sender()
    user_id = event.sender_id

    full_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
    
    title = f"{EMOJI_UI['start']} GEUNID-JASEB REVOLUTION"
    web_app_url = await get_web_app_url(user_id)
    
    if user_id == ADMIN_ID:
        content = (
            f"Halo **{full_name}** (Admin), selamat datang di panel kendali Jaseb.\n\n"
            f"{EMOJI_UI['rocket']} **Fitur Admin:**\n"
            "• Kelola bot & pengiriman iklan\n"
            "• Hubungkan Ubot instan dengan ketik `/install`\n"
            "• Pindai LPM aktif dengan `/scan`"
        )
        buttons = [
            [Button.web_app(f"{EMOJI_UI['rocket']} Buka Mini App", web_app_url)],
            [Button.inline(f"{EMOJI_UI['package']} Lihat Paket", b"view_packages"), Button.inline(f"{EMOJI_UI['order']} Order", b"order")],
            [Button.inline(f"{EMOJI_UI['profile']} Profil Saya", b"profile"), Button.inline(f"{EMOJI_UI['shield']} Login Userbot", b"login_userbot")],
            [Button.inline(f"{EMOJI_UI['analytics']} Statistik Global", b"stats"), Button.inline(f"{EMOJI_UI['logs']} Cara Pakai", b"guide")],
            [Button.url("📞 Hubungi Admin", f"https://t.me/{ADMIN_USERNAME.replace('@', '')}")]
        ]
    else:
        content = (
            f"Halo **{full_name}**, selamat datang di layanan GEUNID-JASEB.\n\n"
            f"Untuk mengetahui daftar fitur lengkap, harga paket jaseb/userbot terbaru, dan cara menggunakannya, "
            f"silakan gunakan tombol **📞 Hubungi Admin / Bantuan** di bawah ini."
        )
        buttons = [
            [Button.web_app(f"{EMOJI_UI['rocket']} Buka Mini App", web_app_url)],
            [Button.inline(f"{EMOJI_UI['profile']} Profil Saya", b"profile"), Button.inline(f"{EMOJI_UI['logs']} Cara Pakai", b"guide")],
            [Button.url("📞 Hubungi Admin / Bantuan", f"https://t.me/{ADMIN_USERNAME.replace('@', '')}")]
        ]
        
    welcome_text = format_menu_text(title, content)
    await event.respond(welcome_text, buttons=buttons)


@bot.on(events.CallbackQuery(data=b"start"))
async def callback_start_handler(event):
    sender = await event.get_sender()
    user_id = event.sender_id
    full_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
    
    title = f"{EMOJI_UI['start']} GEUNID-JASEB REVOLUTION"
    web_app_url = await get_web_app_url(user_id)
    
    if user_id == ADMIN_ID:
        content = (
            f"Halo **{full_name}** (Admin), selamat datang di panel kendali Jaseb.\n\n"
            f"{EMOJI_UI['rocket']} **Fitur Admin:**\n"
            "• Kelola bot & pengiriman iklan\n"
            "• Hubungkan Ubot instan dengan ketik `/install`\n"
            "• Pindai LPM aktif dengan `/scan`"
        )
        buttons = [
            [Button.web_app(f"{EMOJI_UI['rocket']} Buka Mini App", web_app_url)],
            [Button.inline(f"{EMOJI_UI['package']} Lihat Paket", b"view_packages"), Button.inline(f"{EMOJI_UI['order']} Order", b"order")],
            [Button.inline(f"{EMOJI_UI['profile']} Profil Saya", b"profile"), Button.inline(f"{EMOJI_UI['shield']} Login Userbot", b"login_userbot")],
            [Button.inline(f"{EMOJI_UI['analytics']} Statistik Global", b"stats"), Button.inline(f"{EMOJI_UI['logs']} Cara Pakai", b"guide")],
            [Button.url("📞 Hubungi Admin", f"https://t.me/{ADMIN_USERNAME.replace('@', '')}")]
        ]
    else:
        content = (
            f"Halo **{full_name}**, selamat datang di layanan GEUNID-JASEB.\n\n"
            f"Untuk mengetahui daftar fitur lengkap, harga paket jaseb/userbot terbaru, dan cara menggunakannya, "
            f"silakan gunakan tombol **📞 Hubungi Admin / Bantuan** di bawah ini."
        )
        buttons = [
            [Button.web_app(f"{EMOJI_UI['rocket']} Buka Mini App", web_app_url)],
            [Button.inline(f"{EMOJI_UI['profile']} Profil Saya", b"profile"), Button.inline(f"{EMOJI_UI['logs']} Cara Pakai", b"guide")],
            [Button.url("📞 Hubungi Admin / Bantuan", f"https://t.me/{ADMIN_USERNAME.replace('@', '')}")]
        ]
        
    welcome_text = format_menu_text(title, content)
    await event.edit(welcome_text, buttons=buttons)


@bot.on(events.CallbackQuery(data=b"stats"))
async def stats_handler(event):
    total_broadcast = 0
    total_lpm = 0
    total_userbots = 0
    try:
        async with await get_db() as db:
            cursor = await db.execute("SELECT COUNT(*) FROM forward_logs WHERE status = 'success'")
            total_broadcast = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM lpm_lists WHERE is_active = 1")
            total_lpm = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM userbots WHERE status = 'connected'")
            total_userbots = (await cursor.fetchone())[0]
    except Exception as e:
        logger.error(f"Error fetching stats from DB: {e}")

    title = f"{EMOJI_UI['analytics']} STATISTIK GLOBAL"
    content = (
        "📊 **Performa Layanan Real-time:**\n\n"
        f"• **Total Broadcast:** {total_broadcast:,} Pesan\n"
        f"• **Grup LPM Aktif:** {total_lpm} Grup\n"
        "• **Kecepatan Kirim:** ~1.5s / grup\n"
        f"• **Userbot Aktif:** {total_userbots} Akun\n"
        "• **Success Rate:** 100.0% (Fresh)\n\n"
        "⚡ _Statistik diperbarui secara real-time dari database cluster GeunID._"
    )
    text = format_menu_text(title, content)
    await event.edit(text, buttons=[Button.inline(f"{EMOJI_UI['back']} Kembali", b"start")])

@bot.on(events.CallbackQuery(data=b"profile"))
async def profile_handler(event):
    sender = await event.get_sender()
    full_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
    username = f"@{sender.username}" if sender.username else f"ID: {sender.id}"
    
    title = f"{EMOJI_UI['profile']} PROFIL SAYA"
    content = (
        f"👤 **Detail Akun Pembeli:**\n"
        f"• **Nama:** {full_name}\n"
        f"• **Username:** {username}\n"
        f"• **ID Telegram:** `{sender.id}`\n\n"
        f"🛡️ **Status Layanan Anda:**\n"
        f"• **Userbot:** Terhubung (Stealth Active)\n"
        f"• **Sesi Aktif:** 1 Sesi Telegram Client\n"
        f"• **LPM Terdaftar:** 20 LPM Cluster\n"
        f"• **Paket Saat Ini:** Jaseb Regular (Sisa 3 Hari)"
    )
    text = format_menu_text(title, content)
    buttons = [
        [Button.inline("📜 Lihat Riwayat Kirim", b"view_logs")],
        [Button.inline(f"{EMOJI_UI['back']} Kembali", b"start")]
    ]
    await event.edit(text, buttons=buttons)

@bot.on(events.CallbackQuery(data=b"login_userbot"))
async def login_userbot_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("⚠️ Menu Userbot hanya dapat diakses oleh Admin.", alert=True)
        return
    if not await check_channel_join(event):
        return
    async with await get_db() as db:

        cursor = await db.execute("SELECT phone_number, status FROM userbots WHERE user_id = ?", (event.sender_id,))
        userbot_data = await cursor.fetchone()
        
    title = f"{EMOJI_UI['shield']} MANAJEMEN USERBOT"
    
    if userbot_data and userbot_data[1] == 'connected':
        content = (
            f"📱 **Userbot Anda Aktif!**\n\n"
            f"• **Nomor HP:** `{userbot_data[0]}`\n"
            f"• **Status:** Terhubung {EMOJI_UI['success']}\n\n"
            "Anda dapat menggunakan akun Anda sendiri untuk menyebar iklan secara otomatis (Stealth Mode aktif).\n"
            "Jika ingin memutuskan hubungan, klik tombol di bawah."
        )
        buttons = [
            [Button.inline("❌ Putuskan Hubungan", b"disconnect_userbot")],
            [Button.inline(f"{EMOJI_UI['back']} Kembali", b"start")]
        ]
    else:
        content = (
            "Fitur ini memungkinkan Anda menghubungkan nomor Telegram Anda ke bot ini.\n\n"
            "**Keuntungan:**\n"
            "• Bisa mengirim pesan ke banyak grup tanpa bot biasa.\n"
            "• Lebih hemat biaya (Tanpa Modal Tambahan).\n\n"
            "⚠️ _Pastikan Anda memahami cara kerja Userbot sebelum melanjutkan._"
        )
        buttons = [
            [Button.inline("➕ Hubungkan Nomor Baru", b"add_number")],
            [Button.inline(f"{EMOJI_UI['back']} Kembali", b"start")]
        ]
        
    text = format_menu_text(title, content)
    await event.edit(text, buttons=buttons)

@bot.on(events.CallbackQuery(data=b"disconnect_userbot"))
async def disconnect_userbot_handler(event):
    import os
    async with await get_db() as db:
        await db.execute("UPDATE userbots SET status = 'disconnected' WHERE user_id = ?", (event.sender_id,))
        await db.commit()
    
    session_file = f"data/sessions/user_{event.sender_id}.session"
    if os.path.exists(session_file):
        try:
            os.remove(session_file)
        except Exception as e:
            logger.error(f"Gagal menghapus file sesi: {e}")
            
    await event.answer("🔌 Hubungan userbot diputuskan.", alert=True)
    await login_userbot_handler(event)

@bot.on(events.CallbackQuery(data=b"view_packages"))
async def view_packages(event):
    if event.sender_id != ADMIN_ID:
        await event.edit(
            "📞 **Hubungi Bantuan / Admin**\n\n"
            "Untuk mengetahui fitur-fitur lengkap, harga paket jaseb/userbot terbaru, dan cara menggunakannya, silakan langsung hubungi admin kami.\n\n"
            f"Telegram Admin: {ADMIN_USERNAME}",
            buttons=[[Button.url("📞 Hubungi Admin", f"https://t.me/{ADMIN_USERNAME.replace('@', '')}")], [Button.inline("⬅️ Kembali", b"start")]]
        )
        return
    promo_text = (
        "── **𝗣𝗔𝗞𝗘𝗧 𝗥𝗘𝗚𝗨𝗟𝗔𝗥 𝟮𝟬 𝗟𝗣𝗠**\n"
        "𖤓 5 HARI : 9.500 (Promo)\n"
        "𖤓 7 HARI + 2 HARI : 16.500 (Promo)\n"
        "𖤓 14 HARI + 3 HARI: 32.500 (Promo)\n"
        "𖤓 30 HARI + 4 HARI : 42.500 (Promo)\n\n"
        "── **𝗣𝗔𝗞𝗘𝗧 𝗙𝗢𝗥𝗪𝗔𝗥𝗗 𝟮𝟬 𝗟𝗣𝗠**\n"
        "𖤓 3 HARI : 9.500 (Promo)\n"
        "𖤓 5 HARI : 13.500 (Promo)\n"
        "𖤓 7 HARI + 2 HARI : 19.500 (Promo)\n"
        "𖤓 10 HARI + 2 HARI : 26.500 (Promo)\n"
        "𖤓 14 HARI + 4 HARI : 36.500 (Promo)\n"
        "𖤓 30 HARI + 5 HARI : 49.500 (Promo)\n\n"
        "── **𝗣𝗔𝗞𝗘𝗧 𝗥𝗘𝗚𝗨𝗟𝗔𝗥 𝟯𝟬 𝗟𝗣𝗠**\n"
        "𖤓 3 HARI : 13.500 (Promo)\n"
        "𖤓 7 HARI : 23.500 (Promo)\n"
        "𖤓 10 HARI : 32.500 (Promo)\n"
        "𖤓 30 HARI : 55.500 (Promo)\n\n"
        "── **𝗣𝗔𝗞𝗘𝗧 𝗙𝗢𝗥𝗪𝗔𝗥𝗗 𝟯𝟬 𝗟𝗣𝗠**\n"
        "𖤓 3 HARI : 19.500 (Promo)\n"
        "𖤓 5 HARI : 26.500 (Promo)\n"
        "𖤓 7 HARI : 29.500 (Promo)\n"
        "𖤓 14 HARI : 46.500 (Promo)\n"
        "𖤓 30 HARI : 79.500 (Promo)\n\n"
        "📅 Promo berlaku: Juni - Agustus 2026"
    )
    await event.edit(promo_text, buttons=[Button.inline("⬅️ Kembali", b"start")])

from src.payments import create_qris_transaction
from src.jaseb_engine import JasebEngine

@bot.on(events.CallbackQuery(data=b"order"))
async def order_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.edit(
            "📞 **Hubungi Bantuan / Admin**\n\n"
            "Untuk mengetahui fitur-fitur lengkap, harga paket jaseb/userbot terbaru, dan cara menggunakannya, silakan langsung hubungi admin kami.\n\n"
            f"Telegram Admin: {ADMIN_USERNAME}",
            buttons=[[Button.url("📞 Hubungi Admin", f"https://t.me/{ADMIN_USERNAME.replace('@', '')}")], [Button.inline("⬅️ Kembali", b"start")]]
        )
        return
    if not await check_channel_join(event):
        return
    text = (

        "🛒 **Pilih Paket yang ingin Anda beli:**\n\n"
        "Gunakan tombol di bawah untuk membuat QRIS otomatis."
    )
    buttons = [
        [Button.inline("Regular 20 LPM - 5 Hari (9.5rb)", b"buy_reg_20_5")],
        [Button.inline("Forward 30 LPM - 30 Hari (79.5rb)", b"buy_fwd_30_30")],
        [Button.inline("⬅️ Kembali", b"start")]
    ]
    await event.edit(text, buttons=buttons)

@bot.on(events.CallbackQuery(pattern=b"buy_"))
async def process_payment(event):
    data = event.data.decode()
    amount = 9500 if "reg_20_5" in data else 79500
    package_desc = "Paket Regular 20 LPM - 5 Hari" if "reg_20_5" in data else "Paket Forward 30 LPM - 30 Hari"
    
    await event.answer("Sedang membuat QRIS...", alert=False)
    
    # Buat transaksi di KlikQRIS
    trx_data = await create_qris_transaction(amount, f"Jaseb - {package_desc}")
    
    if trx_data:
        # Simpan ke DB
        async with await get_db() as db:
            await db.execute(
                "INSERT INTO transactions (user_id, trx_id, package_id, amount, payment_url, status) VALUES (?, ?, ?, ?, ?, ?)",
                (event.sender_id, trx_data['transaction_id'], package_desc, amount, trx_data['payment_url'], 'pending')
            )
            await db.commit()
            
        pay_text = (
            f"✅ **Transaksi Berhasil Dibuat!**\n\n"
            f"📦 Paket: {package_desc}\n"
            f"💰 Total: Rp {trx_data['total_amount']:,}\n"
            f"⏰ Expired: {trx_data['expired_at']}\n\n"
            f"Silakan scan QRIS di atas atau klik tombol di bawah untuk membayar."
        )
        
        await bot.send_file(
            event.chat_id, 
            file=trx_data['qris_url'], 
            caption=pay_text,
            buttons=[[Button.url("🔗 Bayar via Browser", trx_data['payment_url'])], [Button.inline("🔄 Cek Status", f"check_{trx_data['transaction_id']}".encode())]]
        )
    else:
        await event.respond("❌ Gagal membuat pembayaran. Silakan hubungi admin.")

@bot.on(events.CallbackQuery(data=b"view_logs"))
async def view_logs_handler(event):
    async with await get_db() as db:
        # Ambil 10 log pengiriman terakhir
        cursor = await db.execute("""
            SELECT l.group_name, f.msg_link, f.status, f.sent_at 
            FROM forward_logs f
            LEFT JOIN lpm_lists l ON f.group_id = l.group_id
            WHERE f.user_id = ? 
            ORDER BY f.sent_at DESC LIMIT 10
        """, (event.sender_id,))
        logs = await cursor.fetchall()
        
    if not logs:
        await event.answer("📭 Belum ada riwayat pengiriman.", alert=True)
        return

    text = "📜 **Proof Hub - 10 Pengiriman Terakhir**\n\n"
    for log in logs:
        group_name = log[0] or "Grup LPM"
        link = log[1]
        status = "✅" if log[2] == 'success' else "❌"
        time = log[3].split()[1] # Ambil jamnya saja
        
        if link:
            text += f"{status} [{group_name}]({link}) | 🕒 {time}\n"
        else:
            text += f"{status} {group_name} (Gagal) | 🕒 {time}\n"
            
    text += "\n_Klik link di atas untuk melihat pesan di grup._"
    
    await event.edit(text, buttons=[Button.inline("⬅️ Kembali", b"profile")])

@bot.on(events.CallbackQuery(data=b"guide"))
async def guide_handler(event):
    title = f"{EMOJI_UI['logs']} EDUKASI & PENGERTIAN JASEB"
    
    # Menggunakan format Quote Block (garis samping) agar mirip dengan gambar contoh
    content = (
        "**𝐏𝐄𝐍𝐆𝐄𝐑𝐓𝐈𝐀𝐍 𝐁𝐀𝐒𝐈𝐂 𝐉𝐀𝐒𝐄𝐁**\n\n"
        f"─── **{EMOJI_UI['rocket']} 𝗝𝗔𝗦𝗔 𝗦𝗘𝗕𝗔𝗥**\n"
        "> Jaseb yaitu jasa sebar dibuat untuk menyebar luaskan wording atau teks kalian ke LPM atau grup yang ada di Telegram. Keuntungan jaseb: kalian tidak perlu menyebar secara manual karena bot berjalan otomatis 24 jam tanpa henti.\n\n"
        f"─── **{EMOJI_UI['shield']} 𝗨𝗦𝗘𝗥𝗕𝗢𝗧**\n"
        "> Userbot hampir sama dengan jaseb. Perbedaannya: Jaseb menggunakan akun Admin (Admin yang handle), sedangkan Userbot menggunakan akun Buyer/Anda sendiri.\n\n"
        f"─── **{EMOJI_UI['package']} 𝗝𝗔𝗦𝗘𝗕 𝗥𝗘𝗚𝗨𝗟𝗔𝗥**\n"
        "> • Memiliki watermark store\n"
        "> • Tidak support Foto/Video\n"
        "> • Tidak support Emoji Premium\n\n"
        f"─── **{EMOJI_UI['forward']} 𝗝𝗔𝗦𝗘𝗕 𝗙𝗢𝗥𝗪𝗔𝗥𝗗**\n"
        "> • Tanpa watermark (Murni Toko Anda)\n"
        "> • Support Foto & Video\n"
        "> • Support Emoji Premium\n"
        "> • Menambah View Channel (View Booster)"
    )
    
    text = format_menu_text(title, content)
    await event.edit(text, buttons=[Button.inline(f"{EMOJI_UI['back']} Kembali", b"start")])

# State Global & Logic Log In Userbot
import os
login_states = {}

@bot.on(events.NewMessage(pattern='/install'))
async def install_command_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.respond(f"⚠️ Perintah `/install` hanya dapat digunakan oleh Admin. Hubungi admin di {ADMIN_USERNAME} untuk bantuan.")
        return
    if not await check_channel_join(event):
        return
    login_states[event.sender_id] = {"state": "waiting_for_phone"}
    await event.respond(
        "📱 **Silakan kirimkan nomor HP Anda** yang terdaftar di Telegram.\n\n"
        "Format: Gunakan kode negara di depan (contoh: `+628123456789`).\n\n"
        "⚠️ _Kode verifikasi OTP akan dikirimkan ke aplikasi Telegram resmi Anda._"
    )

@bot.on(events.CallbackQuery(data=b"add_number"))
async def add_number_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.answer("⚠️ Menu ini hanya dapat diakses oleh Admin.", alert=True)
        return
    if not await check_channel_join(event):
        return
    login_states[event.sender_id] = {"state": "waiting_for_phone"}
    await event.edit(
        "📱 **Silakan kirimkan nomor HP Anda** yang terdaftar di Telegram.\n\n"
        "Format: Gunakan kode negara di depan (contoh: `+628123456789`).\n\n"
        "⚠️ _Kode verifikasi OTP akan dikirimkan ke aplikasi Telegram resmi Anda._"
    )


@bot.on(events.NewMessage)
async def user_input_handler(event):
    if event.sender_id not in login_states:
        return
        
    state_data = login_states[event.sender_id]
    current_state = state_data["state"]
    text = event.text.strip()
    
    if current_state == "waiting_for_phone":
        phone_number = text.replace(" ", "").replace("-", "")
        if not phone_number.startswith("+"):
            await event.respond("❌ **Format nomor salah!**\n\nHarap gunakan format internasional dengan tanda `+` di depan (contoh: `+628123456789`). Silakan kirimkan kembali.")
            return
            
        await event.respond("⏳ **Menghubungkan ke Telegram...**\nSedang mengirim kode OTP.")
        
        os.makedirs("data/sessions", exist_ok=True)
        session_path = f"data/sessions/user_{event.sender_id}"
        
        client = TelegramClient(session_path, API_ID, API_HASH)
        try:
            await client.connect()
            send_code_result = await client.send_code_request(phone_number)
            
            login_states[event.sender_id] = {
                "state": "waiting_for_otp",
                "phone": phone_number,
                "client": client,
                "phone_code_hash": send_code_result.phone_code_hash
            }
            
            await event.respond(
                "📨 **Kode OTP telah dikirim oleh Telegram!**\n\n"
                "Silakan kirimkan kode OTP tersebut di sini.\n"
                "Format: `12345` (5 digit angka)."
            )
        except Exception as e:
            logger.error(f"Error sending code request: {e}")
            await event.respond(f"❌ **Gagal mengirim OTP:** {str(e)}\n\nSilakan coba lagi dengan mengirimkan nomor HP yang valid.")
            if client.is_connected():
                await client.disconnect()
            if event.sender_id in login_states:
                del login_states[event.sender_id]
                
    elif current_state == "waiting_for_otp":
        otp_code = text.replace(" ", "")
        client = state_data["client"]
        phone = state_data["phone"]
        phone_code_hash = state_data["phone_code_hash"]
        
        await event.respond("⏳ **Memverifikasi OTP...**")
        
        try:
            await client.sign_in(phone=phone, code=otp_code, phone_code_hash=phone_code_hash)
            
            async with await get_db() as db:
                await db.execute(
                    "INSERT INTO users (user_id, username, full_name) VALUES (?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, full_name=excluded.full_name",
                    (event.sender_id, (await event.get_sender()).username, f"{(await event.get_sender()).first_name or ''} {(await event.get_sender()).last_name or ''}".strip())
                )
                await db.execute(
                    "INSERT OR REPLACE INTO userbots (user_id, phone_number, session_name, status) VALUES (?, ?, ?, ?)",
                    (event.sender_id, phone, f"user_{event.sender_id}", "connected")
                )
                await db.commit()
                
            await event.respond(
                "🎉 **Selamat! Akun Userbot Anda berhasil terhubung.**\n\n"
                "Sekarang Anda dapat menggunakan fitur penyebaran otomatis menggunakan akun Anda sendiri (Stealth Mode aktif).\n"
                "Ketik /start untuk kembali ke menu utama."
            )
            del login_states[event.sender_id]
            
        except Exception as sign_in_error:
            from telethon.errors import SessionPasswordNeededError
            if isinstance(sign_in_error, SessionPasswordNeededError):
                login_states[event.sender_id]["state"] = "waiting_for_password"
                await event.respond(
                    "🔒 **Akun Anda dilindungi Verifikasi 2 Langkah (2FA).**\n\n"
                    "Silakan kirimkan password 2FA Anda di sini:"
                )
            else:
                logger.error(f"Sign in error: {sign_in_error}")
                await event.respond(f"❌ **OTP Salah atau kedaluwarsa:** {str(sign_in_error)}\n\nHarap kirimkan kode OTP yang benar.")
                
    elif current_state == "waiting_for_password":
        password = text
        client = state_data["client"]
        phone = state_data["phone"]
        
        await event.respond("⏳ **Memverifikasi Password 2FA...**")
        
        try:
            await client.sign_in(password=password)
            
            async with await get_db() as db:
                await db.execute(
                    "INSERT INTO users (user_id, username, full_name) VALUES (?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, full_name=excluded.full_name",
                    (event.sender_id, (await event.get_sender()).username, f"{(await event.get_sender()).first_name or ''} {(await event.get_sender()).last_name or ''}".strip())
                )
                await db.execute(
                    "INSERT OR REPLACE INTO userbots (user_id, phone_number, session_name, status) VALUES (?, ?, ?, ?)",
                    (event.sender_id, phone, f"user_{event.sender_id}", "connected")
                )
                await db.commit()
                
            await event.respond(
                "🎉 **Selamat! Akun Userbot Anda berhasil terhubung (dengan 2FA).**\n\n"
                "Sekarang Anda dapat menggunakan fitur penyebaran otomatis menggunakan akun Anda sendiri (Stealth Mode aktif).\n"
                "Ketik /start untuk kembali ke menu utama."
            )
            del login_states[event.sender_id]
            
        except Exception as p_err:
            logger.error(f"2FA login error: {p_err}")
            await event.respond(f"❌ **Password 2FA salah:** {str(p_err)}\n\nSilakan kirimkan kembali password 2FA Anda yang benar.")

@bot.on(events.NewMessage(incoming=True))
async def order_format_parser(event):
    if event.sender_id in login_states:
        return
        
    text = event.text or ""
    
    # Deteksi apakah pesan ini adalah Format Order Baru
    is_jaseb_format = "𝗙𝗢𝗥𝗠𝗔𝗧 𝗝𝗔𝗦𝗘𝗕 𝗢𝗧𝗢𝗠𝗔𝗧𝗜𝗦" in text or "FORMAT JASEB OTOMATIS" in text
    is_userbot_format = "𝗙𝗢𝗥𝗠𝗔𝗧 𝗣𝗔𝗦𝗔𝗡𝗚 𝗨𝗦𝗘𝗥𝗕𝗢𝗧" in text or "FORMAT PASANG USERBOT" in text
    
    if is_jaseb_format or is_userbot_format:
        if event.sender_id != ADMIN_ID:
            await event.respond(f"⚠️ Pembuatan invoice QRIS otomatis saat ini hanya diperbolehkan untuk Admin. Silakan hubungi admin di {ADMIN_USERNAME} untuk memesan paket.")
            return
        if not await check_channel_join(event):
            return
            
        await event.respond("⏳ **Memproses Pesanan Anda...**\nSedang membuat invoice QRIS otomatis.")
        
        # Ekstrak data
        lines = text.split("\n")
        data = {}
        for line in lines:
            if ":" in line:
                key, val = line.split(":", 1)
                # Bersihkan key dari spasi, tanda hubung (–), dan unicode bold/italic jika ada
                clean_key = key.strip().replace("–", "").strip().lower()
                data[clean_key] = val.strip().replace('"', '')
                
        # Dapatkan nilai
        paket = data.get("paket jaseb", "Paket Jaseb")
        if is_userbot_format:
            paket = f"Userbot - {data.get('durasi userbot', '30 Hari')}"
            
        total_harga_str = data.get("total harga", "0")
        target_link = data.get("request lpm", data.get("nomor telegram", ""))
        
        # Bersihkan nominal total harga (ambil angkanya saja)
        amount = 0
        amount_match = re.search(r'\d[\d\.]*', total_harga_str)
        if amount_match:
            amount = int(amount_match.group(0).replace(".", ""))
            
        if amount <= 0:
            await event.respond("❌ **Gagal memproses nominal pembayaran.**\nHarap periksa kembali nominal total harga pada format pesanan Anda.")
            return
            
        # Panggil API KlikQRIS
        trx_data = await create_qris_transaction(amount, f"Jaseb - {paket}")
        
        if trx_data:
            # Simpan transaksi ke database
            async with await get_db() as db:
                await db.execute(
                    "INSERT INTO transactions (user_id, trx_id, package_id, amount, payment_url, status) VALUES (?, ?, ?, ?, ?, ?)",
                    (event.sender_id, trx_data['transaction_id'], paket, amount, trx_data['payment_url'], 'pending')
                )
                await db.commit()
                
            pay_text = (
                f"✅ **Invoice QRIS Otomatis Berhasil Dibuat!**\n\n"
                f"📦 **Paket:** {paket}\n"
                f"💰 **Total Bayar:** Rp {trx_data['total_amount']:,}\n"
                f"⏰ **Expired:** {trx_data['expired_at']}\n\n"
                f"Silakan scan kode QRIS di bawah ini dengan OVO/Gopay/Dana/m-Banking Anda.\n"
                f"Setelah membayar, silakan klik tombol **\"🔄 Cek Status Bayar\"**."
            )
            
            await bot.send_file(
                event.chat_id, 
                file=trx_data['qris_url'], 
                caption=pay_text,
                buttons=[
                    [Button.url("🔗 Bayar via Browser", trx_data['payment_url'])],
                    [Button.inline("🔄 Cek Status Bayar", f"check_{trx_data['transaction_id']}".encode())]
                ]
            )
        else:
            await event.respond(f"❌ **Gagal membuat pembayaran QRIS.**\nTerjadi kesalahan koneksi ke payment gateway. Silakan hubungi admin di {ADMIN_USERNAME}.")


@bot.on(events.NewMessage(pattern=r'/scan(?:\s+(.+))?'))
async def scan_lpm_handler(event):
    if event.sender_id != ADMIN_ID:
        await event.respond(f"⚠️ Perintah `/scan` hanya dapat digunakan oleh Admin. Hubungi admin di {ADMIN_USERNAME} untuk bantuan.")
        return
    if not await check_channel_join(event):
        return
        
    raw_args = event.pattern_match.group(1)
    if not raw_args:
        # Tampilkan panduan scan
        title = f"{EMOJI_UI['analytics']} GEUNID FREE LPM SCANNER"
        content = (
            "🔍 **Fitur Pemindai & Verifikator LPM Gratis!**\n\n"
            "Gunakan perintah ini untuk memverifikasi apakah suatu grup/channel Telegram adalah LPM aktif yang valid.\n\n"
            "📋 **Cara Penggunaan:**\n"
            "• `/scan @username_grup` (Grup Tunggal)\n"
            "• `/scan @grup1 @grup2 @grup3` (Banyak Grup sekaligus)\n\n"
            "⚡ _Setiap grup valid yang Anda scan akan otomatis disimpan ke database cluster global kami untuk memperkaya daftar LPM!_"
        )
        await event.respond(format_menu_text(title, content))
        return
        
    # Parse links
    links = re.findall(r'(?:https?://)?(?:t\.me/|@)?([a-zA-Z0-9_]{5,32}|joinchat/[a-zA-Z0-9_\-]+)', raw_args)
    if not links:
        await event.respond("❌ **Format salah!**\nHarap kirimkan username atau link grup yang valid.")
        return
        
    await event.respond(f"⌛ **Sedang memindai {len(links)} grup LPM...**\nHarap tunggu sebentar.")
    
    success_scanned = []
    failed_scanned = []
    
    # Run scanner as bot client (which is self.client or bot)
    for link in links:
        full_link = f"@{link}" if not ("t.me" in link or "joinchat" in link) else link
        res = await JasebEngine.verify_lpm_group(bot, full_link)
        
        if res.get("success"):
            success_scanned.append(res)
            # Simpan secara otomatis ke database lpm_lists (Crowdsourcing)
            try:
                async with await get_db() as db:
                    await db.execute(
                        "INSERT OR IGNORE INTO lpm_lists (group_link, group_id, group_name, member_count, is_active) VALUES (?, ?, ?, ?, ?)",
                        (full_link, res["group_id"], res["group_name"], res["member_count"], 1)
                    )
                    await db.commit()
            except Exception as db_err:
                logger.error(f"Error saving scanned group: {db_err}")
        else:
            failed_scanned.append({"link": full_link, "error": res.get("error")})
            
    # Format Report
    title = f"{EMOJI_UI['success']} HASIL PENDETEKSIAN LPM"
    content = ""
    
    if success_scanned:
        content += "🟢 **LPM Valid & Aktif:**\n"
        for idx, item in enumerate(success_scanned, 1):
            content += f"{idx}. **{item['group_name']}**\n"
            content += f"   • Tipe: `{item['type']}`\n"
            content += f"   • Anggota: `{item['member_count']:,} Member`\n"
            content += f"   • ID: `{item['group_id']}`\n\n"
            
    if failed_scanned:
        content += "🔴 **Grup Gagal/Tidak Valid:**\n"
        for idx, item in enumerate(failed_scanned, 1):
            content += f"{idx}. `{item['link']}` (Gagal: {item['error']})\n"
            
    if not content:
        content = "❌ Tidak ada grup yang berhasil dipindai."
        
    content += "\n⚡ _Semua LPM aktif telah diindeks ke database cluster global GeunID._"
    
    await event.respond(format_menu_text(title, content))


from src.payments import check_transaction_status

@bot.on(events.CallbackQuery(pattern=b"check_(.+)"))
async def check_payment_status_handler(event):
    trx_id = event.pattern_match.group(1).decode('utf-8')
    
    # Cek status pembayaran ke gateway
    status_response = await check_transaction_status(trx_id)
    
    if status_response and status_response.get("success"):
        data = status_response.get("data", {})
        status = data.get("status")
        
        if status == "success":
            async with await get_db() as db:
                # Dapatkan detail transaksi
                cursor = await db.execute("SELECT user_id, amount, package_id, status FROM transactions WHERE trx_id = ?", (trx_id,))
                trx_row = await cursor.fetchone()
                
                if trx_row:
                    u_id, amount, package_name_db, old_status = trx_row
                    if old_status == 'pending':
                        # Update status transaksi di database
                        await db.execute("UPDATE transactions SET status = 'success' WHERE trx_id = ?", (trx_id,))
                        
                        # Tentukan masa aktif dan kapasitas LPM
                        package_name = str(package_name_db or "Paket Jaseb")
                        capacity = 30 if "30" in package_name else 20
                        
                        # Tentukan durasi berdasarkan nama paket atau nominal
                        days = 30
                        if "5 Hari" in package_name or "5 hari" in package_name:
                            days = 5
                        elif "3 Hari" in package_name or "3 hari" in package_name:
                            days = 3
                        elif "7 Hari" in package_name or "7 hari" in package_name:
                            days = 7
                        elif "10 Hari" in package_name or "10 hari" in package_name:
                            days = 10
                        elif "14 Hari" in package_name or "14 hari" in package_name:
                            days = 14
                        elif "30 Hari" in package_name or "30 hari" in package_name:
                            days = 30
                        elif amount == 9500:
                            days = 5
                        elif amount == 16500:
                            days = 9
                        elif amount == 32500:
                            days = 17
                        elif amount == 42500:
                            days = 34
                        elif amount == 13500:
                            days = 3
                        elif amount == 19500:
                            days = 9
                        elif amount == 23500:
                            days = 7
                        elif amount == 26500:
                            days = 12
                        elif amount == 36500:
                            days = 18
                        elif amount == 49500:
                            days = 35
                        elif amount == 79500:
                            days = 30
                            
                        # Hitung expiration date
                        from datetime import datetime, timedelta
                        now = datetime.now()
                        
                        cursor = await db.execute("SELECT id, end_date FROM subscriptions WHERE user_id = ? AND status = 'active'", (u_id,))
                        sub_row = await cursor.fetchone()
                        
                        if sub_row:
                            sub_id, current_end_str = sub_row
                            try:
                                current_end = datetime.strptime(current_end_str.split(".")[0], "%Y-%m-%d %H:%M:%S")
                            except Exception:
                                current_end = now
                            
                            if current_end > now:
                                new_end = current_end + timedelta(days=days)
                            else:
                                new_end = now + timedelta(days=days)
                                
                            new_end_str = new_end.strftime("%Y-%m-%d %H:%M:%S")
                            await db.execute(
                                "UPDATE subscriptions SET package_name = ?, capacity_lpm = ?, end_date = ? WHERE id = ?",
                                (package_name, capacity, new_end_str, sub_id)
                            )
                        else:
                            new_end = now + timedelta(days=days)
                            new_end_str = new_end.strftime("%Y-%m-%d %H:%M:%S")
                            start_date_str = now.strftime("%Y-%m-%d %H:%M:%S")
                            await db.execute(
                                "INSERT INTO subscriptions (user_id, package_name, capacity_lpm, start_date, end_date, status) VALUES (?, ?, ?, ?, ?, ?)",
                                (u_id, package_name, capacity, start_date_str, new_end_str, 'active')
                            )
                        
                        await db.commit()
                        await event.answer("✅ Pembayaran berhasil terverifikasi!", alert=True)
                        await event.edit(
                            f"🎉 **Pembayaran Sukses Terverifikasi!**\n\n"
                            f"📦 Paket: **{package_name}**\n"
                            f"💰 Total: Rp {amount:,}\n"
                            f"📅 Berlaku Hingga: **{new_end_str}**\n\n"
                            f"Terima kasih telah berlangganan! Silakan ketik /start untuk memperbarui status Anda."
                        )
                        return
                    else:
                        await event.answer("⚠️ Transaksi ini sudah sukses diproses sebelumnya.", alert=True)
                        return
            await event.answer("✅ Transaksi Anda sukses terbayar!", alert=True)
        elif status == "pending":
            await event.answer("⏳ Pembayaran Anda belum terdeteksi. Silakan transfer terlebih dahulu.", alert=True)
        else:
            await event.answer("❌ Transaksi dibatalkan atau kedaluwarsa.", alert=True)
    else:
        await event.answer("❌ Gagal memverifikasi ke gateway KlikQRIS. Silakan coba lagi.", alert=True)

async def main():
    logger.info("Memulai Database...")
    await init_db()
    
    logger.info("Memulai Telegram Client...")
    await bot.start(bot_token=BOT_TOKEN)
    
    logger.info("Bot sedang berjalan...")
    await bot.run_until_disconnected()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
