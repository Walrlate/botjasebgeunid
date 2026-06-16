"""
database.py — Data Access Layer (DAL) ke Supabase (PostgreSQL)
GeunID Jaseb Master - Enterprise Edition
==============================================================
Menggantikan seluruh dependensi aiosqlite dengan Supabase Client.
"""

import os
import logging
import random
from datetime import datetime, timedelta
from src.supabase_client import get_supabase

logger = logging.getLogger(__name__)

def normalize_date(date_str: str) -> str:
    """Mengubah format ISO dari Supabase ke format YYYY-MM-DD HH:MM:SS untuk kompatibilitas."""
    if not date_str:
        return ""
    try:
        # Ganti 'T' dengan spasi, hilangkan milidetik dan offset zona waktu
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
    """Inisialisasi koneksi ke Supabase dan memverifikasi koneksi."""
    try:
        supabase = get_supabase()
        if supabase:
            logger.info("✅ Supabase Enterprise DAL Berhasil Diinisialisasi.")
            return True
    except Exception as e:
        logger.error(f"❌ Gagal inisialisasi Supabase DAL: {e}")
        raise e

def db_ensure_user(user_id: int, username: str = "", full_name: str = ""):
    """Memastikan user_id sudah ada di tabel users untuk menghindari pelanggaran foreign key."""
    try:
        supabase = get_supabase()
        res = supabase.table("users").select("user_id").eq("user_id", user_id).execute()
        if not res.data:
            supabase.table("users").insert({
                "user_id": user_id,
                "username": username or "",
                "full_name": full_name or "",
            }).execute()
            logger.info(f"👤 User baru terdaftar otomatis: {user_id}")
    except Exception as e:
        logger.error(f"Error in db_ensure_user untuk {user_id}: {e}")

# ─────────────────────────────────────────
# HELPER LANGGANAN (SUBSCRIPTIONS)
# ─────────────────────────────────────────

def db_get_active_subscription_id(user_id: int):
    try:
        supabase = get_supabase()
        now_str = datetime.now().isoformat()
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
        now_str = datetime.now().isoformat()
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
        now_str = datetime.now().isoformat()
        res = supabase.table("subscriptions")\
            .select("id, end_date")\
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
                normalize_date(row["end_date"])
            )
        return None
    except Exception as e:
        logger.error(f"Error in db_get_active_subscription_id_and_end: {e}")
        return None

def db_get_active_subscription_broadcast_details(user_id: int):
    try:
        supabase = get_supabase()
        now_str = datetime.now().isoformat()
        res = supabase.table("subscriptions")\
            .select("package_name, capacity_lpm, request_lpm, broadcast_interval_hours")\
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
                row["broadcast_interval_hours"]
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

def db_add_subscription(user_id: int, package_name: str, capacity_lpm: int, start_date: str, end_date: str):
    try:
        db_ensure_user(user_id)
        # Konversi ke ISO format untuk PostgreSQL
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
        supabase.table("subscriptions").insert({
            "user_id": user_id,
            "package_name": package_name,
            "capacity_lpm": capacity_lpm,
            "start_date": sd_iso,
            "end_date": ed_iso,
            "status": "active",
            "broadcast_interval_hours": 0.5
        }).execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_add_subscription: {e}")
        return False

def db_update_subscription_dates(sub_id: int, end_date: str, capacity_lpm: int, package_name: str):
    try:
        try:
            ed_dt = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S")
            ed_iso = ed_dt.isoformat()
        except:
            ed_iso = end_date
            
        supabase = get_supabase()
        supabase.table("subscriptions").update({
            "end_date": ed_iso,
            "capacity_lpm": capacity_lpm,
            "package_name": package_name
        }).eq("id", sub_id).execute()
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
        now_str = datetime.now().isoformat()
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
        now = datetime.now()
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

def db_save_user_ad(user_id: int, content: str, media_path: str):
    try:
        db_ensure_user(user_id)
        supabase = get_supabase()
        # Hapus iklan lama
        supabase.table("user_ads").delete().eq("user_id", user_id).execute()
        # Simpan iklan baru
        supabase.table("user_ads").insert({
            "user_id": user_id,
            "title": "Iklan Utama",
            "content": content or "",
            "media_path": media_path or ""
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

def db_get_active_userbots_count() -> int:
    try:
        supabase = get_supabase()
        res = supabase.table("userbots").select("user_id", count="exact").eq("status", "connected").execute()
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
        supabase.table("userbots").upsert({
            "user_id": user_id,
            "phone_number": phone,
            "session_name": session,
            "status": "connected"
        }, on_conflict="user_id").execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_save_userbot: {e}")
        return False

def db_update_userbot_status(user_id: int, status: str):
    try:
        supabase = get_supabase()
        supabase.table("userbots").update({"status": status}).eq("user_id", user_id).execute()
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
    try:
        supabase = get_supabase()
        res = supabase.table("admin_userbots").select("id, phone_number, status, cooldown_until").execute()
        if res.data:
            return [(r["id"], r["phone_number"], r["status"], normalize_date(r.get("cooldown_until"))) for r in res.data]
        return []
    except Exception as e:
        logger.error(f"Error in db_get_admin_userbots: {e}")
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
            
        now = datetime.now()
        active_admins = []
        for r in res.data:
            cooldown = r.get("cooldown_until")
            if cooldown:
                try:
                    cooldown_clean = normalize_date(cooldown)
                    cooldown_dt = datetime.strptime(cooldown_clean, "%Y-%m-%d %H:%M:%S")
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


# ─────────────────────────────────────────
# HELPER TRANSAKSI (TRANSACTIONS)
# ─────────────────────────────────────────

def db_save_transaction(user_id: int, trx_id: str, package_id: str, amount: int, payment_url: str):
    try:
        db_ensure_user(user_id)
        supabase = get_supabase()
        supabase.table("transactions").insert({
            "user_id": user_id,
            "trx_id": trx_id,
            "package_id": package_id,
            "amount": amount,
            "payment_url": payment_url,
            "status": "pending"
        }).execute()
        return True
    except Exception as e:
        logger.error(f"Error in db_save_transaction: {e}")
        return False

def db_get_transaction(trx_id: str):
    try:
        supabase = get_supabase()
        res = supabase.table("transactions").select("user_id, amount, package_id, status").eq("trx_id", trx_id).execute()
        if res.data:
            r = res.data[0]
            return (r["user_id"], r["amount"], r["package_id"], r["status"])
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
        res = supabase.table("lpm_lists")\
            .select("group_link")\
            .eq("is_active", True)\
            .eq("is_blacklisted", False)\
            .order("member_count", desc=True)\
            .limit(limit)\
            .execute()
        if res.data:
            return [r["group_link"] for r in res.data]
        return []
    except Exception as e:
        logger.error(f"Error in db_get_active_lpm_lists: {e}")
        return []

def db_insert_forward_log(user_id: int, ad_id: int, group_id: int, msg_link: str, status: str, error_msg: str = ""):
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
            "sent_at": datetime.now().isoformat()
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
