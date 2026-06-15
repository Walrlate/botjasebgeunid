import asyncio
import random
import logging
from telethon import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.types import PeerChannel, PeerUser, PeerChat
from telethon.errors import FloodWaitError
from src.database import get_db

logger = logging.getLogger(__name__)

class JasebEngine:
    def __init__(self, user_session_name, api_id, api_hash):
        self.client = TelegramClient(user_session_name, api_id, api_hash, receive_updates=False)
        self.is_running = False

    async def start(self):
        if not self.client.is_connected():
            await self.client.connect()

    async def stop(self):
        await self.client.disconnect()
        self.is_running = False

    async def broadcast_with_stealth(self, user_id, ad_id, group_links, delay_mode='slowly', auto_join_leave=True):
        """
        GEUNID Premium Broadcast Engine (Stealth Mode)
        
        Menerapkan ilmu otomasi terbaik:
        1. Auto-Join & Leave: Otomatis masuk grup target, kirim iklan, lalu langsung keluar agar chat bersih.
        2. Ritme Jeda (Anti-Flood 429):
           - 'slowly': Jeda aman 30-60 detik tiap pengiriman ke 1 grup.
           - 'instant': Kirim cepat antar grup (3-5 detik), jeda panjang setelah seluruh grup selesai.
        3. FloodWait Resilience: Otomatis tidur jika terkena pembatasan rate limit Telegram.
        """
        self.is_running = True
        async with get_db() as db:
            # Ambil konten iklan beserta info forward jika ada
            cursor = await db.execute("SELECT content, media_path, fwd_chat_id, fwd_peer_type, fwd_msg_id FROM user_ads WHERE id = ?", (ad_id,))
            ad = await cursor.fetchone()
            if not ad:
                logger.error(f"Ad {ad_id} not found")
                self.is_running = False
                return False
            
            content, media_path, fwd_chat_id, fwd_peer_type, fwd_msg_id = ad
 
            # Ambil package_name untuk mendeteksi apakah Regular
            cursor = await db.execute("""
                SELECT package_name FROM subscriptions 
                WHERE user_id = ? AND status = 'active'
                ORDER BY end_date DESC LIMIT 1
            """, (user_id,))
            sub_row = await cursor.fetchone()
            package_name = sub_row[0] if sub_row else ""
 
            # Tambahkan watermark jika paket Regular
            if package_name and "regular" in package_name.lower() and content:
                from src.config import BOT_USERNAME
                content = f"{content}\n\n• Promote Auto by @{BOT_USERNAME}"
 
            for link in group_links:
                if not self.is_running:
                    break
                
                try:
                    # Resolve entity
                    entity = await self.client.get_entity(link)

                    # 1. Auto-Join if enabled
                    if auto_join_leave:
                        logger.info(f"Auto-joining target group: {link}")
                        await self.client(JoinChannelRequest(entity))
                        await asyncio.sleep(random.uniform(2, 4)) # Jeda aman setelah join

                    # 2. Stealth typing simulation
                    async with self.client.action(entity, 'typing'):
                        await asyncio.sleep(random.uniform(3, 7)) # Jeda simulasi mengetik manusiawi

                        if fwd_chat_id and fwd_msg_id:
                            # METODE NATIVE FORWARD (Paket Forward)
                            if fwd_peer_type == 'username':
                                from_peer = fwd_chat_id
                            elif fwd_peer_type == 'channel':
                                from_peer = PeerChannel(int(fwd_chat_id))
                            elif fwd_peer_type == 'user':
                                from_peer = PeerUser(int(fwd_chat_id))
                            elif fwd_peer_type == 'chat':
                                from_peer = PeerChat(int(fwd_chat_id))
                            else:
                                from_peer = int(fwd_chat_id) if fwd_chat_id.isdigit() else fwd_chat_id

                            # Lakukan forward secara native
                            msg_list = await self.client.forward_messages(entity, messages=fwd_msg_id, from_peer=from_peer)
                            msg = msg_list[0] if isinstance(msg_list, list) else msg_list
                        else:
                            # METODE COPY-PASTE HTML (Paket Regular & Userbot)
                            if media_path:
                                msg = await self.client.send_file(entity, media_path, caption=content, parse_mode='html')
                            else:
                                msg = await self.client.send_message(entity, content, parse_mode='html')
                        
                        # Buat link pesan (Proof Hub)
                        msg_link = f"https://t.me/c/{str(msg.peer_id.channel_id)}/{msg.id}" if hasattr(msg.peer_id, 'channel_id') else "Private/Linked"
                        
                        # Simpan log sukses
                        await db.execute(
                            "INSERT INTO forward_logs (user_id, ad_id, group_id, msg_link, status) VALUES (?, ?, ?, ?, ?)",
                            (user_id, ad_id, entity.id, msg_link, 'success')
                        )
                    
                    logger.info(f"Successfully sent to {link}")

                    # 3. Auto-Leave if enabled to keep client chat list clean
                    if auto_join_leave:
                        logger.info(f"Auto-leaving target group: {link}")
                        await self.client(LeaveChannelRequest(entity))
                    
                    # 4. Handle Delay Mode
                    if delay_mode == 'slowly':
                        # Jeda panjang tiap pengiriman grup (Slowly)
                        sleep_time = random.uniform(30, 60)
                        logger.info(f"Delay slowly: Sleeping for {sleep_time:.2f}s before next group")
                        await asyncio.sleep(sleep_time)
                    else:
                        # Jeda instan minimal (Instant)
                        sleep_time = random.uniform(3, 5)
                        logger.info(f"Delay instant: Sleeping for {sleep_time:.2f}s before next group")
                        await asyncio.sleep(sleep_time)

                except FloodWaitError as fwe:
                    # Penanganan anti-ban / limit floodwait otomatis
                    logger.warning(f"Telegram FloodWait triggered! Must sleep for {fwe.seconds}s")
                    await db.execute(
                        "INSERT INTO forward_logs (user_id, ad_id, group_id, status, error_msg) VALUES (?, ?, ?, ?, ?)",
                        (user_id, ad_id, 0, 'failed', f"FloodWait: Harap tunggu {fwe.seconds} detik")
                    )
                    await asyncio.sleep(fwe.seconds)
                except Exception as e:
                    logger.error(f"Failed to send to {link}: {e}")
                    await db.execute(
                        "INSERT INTO forward_logs (user_id, ad_id, group_id, status, error_msg) VALUES (?, ?, ?, ?, ?)",
                        (user_id, ad_id, 0, 'failed', str(e))
                    )
                
                await db.commit()
            
            # Jika menggunakan mode 'instant', jeda panjang dilakukan di akhir seluruh siklus putaran grup
            if self.is_running and delay_mode == 'instant':
                cycle_delay = random.uniform(900, 1800) # Jeda siklus 15 - 30 menit
                logger.info(f"Instant round completed. Sleeping for {cycle_delay:.2f}s before next cycle start")
                await asyncio.sleep(cycle_delay)
        
        self.is_running = False
        return True

    def toggle_stop(self):
        self.is_running = False

    @staticmethod
    async def verify_lpm_group(client, group_link):
        """
        GEUNID Free LPM Verification Engine
        
        Memvalidasi link grup/channel Telegram secara real-time:
        1. Mengecek tipe entitas (megagroup/channel).
        2. Mendapatkan jumlah anggota (member count).
        3. Menentukan status keaktifan grup.
        """
        try:
            # Clean username/link
            clean_link = group_link.strip().replace("https://t.me/", "").replace("t.me/", "").replace("@", "")
            if not clean_link:
                return {"success": False, "error": "Link kosong"}
                
            # Resolve entity
            entity = await client.get_entity(clean_link)
            
            is_group = hasattr(entity, 'megagroup') and entity.megagroup
            is_channel = hasattr(entity, 'broadcast') and entity.broadcast
            
            member_count = 0
            if hasattr(entity, 'participants_count') and entity.participants_count is not None:
                member_count = entity.participants_count
            else:
                try:
                    from telethon.tl.functions.channels import GetFullChannelRequest
                    full_info = await client(GetFullChannelRequest(channel=entity))
                    member_count = full_info.full_chat.participants_count
                except Exception:
                    member_count = 0
                    
            return {
                "success": True,
                "group_id": entity.id,
                "group_name": entity.title,
                "member_count": member_count,
                "is_active": True,
                "type": "Supergroup" if is_group else "Channel" if is_channel else "Chat"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
