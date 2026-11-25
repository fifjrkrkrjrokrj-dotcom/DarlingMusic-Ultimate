import inspect
import random
import sys
from typing import List, Set

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

try:
    from pyrogram.enums import ButtonStyle
except ImportError:
    from enum import Enum, auto

    class ButtonStyle(Enum):
        DEFAULT = auto()
        PRIMARY = auto()
        DANGER = auto()
        SUCCESS = auto()
        LINK = auto()

_SUPPORTS_BUTTON_STYLE = "style" in inspect.signature(InlineKeyboardButton.__init__).parameters
if not _SUPPORTS_BUTTON_STYLE:
    _ORIG_BTN_INIT = InlineKeyboardButton.__init__

    def _compat_btn_init(self, *args, style=None, **kwargs):
        _ORIG_BTN_INIT(self, *args, **kwargs)

    InlineKeyboardButton.__init__ = _compat_btn_init

import config

VALID_STYLES = ("none", "primary", "danger", "success", "mix", "pattern")
_STYLE_CYCLE = (ButtonStyle.PRIMARY, ButtonStyle.SUCCESS, ButtonStyle.DANGER)
_STYLE_MAP = {
    "none": ButtonStyle.DEFAULT,
    "primary": ButtonStyle.PRIMARY,
    "danger": ButtonStyle.DANGER,
    "success": ButtonStyle.SUCCESS,
}

_CURRENT_STYLE: str = "none"
_APPLY_TO_CLONES: bool = True
_ADMIN_CACHE: Set[int] = set()
_HOOK_INSTALLED: bool = False


def _get_mongodb():
    from ClonyMusic.core.mongo import mongodb
    return mongodb


_SC_MAP = str.maketrans(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ",
)


def small_caps(text: str) -> str:
    """Convert ASCII letters to Unicode small caps while keeping symbols/digits intact."""
    if not text or not isinstance(text, str):
        return text
    return str(text).translate(_SC_MAP)


def sc_button(text: str, *args, **kwargs) -> InlineKeyboardButton:
    """Create an InlineKeyboardButton whose label uses uniform small-caps styling."""
    return InlineKeyboardButton(small_caps(text), *args, **kwargs)


def get_button_style() -> str:
    return _CURRENT_STYLE


def get_apply_to_clones() -> bool:
    return _APPLY_TO_CLONES


async def load_button_style() -> str:
    global _CURRENT_STYLE, _APPLY_TO_CLONES
    try:
        doc = await _get_mongodb().bot_settings.find_one({"_id": "button_style"})
        if doc:
            if doc.get("mode") in VALID_STYLES:
                _CURRENT_STYLE = doc["mode"]
            if "apply_to_clones" in doc:
                _APPLY_TO_CLONES = bool(doc["apply_to_clones"])
    except Exception:
        pass
    return _CURRENT_STYLE


async def set_button_style(mode: str) -> str:
    global _CURRENT_STYLE
    mode = mode.lower().strip()
    if mode not in VALID_STYLES:
        raise ValueError(f"Invalid button style: {mode}")
    _CURRENT_STYLE = mode
    await _get_mongodb().bot_settings.update_one(
        {"_id": "button_style"},
        {"$set": {"mode": mode}},
        upsert=True,
    )
    return _CURRENT_STYLE


async def set_apply_to_clones(enabled: bool) -> bool:
    global _APPLY_TO_CLONES
    _APPLY_TO_CLONES = bool(enabled)
    await _get_mongodb().bot_settings.update_one(
        {"_id": "button_style"},
        {"$set": {"apply_to_clones": _APPLY_TO_CLONES}},
        upsert=True,
    )
    return _APPLY_TO_CLONES


def _resolve_style(mode: str, index: int) -> ButtonStyle:
    if mode in _STYLE_MAP:
        return _STYLE_MAP[mode]
    if mode == "mix":
        return random.choice(_STYLE_CYCLE)
    if mode == "pattern":
        return _STYLE_CYCLE[index % len(_STYLE_CYCLE)]
    return ButtonStyle.DEFAULT


def apply_style_to_markup(markup: InlineKeyboardMarkup) -> InlineKeyboardMarkup:
    if not markup or not getattr(markup, "inline_keyboard", None):
        return markup
    mode = _CURRENT_STYLE
    idx = 0
    for row in markup.inline_keyboard:
        if not row:
            continue
        for btn in row:
            if isinstance(btn, InlineKeyboardButton):
                if getattr(btn, "text", None):
                    btn.text = small_caps(btn.text)
                if _SUPPORTS_BUTTON_STYLE and mode != "none":
                    if getattr(btn, "style", ButtonStyle.DEFAULT) == ButtonStyle.DEFAULT:
                        btn.style = _resolve_style(mode, idx)
            idx += 1
    return markup


def install_button_style_hook() -> None:
    """Hook InlineKeyboardMarkup.__init__ so all bot buttons automatically follow the active style."""
    global _HOOK_INSTALLED
    if _HOOK_INSTALLED:
        return
    _orig_init = InlineKeyboardMarkup.__init__

    def _styled_init(self, *args, **kwargs):
        try:
            _orig_init(self, *args, **kwargs)
        except TypeError:
            try:
                sig = inspect.signature(_orig_init)
                valid_kw = {k: v for k, v in kwargs.items() if k in sig.parameters}
                _orig_init(self, *args, **valid_kw)
            except Exception:
                ik = kwargs.get("inline_keyboard")
                if ik is not None:
                    try:
                        _orig_init(self, inline_keyboard=ik)
                    except Exception:
                        _orig_init(self, [])
                elif args:
                    try:
                        _orig_init(self, args[0])
                    except Exception:
                        _orig_init(self, [])
                else:
                    _orig_init(self, [])
        except Exception:
            try:
                _orig_init(self, [])
            except Exception:
                pass

        try:
            apply_style_to_markup(self)
        except Exception:
            pass

    InlineKeyboardMarkup.__init__ = _styled_init
    _HOOK_INSTALLED = True


# ---------------- BOT ADMINS MANAGEMENT ----------------

async def load_bot_admins() -> Set[int]:
    global _ADMIN_CACHE
    _ADMIN_CACHE = set()
    if config.OWNER_ID:
        _ADMIN_CACHE.add(int(config.OWNER_ID))
    for uid in getattr(config, "BOT_ADMINS", []):
        _ADMIN_CACHE.add(int(uid))
    try:
        doc = await _get_mongodb().bot_settings.find_one({"_id": "bot_admins"})
        if doc and isinstance(doc.get("admins"), list):
            for uid in doc["admins"]:
                _ADMIN_CACHE.add(int(uid))
    except Exception:
        pass
    return _ADMIN_CACHE


def is_bot_admin(user_id: int) -> bool:
    if not user_id:
        return False
    uid = int(user_id)
    if config.OWNER_ID and uid == int(config.OWNER_ID):
        return True
    if uid in getattr(config, "BOT_ADMINS", []):
        return True
    return uid in _ADMIN_CACHE


async def get_db_admins() -> List[int]:
    try:
        doc = await _get_mongodb().bot_settings.find_one({"_id": "bot_admins"})
        if doc and isinstance(doc.get("admins"), list):
            return [int(x) for x in doc["admins"]]
    except Exception:
        pass
    return []


async def add_bot_admin(user_id: int) -> bool:
    uid = int(user_id)
    _ADMIN_CACHE.add(uid)
    await _get_mongodb().bot_settings.update_one(
        {"_id": "bot_admins"},
        {"$addToSet": {"admins": uid}},
        upsert=True,
    )
    return True


async def remove_bot_admin(user_id: int) -> bool:
    uid = int(user_id)
    if config.OWNER_ID and uid == int(config.OWNER_ID):
        return False
    _ADMIN_CACHE.discard(uid)
    await _get_mongodb().bot_settings.update_one(
        {"_id": "bot_admins"},
        {"$pull": {"admins": uid}},
    )
    return True
