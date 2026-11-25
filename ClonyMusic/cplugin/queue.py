import asyncio
import random

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import config
from ClonyMusic import LOGGER, YouTube
from ClonyMusic.core.call import Lucky
from ClonyMusic.misc import db
from ClonyMusic.utils.database import get_lang
from ClonyMusic.utils.feature_flags import is_feature_enabled
from ClonyMusic.cplugin.buttons import stream_markup
from ClonyMusic.cplugin.utils.cthumbnail import gen_thumb as get_thumb
from ClonyMusic.utils.player_extras import has_vc_admin_rights
from config import BANNED_USERS
from strings import get_string


_ACTIVE_QUEUE_MSGS: dict = {}


def clear_active_queue_msg(chat_id: int):
    q_msg = _ACTIVE_QUEUE_MSGS.pop(int(chat_id), None)
    if q_msg:
        try:
            asyncio.create_task(q_msg.delete())
        except Exception:
            pass


async def _auto_delete_queue_msg(chat_id: int, msg, delay: int = 180):
    await asyncio.sleep(delay)
    if _ACTIVE_QUEUE_MSGS.get(int(chat_id)) is msg:
        _ACTIVE_QUEUE_MSGS.pop(int(chat_id), None)
        try:
            await msg.delete()
        except Exception:
            pass


def _build_queue_view(chat_id: int):
    queue = db.get(chat_id)
    if not queue:
        return None, None
    now = queue[0]
    lines = [
        "<blockquote><b><u>Active Playback Queue</u></b></blockquote>\n",
        f"<b>Now Playing:</b> {now.get('title', 'Unknown')[:40]} (<code>{now.get('dur', '0:00')}</code>)",
    ]
    buttons = []
    if len(queue) > 1:
        lines.append("\n<b>Up Next:</b>")
        row = []
        for idx, item in enumerate(queue[1:9], start=2):
            title = item.get("title", "Unknown")[:32]
            dur = item.get("dur", "0:00")
            lines.append(f"<b>{idx}.</b> {title} (<code>{dur}</code>)")
            row.append(InlineKeyboardButton(f"ᴘʟᴀʏ ɴᴏᴡ #{idx}", callback_data=f"PlayNow {idx - 1}|{chat_id}"))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        if len(queue) > 9:
            lines.append(f"\n<i>...and {len(queue) - 9} more tracks in queue.</i>")
    else:
        lines.append("\n<i>Queue is empty after current track.</i>")

    buttons.append([InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close")])
    return "\n".join(lines), InlineKeyboardMarkup(buttons)


@Client.on_message(filters.command(["queue", "q", "cqueue"]) & filters.group & ~BANNED_USERS)
async def queue_command(client, message: Message):
    if not is_feature_enabled("queue"):
        return await message.reply_text("<b>Disabled:</b> Queue feature is currently turned off by Admin.")
    text, markup = _build_queue_view(message.chat.id)
    if not text:
        return await message.reply_text("<b>Nothing is currently playing in this chat.</b>")
    sent = await message.reply_text(text, reply_markup=markup)
    if sent:
        _ACTIVE_QUEUE_MSGS[int(message.chat.id)] = sent
        asyncio.create_task(_auto_delete_queue_msg(message.chat.id, sent, 180))


@Client.on_callback_query(filters.regex(r"^OpenQueue\|") & ~BANNED_USERS)
async def open_queue_cb(client, cq: CallbackQuery):
    try:
        if not is_feature_enabled("queue"):
            return await cq.answer("Queue feature is disabled by Admin.", show_alert=True)
        chat_id = int(cq.data.split("|", 1)[1])
        text, markup = _build_queue_view(chat_id)
        if not text:
            return await cq.answer("Queue is empty.", show_alert=True)
        await cq.answer()
        sent = await cq.message.reply_text(text, reply_markup=markup)
        if sent:
            _ACTIVE_QUEUE_MSGS[int(chat_id)] = sent
            asyncio.create_task(_auto_delete_queue_msg(chat_id, sent, 180))
    except Exception as e:
        LOGGER(__name__).error(f"Clone OpenQueue error: {e}")
        await cq.answer(f"Queue error: {type(e).__name__}", show_alert=True)


@Client.on_callback_query(filters.regex(r"^PlayNow ") & ~BANNED_USERS)
async def play_now_cb(client, cq: CallbackQuery):
    try:
        payload = cq.data.split(" ", 1)[1]
        idx_str, chat_str = payload.split("|", 1)
        idx = int(idx_str)
        chat_id = int(chat_str)
    except Exception:
        return await cq.answer("Invalid queue item.", show_alert=True)

    try:
        if not await has_vc_admin_rights(client, chat_id, cq.from_user.id):
            return await cq.answer("Only Group Admins (with VC permission) can use Play Now!", show_alert=True)

        queue = db.get(chat_id)
        if not queue:
            return await cq.answer("Queue is empty.", show_alert=True)
        if idx < 0:
            idx = len(queue) - 1
        if idx <= 0 or idx >= len(queue):
            return await cq.answer("Track is no longer in queue.", show_alert=True)

        await cq.answer("Playing selected track now...")
        selected = queue.pop(idx)
        try:
            old_mystic = queue[0].get("mystic")
            if old_mystic:
                await old_mystic.delete()
        except Exception:
            pass
        queue[0] = selected
        db[chat_id][0]["played"] = 0

        queued = selected["file"]
        title = selected["title"].title()
        user = selected["by"]
        duration = selected["dur"]
        streamtype = selected["streamtype"]
        videoid = selected["vidid"]
        is_video = str(streamtype) == "video"

        if "live_" in str(queued):
            n, link = await YouTube.video(videoid, True)
            if n == 0:
                return await cq.message.reply_text("<b>Failed to fetch live stream.</b>")
            target_link = link
        elif "vid_" in str(queued):
            target_link, _ = await YouTube.download(videoid, None, videoid=True, video=is_video)
            if not target_link:
                return await cq.message.reply_text("<b>Failed to download selected track.</b>")
        else:
            target_link = queued

        me = await client.get_me()
        lang = await get_lang(chat_id)
        _ = get_string(lang)
        _, img = await asyncio.gather(
            Lucky.skip_stream(chat_id, target_link, video=is_video),
            get_thumb(videoid, client=client),
        )
        if not img:
            img = random.choice(config.STREAM_IMG_URL) if isinstance(config.STREAM_IMG_URL, list) else config.STREAM_IMG_URL

        run = await cq.message.reply_photo(
            photo=img,
            caption=_["stream_1"].format(
                f"https://t.me/{me.username}?start=info_{videoid}",
                title[:23],
                duration,
                user,
            ),
            reply_markup=InlineKeyboardMarkup(stream_markup(_, chat_id)),
            has_spoiler=True,
        )
        db[chat_id][0]["mystic"] = run
        db[chat_id][0]["markup"] = "stream"

        try:
            await cq.message.delete()
        except Exception:
            pass
        clear_active_queue_msg(chat_id)
    except Exception as e:
        LOGGER(__name__).error(f"Clone PlayNow error: {e}")
        await cq.answer(f"PlayNow error: {type(e).__name__}", show_alert=True)
