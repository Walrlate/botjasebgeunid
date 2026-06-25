#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GEUNID JASEB - Pembuat Berkas Sesi (.session) Lokal
Jalankan script ini di komputer/laptop Anda untuk membuat file sesi Telegram.
Setelah berhasil, upload file hasil (.session) langsung ke Telegram Bot.
"""
import os
import sys

print("=" * 60)
print("  PEMBUAT BERKAS SESI USERBOT LOKAL - GEUNID JASEB")
print("=" * 60)
print()

try:
    from telethon import TelegramClient
    from telethon.network.connection.tcpobfuscated import ConnectionTcpObfuscated
except ImportError:
    print("[ERROR] Pustaka Telethon belum terinstall.")
    print("Silakan jalankan perintah berikut di terminal Anda terlebih dahulu:")
    print("   pip install telethon")
    print()
    input("Tekan Enter untuk keluar...")
    sys.exit(1)

# API ID & API HASH bawaan untuk koneksi Telegram
API_ID = 33241986
API_HASH = "7a06ee0626359f4f46bc0f5082f81155"

def get_valid_phone():
    while True:
        phone = input("Masukkan nomor HP Telegram Anda (format: +628xxx): ").strip().replace(" ", "")
        if phone.startswith("+") and len(phone) >= 10:
            return phone
        print("❌ Format salah! Nomor HP wajib diawali tanda '+' dan kode negara. Contoh: +628123456789")
        print()

async def main():
    phone = get_valid_phone()
    # Format nama berkas: +628xxx.session
    session_name = phone
    
    print()
    print(f"[...] Menghubungkan ke Telegram untuk nomor {phone}...")
    client = TelegramClient(
        session_name, 
        API_ID, 
        API_HASH,
        connection=ConnectionTcpObfuscated
    )
    
    try:
        await client.start(phone=lambda: phone)
        me = await client.get_me()
        display_name = f"{me.first_name} {me.last_name}".strip() if me.last_name else me.first_name
        
        print()
        print("=" * 60)
        print("🎉 LOGIN BERHASIL!")
        print("=" * 60)
        print(f"👤 Nama Akun : {display_name}")
        print(f"📞 Nomor HP  : {phone}")
        print(f"📁 Berkas Sesi: {session_name}.session")
        print("=" * 60)
        print()
        print("Langkah selanjutnya:")
        print(f"1. Temukan berkas bernama '{session_name}.session' di folder yang sama dengan script ini.")
        print("2. Kirim/Drag-and-drop berkas tersebut langsung ke chat Telegram Bot Jaseb Anda.")
        print("3. Bot akan otomatis mendeteksi dan mengaktifkan userbot Anda!")
        print()
        
    except Exception as e:
        print()
        print(f"❌ Terjadi kesalahan: {e}")
    finally:
        await client.disconnect()
        
    input("Tekan Enter untuk keluar...")

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
