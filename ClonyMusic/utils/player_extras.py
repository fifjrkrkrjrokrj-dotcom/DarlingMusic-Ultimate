import asyncio
import random
import re
from typing import Dict, List, Set, Tuple

import aiohttp
from pyrogram.enums import ChatMemberStatus, ChatType
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import config
from ClonyMusic import LOGGER, YouTube, app
from ClonyMusic.core.call import Lucky
from ClonyMusic.core.mongo import mongodb
from ClonyMusic.misc import SUDOERS, db
from ClonyMusic.utils.button_style import ButtonStyle, is_bot_admin
from ClonyMusic.utils.database import get_assistant, get_authuser_names, get_lang
from ClonyMusic.utils.feature_flags import is_feature_enabled
from ClonyMusic.utils.formatters import int_to_alpha
from ClonyMusic.utils.inline.play import stream_markup
from ClonyMusic.utils.inline.queue import aq_markup
from ClonyMusic.utils.stream.queue import put_queue
from ClonyMusic.utils.thumbnails import get_thumb
from ClonyMusic.utils.vc_watcher import auto_delete_msg
from strings import get_string

_AUTOPLAY_CHATS: Set[int] = set()
_247_CHATS: Set[int] = set()
_VOTESKIP_MAP: dict = {}
VOTESKIP_THRESHOLD: int = 3
_PLAYLIST_TASKS: Dict[Tuple[int, int], asyncio.Task] = {}


def track_playlist_message(msg, delay: int = 300):
    if not msg or not getattr(msg, "chat", None) or not getattr(msg, "id", None):
        return
    key = (int(msg.chat.id), int(msg.id))
    old_task = _PLAYLIST_TASKS.pop(key, None)
    if old_task and not old_task.done():
        old_task.cancel()

    async def _timer():
        try:
            await asyncio.sleep(delay)
            await msg.delete()
        except Exception:
            pass
        finally:
            _PLAYLIST_TASKS.pop(key, None)

    _PLAYLIST_TASKS[key] = asyncio.create_task(_timer())


def cancel_playlist_message(msg):
    if not msg or not getattr(msg, "chat", None) or not getattr(msg, "id", None):
        return
    key = (int(msg.chat.id), int(msg.id))
    task = _PLAYLIST_TASKS.pop(key, None)
    if task and not task.done():
        task.cancel()


async def has_vc_admin_rights(client, chat_id: int, user_id: int) -> bool:
    """Check if user has VC management/admin permissions (cached or live)."""
    if not user_id:
        return False
    if is_bot_admin(user_id) or user_id in SUDOERS:
        return True
    if user_id in config.adminlist.get(chat_id, []):
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        if member.status == ChatMemberStatus.OWNER:
            return True
        if member.status == ChatMemberStatus.ADMINISTRATOR:
            if not member.privileges or member.privileges.can_manage_video_chats:
                return True
    except Exception:
        pass
    try:
        auths = await get_authuser_names(chat_id)
        if int_to_alpha(user_id) in auths:
            return True
    except Exception:
        pass
    return False


def reset_voteskip(chat_id: int):
    _VOTESKIP_MAP.pop(int(chat_id), None)


async def handle_voteskip(client, chat_id: int, user_id: int, reply_target):
    """Handle Vote-to-Skip for a group VC. Skips once VOTESKIP_THRESHOLD unique users vote."""
    if not is_feature_enabled("voteskip"):
        return False, "Vote-to-Skip is currently disabled by Admin."
    queue = db.get(chat_id)
    if not queue:
        return False, "Nothing is playing right now."

    vid_key = f"{queue[0].get('vidid', '')}_{len(queue)}"
    entry = _VOTESKIP_MAP.get(chat_id)
    if not entry or entry.get("key") != vid_key:
        entry = {"key": vid_key, "voters": set()}
        _VOTESKIP_MAP[chat_id] = entry

    if user_id in entry["voters"]:
        return False, f"You already voted ({len(entry['voters'])}/{VOTESKIP_THRESHOLD})."

    entry["voters"].add(user_id)
    count = len(entry["voters"])
    if count < VOTESKIP_THRESHOLD:
        return True, f"Vote Skip: {count}/{VOTESKIP_THRESHOLD} votes recorded."

    _VOTESKIP_MAP.pop(chat_id, None)
    popped = queue.pop(0)
    if popped:
        try:
            from ClonyMusic.utils.stream.autoclear import auto_clean
            await auto_clean(popped)
        except Exception:
            pass

    if not queue:
        await Lucky.stop_stream(chat_id)
        return True, f"Vote Skip passed ({VOTESKIP_THRESHOLD}/{VOTESKIP_THRESHOLD}). Queue ended, VC stopped."

    nxt = queue[0]
    nxt["played"] = 0
    queued = nxt["file"]
    videoid = nxt["vidid"]
    is_video = str(nxt.get("streamtype")) == "video"
    if "live_" in str(queued):
        n, link = await YouTube.video(videoid, True)
        target = link if n else None
    elif "vid_" in str(queued):
        target, _ = await YouTube.download(videoid, None, videoid=True, video=is_video)
    else:
        target = queued

    if not target:
        await Lucky.stop_stream(chat_id)
        return True, "Vote Skip passed, but failed to load next track."

    me = await client.get_me()
    lang = await get_lang(chat_id)
    _ = get_string(lang)
    _, img = await asyncio.gather(
        Lucky.skip_stream(chat_id, target, video=is_video),
        get_thumb(videoid),
    )
    if not img:
        img = random.choice(config.STREAM_IMG_URL) if isinstance(config.STREAM_IMG_URL, list) else config.STREAM_IMG_URL

    run = await reply_target.reply_photo(
        photo=img,
        caption=_["stream_1"].format(
            f"https://t.me/{me.username}?start=info_{videoid}",
            nxt["title"].title()[:23],
            nxt["dur"],
            nxt["by"],
        ),
        reply_markup=InlineKeyboardMarkup(stream_markup(_, chat_id)),
        has_spoiler=True,
    )
    db[chat_id][0]["mystic"] = run
    db[chat_id][0]["markup"] = "stream"
    return True, f"Vote Skip passed ({VOTESKIP_THRESHOLD}/{VOTESKIP_THRESHOLD}). Skipped to next track."


def is_autoplay(chat_id: int) -> bool:
    return is_feature_enabled("autoplay") and int(chat_id) in _AUTOPLAY_CHATS


def toggle_autoplay(chat_id: int) -> bool:
    cid = int(chat_id)
    enabled = False
    if cid in _AUTOPLAY_CHATS:
        _AUTOPLAY_CHATS.discard(cid)
        enabled = False
    else:
        _AUTOPLAY_CHATS.add(cid)
        enabled = True
    try:
        from ClonyMusic.core.mongo import mongodb
        async def _save():
            try:
                if enabled:
                    await mongodb.bot_settings.update_one({"_id": "autoplay_chats"}, {"$addToSet": {"chats": cid}}, upsert=True)
                else:
                    await mongodb.bot_settings.update_one({"_id": "autoplay_chats"}, {"$pull": {"chats": cid}}, upsert=True)
            except Exception:
                pass
        asyncio.create_task(_save())
    except Exception:
        pass
    return enabled


async def load_autoplay_chats():
    global _AUTOPLAY_CHATS
    try:
        from ClonyMusic.core.mongo import mongodb
        doc = await mongodb.bot_settings.find_one({"_id": "autoplay_chats"})
        if doc and isinstance(doc.get("chats"), list):
            for c in doc["chats"]:
                _AUTOPLAY_CHATS.add(int(c))
    except Exception:
        pass


def is_247(chat_id: int) -> bool:
    return is_feature_enabled("247") and int(chat_id) in _247_CHATS


def toggle_247(chat_id: int) -> bool:
    cid = int(chat_id)
    enabled = False
    if cid in _247_CHATS:
        _247_CHATS.discard(cid)
        enabled = False
    else:
        _247_CHATS.add(cid)
        enabled = True
    try:
        from ClonyMusic.core.mongo import mongodb
        async def _save():
            try:
                if enabled:
                    await mongodb.bot_settings.update_one({"_id": "chats_247"}, {"$addToSet": {"chats": cid}}, upsert=True)
                else:
                    await mongodb.bot_settings.update_one({"_id": "chats_247"}, {"$pull": {"chats": cid}}, upsert=True)
            except Exception:
                pass
        asyncio.create_task(_save())
    except Exception:
        pass
    return enabled


async def load_247_chats():
    global _247_CHATS
    try:
        from ClonyMusic.core.mongo import mongodb
        doc = await mongodb.bot_settings.find_one({"_id": "chats_247"})
        if doc and isinstance(doc.get("chats"), list):
            for c in doc["chats"]:
                _247_CHATS.add(int(c))
    except Exception:
        pass


async def get_user_playlist(user_id: int) -> List[dict]:
    doc = await mongodb.user_playlists.find_one({"user_id": int(user_id)})
    if doc and isinstance(doc.get("tracks"), list):
        return doc["tracks"]
    return []


async def save_track_for_user(user_id: int, track: dict) -> str:
    uid = int(user_id)
    tracks = await get_user_playlist(uid)
    vidid = str(track.get("vidid", ""))
    if any(str(t.get("vidid")) == vidid for t in tracks):
        return "exists"
    if len(tracks) >= 30:
        return "full"
    entry = {
        "vidid": vidid,
        "title": str(track.get("title", "Unknown"))[:60],
        "dur": str(track.get("dur", "0:00")),
        "streamtype": str(track.get("streamtype", "audio")),
    }
    await mongodb.user_playlists.update_one(
        {"user_id": uid},
        {"$push": {"tracks": entry}},
        upsert=True,
    )
    return "saved"


async def remove_user_track(user_id: int, idx: int) -> bool:
    uid = int(user_id)
    tracks = await get_user_playlist(uid)
    if idx < 0 or idx >= len(tracks):
        return False
    tracks.pop(idx)
    await mongodb.user_playlists.update_one(
        {"user_id": uid},
        {"$set": {"tracks": tracks}},
        upsert=True,
    )
    return True


async def clear_user_playlist(user_id: int):
    await mongodb.user_playlists.delete_one({"user_id": int(user_id)})


def build_playlist_ui(user_id: int, tracks: List[dict]) -> Tuple[str, InlineKeyboardMarkup]:
    if not tracks:
        return (
            "<blockquote><b><u>My Saved Playlist</u></b></blockquote>\n\n"
            "<i>Your saved playlist is currently empty.</i>\n"
            "Open <b>More ➔ Save</b> on any playing track to save it here.",
            InlineKeyboardMarkup([[InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close", style=ButtonStyle.DANGER)]]),
        )

    lines = [f"<blockquote><b><u>My Saved Playlist ({len(tracks)}/30)</u></b></blockquote>\n"]
    buttons = [
        [
            InlineKeyboardButton("ᴘʟᴀʏ ᴀʟʟ (ᴀᴜᴅɪᴏ)", callback_data=f"UPLPlayAll a|{user_id}", style=ButtonStyle.SUCCESS),
            InlineKeyboardButton("ᴘʟᴀʏ ᴀʟʟ (ᴠɪᴅᴇᴏ)", callback_data=f"UPLPlayAll v|{user_id}", style=ButtonStyle.PRIMARY),
        ],
        [
            InlineKeyboardButton("sʜᴜғғʟᴇ ᴘʟᴀʏ", callback_data=f"UPLShuffle|{user_id}", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("ʀᴇғʀᴇsʜ", callback_data=f"UPLRefresh|{user_id}"),
        ],
    ]
    for idx, t in enumerate(tracks[:8], start=1):
        lines.append(f"<b>{idx}.</b> {t.get('title', 'Unknown')[:35]} (<code>{t.get('dur', '0:00')}</code>)")
        buttons.append(
            [
                InlineKeyboardButton(f"ᴘʟᴀʏ #{idx}", callback_data=f"UPLPlayOne {idx - 1}|{user_id}", style=ButtonStyle.SUCCESS),
                InlineKeyboardButton(f"ʀᴇᴍᴏᴠᴇ #{idx}", callback_data=f"UPLDelOne {idx - 1}|{user_id}", style=ButtonStyle.DANGER),
            ]
        )
    if len(tracks) > 8:
        lines.append(f"\n<i>...and {len(tracks) - 8} more saved tracks (Play All plays all {len(tracks)}).</i>")

    buttons.append(
        [
            InlineKeyboardButton("ᴄʟᴇᴀʀ ᴀʟʟ", callback_data=f"UPLClear|{user_id}", style=ButtonStyle.DANGER),
            InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close"),
        ]
    )
    return "\n".join(lines), InlineKeyboardMarkup(buttons)


async def play_saved_tracks(
    client,
    cq: CallbackQuery,
    tracks: List[dict],
    video: bool = False,
    shuffle: bool = False,
):
    if cq.message.chat.type == ChatType.PRIVATE:
        return await cq.answer("⚠️ Group VC mein /myplaylist bhej kar Play All dabayein!", show_alert=True)

    cancel_playlist_message(cq.message)
    try:
        await cq.message.delete()
    except Exception:
        pass

    chat_id = cq.message.chat.id
    items = list(tracks)
    if shuffle:
        random.shuffle(items)

    await cq.answer("🎵 Playing your saved playlist...", show_alert=False)
    status = await cq.message.reply_text(f"⏳ **Loading `{len(items)}` saved tracks into VC...**")

    first = items[0]
    vidid = first["vidid"]
    title = first["title"]
    dur = first["dur"]
    user_mention = cq.from_user.mention if cq.from_user else "User"
    streamtype = "video" if video else "audio"

    file_path, _ = await YouTube.download(vidid, None, videoid=True, video=video)
    if not file_path:
        return await status.edit_text("❌ **Failed to download first track from playlist.**")

    lang = await get_lang(chat_id)
    _ = get_string(lang)
    me = await client.get_me()
    is_clone = bool(me.id != (getattr(app, "id", 0) or int(getattr(config, "BOT_ID", 0) or 0)))
    userbot = await get_assistant(chat_id) if is_clone else None

    already_active = bool(db.get(chat_id))
    from ClonyMusic.utils.vc_watcher import register_chat_bot
    register_chat_bot(chat_id, client)
    if not already_active:
        try:
            await Lucky.join_call(chat_id, chat_id, file_path, video=video, userbot=userbot)
        except Exception as e:
            return await status.edit_text(f"❌ **VC Error:** `{e}`")
        await put_queue(
            chat_id, chat_id, file_path, title, dur, user_mention, vidid, cq.from_user.id, streamtype
        )
        db[chat_id][0]["client"] = client
        if is_clone:
            from ClonyMusic.cplugin.utils.cthumbnail import get_thumb as c_get_thumb
            try:
                img = await c_get_thumb(vidid, user_id=cq.from_user.id, client=client, title=title, duration=dur)
            except Exception:
                img = None
        else:
            try:
                img = await get_thumb(vidid, title=title, duration=dur)
            except Exception:
                img = None
        if not img:
            img = f"https://img.youtube.com/vi/{vidid}/hqdefault.jpg"
        run = await cq.message.reply_photo(
            photo=img,
            caption=_["stream_1"].format(
                f"https://t.me/{me.username}?start=info_{vidid}",
                title[:23],
                dur,
                user_mention,
            ),
            reply_markup=InlineKeyboardMarkup(stream_markup(_, chat_id)),
            has_spoiler=True,
        )
        db[chat_id][0]["mystic"] = run
        db[chat_id][0]["markup"] = "stream"
        try:
            await status.delete()
        except Exception:
            pass
    else:
        await put_queue(
            chat_id, chat_id, f"vid_{vidid}", title, dur, user_mention, vidid, cq.from_user.id, streamtype
        )
        position = len(db.get(chat_id) or []) - 1
        button = aq_markup(_, chat_id, position)
        sent_q = await cq.message.reply_text(
            _["queue_4"].format(position, title[:27], dur, user_mention),
            reply_markup=InlineKeyboardMarkup(button),
        )
        if sent_q:
            asyncio.create_task(auto_delete_msg(sent_q, delay=15))
        try:
            await status.delete()
        except Exception:
            pass

    for extra in items[1:]:
        await put_queue(
            chat_id,
            chat_id,
            f"vid_{extra['vidid']}",
            extra["title"],
            extra["dur"],
            user_mention,
            extra["vidid"],
            cq.from_user.id,
            streamtype,
        )
        if chat_id in db and db[chat_id]:
            db[chat_id][-1]["client"] = client


# ---------------- PLAYER MENU TRACKING ----------------
_PLAYER_MENU_ACTIVE: Dict[int, bool] = {}


def set_player_menu_active(chat_id: int, active: bool) -> None:
    """Track whether More/Effects sub-menu is currently open in chat to prevent timer overwrite."""
    _PLAYER_MENU_ACTIVE[int(chat_id)] = bool(active)


def is_player_menu_active(chat_id: int) -> bool:
    """Return True if More/Effects sub-menu is currently open in chat."""
    return _PLAYER_MENU_ACTIVE.get(int(chat_id), False)


# ---------------- ROBUST LYRICS FETCHER ----------------
def clean_song_title(raw_title: str) -> str:
    """Strip junk prefixes, suffixes, unclosed brackets, and metadata words from track titles."""
    if not raw_title:
        return ""
    t = re.sub(r"\(.*?\)|\[.*?\]|\{.*?\}", " ", raw_title)
    t = re.sub(r"[\(\[\{].*$", " ", t)
    t = re.sub(r"\.{2,}", " ", t)
    junk = r"\b(official|music|video|audio|lyrics?|lyrical|full song|full video|full track|remix|slowed|reverb|4k|hd|hq|teaser|trailer|feat|ft|prod)\b"
    t = re.sub(junk, " ", t, flags=re.I)
    t = re.sub(r"[:|/\-_~]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


async def fetch_lyrics(raw_title: str) -> str:
    """Fetch lyrics from lrclib.net with title normalization and plain/synced fallbacks."""
    clean1 = clean_song_title(raw_title)
    if not clean1:
        return ""

    queries = [clean1]
    parts = [p.strip() for p in re.split(r"[-:]", raw_title) if p.strip()]
    for p in parts:
        cp = clean_song_title(p)
        if cp and cp not in queries and len(cp) > 2:
            queries.append(cp)

    try:
        async with aiohttp.ClientSession(headers={"User-Agent": "ClonyMusicBot/1.0"}) as session:
            for q in queries:
                try:
                    async with session.get(
                        "https://lrclib.net/api/search",
                        params={"q": q},
                        timeout=aiohttp.ClientTimeout(total=8),
                    ) as resp:
                        if resp.status != 200:
                            continue
                        data = await resp.json()
                        if isinstance(data, list) and data:
                            for item in data:
                                txt = item.get("plainLyrics") or ""
                                if not txt.strip() and item.get("syncedLyrics"):
                                    txt = re.sub(r"\[\d+:\d+\.\d+\]\s*", "", item["syncedLyrics"])
                                if txt.strip():
                                    return txt.strip()[:3800]
                except Exception:
                    continue
    except Exception:
        pass
    return ""
