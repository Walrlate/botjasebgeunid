"""
logic.py — Pusat Logika Bisnis GEUNID JASEB (AUDITED BY JARVIS)
==============================================================
Menangani aktivasi paket, durasi, kapasitas, dan orkestrasi broadcast.
Mencegah circular import antara main.py dan admin_handlers.py.
"""

import asyncio
import logging
import re
import os
import random
from datetime import datetime, timedelta
from telethon.tl.types import PeerChannel, PeerUser, PeerChat
from src.database import (
    db_get_transaction,
    db_get_active_subscription_id_and_end,
    db_update_subscription_dates,
    db_add_subscription,
    db_update_transaction_status,
    db_get_active_subscription_broadcast_details,
    db_get_latest_user_ad_id,
    db_get_active_lpm_lists,
    db_get_userbot_session_and_status,
    db_get_active_admin_userbots,
    db_cooldown_admin_userbot,
    db_get_lpm_sharded_for_admin
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# Helpers: Durasi & Kapasitas
# ─────────────────────────────────────────

def get_package_duration_days(package_name: str, amount: int, prices: dict) -> int:
    """Menganalisis durasi paket berdasarkan nama dan harga promo."""
    if not prices: return 30
    amount = int(amount)
    # Cek di kategori prices.json
    for category in ['regular', 'forward', 'userbot']:
        for item in prices.get(category, []):
            if int(item.get('promoPrice', 0)) == amount or int(item.get('price', 0)) == amount:
                dur_str = item.get('duration', '')
                days = int(re.search(r'(\d+)', dur_str).group(1)) if re.search(r'(\d+)', dur_str) else 30
                # Tambah bonus jika ada
                bonus = re.search(r'\+(\d+)', item.get('bonus', ''))
                if bonus: days += int(bonus.group(1))
                return days
    # Fallback ke pencarian teks di nama paket
    m = re.search(r'(\d+)\s*Hari', package_name, re.IGNORECASE)
    return int(m.group(1)) if m else 30

active_broadcasts = set()

def get_capacity_from_package(package_name: str) -> int:
    """Mendapatkan kapasitas LPM dari teks nama paket secara dinamis."""
    if "userbot" in package_name.lower():
        return 0
    m = re.search(r'(\d+)\s*LPM', package_name, re.IGNORECASE)
    if m:
        return int(m.group(1))
    for lpm in [100, 50, 30, 20]:
        if str(lpm) in package_name: return lpm
    return 20

# ─────────────────────────────────────────
# Core: Aktivasi Paket (Mutlak & Aman)
# ─────────────────────────────────────────

async def process_activation(bot, trx_id: str, prices: dict, login_states: dict):
    """
    Proses aktivasi paket tunggal yang aman dari duplikasi.
    Digunakan oleh Bot Callback, API Web, dan Admin Paste Format.
    """
    from datetime import timezone
    now = datetime.now(timezone.utc)
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    
    # 1. Lock transaksi agar tidak diproses 2x (Idempotency)
    row = db_get_transaction(trx_id)
    
    if not row:
        return False, "Transaksi tidak ditemukan."
    
    uid, amt, pkg_name, status, assigned_admin_ub_id, quantity = row
    if status == 'success':
        return True, "Sudah aktif."

    # 2. Hitung Parameter Paket
    days = get_package_duration_days(pkg_name, amt, prices)
    cap = get_capacity_from_package(pkg_name)
    
    # 3. Update atau Insert Subskripsi
    active_sub = db_get_active_subscription_id_and_end(uid)
    
    if active_sub:
        # MODE PERPANJANG
        sub_id, old_end_str, old_assigned_id = active_sub
        try:
            old_end_dt = datetime.strptime(old_end_str.split(".")[0].strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            base_date = max(old_end_dt, now)
        except:
            base_date = now
        new_end = (base_date + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        final_assigned_id = old_assigned_id if old_assigned_id is not None else assigned_admin_ub_id
        db_update_subscription_dates(sub_id, new_end, cap, pkg_name, final_assigned_id, max_userbots=quantity)
    else:
        # MODE BARU
        new_end = (now + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        db_add_subscription(uid, pkg_name, cap, now_str, new_end, assigned_admin_ub_id, max_userbots=quantity)
    
    # 4. Tandai transaksi sukses
    db_update_transaction_status(trx_id, "success")
    
    # 5. Set alur bot selanjutnya (Minta Materi / Minta HP)
    is_ubot = "userbot" in pkg_name.lower()
    login_states[uid] = {"state": "waiting_for_phone" if is_ubot else "waiting_for_ad"}
    
    # 6. Notifikasi User
    notif_msg = (
        f"🎉 **PEMBAYARAN DITERIMA!**\n\n"
        f"📦 Paket: **{pkg_name}**\n"
        f"⏳ Berlaku hingga: `{new_end[:10]}`\n\n"
    )
    if is_ubot:
        notif_msg += "🤖 Silakan kirimkan **Nomor HP** akun Telegram Anda (format: `+628xxx`):"
    else:
        notif_msg += "✍️ Silakan kirimkan **Materi Iklan** Anda (teks, foto, atau forward):"
        
    # Kirim ke user secara independen
    try:
        await bot.send_message(uid, notif_msg)
    except Exception as e:
        logger.error(f"Gagal kirim notif aktivasi ke user {uid} (kemungkinan bot diblokir): {e}")
        
    # Kirim ke admin secara independen dengan info profil dinamis
    try:
        from src.database import db_get_user_info
        u_info = db_get_user_info(uid)
        from src.config import ADMIN_ID
        from src.notifications import notify_admin_payment_success
        await notify_admin_payment_success(
            bot, int(ADMIN_ID), uid, u_info["full_name"], u_info["username"], pkg_name, amt, new_end[:10]
        )
    except Exception as e:
        logger.error(f"Gagal kirim notif aktivasi ke admin untuk user {uid}: {e}")

    # 7. Kirim Testimoni Awal Pembelian Sukses ke Channel @geunidk (dengan screenshot jika manual)
    try:
        from src.database import db_get_user_info
        u_info = db_get_user_info(uid)
        full_name = u_info["full_name"] if u_info else "Pembeli"
        username_str = f"@{u_info['username']}" if u_info and u_info.get("username") else f"ID: {uid}"
        
        testi_msg = (
            "💰 <b>TESTIMONI PEMBELIAN BARU</b> 💰\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 Pembeli: <b>{full_name}</b> ({username_str})\n"
            f"📦 Paket: <b>{pkg_name}</b>\n"
            f"💰 Nominal: <b>Rp {amt:,}</b>\n"
            f"⚡ Status: <b>Sukses & Aktif 🟢</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Terima kasih telah membeli layanan kami! 🙏\n"
            "🤖 Powered by @GeunID"
        )
        
        # Cari file screenshot bukti transfer manual
        import glob
        import os
        proof_files = glob.glob(f"data/proofs/proof_{trx_id}.*")
        proof_file = proof_files[0] if proof_files else None
        
        if proof_file and os.path.exists(proof_file):
            await bot.send_file("@geunidk", file=proof_file, caption=testi_msg, parse_mode='html')
    except Exception as testi_err:
        logger.error(f"Gagal kirim testimoni awal ke @geunidk: {testi_err}")

    # 8. Kirim Permintaan Rating / Feedback ke Pembeli
    rating_text = (
        "🙏 **Terima kasih telah menggunakan GEUNID JASEB!**\n\n"
        "Pembelian Anda telah selesai diproses. Silakan berikan bintang/feedback "
        "mengenai pengalaman transaksi Anda demi meningkatkan layanan kami:"
    )
    from telethon import Button
    buttons = [
        [
            Button.inline("⭐️ 5", f"rate_5_{trx_id}".encode()),
            Button.inline("⭐️ 4", f"rate_4_{trx_id}".encode()),
            Button.inline("⭐️ 3", f"rate_3_{trx_id}".encode())
        ],
        [
            Button.inline("⭐️ 2", f"rate_2_{trx_id}".encode()),
            Button.inline("⭐️ 1", f"rate_1_{trx_id}".encode()),
            Button.inline("❌ Skip", f"rate_skip_{trx_id}".encode())
        ]
    ]
    try:
        await bot.send_message(uid, rating_text, buttons=buttons)
    except Exception as rate_send_err:
        logger.error(f"Gagal kirim penawaran rating ke user {uid}: {rate_send_err}")
        
    return True, new_end

# ─────────────────────────────────────────
# Core: Orkestrasi Broadcast (Multi-Admin)
# ─────────────────────────────────────────

async def run_single_userbot_broadcast(bot, user_id: int, ad_id: int, session_name: str, phone: str, chunk_links: list, api_id, api_hash, subscription_id: int):
    from src.jaseb_engine import JasebEngine
    from src.userbot_manager import get_session_lock, active_clients
    
    # Ambil client aktif yang sudah terhubung — hindari membuka koneksi duplikat
    existing_client = active_clients.get(phone)
    
    async with get_session_lock(session_name):
        eng = JasebEngine(
            f"data/sessions/{session_name}",
            api_id,
            api_hash,
            existing_client=existing_client  # Injeksi client aktif jika ada
        )
        try:
            await eng.start()
            res = await eng.broadcast_with_stealth(user_id, ad_id, chunk_links, 'slowly', subscription_id=subscription_id)
            return res
        except Exception as e:
            logger.error(f"Gagal broadcast userbot pembeli {phone} ({user_id}): {e}")
            from src.database import db_update_userbot_status
            db_update_userbot_status(phone, 'disconnected')
            
            try:
                await bot.send_message(user_id, f"⚠️ **USERBOT TERPUTUS!**\n\nSesi userbot `{phone}` terputus or kedaluwarsa. Silakan sambungkan kembali via Bot.")
            except: pass
            
            try:
                from src.database import db_get_user_info
                u_info = db_get_user_info(user_id)
                from src.config import ADMIN_ID
                from src.notifications import notify_admin_userbot_disconnected
                await notify_admin_userbot_disconnected(bot, int(ADMIN_ID), user_id, u_info["full_name"], u_info["username"])
            except Exception as notif_err:
                logger.error(f"Gagal kirim notif diskoneksi userbot ke admin: {notif_err}")
                
            return {"success_count": 0, "failed_count": len(chunk_links), "success_links": []}
        finally:
            await eng.stop()

async def run_broadcast_cycle(bot, user_id: int, api_id, api_hash, subscription_id: int = None):
    """
    Eksekusi satu siklus broadcast. Menangani pemilihan pool admin atau ubot pembeli.
    """
    if user_id in active_broadcasts:
        logger.warning(f"⚠️ Broadcast untuk user {user_id} sedang berjalan. Siklus ganda diabaikan.")
        return

    # Pastikan kita memiliki subscription_id
    if subscription_id is None:
        from src.database import db_get_active_subscription_id
        sub_res = db_get_active_subscription_id(user_id)
        if sub_res:
            subscription_id = sub_res[0]
        else:
            logger.warning(f"Tidak ada subscription aktif untuk user_id {user_id}")
            return

    active_broadcasts.add(user_id)
    try:
        from src.notifications import notify_client_broadcast_done
        from datetime import timezone
        
        # 1. Ambil Langganan
        from src.database import db_get_active_subscription_broadcast_details_by_id
        sub = db_get_active_subscription_broadcast_details_by_id(subscription_id)
        if not sub: return
        
        pkg, cap, req_lpm, iv, assigned_admin_ub_id = sub
        
        # 2. Ambil Iklan
        ad = db_get_latest_user_ad_id(user_id)
        if not ad:
            try: await bot.send_message(user_id, "⚠️ Iklan Anda kosong. Gunakan /edit_jaseb.");
            except: pass
            return
        ad_id = ad[0]
        
        # 3. Siapkan Target LPM
        links = [l.strip() for l in (req_lpm or "").split() if l.strip()]
        sisa = max(0, cap - len(links))
        if sisa > 0:
            if "userbot" not in pkg.lower() and assigned_admin_ub_id:
                # Gunakan porsi LPM eksklusif (slot tetap 100 LPM) milik bot admin yang ditugaskan.
                # Fungsi sharding selalu mengembalikan 100 LPM dari slot-nya — potong sesuai kapasitas (sisa).
                sharded = db_get_lpm_sharded_for_admin(assigned_admin_ub_id)
                links.extend(sharded[:sisa])
            else:
                links.extend(db_get_active_lpm_lists(sisa))

        if "userbot" in pkg.lower():
            # JALUR USERBOT PEMBELI (Mendukung Bulk / Sharding Akun Klien)
            from src.database import db_get_userbots_by_subscription
            from src.userbot_manager import active_clients
            ubots = db_get_userbots_by_subscription(subscription_id)
            connected_ubots = [u for u in ubots if u["status"] == "connected"]
            
            if not connected_ubots:
                try: await bot.send_message(user_id, "⚠️ Seluruh akun userbot Anda terputus! Sambungkan kembali melalui Panel.");
                except: pass
                return
            
            # Ambil semua grup lokal yang diikuti oleh akun userbot ini secara otomatis
            userbot_local_groups = []
            userbot_local_links = []
            
            for ub in connected_ubots:
                phone = ub["phone_number"]
                client = active_clients.get(phone)
                if client:
                    try:
                        async for dialog in client.iter_dialogs(limit=100):
                            if dialog.is_group or dialog.is_channel:
                                title = dialog.name or "Grup Tanpa Nama"
                                username = getattr(dialog.entity, 'username', None)
                                group_link = f"https://t.me/{username}" if username else None
                                group_id = dialog.entity.id
                                member_count = getattr(dialog.entity, 'participants_count', 0) or 0
                                
                                # Siapkan data untuk database LPM admin
                                userbot_local_groups.append({
                                    "name": title,
                                    "link": group_link,
                                    "group_id": group_id,
                                    "member_count": member_count
                                })
                                
                                # Siapkan target kirim (utamakan link username, fallback ke ID grup jika privat)
                                target_send = group_link if group_link else str(group_id)
                                if target_send:
                                    userbot_local_links.append(target_send)
                    except Exception as ex_dlg:
                        logger.error(f"Error fetching local dialogs for broadcast on {phone}: {ex_dlg}")
            
            # Sinkronisasikan grup-grup tersebut ke tabel lpm_lists admin
            if userbot_local_groups:
                from src.database import db_save_userbot_groups_to_lpm
                db_save_userbot_groups_to_lpm(userbot_local_groups)
                
            # Gabungkan dengan target khusus pembeli (req_lpm)
            custom_links = [l.strip() for l in (req_lpm or "").split() if l.strip()]
            
            # Gabungkan target (hindari duplikat)
            target_links = list(dict.fromkeys(custom_links + userbot_local_links))
            
            # Batasi target_links agar tidak melebihi kapasitas (cap) jika cap > 0
            if cap > 0:
                target_links = target_links[:cap]
            
            # Fallback jika target link kosong sama sekali, ambil dari LPM global
            if not target_links:
                target_links = db_get_active_lpm_lists(cap if cap > 0 else 50)
                
            # Bagi target LPM secara merata ke seluruh ubot yang online
            chunks = [target_links[i::len(connected_ubots)] for i in range(len(connected_ubots))]
            
            tasks = []
            for idx, ub in enumerate(connected_ubots):
                sess = ub["session_name"]
                phone = ub["phone_number"]
                chunk_links = chunks[idx]
                if not chunk_links: continue
                
                tasks.append(run_single_userbot_broadcast(
                    bot, user_id, ad_id, sess, phone, chunk_links, api_id, api_hash, subscription_id
                ))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            total_success = 0
            total_failed = 0
            all_success_links = []
            
            for r in results:
                if isinstance(r, dict):
                    total_success += r.get("success_count", 0)
                    total_failed += r.get("failed_count", 0)
                    all_success_links.extend(r.get("success_links", []))
                elif isinstance(r, Exception):
                    logger.error(f"Error in single userbot broadcast task: {r}")
            
            await notify_client_broadcast_done(bot, user_id, total_success, total_failed, iv or 0.5, all_success_links)
        else:
            # JALUR POOL ADMIN (Slot Terikat / Fallback Global)
            assigned_admin = None
            if assigned_admin_ub_id:
                from src.database import db_get_admin_userbot_by_id
                assigned_admin = db_get_admin_userbot_by_id(assigned_admin_ub_id)
            
            # Kumpulkan daftar admin yang akan memproses broadcast
            admins_to_use = []
            if assigned_admin and assigned_admin[3] == 'connected':
                # Masukkan bot admin eksklusif terpilih ke daftar utama
                admins_to_use.append((assigned_admin[0], assigned_admin[1], assigned_admin[2]))
            
            # Ambil sisa admin yang aktif sebagai cadangan (fallback jika bot utama limit/off)
            active_pool = db_get_active_admin_userbots()
            
            # Saring agar tidak menduplikasi bot utama dalam daftar
            assigned_id = assigned_admin[2] if assigned_admin else None
            backups = [a for a in active_pool if a[2] != assigned_id]
            
            # Satukan: Bot utama di depan, diikuti oleh bot-bot cadangan (smart redirect)
            admins_to_use.extend(backups)
            
            if not admins_to_use:
                logger.error(f"Pool Admin Kosong untuk user {user_id}")
                try: await bot.send_message(user_id, "⚠️ **Sistem Sibuk:** Seluruh bot admin sedang limit atau offline. Silakan hubungi admin.")
                except: pass
                return
                
            unprocessed = links.copy()
            custom_set = set([l.strip() for l in (req_lpm or "").split() if l.strip()])
            total_succ = 0
            total_fail = 0
            total_success_links = []
            
            is_redirected = False
            
            for sess, phone, aid in admins_to_use:
                if not unprocessed: break
                
                # Jika bot saat ini bukan bot utama, ganti jatah slot LPM dengan slot milik bot saat ini
                if assigned_id and aid != assigned_id:
                    unprocessed_custom = [lnk for lnk in unprocessed if lnk in custom_set]
                    unprocessed_slot_count = len(unprocessed) - len(unprocessed_custom)
                    
                    if unprocessed_slot_count > 0:
                        new_slot_links = db_get_lpm_sharded_for_admin(aid)
                        new_slot_to_send = new_slot_links[:unprocessed_slot_count]
                        unprocessed = unprocessed_custom + new_slot_to_send
                        logger.info(f"🔄 Smart Redirect: Mengganti {unprocessed_slot_count} slot LPM dengan slot milik bot {phone}")
                
                # Jika kita beralih ke bot cadangan di tengah jalan (Smart Redirect)
                if assigned_id and aid != assigned_id and not is_redirected:
                    is_redirected = True
                    logger.info(f"🔄 Smart Redirect aktif: Mengalihkan sisa iklan user {user_id} ke bot cadangan {phone} karena bot utama limit.")
                    try:
                        await bot.send_message(user_id, f"🔄 **Smart Redirect:** Bot utama Anda sedang beristirahat (limit). Pengiriman dialihkan ke bot cadangan `{phone}` agar iklan tetap selesai terkirim.")
                    except: pass
                
                from src.userbot_manager import get_session_lock
                async with get_session_lock(sess):
                    eng = JasebEngine(f"data/sessions/{sess}", api_id, api_hash)
                    try:
                        await eng.start()
                        res = await eng.broadcast_with_stealth(user_id, ad_id, unprocessed, 'slowly' if 'regular' in pkg.lower() else 'instant')
                        total_succ += res.get("success_count", 0)
                        total_fail += res.get("failed_count", 0)
                        total_success_links.extend(res.get("success_links", []))
                        unprocessed = res.get("unprocessed_links", [])
                        
                        if res.get("floodwait_seconds", 0) > 300:
                            until = (datetime.now(timezone.utc) + timedelta(seconds=res["floodwait_seconds"])).strftime("%Y-%m-%d %H:%M:%S")
                            db_cooldown_admin_userbot(aid, until)
                            
                            # Jika bot admin limit/floodwait, ubah statusnya ke disconnected agar Mini App tahu ada gangguan
                            from src.database import db_update_admin_userbot_status
                            db_update_admin_userbot_status(aid, "disconnected")
                            continue
                        
                        if not unprocessed:
                            break
                    except Exception as ex:
                        logger.error(f"Error pada bot admin {phone} saat broadcast: {ex}")
                        # Jika error koneksi/kredensial, ubah status admin ke disconnected
                        from src.database import db_update_admin_userbot_status
                        db_update_admin_userbot_status(aid, "disconnected")
                        continue
                    finally:
                        await eng.stop()
                
            await notify_client_broadcast_done(bot, user_id, total_succ, total_fail, iv or 0.5, total_success_links)
    finally:
        active_broadcasts.discard(user_id)
