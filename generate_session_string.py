#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script pembantu untuk mengkonversi file session Telethon yang sudah ada
menjadi StringSession yang bisa disimpan sebagai Environment Variable di Railway.
"""
import asyncio
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

API_ID = int(os.getenv('API_ID', 0))
API_HASH = os.getenv('API_HASH', '')

async def main():
    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession
        
        print("=" * 60)
        print("  GENERATOR SESSION STRING - GEUNID JASEB BOT")
        print("=" * 60)
        print()
        
        # Coba baca dari file session yang sudah ada
        session_files = ['bot_session', 'data/bot_session']
        existing_session = None
        
        for sf in session_files:
            sf_path = sf + '.session'
            if os.path.exists(sf_path):
                print(f"[OK] Ditemukan file session: {sf_path}")
                existing_session = sf
                break
        
        if existing_session:
            print("[...] Mengkonversi file session yang ada menjadi StringSession...")
            async with TelegramClient(existing_session, API_ID, API_HASH) as client:
                string_session = client.session.save()
                print()
                print("[SUKSES] Berhasil! Salin StringSession di bawah ini:")
                print("=" * 60)
                print(string_session)
                print("=" * 60)
                print()
                print("Langkah selanjutnya di Railway:")
                print("1. Buka Railway Dashboard > Project Anda > Variables")
                print("2. Tambahkan variable baru:")
                print("   Key   : BOT_SESSION_STRING")
                print(f"   Value : (tempel string panjang yang ada di atas)")
                print()
        else:
            print("[!] Tidak ada file session yang ditemukan.")
            print("Membuat sesi baru (perlu login via nomor HP)...")
            print()
            phone = input("Masukkan nomor HP Anda (format: +628xxx): ").strip()
            
            async with TelegramClient(StringSession(), API_ID, API_HASH) as client:
                await client.start(phone=phone)
                string_session = client.session.save()
                print()
                print("[SUKSES] Login berhasil! StringSession Anda:")
                print("=" * 60)
                print(string_session)
                print("=" * 60)
                
    except ImportError:
        print("[ERROR] Telethon belum terinstall.")
        print("   Jalankan: pip install telethon python-dotenv")

if __name__ == '__main__':
    asyncio.run(main())
