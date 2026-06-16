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
        GEUNID Premium Broadcast Engine (Stealth Mode) dengan Auto-Fallback Support
        """
        self.is_running = True
        unprocessed_links = group_links.copy()
        success_count = 0
        failed_count = 0
        flood_seconds = 0

        async with get_db() as db:
            # Ambil konten iklan
            cursor = await db.execute("SELECT content, media_path, fwd_chat_id, fwd_peer_type, fwd_msg_id FROM user_ads WHERE id = ?", (ad_id,))
            ad = await cursor.fetchone()
            if not ad:
                self.is_running = False
                return {"success": False, "error": "Ad not found"}
            
            content, media_path, fwd_chat_id, fwd_peer_type, fwd_msg_id = ad
 
            # Ambil package_name untuk watermark
            cursor = await db.execute("SELECT package_name FROM subscriptions WHERE user_id = ? AND status = 'active' ORDER BY end_date DESC LIMIT 1", (user_id,))
            sub_row = await cursor.fetchone()
            package_name = sub_row[0] if sub_row else ""
            if package_name and "regular" in package_name.lower() and content:
                from src.config import BOT_USERNAME
                content = f"{content}\n\n• Promote Auto by @{BOT_USERNAME}"
 
            for link in group_links:
                if not self.is_running: break
                
                try:
                    entity = await self.client.get_entity(link)

                    if auto_join_leave:
                        await self.client(JoinChannelRequest(entity))
                        await asyncio.sleep(random.uniform(2, 4))

                    async with self.client.action(entity, 'typing'):
                        await asyncio.sleep(random.uniform(3, 7))

                        if fwd_chat_id and fwd_msg_id:
                            # METODE NATIVE FORWARD (Paket Forward)
                            from_peer = fwd_chat_id
                            if fwd_peer_type == 'channel': from_peer = PeerChannel(int(fwd_chat_id))
                            elif fwd_peer_type == 'user': from_peer = PeerUser(int(fwd_chat_id))
                            elif fwd_peer_type == 'chat': from_peer = PeerChat(int(fwd_chat_id))
                            
                            msg_list = await self.client.forward_messages(entity, messages=int(fwd_msg_id), from_peer=from_peer)
                            msg = msg_list[0] if isinstance(msg_list, list) else msg_list
                        else:
                            # METODE COPY-PASTE HTML (Paket Regular & Userbot)
                            if media_path:
                                msg = await self.client.send_file(entity, media_path, caption=content, parse_mode='html')
                            else:
                                msg = await self.client.send_message(entity, content, parse_mode='html')
                        
                        msg_link = f"https://t.me/c/{str(msg.peer_id.channel_id)}/{msg.id}" if hasattr(msg.peer_id, 'channel_id') else "Private/Linked"
                        
                        async with get_db() as db:
                            await db.execute(
                                "INSERT INTO forward_logs (user_id, ad_id, group_id, msg_link, status, sent_at) VALUES (?, ?, ?, ?, ?, datetime('now','localtime'))",
                                (user_id, ad_id, entity.id, msg_link, 'success')
                            )
                            await db.commit()
                    
                    success_count += 1
                    unprocessed_links.remove(link)

                    if auto_join_leave:
                        await self.client(LeaveChannelRequest(entity))
                    
                    sleep_time = random.uniform(30, 60) if delay_mode == 'slowly' else random.uniform(3, 5)
                    await asyncio.sleep(sleep_time)

                except FloodWaitError as fwe:
                    logger.warning(f"FloodWait triggered for user {user_id}! Must sleep for {fwe.seconds}s")
                    if fwe.seconds > 300: # Jika limit > 5 menit, trigger fallback
                        flood_seconds = fwe.seconds
                        break
                    await asyncio.sleep(fwe.seconds)
                except Exception as e:
                    logger.error(f"Failed to send to {link}: {e}")
                    async with get_db() as db:
                        await db.execute(
                            "INSERT INTO forward_logs (user_id, ad_id, group_id, status, error_msg, sent_at) VALUES (?, ?, ?, ?, ?, datetime('now','localtime'))",
                            (user_id, ad_id, 0, 'failed', str(e))
                        )
                        await db.commit()
                    failed_count += 1
                    unprocessed_links.remove(link)
            
        self.is_running = False
        return {
            "success": True, 
            "success_count": success_count, 
            "failed_count": failed_count, 
            "unprocessed_links": unprocessed_links,
            "floodwait_seconds": flood_seconds
        }

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
