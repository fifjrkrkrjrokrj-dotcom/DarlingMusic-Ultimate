import asyncio
import random

from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import (
    ChatAdminRequired,
    InviteRequestSent,
    UserAlreadyParticipant,
    UserNotParticipant,
    PeerIdInvalid
)
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from ClonyMusic import YouTube, app
from ClonyMusic.misc import SUDOERS
from ClonyMusic.utils.database import (
    get_assistant,
    get_cmode,
    get_lang,
    get_playmode,
    get_playtype,
    is_active_chat,
    is_maintenance,
)
from ClonyMusic.utils.inline import botplaylist_markup
from ClonyMusic.utils.fsub import (
    check_cooldown,
    check_fsub,
    contains_blocked_word,
    get_chat_play_lock,
)
from config import PLAYLIST_IMG_URL, SUPPORT_CHAT, adminlist
from strings import get_string

links = {}
clinks = {}


async def _pre_play_checks(client, message) -> bool:
    if not message.from_user:
        return True
    uid = message.from_user.id
    wait = check_cooldown(uid, "play", 2)
    if wait:
        await message.reply_text(f"<b>Slow down:</b> Please wait <code>{wait}s</code> before another play request.")
        return False
    bad = contains_blocked_word(message.text or "")
    if bad:
        await message.reply_text("<b>Blocked:</b> This query contains a keyword restricted by Bot Admin.")
        return False
    if not await check_fsub(client, message):
        return False
    return True


def _pick_img(val):
    if isinstance(val, list) and val:
        return random.choice(val)
    return val


def PlayWrapper(command):
    async def wrapper(client, message):
        if not await _pre_play_checks(client, message):
            return
        language = await get_lang(message.chat.id)
        _ = get_string(language)
        if message.sender_chat:
            upl = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="ʜᴏᴡ ᴛᴏ ғɪx ?",
                            callback_data="LuckymousAdmin",
                        ),
                    ]
                ]
            )
            return await message.reply_text(_["general_3"], reply_markup=upl)

        if await is_maintenance() is False:
            if message.from_user.id not in SUDOERS:
                return await message.reply_text(
                    text=f"{app.mention} ɪs ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ, ᴠɪsɪᴛ <a href={SUPPORT_CHAT}>sᴜᴘᴘᴏʀᴛ ᴄʜᴀᴛ</a> ғᴏʀ ᴋɴᴏᴡɪɴɢ ᴛʜᴇ ʀᴇᴀsᴏɴ.",
                    disable_web_page_preview=True,
                )

        try:
            await message.delete()
        except:
            pass

        audio_telegram = (
            (message.reply_to_message.audio or message.reply_to_message.voice)
            if message.reply_to_message
            else None
        )
        video_telegram = (
            (message.reply_to_message.video or message.reply_to_message.document)
            if message.reply_to_message
            else None
        )
        url = await YouTube.url(message)
        if audio_telegram is None and video_telegram is None and url is None:
            if len(message.command) < 2:
                if "stream" in message.command:
                    return await message.reply_text(_["str_1"])
                buttons = botplaylist_markup(_)
                return await message.reply_photo(
                    photo=_pick_img(PLAYLIST_IMG_URL),
                    caption=_["play_18"],
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
        if message.command[0][0] == "c":
            chat_id = await get_cmode(message.chat.id)
            if chat_id is None:
                return await message.reply_text(_["setting_7"])
            try:
                chat = await app.get_chat(chat_id)
            except:
                return await message.reply_text(_["cplay_4"])
            channel = chat.title
        else:
            chat_id = message.chat.id
            channel = None
        playmode = await get_playmode(message.chat.id)
        playty = await get_playtype(message.chat.id)
        if playty != "Everyone":
            if message.from_user.id not in SUDOERS:
                admins = adminlist.get(message.chat.id)
                if not admins:
                    return await message.reply_text(_["admin_13"])
                else:
                    if message.from_user.id not in admins:
                        return await message.reply_text(_["play_4"])
        if message.command[0][0] == "v":
            video = True
        else:
            if "-v" in message.text:
                video = True
            else:
                video = True if message.command[0][1] == "v" else None
        if message.command[0][-1] == "e":
            if not await is_active_chat(chat_id):
                return await message.reply_text(_["play_16"])
            fplay = True
        else:
            fplay = None

        if not await is_active_chat(chat_id):
            userbot = await get_assistant(chat_id)
            try:
                try:
                    get = await app.get_chat_member(chat_id, userbot.id)
                except ChatAdminRequired:
                    return await message.reply_text(_["call_1"])
                if (
                    get.status == ChatMemberStatus.BANNED
                    or get.status == ChatMemberStatus.RESTRICTED
                ):
                    return await message.reply_text(
                        _["call_2"].format(
                            app.mention, userbot.id, userbot.name, userbot.username
                        ), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(text= "๏ 𝗨ɴʙᴀɴ 𝗔ssɪsᴛᴀɴᴛ ๏", callback_data=f"unban_assistant")]])
                    )
            except UserNotParticipant:
                if chat_id in links:
                    invitelink = links[chat_id]
                else:
                    if message.chat.username:
                        invitelink = message.chat.username
                        try:
                            await userbot.resolve_peer(invitelink)
                        except:
                            pass
                    else:
                        try:
                            invitelink = await app.export_chat_invite_link(chat_id)
                        except ChatAdminRequired:
                            return await message.reply_text(_["call_1"])
                        except Exception as e:
                            return await message.reply_text(
                                _["call_3"].format(app.mention, type(e).__name__)
                            )

                if invitelink.startswith("https://t.me/+"):
                    invitelink = invitelink.replace(
                        "https://t.me/+", "https://t.me/joinchat/"
                    )
                myu = await message.reply_text(_["call_4"].format(app.mention))
                try:
                    await asyncio.sleep(1)
                    await userbot.join_chat(invitelink)
                except InviteRequestSent:
                    try:
                        await app.approve_chat_join_request(chat_id, userbot.id)
                    except Exception as e:
                        return await message.reply_text(
                            _["call_3"].format(app.mention, type(e).__name__)
                        )
                    await asyncio.sleep(3)
                    await myu.edit(_["call_5"].format(app.mention))
                except UserAlreadyParticipant:
                    pass
                except Exception as e:
                    return await message.reply_text(
                        _["call_3"].format(app.mention, type(e).__name__)
                    )

                links[chat_id] = invitelink

                try:
                    await userbot.resolve_peer(chat_id)
                except:
                    pass

        async with get_chat_play_lock(chat_id):
            return await command(
                client,
                message,
                _,
                chat_id,
                video,
                channel,
                playmode,
                url,
                fplay,
            )

    return wrapper

def CPlayWrapper(command):
    async def wrapper(client, message):
        if not await _pre_play_checks(client, message):
            return
        i = await client.get_me()
        language = await get_lang(message.chat.id)
        _ = get_string(language)
        if message.sender_chat:
            upl = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="ʜᴏᴡ ᴛᴏ ғɪx ?",
                            callback_data="LuckymousAdmin",
                        ),
                    ]
                ]
            )
            return await message.reply_text(_["general_3"], reply_markup=upl)

        if await is_maintenance() is False:
            if message.from_user.id not in SUDOERS:
                return await message.reply_text(
                    text=f"{i.mention} ɪs ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ, ᴠɪsɪᴛ <a href={SUPPORT_CHAT}>sᴜᴘᴘᴏʀᴛ ᴄʜᴀᴛ</a> ғᴏʀ ᴋɴᴏᴡɪɴɢ ᴛʜᴇ ʀᴇᴀsᴏɴ.",
                    disable_web_page_preview=True,
                )

        try:
            await message.delete()
        except:
            pass

        audio_telegram = (
            (message.reply_to_message.audio or message.reply_to_message.voice)
            if message.reply_to_message
            else None
        )
        video_telegram = (
            (message.reply_to_message.video or message.reply_to_message.document)
            if message.reply_to_message
            else None
        )
        url = await YouTube.url(message)
        if audio_telegram is None and video_telegram is None and url is None:
            if len(message.command) < 2:
                if "stream" in message.command:
                    return await message.reply_text(_["str_1"])
                buttons = botplaylist_markup(_)
                return await message.reply_photo(
                    photo=_pick_img(PLAYLIST_IMG_URL),
                    caption=_["play_18"],
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
        if message.command[0][0] == "c":
            chat_id = await get_cmode(message.chat.id)
            if chat_id is None:
                return await message.reply_text(_["setting_7"])
            try:
                chat = await client.get_chat(chat_id)
            except:
                return await message.reply_text(_["cplay_4"])
            channel = chat.title
        else:
            chat_id = message.chat.id
            channel = None
        playmode = await get_playmode(message.chat.id)
        playty = await get_playtype(message.chat.id)
        if playty != "Everyone":
            if message.from_user.id not in SUDOERS:
                admins = adminlist.get(message.chat.id)
                if not admins:
                    return await message.reply_text(_["admin_13"])
                else:
                    if message.from_user.id not in admins:
                        return await message.reply_text(_["play_4"])
        if message.command[0][0] == "v":
            video = True
        else:
            if "-v" in message.text:
                video = True
            else:
                video = True if message.command[0][1] == "v" else None
        if message.command[0][-1] == "e":
            if not await is_active_chat(chat_id):
                return await message.reply_text(_["play_16"])
            fplay = True
        else:
            fplay = None

        if not await is_active_chat(chat_id):
            if hasattr(client, "assistant") and client.assistant:
                userbot = client.assistant
            else:
                userbot = await get_assistant(chat_id)
            
            # --- FIX: Helper variables ---
            if hasattr(userbot, "me"):
                ub_id = userbot.me.id
                ub_username = userbot.me.username
                ub_name = userbot.me.first_name
            else:
                ub_id = userbot.id
                ub_username = userbot.username
                ub_name = userbot.name

            try:
                try:
                    # --- FIX START: Self-Check via Assistant ---
                    get = await userbot.get_chat_member(chat_id, "me")
                    # --- FIX END ---
                except:
                    # Agar Assistant khud check nahi kar paaya, matlab wo group me nahi hai
                    raise UserNotParticipant

                if (
                    get.status == ChatMemberStatus.BANNED
                    or get.status == ChatMemberStatus.RESTRICTED
                ):
                    return await message.reply_text(
                        _["call_2"].format(
                            i.mention, ub_id, ub_name, ub_username
                        )
                    )
            except UserNotParticipant:
                if chat_id in clinks:
                    invitelink = clinks[chat_id]
                else:
                    if message.chat.username:
                        invitelink = message.chat.username
                        try:
                            await userbot.resolve_peer(invitelink)
                        except:
                            pass
                    else:
                        try:
                            invitelink = await client.export_chat_invite_link(chat_id)
                        except ChatAdminRequired:
                            return await message.reply_text(_["call_1"])
                        except Exception as e:
                            return await message.reply_text(
                                _["call_3"].format(i.mention, type(e).__name__)
                            )

                if invitelink.startswith("https://t.me/+"):
                    invitelink = invitelink.replace(
                        "https://t.me/+", "https://t.me/joinchat/"
                    )
                myu = await message.reply_text(_["call_4"].format(i.mention))
                try:
                    await asyncio.sleep(1)
                    await userbot.join_chat(invitelink)
                except InviteRequestSent:
                    try:
                        await client.approve_chat_join_request(chat_id, ub_id)
                    except Exception as e:
                        return await message.reply_text(
                            _["call_3"].format(i.mention, type(e).__name__)
                        )
                    await asyncio.sleep(3)
                    await myu.edit(_["call_5"].format(i.mention))
                except UserAlreadyParticipant:
                    pass
                except Exception as e:
                    return await message.reply_text(
                        _["call_3"].format(i.mention, type(e).__name__)
                    )

                clinks[chat_id] = invitelink

                try:
                    await userbot.resolve_peer(chat_id)
                except:
                    pass

        async with get_chat_play_lock(chat_id):
            return await command(
                client,
                message,
                _,
                chat_id,
                video,
                channel,
                playmode,
                url,
                fplay,
            )

    return wrapper