"""
supabase_client.py - Konektor Tunggal ke Supabase (PostgreSQL)
GeunID Jaseb Master - Enterprise Edition
"""
import os
import logging
from supabase import create_client, Client
from src.config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

supabase: Client = None

def init_supabase():
    global supabase
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("SUPABASE_URL atau SUPABASE_KEY belum disetel!")
        raise ValueError("Kredensial Supabase kosong.")
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("✅ Koneksi Supabase Berhasil Diinisialisasi.")
    return supabase

def get_supabase() -> Client:
    global supabase
    if supabase is None:
        return init_supabase()
    return supabase
