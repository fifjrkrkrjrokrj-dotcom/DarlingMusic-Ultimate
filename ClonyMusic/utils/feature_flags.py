from typing import Dict

from ClonyMusic.core.mongo import mongodb

FEATURE_LABELS = {
    "effects": "Audio Effects",
    "queue": "Queue & Play Now",
    "save": "Save & My Playlist",
    "autoplay": "AutoPlay Radio",
    "lyrics": "Live Lyrics",
    "shuffle": "Shuffle",
    "247": "24/7 VC Mode",
    "voteskip": "Vote-to-Skip",
    "av_switch": "Audio/Video Switch",
    "vc_notify": "VC Join/Invite Alerts",
}

_FLAGS: Dict[str, bool] = {k: True for k in FEATURE_LABELS}
VALID_LOG_MODES = ("all", "play_error", "error_only", "off")
_LOG_MODE: str = "all"


def get_log_mode() -> str:
    return _LOG_MODE


def should_log(kind: str) -> bool:
    if _LOG_MODE == "off":
        return False
    if _LOG_MODE == "error_only":
        return kind == "error"
    if _LOG_MODE == "play_error":
        return kind in ("play", "error")
    return True


async def set_log_mode(mode: str) -> str:
    global _LOG_MODE
    mode = mode.lower().strip()
    if mode not in VALID_LOG_MODES:
        raise ValueError(f"Invalid log mode: {mode}")
    _LOG_MODE = mode
    await mongodb.bot_settings.update_one(
        {"_id": "log_mode"},
        {"$set": {"mode": mode}},
        upsert=True,
    )
    return _LOG_MODE


def is_feature_enabled(name: str) -> bool:
    return _FLAGS.get(name, True)


def get_all_features() -> Dict[str, bool]:
    return dict(_FLAGS)


async def load_feature_flags() -> Dict[str, bool]:
    global _LOG_MODE
    try:
        doc = await mongodb.bot_settings.find_one({"_id": "feature_flags"})
        if doc and isinstance(doc.get("flags"), dict):
            for k in FEATURE_LABELS:
                if k in doc["flags"]:
                    _FLAGS[k] = bool(doc["flags"][k])
        ldoc = await mongodb.bot_settings.find_one({"_id": "log_mode"})
        if ldoc and ldoc.get("mode") in VALID_LOG_MODES:
            _LOG_MODE = ldoc["mode"]
    except Exception:
        pass
    return dict(_FLAGS)


async def toggle_feature_flag(name: str) -> bool:
    if name not in FEATURE_LABELS:
        return True
    new_val = not _FLAGS.get(name, True)
    _FLAGS[name] = new_val
    await mongodb.bot_settings.update_one(
        {"_id": "feature_flags"},
        {"$set": {f"flags.{name}": new_val}},
        upsert=True,
    )
    return new_val
