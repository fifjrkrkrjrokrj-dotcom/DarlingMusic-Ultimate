import asyncio
import html
import time
from typing import Dict, Optional, Tuple

from pyrogram.enums import ChatMemberStatus, ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import config
from ClonyMusic.utils.button_style import ButtonStyle
from ClonyMusic.utils.feature_flags import is_feature_enabled

_CHAT_BOT_CLIENTS: Dict[int, object] = {}
_ACTIVE_JOIN_MSGS: Dict[Tuple[int, int], object] = {}
_JOIN_COOLDOWN: Dict[Tuple[int, int], float] = {}
_LEFT_COOLDOWN: Dict[Tuple[int, int], float] = {}
_INVITE_DEDUP: Dict[Tuple[int, int], float] = {}
_CHAT_CACHE: Dict[int, Tuple[float, dict]] = {}
_USER_INFO_CACHE: Dict[int, Tuple[str, str]] = {}

VC_DELETE_DELAY: int = 6


def register_chat_bot(chat_id: int, client) -> None:
    """Remember which bot client (Main or Clone) is serving a given chat."""
    if not chat_id or client is None:
        return
    _CHAT_BOT_CLIENTS[int(chat_id)] = client
    if len(_CHAT_BOT_CLIENTS) > 4000:
        for k in list(_CHAT_BOT_CLIENTS.keys())[:1000]:
            _CHAT_BOT_CLIENTS.pop(k, None)


def get_chat_bot(chat_id: int):
    return _CHAT_BOT_CLIENTS.get(int(chat_id))


def remember_user(user) -> None:
    """Cache user full name so we never have to display raw numeric user IDs."""
    if not user or not getattr(user, "id", None):
        return
    uid = int(user.id)
    first = getattr(user, "first_name", "") or ""
    last = getattr(user, "last_name", "") or ""
    full_name = f"{first} {last}".strip()
    username = getattr(user, "username", "") or ""
    if full_name or username:
        _USER_INFO_CACHE[uid] = (full_name or username, username)
        if len(_USER_INFO_CACHE) > 5000:
            for k in list(_USER_INFO_CACHE.keys())[:1000]:
                _USER_INFO_CACHE.pop(k, None)


async def _safe_delete(msg) -> None:
    if not msg:
        return
    try:
        await msg.delete()
    except Exception:
        pass


async def _auto_delete_msg(sent_msg, delay: int = VC_DELETE_DELAY) -> None:
    await asyncio.sleep(delay)
    await _safe_delete(sent_msg)


auto_delete_msg = _auto_delete_msg


async def _auto_delete_join_msg(chat_id: int, user_id: int, sent_msg, delay: int = VC_DELETE_DELAY) -> None:
    await asyncio.sleep(delay)
    key = (int(chat_id), int(user_id))
    if _ACTIVE_JOIN_MSGS.get(key) is sent_msg:
        _ACTIVE_JOIN_MSGS.pop(key, None)
        await _safe_delete(sent_msg)


async def clear_vc_join_msgs(chat_id: int) -> None:
    """Delete all active VC notification messages tracked for chat_id (e.g. when VC ends)."""
    cid = int(chat_id)
    keys = [k for k in _ACTIVE_JOIN_MSGS if k[0] == cid]
    for k in keys:
        msg = _ACTIVE_JOIN_MSGS.pop(k, None)
        if msg:
            asyncio.create_task(_safe_delete(msg))


async def _get_vc_url(bot_client, chat_id: int) -> str:
    now = time.monotonic()
    cached = _CHAT_CACHE.get(int(chat_id))
    if cached and now - cached[0] < 300:
        info = cached[1]
    else:
        info = {"username": None, "invite_link": None}
        try:
            chat = await bot_client.get_chat(chat_id)
            info["username"] = getattr(chat, "username", None)
            info["invite_link"] = getattr(chat, "invite_link", None)
        except Exception:
            pass
        _CHAT_CACHE[int(chat_id)] = (now, info)
        if len(_CHAT_CACHE) > 2000:
            for k in list(_CHAT_CACHE.keys())[:500]:
                _CHAT_CACHE.pop(k, None)

    if info.get("username"):
        return f"https://t.me/{info['username']}?videochat"
    cid_str = str(chat_id)
    if cid_str.startswith("-100"):
        return f"https://t.me/c/{cid_str[4:]}?videochat"
    return info.get("invite_link") or config.SUPPORT_CHAT


async def _resolve_user_mention(uid: int, bot_client, assistant_client, chat_id: int) -> str:
    """Resolve user to a styled mention link with full name, never showing a raw numeric ID."""
    if uid < 0:
        try:
            chat = await bot_client.get_chat(uid)
            title = html.escape(getattr(chat, "title", None) or "Anonymous")
            return f"<b>{title}</b>"
        except Exception:
            return "<b>Anonymous</b>"

    if uid in _USER_INFO_CACHE:
        safe_name = html.escape(_USER_INFO_CACHE[uid][0])
        return f"<a href='tg://user?id={uid}'>{safe_name}</a>"

    user = None
    from ClonyMusic import app
    # 1. Try get_chat_member via bot, assistant, then app
    for client in (bot_client, assistant_client, app):
        if not client:
            continue
        try:
            member = await client.get_chat_member(chat_id, uid)
            if member and getattr(member, "user", None):
                user = member.user
                remember_user(user)
                break
        except Exception:
            pass

    # 2. Try get_users via assistant (userbot has complete contact/peer resolution)
    if not user and assistant_client:
        try:
            user = await assistant_client.get_users(uid)
            if user:
                remember_user(user)
        except Exception:
            pass

    # 3. Try get_users via bot
    if not user and bot_client:
        try:
            user = await bot_client.get_users(uid)
            if user:
                remember_user(user)
        except Exception:
            pass

    # 4. Fallback to main app
    if not user:
        try:
            user = await app.get_users(uid)
            if user:
                remember_user(user)
        except Exception:
            pass

    if user:
        first = getattr(user, "first_name", "") or ""
        last = getattr(user, "last_name", "") or ""
        full_name = f"{first} {last}".strip() or getattr(user, "username", None) or "User"
        safe_name = html.escape(full_name)
        return f"<a href='tg://user?id={uid}'>{safe_name}</a>"

    return f"<a href='tg://user?id={uid}'>User</a>"


async def _resolve_auth_role(bot_client, assistant_client, chat_id: int, user_id: int) -> str:
    from ClonyMusic.misc import SUDOERS
    from ClonyMusic.utils.database import get_authuser_names
    from ClonyMusic.utils.formatters import int_to_alpha

    if user_id < 0:
        return "Channel"
    if user_id in SUDOERS:
        return "Sudo"

    for client in (bot_client, assistant_client):
        if not client:
            continue
        try:
            member = await client.get_chat_member(chat_id, user_id)
            if member.status == ChatMemberStatus.OWNER:
                return "Owner"
            if member.status == ChatMemberStatus.ADMINISTRATOR:
                return "Admin"
            break
        except Exception:
            pass

    try:
        auths = await get_authuser_names(chat_id)
        if int_to_alpha(user_id) in auths:
            return "Auth"
    except Exception:
        pass
    return "Member"


async def handle_video_chat_invited(client, message) -> None:
    """Reply cleanly in HTML blockquote when users are invited to a Video Chat."""
    if not is_feature_enabled("vc_notify"):
        return
    if not message or not message.chat or not getattr(message, "video_chat_members_invited", None):
        return

    chat_id = message.chat.id
    register_chat_bot(chat_id, client)

    now = time.monotonic()
    dedup_key = (int(chat_id), int(message.id))
    if now - _INVITE_DEDUP.get(dedup_key, 0.0) < 10.0:
        return
    _INVITE_DEDUP[dedup_key] = now
    if len(_INVITE_DEDUP) > 2000:
        for k in list(_INVITE_DEDUP.keys())[:1000]:
            if now - _INVITE_DEDUP[k] > 30.0:
                _INVITE_DEDUP.pop(k, None)

    def _safe_html_mention(u) -> str:
        if not u:
            return "User"
        remember_user(u)
        uid = getattr(u, "id", 0)
        first = getattr(u, "first_name", "") or ""
        last = getattr(u, "last_name", "") or ""
        full_name = f"{first} {last}".strip() or getattr(u, "username", "") or "User"
        safe_name = html.escape(full_name)
        if uid:
            return f"<a href='tg://user?id={uid}'>{safe_name}</a>"
        return safe_name

    inviter = _safe_html_mention(message.from_user) if message.from_user else "Someone"

    invited = getattr(message.video_chat_members_invited, "users", None) or []
    names_list = [_safe_html_mention(u) for u in invited if u]
    names = ", ".join(names_list) or "a member"
    text = f"<blockquote>✈️ <b>{inviter} ɪɴᴠɪᴛᴇᴅ {names} ᴛᴏ ᴛʜᴇ ᴠɪᴅᴇᴏ ᴄʜᴀᴛ</b></blockquote>"

    vc_url = await _get_vc_url(client, chat_id)
    if not vc_url:
        vc_url = config.SUPPORT_CHAT
    markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("📞 ᴊᴏɪɴ ᴠᴄ", url=vc_url, style=ButtonStyle.SUCCESS)]]
    )

    try:
        await message.reply_text(
            text,
            reply_markup=markup,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    except Exception:
        try:
            await client.send_message(
                chat_id,
                text,
                reply_markup=markup,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except Exception:
            pass


async def handle_vc_participant_update(assistant_pytgcalls, update) -> None:
    """Post #JoinedVc / #LeftVc cards + JOIN VC button, and auto-delete after 5-7 seconds."""
    if not is_feature_enabled("vc_notify"):
        return

    from pytgcalls.types import GroupCallParticipant, UpdatedGroupCallParticipant
    from ClonyMusic import app
    from ClonyMusic.core.userbot import assistantids
    from ClonyMusic.misc import db

    if not isinstance(update, UpdatedGroupCallParticipant):
        return

    chat_id = int(getattr(update, "chat_id", 0) or 0)
    if not chat_id or chat_id == config.LOGGER_ID:
        return

    participant = getattr(update, "participant", None)
    uid = int(getattr(participant, "user_id", 0) or 0)
    if not uid:
        return

    mt = getattr(assistant_pytgcalls, "_mtproto", None)
    self_id = getattr(getattr(mt, "me", None), "id", None)
    if (self_id and uid == int(self_id)) or uid in assistantids:
        return

    queue = db.get(chat_id)
    if queue and isinstance(queue, list):
        target_chat_id = int(queue[0].get("chat_id") or chat_id)
        bot_client = queue[0].get("client") or get_chat_bot(chat_id) or app
    else:
        target_chat_id = chat_id
        bot_client = get_chat_bot(chat_id) or app

    assistant_client = mt
    key = (target_chat_id, uid)
    action = update.action

    # Handle LEFT / KICKED -> send #LeftVc and delete previous join msg
    if action & (GroupCallParticipant.Action.LEFT | GroupCallParticipant.Action.KICKED):
        old_msg = _ACTIVE_JOIN_MSGS.pop(key, None)
        if old_msg:
            asyncio.create_task(_safe_delete(old_msg))

        now = time.monotonic()
        if now - _LEFT_COOLDOWN.get(key, 0.0) < 4.0:
            return
        _LEFT_COOLDOWN[key] = now
        if len(_LEFT_COOLDOWN) > 4000:
            for k in list(_LEFT_COOLDOWN.keys())[:1000]:
                if now - _LEFT_COOLDOWN[k] > 30.0:
                    _LEFT_COOLDOWN.pop(k, None)

        mention, auth_role, vc_url = await asyncio.gather(
            _resolve_user_mention(uid, bot_client, assistant_client, target_chat_id),
            _resolve_auth_role(bot_client, assistant_client, target_chat_id, uid),
            _get_vc_url(bot_client, target_chat_id),
            return_exceptions=True,
        )
        if isinstance(mention, Exception):
            mention = f"<a href='tg://user?id={uid}'>User</a>"
        if isinstance(auth_role, Exception):
            auth_role = "Member"
        if isinstance(vc_url, Exception) or not vc_url:
            vc_url = config.SUPPORT_CHAT

        text = (
            f"<blockquote><b>#LeftVc</b>\n"
            f"<b>ⓘ USER - </b>{mention}\n"
            f"<b>ⓘ USERID - </b><code>{uid}</code>\n"
            f"<b>ⓘ AUTH - </b>{auth_role}</blockquote>"
        )
        markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("📞 ᴊᴏɪɴ ᴠᴄ", url=vc_url, style=ButtonStyle.SUCCESS)]]
        )
        try:
            sent = await bot_client.send_message(
                target_chat_id,
                text,
                reply_markup=markup,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            asyncio.create_task(_auto_delete_msg(sent, delay=VC_DELETE_DELAY))
        except Exception:
            pass
        return

    if not (action & GroupCallParticipant.Action.JOINED):
        return

    now = time.monotonic()
    if now - _JOIN_COOLDOWN.get(key, 0.0) < 4.0:
        return
    _JOIN_COOLDOWN[key] = now
    if len(_JOIN_COOLDOWN) > 4000:
        for k in list(_JOIN_COOLDOWN.keys())[:1000]:
            if now - _JOIN_COOLDOWN[k] > 30.0:
                _JOIN_COOLDOWN.pop(k, None)

    # Clear any stale card for the same user before posting the new one
    prev_msg = _ACTIVE_JOIN_MSGS.pop(key, None)
    if prev_msg:
        asyncio.create_task(_safe_delete(prev_msg))

    mention, auth_role, vc_url = await asyncio.gather(
        _resolve_user_mention(uid, bot_client, assistant_client, target_chat_id),
        _resolve_auth_role(bot_client, assistant_client, target_chat_id, uid),
        _get_vc_url(bot_client, target_chat_id),
        return_exceptions=True,
    )
    if isinstance(mention, Exception):
        mention = f"<a href='tg://user?id={uid}'>User</a>"
    if isinstance(auth_role, Exception):
        auth_role = "Member"
    if isinstance(vc_url, Exception) or not vc_url:
        vc_url = config.SUPPORT_CHAT

    text = (
        f"<blockquote><b>#JoinedVc</b>\n"
        f"<b>ⓘ USER - </b>{mention}\n"
        f"<b>ⓘ USERID - </b><code>{uid}</code>\n"
        f"<b>ⓘ AUTH - </b>{auth_role}</blockquote>"
    )
    markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("📞 ᴊᴏɪɴ ᴠᴄ", url=vc_url, style=ButtonStyle.SUCCESS)]]
    )

    try:
        sent = await bot_client.send_message(
            target_chat_id,
            text,
            reply_markup=markup,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    except Exception:
        return

    _ACTIVE_JOIN_MSGS[key] = sent
    asyncio.create_task(_auto_delete_join_msg(target_chat_id, uid, sent, delay=VC_DELETE_DELAY))

