import asyncio
import time
from typing import Dict, List, Optional, Tuple

from pyrogram.errors import UserNotParticipant
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from ClonyMusic.core.mongo import mongodb
from ClonyMusic.utils.button_style import is_bot_admin

_FSUB_ENABLED: bool = False
_FSUB_CHAT: Optional[str] = None  # @username or numeric -100... id
_COOLDOWNS: Dict[Tuple[int, str], float] = {}
_CHAT_PLAY_LOCKS: Dict[int, asyncio.Lock] = {}
_BLOCKED_WORDS: List[str] = []


def get_chat_play_lock(chat_id: int) -> asyncio.Lock:
    cid = int(chat_id)
    lock = _CHAT_PLAY_LOCKS.get(cid)
    if lock is None:
        lock = asyncio.Lock()
        _CHAT_PLAY_LOCKS[cid] = lock
    if len(_CHAT_PLAY_LOCKS) > 3000:
        for k in list(_CHAT_PLAY_LOCKS.keys())[:1000]:
            if not _CHAT_PLAY_LOCKS[k].locked():
                _CHAT_PLAY_LOCKS.pop(k, None)
    return lock


async def load_fsub_settings():
    global _FSUB_ENABLED, _FSUB_CHAT, _BLOCKED_WORDS
    try:
        doc = await mongodb.bot_settings.find_one({"_id": "fsub"})
        if doc:
            _FSUB_ENABLED = bool(doc.get("enabled", False))
            _FSUB_CHAT = doc.get("chat")
        bdoc = await mongodb.bot_settings.find_one({"_id": "blocked_words"})
        if bdoc and isinstance(bdoc.get("words"), list):
            _BLOCKED_WORDS = [str(w).lower().strip() for w in bdoc["words"] if str(w).strip()]
    except Exception:
        pass


def get_blocked_words() -> List[str]:
    return list(_BLOCKED_WORDS)


def contains_blocked_word(text: str) -> Optional[str]:
    if not text or not _BLOCKED_WORDS:
        return None
    low = text.lower()
    for w in _BLOCKED_WORDS:
        if w in low:
            return w
    return None


async def add_blocked_word(word: str) -> bool:
    w = word.lower().strip()
    if not w or w in _BLOCKED_WORDS:
        return False
    _BLOCKED_WORDS.append(w)
    await mongodb.bot_settings.update_one(
        {"_id": "blocked_words"},
        {"$addToSet": {"words": w}},
        upsert=True,
    )
    return True


async def remove_blocked_word(word: str) -> bool:
    w = word.lower().strip()
    if w in _BLOCKED_WORDS:
        _BLOCKED_WORDS.remove(w)
        await mongodb.bot_settings.update_one(
            {"_id": "blocked_words"},
            {"$pull": {"words": w}},
        )
        return True
    return False


async def clear_blocked_words():
    _BLOCKED_WORDS.clear()
    await mongodb.bot_settings.delete_one({"_id": "blocked_words"})


def get_fsub_state() -> Tuple[bool, Optional[str]]:
    return _FSUB_ENABLED, _FSUB_CHAT


async def set_fsub_enabled(enabled: bool):
    global _FSUB_ENABLED
    _FSUB_ENABLED = bool(enabled)
    await mongodb.bot_settings.update_one(
        {"_id": "fsub"}, {"$set": {"enabled": _FSUB_ENABLED}}, upsert=True
    )


async def set_fsub_chat(chat: str):
    global _FSUB_CHAT
    _FSUB_CHAT = chat.strip()
    await mongodb.bot_settings.update_one(
        {"_id": "fsub"}, {"$set": {"chat": _FSUB_CHAT}}, upsert=True
    )


def check_cooldown(user_id: int, action: str = "play", seconds: int = 3) -> int:
    """Return remaining cooldown seconds (0 if allowed)."""
    if is_bot_admin(user_id):
        return 0
    now = time.monotonic()
    key = (int(user_id), action)
    last = _COOLDOWNS.get(key, 0.0)
    diff = now - last
    if diff < seconds:
        return max(1, int(seconds - diff + 0.99))
    _COOLDOWNS[key] = now
    if len(_COOLDOWNS) > 5000:
        _COOLDOWNS.clear()
    return 0


async def check_fsub(client, message: Message) -> bool:
    """Return True if user is allowed to proceed, False if blocked by FSub (and replies with join button)."""
    if not _FSUB_ENABLED or not _FSUB_CHAT or not message.from_user:
        return True
    uid = message.from_user.id
    if is_bot_admin(uid):
        return True

    target = int(_FSUB_CHAT) if str(_FSUB_CHAT).lstrip("-").isdigit() else _FSUB_CHAT
    try:
        await client.get_chat_member(target, uid)
        return True
    except UserNotParticipant:
        try:
            chat_obj = await client.get_chat(target)
            invite = chat_obj.invite_link or (f"https://t.me/{chat_obj.username}" if chat_obj.username else None)
            title = chat_obj.title or "Our Channel"
        except Exception:
            invite = f"https://t.me/{str(_FSUB_CHAT).lstrip('@')}" if not str(_FSUB_CHAT).lstrip("-").isdigit() else None
            title = "Our Channel"

        buttons = []
        if invite:
            buttons.append([InlineKeyboardButton(f"ᴊᴏɪɴ {title}", url=invite)])
        await message.reply_text(
            f"⚠️ **Join Required!**\n\nBot use karne ke liye pehle **{title}** join karein, phir dobara try karein.",
            reply_markup=InlineKeyboardMarkup(buttons) if buttons else None,
        )
        return False
    except Exception:
        return True
