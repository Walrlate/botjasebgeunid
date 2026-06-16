import asyncio
import random
import logging
import os
from telethon import TelegramClient
from telethon.network import ConnectionTcpObfuscated
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.types import PeerChannel, PeerUser, PeerChat
from telethon.errors import FloodWaitError
from src.database import (
    db_get_user_ad_by_id,
    db_get_active_subscription_status,
    db_insert_forward_log
)

logger = logging.getLogger(__name__)

class JasebEngine:
    def __init__(self, user_session_name, api_id, api_hash):
        self.client = TelegramClient(
            user_session_name, 
            api_id, 
            api_hash, 
            receive_updates=False,
            connection=ConnectionTcpObfuscated,
            timeout=30,
            connection_retries=10,
            retry_delay=5
        )
        self.is_running = False

    async def start(self):
        if not self.client.is_connected():
            await self.client.connect()

    async def stop(self):
        try:
            if self.client.is_connected():
                await self.client.disconnect()
        except: pass
        self.is_running = False

    async def broadcast_with_stealth(self, user_id, ad_id, group_links, delay_mode='slowly'):
        """
        GEUNID ANTI-BAN BROADCAST ENGINE
        """
        self.is_running = True
        unprocessed_links = group_links.copy()
        success_count = 0
        failed_count = 0
        flood_seconds = 0

        ad = db_get_user_ad_by_id(ad_id)
        if not ad:
            self.is_running = False
            return {"success": False, "error": "Ad not found"}
        
        content, media_path, fwd_chat_id, fwd_peer_type, fwd_msg_id = ad

        sub_row = db_get_active_subscription_status(user_id)
        package_name = sub_row[0] if sub_row else ""

        # Branding Otomatis
        if content and not (fwd_chat_id and fwd_msg_id):
            import src.config
            if "regular" in package_name.lower():
                content = f"{content}\n\n• Promoted by @{src.config.BOT_USERNAME}"

        # Fetch joined dialogs to cache memberships and avoid JoinChannelRequest
        joined_ids = set()
        try:
            async for dialog in self.client.iter_dialogs(limit=None):
                if dialog.is_group or dialog.is_channel:
                    joined_ids.add(dialog.entity.id)
        except Exception as e:
            logger.error(f"Gagal mengambil daftar grup terdaftar (iter_dialogs): {e}")

        joins_this_cycle = 0
        max_joins_per_cycle = 5

        for link in group_links:
            if not self.is_running: break
            
            entity = None
            try:
                # 1. Resolve & Join private link atau public link secara cerdas
                is_private_invite = "joinchat/" in link or "+" in link
                
                if is_private_invite:
                    # Ini tautan undangan private
                    invite_hash = link.split("/")[-1].replace("+", "")
                    from telethon.tl.functions.messages import ImportChatInviteRequest
                    try:
                        # Coba join private group
                        logger.info(f"Userbot bergabung ke private invite link: {link}")
                        await self.client(ImportChatInviteRequest(invite_hash))
                        joins_this_cycle += 1
                        await asyncio.sleep(random.uniform(20, 30))
                    except Exception as invite_err:
                        if "UserAlreadyParticipantError" in str(invite_err):
                            pass
                        else:
                            logger.error(f"Gagal join private link {link}: {invite_err}")
                            if link in unprocessed_links:
                                unprocessed_links.remove(link)
                            continue
                            
                    # Coba ambil entity chat setelah join sukses
                    try:
                        entity = await self.client.get_entity(link)
                    except Exception as ent_err:
                        logger.error(f"Gagal resolve private link setelah join {link}: {ent_err}")
                        if link in unprocessed_links:
                            unprocessed_links.remove(link)
                        continue
                else:
                    # Tautan publik biasa
                    try:
                        entity = await self.client.get_entity(link)
                    except Exception as e:
                        logger.error(f"Gagal resolve {link}: {e}")
                        if link in unprocessed_links:
                            unprocessed_links.remove(link)
                        continue

                # 2. ANTI-BAN MEMBERSHIP PROTOCOL (Untuk Public Group)
                if not is_private_invite and entity:
                    is_in_group = entity.id in joined_ids
                    if not is_in_group:
                        if joins_this_cycle >= max_joins_per_cycle:
                            logger.info(f"Batas join baru tercapai ({max_joins_per_cycle}). Menunda join {link} untuk siklus berikutnya.")
                            continue
                            
                        logger.info(f"Userbot belum bergabung ke {link}. Mencoba bergabung...")
                        await self.client(JoinChannelRequest(entity))
                        joined_ids.add(entity.id)
                        joins_this_cycle += 1
                        await asyncio.sleep(random.uniform(15, 25))

                # 3. JARVIS PROACTIVE: Simulasi Manusia (Typing) jika sudah bergabung
                try:
                    async with self.client.action(entity, 'typing'):
                        await asyncio.sleep(random.uniform(2, 4))
                except Exception as e:
                    logger.debug(f"Gagal mensimulasikan typing: {e}")

                # 4. Smart-Tagging (Dinamis)
                final_content = content
                if not (fwd_chat_id and fwd_msg_id) and random.random() < 0.2:
                    final_content = f"{final_content}\n#LPM #Promote"

                # 5. EXECUTION
                if fwd_chat_id and fwd_msg_id:
                    clean_fwd_id = int(str(fwd_chat_id).replace("-100", ""))
                    if fwd_peer_type == 'channel': from_peer = PeerChannel(clean_fwd_id)
                    elif fwd_peer_type == 'user': from_peer = PeerUser(clean_fwd_id)
                    elif fwd_peer_type == 'chat': from_peer = PeerChat(clean_fwd_id)
                    
                    msg_list = await self.client.forward_messages(entity, messages=int(fwd_msg_id), from_peer=from_peer)
                    if not msg_list:
                        raise ValueError("Pesan sumber forward tidak ditemukan atau tidak dapat diakses.")
                    msg = msg_list[0] if isinstance(msg_list, list) else msg_list
                else:
                    if media_path and os.path.exists(media_path):
                        msg = await self.client.send_file(entity, media_path, caption=final_content, parse_mode='html')
                    else:
                        msg = await self.client.send_message(entity, final_content, parse_mode='html')
                
                # 6. Link Generation (ROBUST)
                if hasattr(entity, 'username') and entity.username:
                    msg_link = f"https://t.me/{entity.username}/{msg.id}"
                elif hasattr(msg.peer_id, 'channel_id'):
                    msg_link = f"https://t.me/c/{msg.peer_id.channel_id}/{msg.id}"
                else:
                    msg_link = "Private/Linked"
                
                db_insert_forward_log(user_id, ad_id, entity.id, msg_link, 'success')
                
                success_count += 1
                unprocessed_links.remove(link)

                # PERSISTENT PROTOCOL: No Leave.
                sleep_time = random.uniform(30, 60) if delay_mode == 'slowly' else random.uniform(5, 10)
                await asyncio.sleep(sleep_time)

            except FloodWaitError as fwe:
                logger.warning(f"Terkena FloodWait selama {fwe.seconds} detik.")
                if fwe.seconds > 300:
                    flood_seconds = fwe.seconds
                    break
                await asyncio.sleep(fwe.seconds)
            except Exception as e:
                logger.error(f"Error {link}: {e}")
                failed_count += 1
                if link in unprocessed_links:
                    unprocessed_links.remove(link)
                # Catat kegagalan ke database
                ent_id = entity.id if ('entity' in locals() and entity) else 0
                db_insert_forward_log(user_id, ad_id, ent_id, "", 'failed', str(e))
        
        self.is_running = False
        return {"success": True, "success_count": success_count, "failed_count": failed_count, "unprocessed_links": unprocessed_links, "floodwait_seconds": flood_seconds}

    @staticmethod
    async def verify_lpm_group(client, group_link):
        try:
            if "joinchat/" in group_link or "+" in group_link:
                invite_hash = group_link.split("/")[-1].replace("+", "")
                from telethon.tl.functions.messages import CheckChatInviteRequest
                try:
                    invite_info = await client(CheckChatInviteRequest(invite_hash))
                    title = ""
                    participants_count = 0
                    chat_id = 0
                    
                    from telethon.tl.types import ChatInviteAlready, ChatInvite
                    if isinstance(invite_info, ChatInviteAlready):
                        title = invite_info.chat.title
                        participants_count = getattr(invite_info.chat, 'participants_count', 0)
                        chat_id = invite_info.chat.id
                    elif isinstance(invite_info, ChatInvite):
                        title = invite_info.title
                        participants_count = invite_info.participants_count
                    return {"success": True, "group_id": chat_id, "group_name": title, "member_count": participants_count}
                except Exception as e:
                    return {"success": False, "error": str(e)}

            clean_link = group_link.strip().replace("https://t.me/", "").replace("t.me/", "").replace("@", "")
            if not clean_link: return {"success": False, "error": "Empty"}
            entity = await client.get_entity(clean_link)
            member_count = 0
            if hasattr(entity, 'participants_count'): member_count = entity.participants_count
            else:
                try:
                    from telethon.tl.functions.channels import GetFullChannelRequest
                    full_info = await client(GetFullChannelRequest(channel=entity))
                    member_count = full_info.full_chat.participants_count
                except: pass
            return {"success": True, "group_id": entity.id, "group_name": entity.title, "member_count": member_count}
        except Exception as e: return {"success": False, "error": str(e)}
