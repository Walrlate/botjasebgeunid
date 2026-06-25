"""
database.py — Data Access Layer (DAL) ke Supabase (PostgreSQL)
GeunID Jaseb Master - Enterprise Edition
==============================================================
Menggantikan seluruh dependensi aiosqlite dengan Supabase Client.
"""

import os
import logging
import random
from datetime import datetime, timedelta, timezone
from src.supabase_client import get_supabase

logger = logging.getLogger(__name__)

def parse_utc_date(date_str: str) -> datetime:
    """Mengubah format ISO Supabase (UTC) ke timezone-aware UTC datetime."""
    if not date_str:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        clean = date_str.replace("Z", "+00:00")
        return datetime.fromisoformat(clean)
    except:
        try:
            clean = date_str.replace("T", " ").split(".")[0].split("+")[0].strip()
            dt = datetime.strptime(clean, "%Y-%m-%d %H:%M:%S")
            return dt.replace(tzinfo=timezone.utc)
        except:
            return datetime.min.replace(tzinfo=timezone.utc)

def normalize_date(date_str: str) -> str:
    """Mengubah format ISO dari Supabase ke format YYYY-MM-DD HH:MM:SS untuk kompatibilitas."""
    if not date_str:
        return ""
    try:
        date_str = date_str.replace("T", " ")
        if "+" in date_str:
            date_str = date_str.split("+")[0]
        if "." in date_str:
            date_str = date_str.split(".")[0]
        return date_str.strip()
    except Exception as e:
        logger.error(f"Error normalizing date {date_str}: {e}")
        return date_str

async def init_db():
    """Inisialisasi koneksi ke Supabase dan memverifikasi koneksi dengan test query."""
    try:
        supabase = get_supabase()
        # Test query ringan untuk verifikasi kredensial
        supabase.table("users").select("user_id").limit(1).execute()
        logger.info("✅ Supabase Enterprise DAL Berhasil Diinisialisasi dan Terverifikasi.")
        return True
    except Exception as e:
        logger.error(f"❌ Gagal inisialisasi Supabase DAL: {e}")
        raise e

def db_ensure_user(user_id: int, username: str = "", full_name: str = ""):
    """Memastikan user_id sudah ada di tabel users dan memperbarui profil terbaru."""
    try:
        supabase = get_supabase()
        res = supabase.table("users").select("user_id").eq("user_id", user_id).execute()
        
        insert_data = {
            "user_id": user_id,
            "username": username or "",
            "full_name": full_name or "",
        }
        
        if not res.data:
            supabase.table("users").insert(insert_data).execute()
            logger.info(f"👤 User baru terdaftar otomatis: {user_id}")
        else:
            # Selalu update data profil terbaru jika parameter tidak kosong
            if username or full_name:
                update_data = {}
                if username: update_data["username"] = username
                if full_name: update_data["full_name"] = full_name
                if update_data:
                    supabase.table("users").update(update_data).eq("user_id", user_id).execute()
    except Exception as e:
        logger.error(f"Error in db_ensure_user untuk {user_id}: {e}")

def db_get_user_info(user_id: int) -> dict:
    """Mengambil username dan full_name user berdasarkan user_id dari Supabase."""
    try:
        supabase = get_supabase()
        res = supabase.table("users").select("username, full_name").eq("user_id", user_id).execute()
        if res.data:
            row = res.data[0]
            return {
                "username": row.get("username") or "",
                "full_name": row.get("full_name") or "Client"
            }
    except Exception as e:
        logger.error(f"Error in db_get_user_info untuk {user_id}: {e}")
    return {"username": "", "full_name": "Client"}

# ─────────────────────────────────────────
# HELPER LANGGANAN (SUBSCRIPTIONS)
# ─────────────────────────────────────────

def db_get_active_subscription_id(user_id: int):
    try:
        supabase = get_supabase()
        now_str = datetime.now(timezone.utc).isoformat()
        res = supabase.table("subscriptions")\
            .select("id")\
            .eq("user_id", user_id)\
            .eq("status", "active")\
            .gt("end_date", now_str)\
            .order("end_date", desc=True)\
            .limit(1)\
            .execute()
        if res.data:
            return (res.data[0]["id"],)
        return None
    except Exception as e:
        logger.error(f"Error in db_get_active_subscription_id: {e}")
        return None

def db_get_active_subscription_status(user_id: int):
    try:
        supabase = get_supabase()
        now_str = datetime.now(timezone.utc).isoformat()
        res = supabase.table("subscriptions")\
            .select("package_name, capacity_lpm, end_date, broadcast_interval_hours")\
            .eq("user_id", user_id)\
            .eq("status", "active")\
            .gt("end_date", now_str)\
            .order("end_date", desc=True)\
            .limit(1)\
            .execute()
        if res.data:
            row = res.data[0]
            return (
                row["package_name"],
                row["capacity_lpm"],
                normalize_date(row["end_date"]),
                row["broadcast_interval_hours"]
            )
        return None
    except Exception as e:
        logger.error(f"Error in db_get_active_subscription_status: {e}")
        return None

def db_get_active_subscription_id_and_end(user_id: int):
    try:
        supabase = get_supabase()
        now_str = datetime.now(timezone.utc).isoformat()
        res = supabase.table("subscriptions")\
            .select("id, end_date, assigned_admin_ub_id")\
            .eq("user_id", user_id)\
            .eq("status", "active")\
            .gt("end_date", now_str)\
            .order("end_date", desc=True)\
            .limit(1)\
            .execute()
        if res.data:
            row = res.data[0]
            return (
                row["id"],
                normalize_date(row["end_date"]),
                row.get("assigned_admin_ub_id")
            )
        return None
    except Exception as e:
        logger.error(f"Error in db_get_active_subscription_id_and_end: {e}")
        return None

def db_get_active_subscription_broadcast_details(user_id: int):
    try:
        supabase = get_supabase()
        now_str = datetime.now(timezone.utc).isoformat()
        res = supabase.table("subscriptions")\
            .select("package_name, capacity_lpm, request_lpm, broadcast_interval_hours, assigned_admin_ub_id")\
            .eq("user_id", user_id)\
            .eq("status", "active")\
            .gt("end_date", now_str)\
            .order("end_date", desc=True)\
            .limit(1)\
            .execute()
        if res.data:
            row = res.data[0]
            return (
                row["package_name"],
                row["capacity_lpm"],
                row["request_lpm"],
                row["broadcast_interval_hours"],
                row["assigned_admin_ub_id"]
            )
        return None
    except Exception as e:
        logger.error(f"Error in db_get_active_subscription_broadcast_details: {e}")
        return None

def db_update_subscription_lpm(user_id: int, lpm_list_str: str):
    try:
        supabase = get_supabase()
        supabase.table("subscriptions")\
            .update({"request_lpm": lpm_list_str or None})\
            .eq("user_id", user_id)\
            .eq("status", "active")\
            .execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_update_subscription_lpm: {e}")
        return False

def db_add_subscription(user_id: int, package_name: str, capacity_lpm: int, start_date: str, end_date: str, assigned_admin_ub_id: int = None, max_userbots: int = 1):
    try:
        db_ensure_user(user_id)
        try:
            sd_dt = datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S")
            sd_iso = sd_dt.isoformat()
        except:
            sd_iso = start_date
        try:
            ed_dt = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S")
            ed_iso = ed_dt.isoformat()
        except:
            ed_iso = end_date
            
        supabase = get_supabase()
        insert_data = {
            "user_id": user_id,
            "package_name": package_name,
            "capacity_lpm": capacity_lpm,
            "start_date": sd_iso,
            "end_date": ed_iso,
            "status": "active",
            "broadcast_interval_hours": 0.5,
            "max_userbots": max_userbots
        }
        if assigned_admin_ub_id is not None:
            insert_data["assigned_admin_ub_id"] = assigned_admin_ub_id
            
        supabase.table("subscriptions").insert(insert_data).execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_add_subscription: {e}")
        return False

def db_update_subscription_dates(sub_id: int, end_date: str, capacity_lpm: int, package_name: str, assigned_admin_ub_id: int = None, max_userbots: int = 1):
    try:
        try:
            ed_dt = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S")
            ed_iso = ed_dt.isoformat()
        except:
            ed_iso = end_date
            
        supabase = get_supabase()
        update_data = {
            "end_date": ed_iso,
            "capacity_lpm": capacity_lpm,
            "package_name": package_name,
            "max_userbots": max_userbots
        }
        if assigned_admin_ub_id is not None:
            update_data["assigned_admin_ub_id"] = assigned_admin_ub_id
            
        supabase.table("subscriptions").update(update_data).eq("id", sub_id).execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_update_subscription_dates: {e}")
        return False

def db_get_active_subscriptions_list(limit: int = 10):
    try:
        supabase = get_supabase()
        res = supabase.table("subscriptions")\
            .select("user_id, package_name, end_date")\
            .eq("status", "active")\
            .order("end_date", desc=False)\
            .limit(limit)\
            .execute()
        if res.data:
            return [(r["user_id"], r["package_name"], normalize_date(r["end_date"])) for r in res.data]
        return []
    except Exception as e:
        logger.error(f"Error in db_get_active_subscriptions_list: {e}")
        return []

def db_get_active_users_for_scheduler():
    try:
        supabase = get_supabase()
        now_str = datetime.now(timezone.utc).isoformat()
        res = supabase.table("subscriptions")\
            .select("user_id, broadcast_interval_hours")\
            .eq("status", "active")\
            .gt("end_date", now_str)\
            .execute()
        if res.data:
            return list(set((r["user_id"], r["broadcast_interval_hours"]) for r in res.data))
        return []
    except Exception as e:
        logger.error(f"Error in db_get_active_users_for_scheduler: {e}")
        return []

def db_get_expiring_subscriptions(limit_hours: int = 24):
    try:
        supabase = get_supabase()
        now = datetime.now(timezone.utc)
        now_str = now.isoformat()
        limit_str = (now + timedelta(hours=limit_hours)).isoformat()
        res = supabase.table("subscriptions")\
            .select("user_id, package_name, end_date")\
            .eq("status", "active")\
            .gte("end_date", now_str)\
            .lte("end_date", limit_str)\
            .execute()
        if res.data:
            return [(r["user_id"], r["package_name"], normalize_date(r["end_date"])) for r in res.data]
        return []
    except Exception as e:
        logger.error(f"Error in db_get_expiring_subscriptions: {e}")
        return []


# ─────────────────────────────────────────
# HELPER USERADS (IKLAN)
# ─────────────────────────────────────────

def db_save_user_ad(user_id: int, content: str, media_path: str, fwd_chat_id: str = None, fwd_peer_type: str = None, fwd_msg_id: int = None):
    try:
        db_ensure_user(user_id)
        supabase = get_supabase()
        # Hapus iklan lama yang bertitle "Iklan Utama"
        supabase.table("user_ads").delete().eq("user_id", user_id).eq("title", "Iklan Utama").execute()
        # Simpan iklan baru
        supabase.table("user_ads").insert({
            "user_id": user_id,
            "title": "Iklan Utama",
            "content": content or "",
            "media_path": media_path or "",
            "fwd_chat_id": fwd_chat_id,
            "fwd_peer_type": fwd_peer_type,
            "fwd_msg_id": fwd_msg_id
        }).execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_save_user_ad: {e}")
        return False

def db_get_user_ad_by_id(ad_id: int):
    try:
        supabase = get_supabase()
        res = supabase.table("user_ads")\
            .select("content, media_path, fwd_chat_id, fwd_peer_type, fwd_msg_id")\
            .eq("id", ad_id)\
            .execute()
        if res.data:
            r = res.data[0]
            return (
                r.get("content"),
                r.get("media_path"),
                r.get("fwd_chat_id"),
                r.get("fwd_peer_type"),
                r.get("fwd_msg_id")
            )
        return None
    except Exception as e:
        logger.error(f"Error in db_get_user_ad_by_id: {e}")
        return None

def db_get_latest_user_ad_id(user_id: int):
    try:
        supabase = get_supabase()
        res = supabase.table("user_ads")\
            .select("id")\
            .eq("user_id", user_id)\
            .eq("title", "Iklan Utama")\
            .order("created_at", desc=True)\
            .limit(1)\
            .execute()
        if res.data:
            return (res.data[0]["id"],)
        return None
    except Exception as e:
        logger.error(f"Error in db_get_latest_user_ad_id: {e}")
        return None


# ─────────────────────────────────────────
# HELPER USERBOTS & ADMIN POOL
# ─────────────────────────────────────────

def db_get_userbot_status(user_id: int) -> str:
    try:
        supabase = get_supabase()
        res = supabase.table("userbots").select("status").eq("user_id", user_id).execute()
        if res.data:
            # Jika ada minimal satu akun userbot yang terhubung, status global adalah connected
            for row in res.data:
                if row.get("status") == "connected":
                    return "connected"
            # Jika semua terputus, kembalikan status baris pertama
            return res.data[0]["status"]
        return "disconnected"
    except Exception as e:
        logger.error(f"Error in db_get_userbot_status: {e}")
        return "disconnected"

def db_get_userbot_session_and_status(user_id: int):
    try:
        supabase = get_supabase()
        res = supabase.table("userbots").select("session_name, status").eq("user_id", user_id).execute()
        if res.data:
            r = res.data[0]
            return (r["session_name"], r["status"])
        return None
    except Exception as e:
        logger.error(f"Error in db_get_userbot_session_and_status: {e}")
        return None

def db_get_userbot_by_subscription(sub_id: int):
    """Mengambil sesi dan status userbot yang terkait dengan ID langganan tertentu."""
    try:
        supabase = get_supabase()
        res = supabase.table("userbots").select("session_name, status").eq("subscription_id", sub_id).execute()
        if res.data:
            r = res.data[0]
            return (r["session_name"], r["status"])
        return None
    except Exception as e:
        logger.error(f"Error in db_get_userbot_by_subscription: {e}")
        return None

def db_get_active_userbots_count() -> int:
    try:
        supabase = get_supabase()
        res = supabase.table("userbots").select("phone_number", count="exact").eq("status", "connected").execute()
        return res.count or 0
    except Exception as e:
        logger.error(f"Error in db_get_active_userbots_count: {e}")
        return 0

def db_save_admin_userbot(phone: str, session: str):
    try:
        supabase = get_supabase()
        supabase.table("admin_userbots").upsert({
            "phone_number": phone,
            "session_name": session,
            "status": "connected"
        }, on_conflict="phone_number").execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_save_admin_userbot: {e}")
        return False

def db_save_userbot(user_id: int, phone: str, session: str):
    try:
        db_ensure_user(user_id)
        supabase = get_supabase()
        
        # Cari subscription aktif milik user_id yang bertipe 'userbot'
        now_str = datetime.now(timezone.utc).isoformat()
        res_subs = supabase.table("subscriptions") \
            .select("id") \
            .eq("user_id", user_id) \
            .eq("status", "active") \
            .gt("end_date", now_str) \
            .ilike("package_name", "%userbot%") \
            .order("end_date", desc=True) \
            .execute()
        
        assigned_sub_id = None
        if res_subs.data:
            assigned_sub_id = res_subs.data[0]["id"]
            
        supabase.table("userbots").upsert({
            "phone_number": phone,
            "user_id": user_id,
            "session_name": session,
            "status": "connected",
            "subscription_id": assigned_sub_id
        }, on_conflict="phone_number").execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_save_userbot: {e}")
        return False

def db_update_userbot_profile(phone: str, display_name: str, photo_url: str = None) -> bool:
    try:
        supabase = get_supabase()
        payload = {"display_name": display_name}
        if photo_url:
            payload["photo_url"] = photo_url
        supabase.table("userbots").update(payload).eq("phone_number", phone).execute()
        return True
    except Exception as e:
        logger.warning(f"Gagal update profil userbot di database (kemungkinan kolom display_name/photo_url belum dibuat): {e}")
        return False

def db_update_userbot_groups_count(phone: str, count: int) -> bool:
    try:
        supabase = get_supabase()
        supabase.table("userbots").update({"groups_count": count}).eq("phone_number", phone).execute()
        return True
    except Exception as e:
        logger.warning(f"Gagal update groups_count userbot di database (kemungkinan kolom groups_count belum dibuat): {e}")
        return False

def db_update_userbot_status(session_name_or_phone: str, status: str):
    try:
        supabase = get_supabase()
        # Deteksi apakah parameter adalah phone (mengandung angka besar) atau session_name
        if session_name_or_phone.replace("+", "").isdigit():
            supabase.table("userbots").update({"status": status}).eq("phone_number", session_name_or_phone).execute()
        else:
            supabase.table("userbots").update({"status": status}).eq("session_name", session_name_or_phone).execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_update_userbot_status: {e}")
        return False

def db_get_admin_userbot_session(aid: int) -> str:
    try:
        supabase = get_supabase()
        res = supabase.table("admin_userbots").select("session_name").eq("id", aid).execute()
        if res.data:
            return res.data[0]["session_name"]
        return ""
    except Exception as e:
        logger.error(f"Error in db_get_admin_userbot_session: {e}")
        return ""

def db_delete_admin_userbot(aid: int):
    try:
        supabase = get_supabase()
        supabase.table("admin_userbots").delete().eq("id", aid).execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_delete_admin_userbot: {e}")
        return False

def db_get_admin_userbots():
    """Mengambil semua admin userbots diurutkan by ID ASC (konsisten dengan logika slot sharding LPM)."""
    try:
        supabase = get_supabase()
        res = supabase.table("admin_userbots") \
            .select("id, phone_number, status, cooldown_until, lpm_description") \
            .order("id", desc=False) \
            .execute()
        if res.data:
            return [(r["id"], r["phone_number"], r["status"], normalize_date(r.get("cooldown_until")), r.get("lpm_description") or "Total LPM 100 Campur") for r in res.data]
        return []
    except Exception as e:
        logger.error(f"Error in db_get_admin_userbots: {e}")
        return []


def db_get_admin_slots_status() -> list:
    """
    Mengambil status slot semua admin pool untuk ditampilkan di Mini App saat checkout.

    Setiap slot admin menampilkan:
      - id             : ID unik admin di database
      - visual_name    : Label tampilan (Bot Admin #1, Bot Admin #2, dst)
      - phone_last4    : 4 digit terakhir nomor HP (untuk identifikasi tanpa expose penuh)
      - status         : 'Tersedia' / 'Penuh' / 'Offline'
      - lpm_slot_start : Nomor LPM pertama di slot ini
      - lpm_slot_end   : Nomor LPM terakhir di slot ini
      - lpm_description: Deskripsi khusus slot LPM (Total LPM 100 Campur / Custom)
      - active_clients : Jumlah klien aktif yang menggunakan admin ini
      - end_date       : Tanggal berakhir klien terakhir (untuk info kapan slot kosong)

    Aturan status:
      - 'Offline'   → admin status != 'connected'
      - 'Penuh'     → ada >= 1 klien aktif yang assigned ke admin ini
      - 'Tersedia'  → connected dan tidak ada klien aktif assigned
    """
    SLOT_SIZE = 100  # Harus konsisten dengan db_get_lpm_sharded_for_admin
    try:
        supabase = get_supabase()

        # Ambil semua admin diurutkan by ID ASC (slot statis)
        res_admins = supabase.table("admin_userbots") \
            .select("id, phone_number, status, cooldown_until, lpm_description") \
            .order("id", desc=False) \
            .execute()
        admins = res_admins.data or []

        if not admins:
            return []

        # Ambil semua subscription aktif yang punya assigned_admin_ub_id
        now_str = datetime.now(timezone.utc).isoformat()
        res_subs = supabase.table("subscriptions") \
            .select("assigned_admin_ub_id, end_date, user_id") \
            .eq("status", "active") \
            .gt("end_date", now_str) \
            .execute()
        subs = res_subs.data or []

        # Buat map: admin_id → list subscription aktif
        admin_subs_map: dict = {}
        for sub in subs:
            aid = sub.get("assigned_admin_ub_id")
            if aid:
                if aid not in admin_subs_map:
                    admin_subs_map[aid] = []
                admin_subs_map[aid].append(sub)

        result = []
        for i, admin in enumerate(admins):
            aid = admin["id"]
            phone = admin.get("phone_number", "")
            status_db = admin.get("status", "disconnected")
            cooldown = admin.get("cooldown_until")
            lpm_desc = admin.get("lpm_description") or "Total LPM 100 Campur"

            # Tentukan label visual
            visual_name = f"Bot Admin #{i + 1}"
            phone_last4 = phone[-4:] if phone and len(phone) >= 4 else "????"

            # Slot LPM statis
            lpm_slot_start = i * SLOT_SIZE + 1
            lpm_slot_end   = (i + 1) * SLOT_SIZE

            # Klien aktif di admin ini
            active_subs = admin_subs_map.get(aid, [])
            active_client_count = len(active_subs)

            # Cari tanggal end_date terjauh (kapan slot akan kosong)
            latest_end = None
            for sub in active_subs:
                ed = sub.get("end_date")
                if ed:
                    if latest_end is None or ed > latest_end:
                        latest_end = ed

            # Format end_date untuk tampil di UI
            end_date_display = None
            if latest_end:
                try:
                    clean = latest_end.replace("T", " ").split("+")[0].split(".")[0].strip()
                    end_date_display = clean  # "YYYY-MM-DD HH:MM:SS"
                except Exception:
                    end_date_display = latest_end[:10]

            # Cek cooldown
            is_on_cooldown = False
            if cooldown:
                try:
                    cooldown_dt = parse_utc_date(cooldown)
                    if cooldown_dt > datetime.now(timezone.utc):
                        is_on_cooldown = True
                except Exception:
                    pass

            # Tentukan status tampilan
            if status_db != "connected" or is_on_cooldown:
                slot_status = "Offline"
            elif active_client_count > 0:
                slot_status = "Disewa"
            else:
                slot_status = "Tersedia"

            result.append({
                "id"              : aid,
                "visual_name"     : visual_name,
                "phone_last4"     : phone_last4,
                "status"          : slot_status,
                "lpm_slot_start"  : lpm_slot_start,
                "lpm_slot_end"    : lpm_slot_end,
                "lpm_description" : lpm_desc,
                "active_clients"  : active_client_count,
                "end_date"        : end_date_display,
            })

        return result
    except Exception as e:
        logger.error(f"Error in db_get_admin_slots_status: {e}")
        return []




def db_get_active_admin_userbots():
    try:
        supabase = get_supabase()
        res = supabase.table("admin_userbots")\
            .select("session_name, phone_number, id, cooldown_until")\
            .eq("status", "connected")\
            .execute()
        if not res.data:
            return []
            
        now = datetime.now(timezone.utc)
        active_admins = []
        for r in res.data:
            cooldown = r.get("cooldown_until")
            if cooldown:
                try:
                    cooldown_dt = parse_utc_date(cooldown)
                    if cooldown_dt > now:
                        continue
                except Exception as ex:
                    logger.error(f"Error parsing cooldown for admin {r.get('id')}: {ex}")
            active_admins.append((r["session_name"], r["phone_number"], r["id"]))
            
        import random
        random.shuffle(active_admins)
        return active_admins
    except Exception as e:
        logger.error(f"Error in db_get_active_admin_userbots: {e}")
        return []

def db_cooldown_admin_userbot(aid: int, until_str: str):
    try:
        supabase = get_supabase()
        try:
            dt = datetime.strptime(until_str, "%Y-%m-%d %H:%M:%S")
            iso_str = dt.isoformat()
        except:
            iso_str = until_str
        supabase.table("admin_userbots").update({"cooldown_until": iso_str}).eq("id", aid).execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_cooldown_admin_userbot: {e}")
        return False

def db_update_admin_userbot_status(admin_id: int, status: str):
    """Memperbarui status bot admin pool (connected / disconnected / dll)."""
    try:
        supabase = get_supabase()
        supabase.table("admin_userbots").update({"status": status}).eq("id", admin_id).execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_update_admin_userbot_status: {e}")
        return False


# ─────────────────────────────────────────
# HELPER TRANSAKSI (TRANSACTIONS)
# ─────────────────────────────────────────

def db_save_transaction(user_id: int, trx_id: str, package_id: str, amount: int, payment_url: str, assigned_admin_ub_id: int = None, quantity: int = 1):
    try:
        db_ensure_user(user_id)
        supabase = get_supabase()
        insert_data = {
            "user_id": user_id,
            "trx_id": trx_id,
            "package_id": package_id,
            "amount": amount,
            "payment_url": payment_url,
            "status": "pending",
            "quantity": quantity
        }
        if assigned_admin_ub_id is not None:
            insert_data["assigned_admin_ub_id"] = assigned_admin_ub_id
            
        supabase.table("transactions").insert(insert_data).execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_save_transaction: {e}")
        return False

def db_get_transaction(trx_id: str):
    try:
        supabase = get_supabase()
        res = supabase.table("transactions").select("user_id, amount, package_id, status, assigned_admin_ub_id, quantity").eq("trx_id", trx_id).execute()
        if res.data:
            r = res.data[0]
            return (r["user_id"], r["amount"], r["package_id"], r["status"], r.get("assigned_admin_ub_id"), r.get("quantity", 1))
        return None
    except Exception as e:
        logger.error(f"Error in db_get_transaction: {e}")
        return None

def db_update_transaction_status(trx_id: str, status: str):
    try:
        supabase = get_supabase()
        supabase.table("transactions").update({"status": status}).eq("trx_id", trx_id).execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_update_transaction_status: {e}")
        return False


# ─────────────────────────────────────────
# HELPER LOGS & LPM LISTS
# ─────────────────────────────────────────

def db_get_lpm_lists_count() -> int:
    try:
        supabase = get_supabase()
        res = supabase.table("lpm_lists")\
            .select("id", count="exact")\
            .eq("is_active", True)\
            .eq("is_blacklisted", False)\
            .execute()
        return res.count or 0
    except Exception as e:
        logger.error(f"Error in db_get_lpm_lists_count: {e}")
        return 0

def db_get_active_lpm_lists(limit: int):
    try:
        supabase = get_supabase()
        query_limit = max(300, limit)
        res = supabase.table("lpm_lists")\
            .select("group_link")\
            .eq("is_active", True)\
            .eq("is_blacklisted", False)\
            .order("member_count", desc=True)\
            .limit(query_limit)\
            .execute()
        if res.data:
            all_links = [r["group_link"] for r in res.data]
            import random
            if len(all_links) > limit:
                return random.sample(all_links, limit)
            else:
                random.shuffle(all_links)
                return all_links
        return []
    except Exception as e:
        logger.error(f"Error in db_get_active_lpm_lists: {e}")
        return []

def db_get_active_lpm_links_with_ids(limit: int):
    try:
        supabase = get_supabase()
        query_limit = max(300, limit)
        res = supabase.table("lpm_lists")\
            .select("group_link, group_id")\
            .eq("is_active", True)\
            .eq("is_blacklisted", False)\
            .order("member_count", desc=True)\
            .limit(query_limit)\
            .execute()
        if res.data:
            import random
            all_data = [(r["group_link"], r["group_id"]) for r in res.data]
            if len(all_data) > limit:
                return random.sample(all_data, limit)
            else:
                random.shuffle(all_data)
                return all_data
        return []
    except Exception as e:
        logger.error(f"Error in db_get_active_lpm_links_with_ids: {e}")
        return []

def db_insert_forward_log(user_id: int, ad_id: int, group_id: int, msg_link: str, status: str, error_msg: str = "", subscription_id: int = None):
    try:
        db_ensure_user(user_id)
        supabase = get_supabase()
        supabase.table("forward_logs").insert({
            "user_id": user_id,
            "ad_id": ad_id,
            "group_id": group_id,
            "msg_link": msg_link or "",
            "status": status,
            "error_msg": error_msg or "",
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "subscription_id": subscription_id
        }).execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_insert_forward_log: {e}")
        return False

def db_get_success_forward_logs_count(user_id: int) -> int:
    try:
        supabase = get_supabase()
        res = supabase.table("forward_logs")\
            .select("id", count="exact")\
            .eq("user_id", user_id)\
            .eq("status", "success")\
            .execute()
        return res.count or 0
    except Exception as e:
        logger.error(f"Error in db_get_success_forward_logs_count: {e}")
        return 0

def db_get_global_success_forward_logs_count() -> int:
    try:
        supabase = get_supabase()
        res = supabase.table("forward_logs")\
            .select("id", count="exact")\
            .eq("status", "success")\
            .execute()
        return res.count or 0
    except Exception as e:
        logger.error(f"Error in db_get_global_success_forward_logs_count: {e}")
        return 0

def db_get_forward_history(user_id: int, limit: int = 50):
    try:
        supabase = get_supabase()
        res = supabase.table("forward_logs")\
            .select("group_id, msg_link, status, error_msg, sent_at")\
            .eq("user_id", user_id)\
            .order("sent_at", desc=True)\
            .limit(limit)\
            .execute()
        
        rows = res.data or []
        if not rows:
            return []
            
        group_ids = list(set(r["group_id"] for r in rows if r.get("group_id")))
        group_map = {}
        if group_ids:
            res_groups = supabase.table("lpm_lists")\
                .select("group_id, group_name")\
                .in_("group_id", group_ids)\
                .execute()
            if res_groups.data:
                group_map = {g["group_id"]: g["group_name"] for g in res_groups.data}
                
        results = []
        for r in rows:
            group_name = group_map.get(r.get("group_id")) or "Grup LPM"
            results.append((
                group_name,
                r.get("msg_link"),
                r.get("status"),
                r.get("error_msg"),
                normalize_date(r.get("sent_at"))
            ))
        return results
    except Exception as e:
        logger.error(f"Error in db_get_forward_history: {e}")
        return []


def db_search_proof_by_group_name(user_id: int, query: str):
    """Mencari riwayat kirim dan bukti link berdasarkan nama grup atau link grup."""
    try:
        supabase = get_supabase()
        query = query.strip()
        if not query:
            return []
        
        # Cari grup di lpm_lists yang mirip nama atau link-nya
        res_groups = supabase.table("lpm_lists")\
            .select("group_id, group_name, group_link")\
            .or_(f"group_name.ilike.%{query}%,group_link.ilike.%{query}%")\
            .execute()
        
        g_data = res_groups.data or []
        if not g_data:
            return []
        
        group_ids = [g["group_id"] for g in g_data if g.get("group_id")]
        if not group_ids:
            return []
            
        # Ambil riwayat kiriman sukses terbaru untuk user_id ke grup-grup tersebut
        res_logs = supabase.table("forward_logs")\
            .select("group_id, msg_link, status, sent_at")\
            .eq("user_id", user_id)\
            .eq("status", "success")\
            .in_("group_id", group_ids)\
            .order("sent_at", desc=True)\
            .limit(10)\
            .execute()
            
        logs = res_logs.data or []
        if not logs:
            return []
            
        group_map = {g["group_id"]: g["group_name"] for g in g_data if g.get("group_id")}
        
        results = []
        for l in logs:
            g_name = group_map.get(l.get("group_id")) or "Grup LPM"
            results.append({
                "group_name": g_name,
                "msg_link": l.get("msg_link"),
                "status": l.get("status"),
                "sent_at": normalize_date(l.get("sent_at"))
            })
        return results
    except Exception as e:
        logger.error(f"Error in db_search_proof_by_group_name: {e}")
        return []


# ─────────────────────────────────────────
# HELPER STATISTIK GLOBAL ADMIN
# ─────────────────────────────────────────

def db_get_admin_stats():
    try:
        supabase = get_supabase()
        
        # 1. Total Users
        res_users = supabase.table("users").select("user_id", count="exact").execute()
        total_users = res_users.count or 0
        
        # 2. Total Revenue
        res_rev = supabase.table("transactions").select("amount").eq("status", "success").execute()
        total_revenue = sum(row.get("amount", 0) for row in res_rev.data) if res_rev.data else 0
        
        # 3. Total Sent
        res_sent = supabase.table("forward_logs").select("id", count="exact").eq("status", "success").execute()
        total_sent = res_sent.count or 0
        
        # 4. Total Admin Userbots
        res_admin_ub = supabase.table("admin_userbots").select("id", count="exact").eq("status", "connected").execute()
        total_admin_ub = res_admin_ub.count or 0
        
        return (total_users, total_revenue, total_sent, total_admin_ub)
    except Exception as e:
        logger.error(f"Error in db_get_admin_stats: {e}")
        return (0, 0, 0, 0)


# ─────────────────────────────────────────
# ADMIN: MANAJEMEN LPM POOL
# ─────────────────────────────────────────

def db_get_lpm_lists_paginated(offset: int = 0, limit: int = 10, active_only: bool = True):
    """Ambil daftar LPM dengan paginasi untuk admin."""
    try:
        supabase = get_supabase()
        q = supabase.table("lpm_lists").select("id, group_link, group_name, member_count, is_active, is_blacklisted")
        if active_only:
            q = q.eq("is_active", True).eq("is_blacklisted", False)
        res = q.order("member_count", desc=True).range(offset, offset + limit - 1).execute()
        return res.data or []
    except Exception as e:
        logger.error(f"Error in db_get_lpm_lists_paginated: {e}")
        return []

def db_add_lpm_entry(group_link: str, group_name: str = "", member_count: int = 0, group_id: int = None) -> bool:
    """Tambahkan LPM baru ke pool."""
    try:
        supabase = get_supabase()
        # Normalisasi link
        link = group_link.strip().lstrip("@")
        if not link.startswith("https://t.me/") and not link.startswith("http"):
            link = f"https://t.me/{link}"
        insert_data = {
            "group_link": link,
            "group_name": group_name or link,
            "member_count": member_count,
            "is_active": True,
            "is_blacklisted": False
        }
        if group_id is not None:
            insert_data["group_id"] = group_id
        supabase.table("lpm_lists").upsert(insert_data, on_conflict="group_link").execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_add_lpm_entry: {e}")
        return False

def db_bulk_add_lpm_entries(links: list) -> int:
    """Tambahkan banyak LPM sekaligus, return jumlah yang berhasil."""
    count = 0
    for raw in links:
        link = raw.strip().lstrip("@")
        if not link:
            continue
        if not link.startswith("https://t.me/") and not link.startswith("http"):
            link = f"https://t.me/{link}"
        if db_add_lpm_entry(link):
            count += 1
    return count


def db_save_userbot_groups_to_lpm(groups: list):
    """Menyimpan atau meng-upsert daftar grup dari userbot pembeli ke dalam tabel lpm_lists secara bulk."""
    try:
        supabase = get_supabase()
        insert_data = []
        for g in groups:
            link = g.get("link")
            if not link:
                continue
            link = link.strip().lstrip("@")
            if not link.startswith("https://t.me/") and not link.startswith("http"):
                link = f"https://t.me/{link}"
            
            insert_data.append({
                "group_link": link,
                "group_name": g.get("name") or link,
                "member_count": g.get("member_count") or 0,
                "is_active": True,
                "is_blacklisted": False,
                "group_id": g.get("group_id")
            })
            
        if insert_data:
            supabase.table("lpm_lists").upsert(insert_data, on_conflict="group_link").execute()
            logger.info(f"✅ Berhasil menyelaraskan {len(insert_data)} grup userbot ke tabel lpm_lists.")
    except Exception as e:
        logger.error(f"Error in db_save_userbot_groups_to_lpm: {e}")

def db_delete_lpm_entry(lpm_id: int) -> bool:
    """Hapus LPM dari pool berdasarkan ID."""
    try:
        supabase = get_supabase()
        supabase.table("lpm_lists").delete().eq("id", lpm_id).execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_delete_lpm_entry: {e}")
        return False

def db_toggle_lpm_status(lpm_id: int, is_active: bool) -> bool:
    """Aktifkan atau nonaktifkan LPM berdasarkan ID."""
    try:
        supabase = get_supabase()
        supabase.table("lpm_lists").update({"is_active": is_active}).eq("id", lpm_id).execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_toggle_lpm_status: {e}")
        return False

def db_blacklist_lpm(lpm_id: int) -> bool:
    """Blacklist LPM (tandai tidak aktif permanen)."""
    try:
        supabase = get_supabase()
        supabase.table("lpm_lists").update({"is_blacklisted": True, "is_active": False}).eq("id", lpm_id).execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_blacklist_lpm: {e}")
        return False

def db_clear_all_lpm() -> bool:
    """Hapus semua LPM dari pool (berbahaya!)."""
    try:
        supabase = get_supabase()
        supabase.table("lpm_lists").delete().neq("id", 0).execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_clear_all_lpm: {e}")
        return False


# ─────────────────────────────────────────
# ADMIN: MANAJEMEN BILLING (SUBSCRIPTIONS)
# ─────────────────────────────────────────

def db_get_all_subscriptions_detail(limit: int = 20):
    """Ambil semua langganan aktif dengan detail lengkap untuk admin."""
    try:
        supabase = get_supabase()
        now_str = datetime.now(timezone.utc).isoformat()
        res = supabase.table("subscriptions")\
            .select("id, user_id, package_name, capacity_lpm, end_date, broadcast_interval_hours, request_lpm, max_userbots")\
            .eq("status", "active")\
            .gt("end_date", now_str)\
            .order("end_date", desc=True)\
            .limit(limit)\
            .execute()
        return res.data or []
    except Exception as e:
        logger.error(f"Error in db_get_all_subscriptions_detail: {e}")
        return []

def db_get_subscription_by_user(user_id: int):
    """Ambil langganan aktif satu user dengan detail lengkap."""
    try:
        supabase = get_supabase()
        now_str = datetime.now(timezone.utc).isoformat()
        res = supabase.table("subscriptions")\
            .select("id, package_name, capacity_lpm, end_date, broadcast_interval_hours, request_lpm, max_userbots")\
            .eq("user_id", user_id)\
            .eq("status", "active")\
            .gt("end_date", now_str)\
            .order("end_date", desc=True)\
            .limit(1)\
            .execute()
        if res.data:
            return res.data[0]
        return None
    except Exception as e:
        logger.error(f"Error in db_get_subscription_by_user: {e}")
        return None

def db_get_pending_transactions(limit: int = 10):
    """Ambil transaksi pending terbaru."""
    try:
        supabase = get_supabase()
        res = supabase.table("transactions")\
            .select("id, user_id, trx_id, package_id, amount, payment_url, created_at, quantity")\
            .eq("status", "pending")\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()
        return res.data or []
    except Exception as e:
        logger.error(f"Error in db_get_pending_transactions: {e}")
        return []

def db_get_transaction_detail(trx_id: str):
    """Ambil detail transaksi berdasarkan trx_id/invoice."""
    try:
        supabase = get_supabase()
        res = supabase.table("transactions").select("*").eq("trx_id", trx_id).execute()
        if res.data:
            return res.data[0]
        return None
    except Exception as e:
        logger.error(f"Error in db_get_transaction_detail: {e}")
        return None

def db_extend_subscription(user_id: int, days: int) -> bool:
    """Perpanjang langganan aktif user sejumlah hari."""
    try:
        supabase = get_supabase()
        now_str = datetime.now(timezone.utc).isoformat()
        res = supabase.table("subscriptions")\
            .select("id, end_date")\
            .eq("user_id", user_id)\
            .eq("status", "active")\
            .gt("end_date", now_str)\
            .order("end_date", desc=True)\
            .limit(1)\
            .execute()
        if not res.data:
            return False
        sub = res.data[0]
        old_end = sub["end_date"]
        try:
            old_dt = datetime.fromisoformat(old_end.replace("Z", "+00:00").split("+")[0])
            if old_dt.tzinfo is None:
                old_dt = old_dt.replace(tzinfo=timezone.utc)
        except:
            old_dt = datetime.now(timezone.utc)
        new_end = (old_dt + timedelta(days=days)).isoformat()
        supabase.table("subscriptions").update({"end_date": new_end}).eq("id", sub["id"]).execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_extend_subscription: {e}")
        return False

def db_set_subscription_interval(user_id: int, interval_hours: float) -> bool:
    """Ubah interval broadcast langganan aktif user."""
    try:
        supabase = get_supabase()
        now_str = datetime.now(timezone.utc).isoformat()
        supabase.table("subscriptions")\
            .update({"broadcast_interval_hours": interval_hours})\
            .eq("user_id", user_id)\
            .eq("status", "active")\
            .gt("end_date", now_str)\
            .execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_set_subscription_interval: {e}")
        return False

def db_revoke_subscription(user_id: int) -> bool:
    """Cabut langganan aktif user (set status expired)."""
    try:
        supabase = get_supabase()
        supabase.table("subscriptions")\
            .update({"status": "expired", "end_date": datetime.now(timezone.utc).isoformat()})\
            .eq("user_id", user_id)\
            .eq("status", "active")\
            .execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_revoke_subscription: {e}")
        return False

def db_set_subscription_lpm_capacity(user_id: int, capacity: int) -> bool:
    """Ubah kapasitas LPM langganan aktif user."""
    try:
        supabase = get_supabase()
        now_str = datetime.now(timezone.utc).isoformat()
        supabase.table("subscriptions")\
            .update({"capacity_lpm": capacity})\
            .eq("user_id", user_id)\
            .eq("status", "active")\
            .gt("end_date", now_str)\
            .execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_set_subscription_lpm_capacity: {e}")
        return False


# ─────────────────────────────────────────
# ADMIN: MANAJEMEN USERBOT PEMBELI
# ─────────────────────────────────────────

def db_get_all_client_userbots(limit: int = 20):
    """Ambil semua userbot pembeli untuk admin."""
    try:
        supabase = get_supabase()
        res = supabase.table("userbots")\
            .select("user_id, phone_number, status, created_at, session_name")\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()
        return res.data or []
    except Exception as e:
        logger.error(f"Error in db_get_all_client_userbots: {e}")
        return []

def db_admin_disconnect_client_userbot(phone_number: str) -> bool:
    """Admin paksa disconnect userbot pembeli berdasarkan nomor HP."""
    try:
        supabase = get_supabase()
        supabase.table("userbots").update({"status": "disconnected"}).eq("phone_number", phone_number).execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_admin_disconnect_client_userbot: {e}")
        return False

def db_admin_delete_client_userbot(phone_number: str) -> tuple:
    """Hapus userbot pembeli berdasarkan nomor HP, return session_name untuk hapus file .session."""
    try:
        supabase = get_supabase()
        res = supabase.table("userbots").select("session_name").eq("phone_number", phone_number).execute()
        session = res.data[0]["session_name"] if res.data else ""
        supabase.table("userbots").delete().eq("phone_number", phone_number).execute()
        return True, session
    except Exception as e:
        logger.error(f"Error in db_admin_delete_client_userbot: {e}")
        return False, ""

def db_get_lpm_entry(lpm_id: int):
    """Ambil detail LPM berdasarkan ID."""
    try:
        supabase = get_supabase()
        res = supabase.table("lpm_lists").select("id, group_link, group_name, member_count").eq("id", lpm_id).execute()
        if res.data:
            return res.data[0]
        return None
    except Exception as e:
        logger.error(f"Error in db_get_lpm_entry: {e}")
        return None

def db_update_lpm_details(lpm_id: int, group_name: str = None, member_count: int = None) -> bool:
    """Update judul LPM (group_name) dan/atau jumlah member."""
    try:
        supabase = get_supabase()
        data = {}
        if group_name is not None:
            data["group_name"] = group_name
        if member_count is not None:
            data["member_count"] = member_count
        if not data:
            return False
        supabase.table("lpm_lists").update(data).eq("id", lpm_id).execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_update_lpm_details: {e}")
        return False

def db_get_last_broadcast_time(user_id: int):
    """Mendapatkan waktu broadcast sukses terakhir dari forward_logs."""
    try:
        supabase = get_supabase()
        res = supabase.table("forward_logs")\
            .select("sent_at")\
            .eq("user_id", user_id)\
            .eq("status", "success")\
            .order("sent_at", desc=True)\
            .limit(1)\
            .execute()
        if res.data:
            sent_at = res.data[0]["sent_at"]
            try:
                # Parsing UTC ISO format dari Supabase ke datetime lokal
                clean_date = sent_at.replace("T", " ").replace("Z", "").split("+")[0].split(".")[0]
                return datetime.strptime(clean_date.strip(), "%Y-%m-%d %H:%M:%S")
            except Exception as ex:
                logger.error(f"Gagal parse date {sent_at}: {ex}")
        return None
    except Exception as e:
        logger.error(f"Error in db_get_last_broadcast_time: {e}")
        return None


# ─────────────────────────────────────────
# EKSPANSI FITUR BARU DATABASE LAYER
# ─────────────────────────────────────────

def db_generate_activation_token(token: str, package_id: str, lpm_capacity: int, duration_days: int) -> bool:
    """Membuat token aktivasi baru oleh admin."""
    try:
        supabase = get_supabase()
        supabase.table("activation_tokens").insert({
            "token": token,
            "package_id": package_id,
            "lpm_capacity": lpm_capacity,
            "duration_days": duration_days
        }).execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_generate_activation_token: {e}")
        return False

def db_redeem_activation_token(token: str, user_id: int) -> tuple:
    """Klaim token aktivasi untuk mengaktifkan subscription secara aman dan atomik."""
    try:
        supabase = get_supabase()
        db_ensure_user(user_id)
        
        # 1. Tandai token telah digunakan secara atomik dahulu untuk mengunci (cegah race condition / double claim)
        now = datetime.now(timezone.utc)
        now_str = now.isoformat()
        
        res_update = supabase.table("activation_tokens").update({
            "used_by": user_id,
            "used_at": now_str
        }).eq("token", token).is_("used_by", "null").execute()
        
        if not res_update.data:
            return False, "Token tidak valid atau sudah pernah digunakan."
            
        token_data = res_update.data[0]
        package_id = token_data["package_id"]
        lpm_capacity = token_data["lpm_capacity"]
        duration_days = token_data["duration_days"]
        
        # Tambah atau perpanjang subscription
        res_sub = supabase.table("subscriptions")\
            .select("id, end_date")\
            .eq("user_id", user_id)\
            .eq("status", "active")\
            .gt("end_date", now_str)\
            .order("end_date", desc=True)\
            .limit(1)\
            .execute()
            
        start_date = now
        if res_sub.data:
            # Perpanjang dari tanggal berakhir subscription lama
            existing_sub = res_sub.data[0]
            try:
                start_date = parse_utc_date(existing_sub["end_date"])
            except:
                start_date = now
                
        if duration_days < 0:
            end_date = start_date + timedelta(hours=abs(duration_days))
        else:
            end_date = start_date + timedelta(days=duration_days)
        
        # Simpan ke tabel subscriptions
        package_name = f"Jaseb {package_id.upper()}"
        
        supabase.table("subscriptions").insert({
            "user_id": user_id,
            "package_name": package_name,
            "capacity_lpm": lpm_capacity,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "status": "active",
            "broadcast_interval_hours": 0.5
        }).execute()
        
        duration_label = f"{abs(duration_days)} jam" if duration_days < 0 else f"{duration_days} hari"
        return True, f"Berhasil mengaktifkan {package_name} selama {duration_label}!"
    except Exception as e:
        logger.error(f"Error in db_redeem_activation_token: {e}")
        return False, f"Terjadi kesalahan database: {e}"

def db_get_auto_replies(user_id: int) -> list:
    """Ambil semua auto reply kata kunci milik user."""
    try:
        supabase = get_supabase()
        res = supabase.table("auto_replies")\
            .select("id, keyword, reply_text, skip_links, max_char_limit, skip_usernames, is_active")\
            .eq("user_id", user_id)\
            .execute()
        return res.data or []
    except Exception as e:
        logger.error(f"Error in db_get_auto_replies: {e}")
        return []

def db_add_auto_reply(user_id: int, keyword: str, reply_text: str, skip_links: bool = True, max_char_limit: int = 70, skip_usernames: str = None) -> bool:
    """Tambah/edit kata kunci auto reply milik user."""
    try:
        db_ensure_user(user_id)
        supabase = get_supabase()
        supabase.table("auto_replies").upsert({
            "user_id": user_id,
            "keyword": keyword.strip().lower(),
            "reply_text": reply_text,
            "skip_links": skip_links,
            "max_char_limit": max_char_limit,
            "skip_usernames": skip_usernames,
            "is_active": True
        }, on_conflict="user_id, keyword").execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_add_auto_reply: {e}")
        return False

def db_delete_auto_reply(user_id: int, reply_id: int) -> bool:
    """Hapus kata kunci auto reply milik user berdasarkan ID."""
    try:
        supabase = get_supabase()
        supabase.table("auto_replies").delete().eq("id", reply_id).eq("user_id", user_id).execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_delete_auto_reply: {e}")
        return False

def db_delete_auto_reply_by_keyword(user_id: int, keyword: str) -> bool:
    """Hapus kata kunci auto reply milik user berdasarkan string kata kunci."""
    try:
        supabase = get_supabase()
        supabase.table("auto_replies").delete().eq("user_id", user_id).eq("keyword", keyword.strip().lower()).execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_delete_auto_reply_by_keyword: {e}")
        return False

def db_get_custom_target_messages(user_id: int) -> list:
    """Ambil semua pesan kustom per target milik user."""
    try:
        supabase = get_supabase()
        res = supabase.table("custom_target_messages")\
            .select("id, target_peer, custom_message, is_active")\
            .eq("user_id", user_id)\
            .execute()
        return res.data or []
    except Exception as e:
        logger.error(f"Error in db_get_custom_target_messages: {e}")
        return []

def db_add_custom_target_message(user_id: int, target_peer: str, custom_message: str) -> bool:
    """Tambah/edit pesan kustom per target milik user."""
    try:
        db_ensure_user(user_id)
        supabase = get_supabase()
        supabase.table("custom_target_messages").upsert({
            "user_id": user_id,
            "target_peer": target_peer.strip().lower(),
            "custom_message": custom_message,
            "is_active": True
        }, on_conflict="user_id, target_peer").execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_add_custom_target_message: {e}")
        return False

def db_delete_custom_target_message(user_id: int, custom_id: int) -> bool:
    """Hapus pesan kustom per target."""
    try:
        supabase = get_supabase()
        supabase.table("custom_target_messages").delete().eq("id", custom_id).eq("user_id", user_id).execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_delete_custom_target_message: {e}")
        return False

def db_update_subscription_schedule(user_id: int, start_hour: int, end_hour: int) -> bool:
    """Update jam operasional sebar harian user."""
    try:
        supabase = get_supabase()
        now_str = datetime.now(timezone.utc).isoformat()
        supabase.table("subscriptions")\
            .update({
                "schedule_start_hour": start_hour,
                "schedule_end_hour": end_hour
            })\
            .eq("user_id", user_id)\
            .eq("status", "active")\
            .gt("end_date", now_str)\
            .execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_update_subscription_schedule: {e}")
        return False

def db_cooldown_client_userbot(phone_number: str, until_str: str) -> bool:
    """Masukkan userbot klien ke masa cooldown/istirahat berdasarkan nomor HP."""
    try:
        supabase = get_supabase()
        try:
            dt = datetime.strptime(until_str, "%Y-%m-%d %H:%M:%S")
            iso_str = dt.isoformat()
        except:
            iso_str = until_str
        supabase.table("userbots").update({"cooldown_until": iso_str}).eq("phone_number", phone_number).execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_cooldown_client_userbot: {e}")
        return False


def db_get_admin_userbot_by_id(aid: int):
    """Mengambil detail satu bot admin berdasarkan ID-nya."""
    try:
        supabase = get_supabase()
        res = supabase.table("admin_userbots").select("session_name, phone_number, id, status").eq("id", aid).execute()
        if res.data:
            r = res.data[0]
            return (r["session_name"], r["phone_number"], r["id"], r["status"])
        return None
    except Exception as e:
        logger.error(f"Error in db_get_admin_userbot_by_id: {e}")
        return None

def db_get_lpm_sharded_for_admin(admin_id: int, limit: int = 100) -> list:
    """
    Mendapatkan porsi LPM eksklusif (slot tetap 100 LPM) untuk bot admin tertentu.

    Prinsip sharding statis berdasarkan urutan ID terdaftar di database:
      - Admin ke-1 (ID terkecil) → LPM slot 1–100   (offset 0)
      - Admin ke-2               → LPM slot 101–200  (offset 100)
      - Admin ke-N               → LPM slot (N-1)*100 + 1 … N*100

    Penting:
      - Menggunakan SEMUA admin_userbots (bukan hanya yang connected) agar
        indeks/slot tidak bergeser saat ada admin yang disconnect atau reconnect.
      - Parameter `limit` pada fungsi ini selalu diabaikan dan dioverride ke 100
        agar setiap admin selalu mendapat slot penuh tanpa overlap.
    """
    SLOT_SIZE = 100  # Kapasitas tetap per admin userbot
    try:
        supabase = get_supabase()

        # ── Ambil SEMUA admin (termasuk disconnected) diurutkan by ID ascending ──
        # Menggunakan semua admin agar slot tidak bergeser saat status berubah
        res_admins = supabase.table("admin_userbots") \
            .select("id") \
            .order("id", desc=False) \
            .execute()
        admins = res_admins.data or []

        admin_ids = [a["id"] for a in admins]
        if admin_id not in admin_ids:
            logger.warning(f"[LPM Sharding] admin_id={admin_id} tidak ditemukan di tabel admin_userbots. Fallback ke LPM acak.")
            return db_get_active_lpm_lists(SLOT_SIZE)

        # ── Hitung offset statis berdasarkan posisi urutan ──
        idx = admin_ids.index(admin_id)   # 0-based index
        start_offset = idx * SLOT_SIZE    # Admin 1 → 0, Admin 2 → 100, dst
        end_offset   = start_offset + SLOT_SIZE - 1

        logger.info(
            f"[LPM Sharding] admin_id={admin_id} | posisi ke-{idx+1} dari {len(admin_ids)} admin "
            f"| slot LPM {start_offset+1}–{end_offset+1} (offset Supabase: {start_offset}–{end_offset})"
        )

        # ── Ambil 100 LPM dari slot yang telah ditentukan ──
        res_lpm = supabase.table("lpm_lists") \
            .select("group_link") \
            .eq("is_active", True) \
            .eq("is_blacklisted", False) \
            .order("id", desc=False) \
            .range(start_offset, end_offset) \
            .execute()

        links = [r["group_link"] for r in res_lpm.data] if res_lpm.data else []

        if not links:
            logger.warning(
                f"[LPM Sharding] Slot offset {start_offset}–{end_offset} kosong untuk admin_id={admin_id}. "
                f"Pool LPM mungkin belum mencapai {end_offset+1} entri. Fallback ke LPM acak global."
            )
            return db_get_active_lpm_lists(SLOT_SIZE)

        logger.info(f"[LPM Sharding] admin_id={admin_id} mendapat {len(links)} LPM dari slot-nya.")

        import random
        random.shuffle(links)  # Acak urutan pengiriman agar terkesan manusiawi
        return links
    except Exception as e:
        logger.error(f"Error in db_get_lpm_sharded_for_admin (admin_id={admin_id}): {e}")
        return []

def db_transfer_userbot_session(old_uid: int, new_uid: int) -> tuple:
    """Mentransfer sesi userbot dan subscription aktif dari user_id lama ke user_id baru secara aman."""
    try:
        supabase = get_supabase()
        db_ensure_user(new_uid)
        
        # 1. Cek apakah old_uid memiliki userbot terdaftar
        res_ub = supabase.table("userbots").select("*").eq("user_id", old_uid).execute()
        if not res_ub.data:
            return False, "Akun Anda tidak memiliki userbot terhubung yang dapat ditransfer."
            
        ub_data = res_ub.data[0]
        phone = ub_data["phone_number"]
        old_session = ub_data["session_name"]
        phone_clean = phone.replace("+", "").replace(" ", "")
        new_session = f"user_{phone_clean}"
        
        # Pindahkan file fisik .session secara lokal hanya jika nama sesinya berbeda
        if old_session != new_session:
            old_path = f"data/sessions/{old_session}.session"
            new_path = f"data/sessions/{new_session}.session"
            
            if os.path.exists(old_path):
                try:
                    import shutil
                    shutil.move(old_path, new_path)
                    # Pindahkan file journal jika ada
                    old_journal = f"{old_path}-journal"
                    new_journal = f"{new_path}-journal"
                    if os.path.exists(old_journal):
                        try: shutil.move(old_journal, new_journal)
                        except: pass
                except Exception as file_err:
                    logger.error(f"Gagal memindahkan file sesi fisik: {file_err}")
                    return False, f"Gagal memindahkan file sesi: {file_err}"
        
        # 3. Update tabel userbots (hapus new_uid lama jika ada, lalu update phone lama ke user baru)
        supabase.table("userbots").delete().eq("user_id", new_uid).execute()
        
        supabase.table("userbots").update({
            "user_id": new_uid,
            "session_name": new_session
        }).eq("phone_number", phone).execute()
        
        # 4. Pindahkan subskripsi aktif jika ada
        res_sub = supabase.table("subscriptions").select("*").eq("user_id", old_uid).eq("status", "active").execute()
        if res_sub.data:
            for sub in res_sub.data:
                # Update user_id subskripsi ke new_uid
                supabase.table("subscriptions").update({"user_id": new_uid}).eq("id", sub["id"]).execute()
                
        # 5. Pindahkan materi iklan
        res_ad = supabase.table("user_ads").select("*").eq("user_id", old_uid).execute()
        if res_ad.data:
            # Hapus iklan new_uid lama
            supabase.table("user_ads").delete().eq("user_id", new_uid).execute()
            for ad in res_ad.data:
                supabase.table("user_ads").update({"user_id": new_uid}).eq("id", ad["id"]).execute()
                
        return True, f"Berhasil memindahkan userbot ke User ID `{new_uid}`!"
    except Exception as e:
        logger.error(f"Error in db_transfer_userbot_session: {e}")
        return False, f"Terjadi kesalahan saat transfer: {e}"

def db_update_userbot_mass_settings(pm_permit_status: bool = None, custom_bio: str = None) -> bool:
    """Melakukan update massal pengaturan PM Permit atau Kustom Bio untuk seluruh userbot klien."""
    try:
        supabase = get_supabase()
        update_data = {}
        if pm_permit_status is not None:
            update_data["pm_permit_status"] = pm_permit_status
        if custom_bio is not None:
            update_data["custom_bio"] = custom_bio
            
        if not update_data:
            return False
            
        supabase.table("userbots").update(update_data).neq("user_id", 0).execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_update_userbot_mass_settings: {e}")
        return False

def db_mass_update_subscription_interval(interval_hours: float) -> bool:
    """Mengubah interval broadcast seluruh subskripsi aktif secara massal."""
    try:
        supabase = get_supabase()
        now_str = datetime.now(timezone.utc).isoformat()
        supabase.table("subscriptions")\
            .update({"broadcast_interval_hours": interval_hours})\
            .eq("status", "active")\
            .gt("end_date", now_str)\
            .execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_mass_update_subscription_interval: {e}")
        return False

def db_save_admin_promote_ad(content: str, buttons_json: str) -> bool:
    """Menyimpan materi iklan promosi admin beserta konfigurasi tombol inline."""
    try:
        from src.config import ADMIN_ID
        db_ensure_user(ADMIN_ID)
        supabase = get_supabase()
        # Hapus iklan promosi lama admin
        supabase.table("user_ads").delete().eq("user_id", ADMIN_ID).eq("title", "Promosi Admin").execute()
        # Simpan iklan baru
        supabase.table("user_ads").insert({
            "user_id": ADMIN_ID,
            "title": "Promosi Admin",
            "content": content or "",
            "buttons_json": buttons_json or ""
        }).execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_save_admin_promote_ad: {e}")
        return False

def db_get_admin_promote_ad() -> tuple:
    """Mengambil materi iklan promosi admin dan konfigurasi tombol inline."""
    try:
        from src.config import ADMIN_ID
        supabase = get_supabase()
        res = supabase.table("user_ads")\
            .select("content, buttons_json")\
            .eq("user_id", ADMIN_ID)\
            .eq("title", "Promosi Admin")\
            .order("created_at", desc=True)\
            .limit(1)\
            .execute()
        if res.data:
            r = res.data[0]
            return r.get("content", ""), r.get("buttons_json", "")
        return "", ""
    except Exception as e:
        logger.error(f"Error in db_get_admin_promote_ad: {e}")
        return "", ""

def db_toggle_pm_permit(phone_number: str) -> tuple:
    """Mengubah status PM Permit (aktif/nonaktif) untuk userbot klien berdasarkan nomor HP."""
    try:
        supabase = get_supabase()
        res = supabase.table("userbots").select("pm_permit_status").eq("phone_number", phone_number).execute()
        curr = res.data[0]["pm_permit_status"] if res.data else False
        new_status = not curr
        supabase.table("userbots").update({"pm_permit_status": new_status}).eq("phone_number", phone_number).execute()
        return True, new_status
    except Exception as e:
        logger.error(f"Error in db_toggle_pm_permit: {e}")
        return False, False

def db_update_custom_bio(phone_number: str, bio: str) -> bool:
    """Mengubah bio kustom untuk userbot klien berdasarkan nomor HP."""
    try:
        supabase = get_supabase()
        supabase.table("userbots").update({"custom_bio": bio}).eq("phone_number", phone_number).execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_update_custom_bio: {e}")
        return False

def db_update_admin_lpm_description(admin_id: int, new_desc: str) -> bool:
    """Memperbarui deskripsi kustom slot LPM untuk admin pool."""
    try:
        supabase = get_supabase()
        supabase.table("admin_userbots").update({"lpm_description": new_desc}).eq("id", admin_id).execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_update_admin_lpm_description: {e}")
        return False

def db_get_userbots_by_subscription(sub_id: int):
    """Mengambil daftar semua userbot (sesi, nomor telepon, status) yang terikat dengan ID langganan tertentu."""
    try:
        supabase = get_supabase()
        try:
            res = supabase.table("userbots")\
                .select("session_name, phone_number, status, pm_permit_status, custom_bio")\
                .eq("subscription_id", sub_id)\
                .execute()
            return res.data or []
        except Exception as e_select:
            logger.warning(f"Gagal select lengkap userbots: {e_select}. Fallback ke kolom dasar.")
            res = supabase.table("userbots")\
                .select("session_name, phone_number, status")\
                .eq("subscription_id", sub_id)\
                .execute()
            data = res.data or []
            for r in data:
                r["pm_permit_status"] = False
                r["custom_bio"] = ""
            return data
    except Exception as e:
        logger.error(f"Error in db_get_userbots_by_subscription: {e}")
        return []

def db_get_active_subscriptions_for_scheduler():
    """Mengambil semua langganan aktif beserta interval broadcast masing-masing."""
    try:
        supabase = get_supabase()
        now_str = datetime.now(timezone.utc).isoformat()
        res = supabase.table("subscriptions")\
            .select("id, user_id, package_name, broadcast_interval_hours, schedule_start_hour, schedule_end_hour")\
            .eq("status", "active")\
            .gt("end_date", now_str)\
            .execute()
        return res.data or []
    except Exception as e:
        logger.error(f"Error in db_get_active_subscriptions_for_scheduler: {e}")
        return []

def db_get_last_broadcast_time_by_sub(sub_id: int):
    """Mendeteksi waktu broadcast terakhir per langganan dari forward_logs."""
    try:
        supabase = get_supabase()
        res = supabase.table("forward_logs")\
            .select("sent_at")\
            .eq("subscription_id", sub_id)\
            .eq("status", "success")\
            .order("sent_at", desc=True)\
            .limit(1)\
            .execute()
        if res.data:
            sent_at = res.data[0]["sent_at"]
            try:
                clean_date = sent_at.replace("T", " ").replace("Z", "").split("+")[0].split(".")[0]
                return datetime.strptime(clean_date.strip(), "%Y-%m-%d %H:%M:%S")
            except Exception as ex:
                logger.error(f"Gagal parse date {sent_at}: {ex}")
        return None
    except Exception as e:
        logger.error(f"Error in db_get_last_broadcast_time_by_sub: {e}")
        return None

def db_get_active_subscriptions_of_user(user_id: int):
    """Mengambil semua langganan aktif milik user untuk dirender di panel kontrol."""
    try:
        supabase = get_supabase()
        now_str = datetime.now(timezone.utc).isoformat()
        res = supabase.table("subscriptions")\
            .select("id, package_name, capacity_lpm, end_date, broadcast_interval_hours, max_userbots")\
            .eq("user_id", user_id)\
            .eq("status", "active")\
            .gt("end_date", now_str)\
            .order("end_date", desc=True)\
            .execute()
        return res.data or []
    except Exception as e:
        logger.error(f"Error in db_get_active_subscriptions_of_user: {e}")
        return []

def db_get_active_subscription_broadcast_details_by_id(sub_id: int):
    """Mengambil detail broadcast langganan berdasarkan ID langganan."""
    try:
        supabase = get_supabase()
        res = supabase.table("subscriptions")\
            .select("package_name, capacity_lpm, request_lpm, broadcast_interval_hours, assigned_admin_ub_id")\
            .eq("id", sub_id)\
            .execute()
        if res.data:
            row = res.data[0]
            return (
                row["package_name"],
                row["capacity_lpm"],
                row["request_lpm"],
                row["broadcast_interval_hours"],
                row["assigned_admin_ub_id"]
            )
        return None
    except Exception as e:
        logger.error(f"Error in db_get_active_subscription_broadcast_details_by_id: {e}")
        return None

def db_upload_session_file(session_name: str) -> bool:
    """Mengunggah file .session lokal ke Supabase Storage (bucket 'sessions')."""
    try:
        supabase = get_supabase()
        file_path = f"data/sessions/{session_name}.session"
        if not os.path.exists(file_path):
            logger.warning(f"File sesi lokal {file_path} tidak ditemukan untuk diunggah.")
            return False
            
        with open(file_path, 'rb') as f:
            file_data = f.read()
            
        # Pastikan bucket 'sessions' ada (buat jika belum ada)
        try:
            supabase.storage.create_bucket('sessions', options={'public': False})
        except Exception:
            pass
            
        supabase.storage.from_('sessions').upload(
            path=f"{session_name}.session",
            file=file_data,
            file_options={"content-type": "application/octet-stream", "upsert": "true"}
        )
        logger.info(f"🟢 Sesi {session_name}.session berhasil disinkronkan ke Supabase Storage.")
        return True
    except Exception as e:
        logger.error(f"Gagal mengunggah file sesi {session_name} ke Supabase Storage: {e}")
        return False

def db_download_session_file(session_name: str) -> bool:
    """Mengunduh file .session dari Supabase Storage (bucket 'sessions') ke disk lokal."""
    try:
        supabase = get_supabase()
        file_path = f"data/sessions/{session_name}.session"
        
        # Unduh file biner
        res = supabase.storage.from_('sessions').download(f"{session_name}.session")
        if res:
            os.makedirs("data/sessions", exist_ok=True)
            with open(file_path, 'wb') as f:
                f.write(res)
            logger.info(f"🟢 Sesi {session_name}.session berhasil diunduh dari Supabase Storage.")
            return True
        return False
    except Exception as e:
        logger.debug(f"Gagal mengunduh file sesi {session_name} dari Supabase Storage: {e}")
        return False


