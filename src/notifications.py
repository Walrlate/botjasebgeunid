"""
notifications.py — Sistem Notifikasi Terpusat GEUNID JASEB

Semua pesan notifikasi yang dikirim ke admin atau client dikelola di sini
agar mudah diubah/diperbaiki tanpa perlu sentuh file lain.
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def notify_admin_new_order(bot, admin_id: int, user_id: int, full_name: str,
                                  username: str, package_name: str, amount: int, trx_id: str):
    """Kirim notifikasi ke admin saat ada order baru masuk."""
    uname_str = f"@{username}" if username else f"ID: {user_id}"
    text = (
        "🛒 **ORDER BARU MASUK!**\n\n"
        f"👤 Client: **{full_name}** ({uname_str})\n"
        f"📦 Paket: `{package_name}`\n"
        f"💰 Nominal: Rp {amount:,}\n"
        f"🔖 Invoice: `{trx_id}`\n"
        f"🕐 Waktu: {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M')} UTC\n\n"
        "⏳ _Menunggu konfirmasi pembayaran..._"
    )
    try:
        await bot.send_message(admin_id, text)
    except Exception as e:
        logger.error(f"Gagal notif admin (new order): {e}")


async def notify_admin_payment_success(bot, admin_id: int, user_id: int, full_name: str,
                                        username: str, package_name: str, amount: int,
                                        end_date_str: str):
    """Kirim notifikasi ke admin saat pembayaran client berhasil."""
    uname_str = f"@{username}" if username else f"ID: {user_id}"
    is_ubot = "userbot" in package_name.lower()
    status_msg = "🤖 _Bot sedang meminta nomor HP userbot dari client..._" if is_ubot else "🤖 _Bot sedang meminta teks jaseb dari client..._"
    text = (
        "✅ **PEMBAYARAN SUKSES!**\n\n"
        f"👤 Client: **{full_name}** ({uname_str})\n"
        f"📦 Paket: `{package_name}`\n"
        f"💰 Total: Rp {amount:,}\n"
        f"📅 Aktif Hingga: `{end_date_str}`\n\n"
        f"{status_msg}"
    )
    try:
        await bot.send_message(admin_id, text)
    except Exception as e:
        logger.error(f"Gagal notif admin (payment success): {e}")


async def notify_client_broadcast_start(bot, user_id: int, total_groups: int, package_name: str):
    """Beri tahu client bahwa broadcast jaseb baru dimulai."""
    text = (
        "🚀 **Jaseb Anda Mulai Disebarkan!**\n\n"
        f"📦 Paket: `{package_name}`\n"
        f"🎯 Target: **{total_groups} grup LPM**\n\n"
        "⏳ _Bot sedang bekerja secara otomatis. Anda akan mendapat laporan setelah selesai._"
    )
    try:
        await bot.send_message(user_id, text)
    except Exception as e:
        logger.error(f"Gagal notif client broadcast start (user {user_id}): {e}")


async def notify_client_broadcast_done(bot, user_id: int, success_count: int,
                                        failed_count: int, next_broadcast_hours: float,
                                        success_links: list = None):
    """Kirim laporan broadcast ke client setelah siklus selesai."""
    interval_text = f"{int(next_broadcast_hours * 60)} menit" if next_broadcast_hours < 1 else f"{next_broadcast_hours} jam"
    
    text = (
        "📊 <b>Laporan Jaseb</b>\n\n"
        "📢 <b>Iklan Anda telah selesai disebarkan ke grup/LPM!</b>\n"
        f"✅ Sukses: <b>{success_count} grup</b>\n"
        f"❌ Gagal: <b>{failed_count} grup</b>\n"
        f"⏰ Broadcast berikutnya: <b>{interval_text} lagi</b> (otomatis)\n\n"
        "💡 <i>Jika ingin bukti kirim di grup tertentu, cukup kirimkan nama/username grup ke bot ini, maka saya akan mencarikan link bukti kirimnya.</i>"
    )
    
    from src.main import get_web_app_url
    from telethon.tl.types import KeyboardButtonWebView
    try:
        url = await get_web_app_url(user_id)
        if "?" in url:
            url += "&tab=history"
        else:
            url += "?tab=history"
        buttons = [[KeyboardButtonWebView(text="📋 Lihat Riwayat Lengkap", url=url)]]
        await bot.send_message(user_id, text, parse_mode='html', buttons=buttons, link_preview=False)
    except Exception as e:
        logger.error(f"Gagal notif client broadcast done dengan tombol (user {user_id}): {e}")
        try:
            await bot.send_message(user_id, text, parse_mode='html', link_preview=False)
        except Exception as e2:
            logger.error(f"Gagal fallback notif client broadcast done (user {user_id}): {e2}")


async def notify_client_subscription_expiring(bot, user_id: int, days_left: int,
                                               package_name: str, admin_username: str):
    """Peringatan ke client bahwa paketnya hampir habis."""
    urgency = "⚠️" if days_left <= 1 else "📢"
    text = (
        f"{urgency} **Paket Jaseb Anda Hampir Habis!**\n\n"
        f"📦 Paket: `{package_name}`\n"
        f"📅 Sisa: **{days_left} hari lagi**\n\n"
        f"Segera perpanjang agar jaseb tidak berhenti!\n"
        f"👉 Ketik /help untuk lihat paket & order ulang.\n"
        f"📞 Atau hubungi: {admin_username}"
    )
    try:
        await bot.send_message(user_id, text)
    except Exception as e:
        logger.error(f"Gagal notif client expiring (user {user_id}): {e}")


async def notify_admin_userbot_disconnected(bot, admin_id: int, user_id: int,
                                             full_name: str, username: str):
    """Beri tahu admin saat userbot client/admin terputus."""
    uname_str = f"@{username}" if username else f"ID: {user_id}"
    text = (
        "🔌 **Userbot Terputus!**\n\n"
        f"👤 Milik: **{full_name}** ({uname_str})\n"
        f"📅 Waktu: {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M')} UTC\n\n"
        "⚠️ _Jaseb untuk client ini dihentikan sementara sampai userbot disambungkan kembali._"
    )
    try:
        await bot.send_message(admin_id, text)
    except Exception as e:
        logger.error(f"Gagal notif admin (userbot disconnected): {e}")


async def notify_client_ad_saved(bot, user_id: int):
    """Konfirmasi ke client bahwa teks jaseb berhasil disimpan."""
    text = (
        "✅ **Teks Jaseb Berhasil Disimpan!**\n\n"
        "Sekarang, silakan kirimkan daftar username/link grup LPM kustom Anda.\n"
        "📋 Format: `@grup1 @grup2 @grup3` (maksimal 10 grup)\n\n"
        "Jika tidak punya LPM kustom dan ingin pakai LPM default sistem, ketik:\n"
        "`/skip`"
    )
    try:
        await bot.send_message(user_id, text)
    except Exception as e:
        logger.error(f"Gagal notif client ad saved (user {user_id}): {e}")
