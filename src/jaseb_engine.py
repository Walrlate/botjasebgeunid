import asyncio
import random
import logging
import os
from telethon import TelegramClient
from telethon.network import ConnectionTcpObfuscated
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.types import PeerChannel, PeerUser, PeerChat
from telethon.errors import FloodWaitError
from src.database import (
    db_get_user_ad_by_id,
    db_get_active_subscription_status,
    db_insert_forward_log
)

logger = logging.getLogger(__name__)

def resolve_spintax(text: str) -> str:
    """Memutar kata secara acak berdasarkan format spintax {pilihan1|pilihan2}."""
    import re
    import random
    if not text:
        return ""
    pattern = re.compile(r'\{([^{}]+)\}')
    def replacer(match):
        choices = match.group(1).split('|')
        return random.choice(choices)
    while True:
        new_text = pattern.sub(replacer, text)
        if new_text == text:
            break
        text = new_text
    return text

class JasebEngine:
    def __init__(self, user_session_name, api_id, api_hash, existing_client=None):
        self._existing_client = existing_client
        self._owns_client = existing_client is None
        
        if existing_client:
            # Gunakan client yang sudah aktif — TIDAK buka koneksi baru
            self.client = existing_client
        else:
            # Fallback: buat client baru dari file sesi (untuk admin pool)
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
        if self._existing_client:
            # Client sudah terhubung — tidak perlu connect lagi
            if not self.client.is_connected():
                await self.client.connect()
            return
            
        if not self.client.is_connected():
            retries = 5
            while retries > 0:
                try:
                    await self.client.connect()
                    break
                except Exception as e:
                    import sqlite3
                    err_str = str(e).lower()
                    if isinstance(e, sqlite3.OperationalError) or "lock" in err_str or "locked" in err_str:
                        logger.warning(f"⚠️ Berkas sesi terkunci, mencoba kembali dalam 3 detik... (Sisa retry: {retries-1}) | Detail: {e}")
                        await asyncio.sleep(3)
                        retries -= 1
                    else:
                        raise e
            else:
                raise RuntimeError("Gagal membuka sesi Telegram karena berkas terkunci oleh proses lain.")

    async def stop(self):
        # Hanya disconnect jika kita yang membuat client-nya (bukan client yang diinjeksi)
        if self._owns_client:
            try:
                if self.client.is_connected():
                    await self.client.disconnect()
            except: pass
        self.is_running = False

    async def broadcast_with_stealth(self, user_id, ad_id, group_links, delay_mode='slowly', is_promote=False, subscription_id: int = None):
        """
        Mengirim pesan ke daftar grup target dengan jeda dinamis dan simulasi perilaku pengguna nyata.
        """
        self.is_running = True
        unprocessed_links = group_links.copy()
        success_count = 0
        failed_count = 0
        flood_seconds = 0
        success_links = []

        ad = db_get_user_ad_by_id(ad_id)
        if not ad:
            self.is_running = False
            return {"success": False, "error": "Ad not found"}
        
        content, media_path, fwd_chat_id, fwd_peer_type, fwd_msg_id = ad

        sub_row = db_get_active_subscription_status(user_id)
        package_name = sub_row[0] if sub_row else ""

        # Ambil custom target messages untuk user_id ini
        from src.database import db_get_custom_target_messages
        custom_messages = db_get_custom_target_messages(user_id)
        custom_map = {}
        for cm in custom_messages:
            if cm.get("is_active"):
                custom_map[cm["target_peer"].lower()] = cm["custom_message"]

        # Branding tidak diterapkan — format asli iklan dipertahankan penuh

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

        from src.logic import active_broadcasts

        for link in group_links:
            if not self.is_running: break
            if user_id not in active_broadcasts:
                logger.info(f"Broadcast untuk user {user_id} dihentikan paksa (dibatalkan oleh admin/sistem).")
                self.is_running = False
                break
            
            entity = None
            try:
                # 1. Resolve & Join private link atau public link secara cerdas
                is_private_invite = "joinchat/" in link or "+" in link
                
                if is_private_invite:
                    invite_hash = link.split("/")[-1].replace("+", "")
                    from telethon.tl.functions.messages import ImportChatInviteRequest
                    try:
                        logger.info(f"Userbot bergabung ke private invite link: {link}")
                        await self.client(ImportChatInviteRequest(invite_hash))
                        joins_this_cycle += 1
                        # Jeda acak manusia saat join
                        await asyncio.sleep(random.uniform(15, 30))
                    except Exception as invite_err:
                        if "UserAlreadyParticipantError" in str(invite_err):
                            pass
                        else:
                            logger.error(f"Gagal join private link {link}: {invite_err}")
                            if link in unprocessed_links:
                                unprocessed_links.remove(link)
                            continue
                            
                    try:
                        entity = await self.client.get_entity(link)
                    except Exception as ent_err:
                        logger.error(f"Gagal resolve private link setelah join {link}: {ent_err}")
                        if link in unprocessed_links:
                            unprocessed_links.remove(link)
                        continue
                else:
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
                        # Jeda acak manusia saat join
                        await asyncio.sleep(random.uniform(15, 25))

                # 3. Simulasi Manusia (Typing) sebelum mengirim pesan
                try:
                    async with self.client.action(entity, 'typing'):
                        # Simulasi mengetik 2-5 detik acak
                        await asyncio.sleep(random.uniform(2, 5))
                except Exception as e:
                    logger.debug(f"Gagal mensimulasikan typing: {e}")

                # 4. Custom Target Message vs default Ad
                final_content = content
                # Cek apakah target link terdaftar di pesan kustom
                link_clean = link.strip().lower().replace("https://t.me/","").replace("t.me/","").replace("@","")
                ent_id_str = str(entity.id) if entity else ""
                
                # Gunakan pesan kustom jika ada pencocokan link atau id grup
                if link_clean in custom_map:
                    final_content = custom_map[link_clean]
                elif ent_id_str in custom_map:
                    final_content = custom_map[ent_id_str]
                elif entity and hasattr(entity, 'username') and entity.username and entity.username.lower() in custom_map:
                    final_content = custom_map[entity.username.lower()]

                # Putar kata iklan secara dinamis (Spintax Auto-Rotation)
                final_content = resolve_spintax(final_content)

                # Tidak menambahkan hashtag — format asli pesan dipertahankan

                # 5. EXECUTION
                if is_promote:
                    import src.config
                    bot_username = src.config.BOT_USERNAME
                    try:
                        results = await self.client.inline_query(bot_username, 'promote')
                        if results:
                            msg = await results[0].click(entity)
                        else:
                            raise ValueError("Hasil inline query kosong.")
                    except Exception as inline_err:
                        logger.warning(f"Gagal kirim via inline query promote, fallback ke teks biasa: {inline_err}")
                        msg = await self.client.send_message(entity, final_content, parse_mode='html')
                elif fwd_chat_id and fwd_msg_id:
                    fwd_chat_id_str = str(fwd_chat_id)
                    if fwd_chat_id_str.startswith("-100"):
                        clean_fwd_id = int(fwd_chat_id_str[4:])
                    elif fwd_chat_id_str.startswith("-"):
                        clean_fwd_id = int(fwd_chat_id_str[1:])
                    else:
                        clean_fwd_id = int(fwd_chat_id_str)
                    
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
                
                db_insert_forward_log(user_id, ad_id, entity.id, msg_link, 'success', subscription_id=subscription_id)
                
                group_title = entity.title if hasattr(entity, 'title') else link
                success_links.append((group_title, msg_link))
                
                success_count += 1
                unprocessed_links.remove(link)

                # PERSISTENT PROTOCOL & Dynamic Random Delay Simulator
                # Menyusun jeda waktu yang dinamis dan acak secara manusiawi
                sleep_time = random.uniform(30, 150) if delay_mode == 'slowly' else random.uniform(5, 25)
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
                ent_id = entity.id if ('entity' in locals() and entity) else 0
                db_insert_forward_log(user_id, ad_id, ent_id, "", 'failed', str(e), subscription_id=subscription_id)
        
        self.is_running = False
        return {"success": True, "success_count": success_count, "failed_count": failed_count, "unprocessed_links": unprocessed_links, "floodwait_seconds": flood_seconds, "success_links": success_links}

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
