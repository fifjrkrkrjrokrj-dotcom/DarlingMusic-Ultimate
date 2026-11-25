import math
from config import SUPPORT_CHAT, OWNER_USERNAME
from pyrogram.types import InlineKeyboardButton
from ClonyMusic import app
from ClonyMusic.misc import db
import config
from ClonyMusic.utils.formatters import seconds_to_min, time_to_seconds


def build_progress_bar(played, dur):
    """Compute playback progress bar without dividing by zero."""
    try:
        played_sec = time_to_seconds(played)
        duration_sec = time_to_seconds(dur)
    except Exception:
        return "◉—————————"
    if duration_sec <= 0:
        return "◉—————————"
    umm = math.floor((played_sec / duration_sec) * 100)
    if umm <= 10:
        return "◉—————————"
    if umm < 20:
        return "—◉————————"
    if umm < 30:
        return "——◉———————"
    if umm < 40:
        return "———◉——————"
    if umm < 50:
        return "————◉—————"
    if umm < 60:
        return "—————◉————"
    if umm < 70:
        return "——————◉———"
    if umm < 80:
        return "———————◉——"
    if umm < 95:
        return "————————◉—"
    return "—————————◉"


def get_chat_progress_times(chat_id):
    playing = db.get(chat_id)
    played_str = "0:00"
    dur_str = "0:00"
    if playing and isinstance(playing, list) and isinstance(playing[0], dict):
        dur_str = str(playing[0].get("dur") or "0:00")
        try:
            played_str = seconds_to_min(int(playing[0].get("played") or 0))
        except Exception:
            played_str = "0:00"
    return played_str, dur_str


def track_markup(_, videoid, user_id, channel, fplay):
    buttons = [
        [
            InlineKeyboardButton(
                text=_["P_B_1"],
                callback_data=f"MusicStream {videoid}|{user_id}|a|{channel}|{fplay}",
            ),
            InlineKeyboardButton(
                text=_["P_B_2"],
                callback_data=f"MusicStream {videoid}|{user_id}|v|{channel}|{fplay}",
            ),
        ],
        [
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data=f"forceclose {videoid}|{user_id}",
            )
        ],
    ]
    return buttons


def stream_markup_timer(_, chat_id, played, dur):
    bar = build_progress_bar(played, dur)

    buttons = [
        [
            InlineKeyboardButton(
                text=f"{played} {bar} {dur}",
                callback_data="GetTimer",
            )
        ],
        [
            InlineKeyboardButton(text="▷", callback_data=f"ADMIN Resume|{chat_id}"),
            InlineKeyboardButton(text="II", callback_data=f"ADMIN Pause|{chat_id}"),
            InlineKeyboardButton(text="↻", callback_data=f"ADMIN Replay|{chat_id}"),
            InlineKeyboardButton(text="‣‣I", callback_data=f"ADMIN Skip|{chat_id}"),
            InlineKeyboardButton(text="▢", callback_data=f"ADMIN Stop|{chat_id}"),
        ],
        [
            InlineKeyboardButton(text="ᴍᴏʀᴇ", callback_data=f"PlayerMore|{chat_id}"),
            InlineKeyboardButton(text=_["CLOSE_BUTTON"], callback_data="close"),
        ]
    ]
    return buttons


def stream_markup(_, chat_id):
    played_str, dur_str = get_chat_progress_times(chat_id)
    return stream_markup_timer(_, chat_id, played_str, dur_str)


def more_controls_markup(_, chat_id):
    from ClonyMusic.utils.feature_flags import is_feature_enabled

    pool = []
    if is_feature_enabled("effects"):
        pool.append(InlineKeyboardButton(text="ᴇғғᴇᴄᴛs", callback_data=f"AudioFXMenu|{chat_id}"))
    if is_feature_enabled("queue"):
        pool.append(InlineKeyboardButton(text="ǫᴜᴇᴜᴇ", callback_data=f"OpenQueue|{chat_id}"))
    if is_feature_enabled("save"):
        pool.append(InlineKeyboardButton(text="sᴀᴠᴇ", callback_data=f"SaveTrack|{chat_id}"))
    if is_feature_enabled("autoplay"):
        pool.append(InlineKeyboardButton(text="ᴀᴜᴛᴏᴘʟᴀʏ", callback_data=f"AutoPlayToggle|{chat_id}"))
    if is_feature_enabled("lyrics"):
        pool.append(InlineKeyboardButton(text="ʟʏʀɪᴄs", callback_data=f"GetLyrics|{chat_id}"))
    if is_feature_enabled("shuffle"):
        pool.append(InlineKeyboardButton(text="sʜᴜғғʟᴇ", callback_data=f"ADMIN Shuffle|{chat_id}"))
    if is_feature_enabled("voteskip"):
        pool.append(InlineKeyboardButton(text="ᴠᴏᴛᴇ sᴋɪᴘ", callback_data=f"VoteSkip|{chat_id}"))
    if is_feature_enabled("av_switch"):
        pool.append(InlineKeyboardButton(text="ᴀᴜᴅɪᴏ/ᴠɪᴅᴇᴏ", callback_data=f"ToggleAV|{chat_id}"))
    if is_feature_enabled("save"):
        pool.append(InlineKeyboardButton(text="ᴍʏ ᴘʟᴀʏʟɪsᴛ", callback_data="OpenMyPlaylist"))

    rows = [pool[i : i + 3] for i in range(0, len(pool), 3)]
    rows.append(
        [
            InlineKeyboardButton(text="ʙᴀᴄᴋ", callback_data=f"PlayerBack|{chat_id}"),
            InlineKeyboardButton(text=_["CLOSE_BUTTON"], callback_data="close"),
        ]
    )
    return rows


def effects_markup(_, chat_id):
    return [
        [
            InlineKeyboardButton(text="ʙᴀss ʙᴏᴏsᴛ", callback_data=f"AudioFX bass|{chat_id}"),
            InlineKeyboardButton(text="ɴɪɢʜᴛᴄᴏʀᴇ", callback_data=f"AudioFX nightcore|{chat_id}"),
        ],
        [
            InlineKeyboardButton(text="8ᴅ ᴀᴜᴅɪᴏ", callback_data=f"AudioFX 8d|{chat_id}"),
            InlineKeyboardButton(text="ᴠᴏᴄᴀʟ ʙᴏᴏsᴛ", callback_data=f"AudioFX vocal|{chat_id}"),
        ],
        [
            InlineKeyboardButton(text="ɴᴏʀᴍᴀʟ", callback_data=f"AudioFX normal|{chat_id}"),
            InlineKeyboardButton(text="ʙᴀᴄᴋ", callback_data=f"PlayerMore|{chat_id}"),
        ],
    ]


def playlist_markup(_, videoid, user_id, ptype, channel, fplay):
    buttons = [
        [
            InlineKeyboardButton(
                text=_["P_B_1"],
                callback_data=f"LuckyPlaylists {videoid}|{user_id}|{ptype}|a|{channel}|{fplay}",
            ),
            InlineKeyboardButton(
                text=_["P_B_2"],
                callback_data=f"LuckyPlaylists {videoid}|{user_id}|{ptype}|v|{channel}|{fplay}",
            ),
        ],
        [
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data=f"forceclose {videoid}|{user_id}",
            ),
        ],
    ]
    return buttons


def livestream_markup(_, videoid, user_id, mode, channel, fplay):
    buttons = [
        [
            InlineKeyboardButton(
                text=_["P_B_3"],
                callback_data=f"LiveStream {videoid}|{user_id}|{mode}|{channel}|{fplay}",
            ),
        ],
        [
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data=f"forceclose {videoid}|{user_id}",
            ),
        ],
    ]
    return buttons


def slider_markup(_, videoid, user_id, query, query_type, channel, fplay):
    query = f"{query[:20]}"
    buttons = [
        [
            InlineKeyboardButton(
                text=_["P_B_1"],
                callback_data=f"MusicStream {videoid}|{user_id}|a|{channel}|{fplay}",
            ),
            InlineKeyboardButton(
                text=_["P_B_2"],
                callback_data=f"MusicStream {videoid}|{user_id}|v|{channel}|{fplay}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="◁",
                callback_data=f"slider B|{query_type}|{query}|{user_id}|{channel}|{fplay}",
            ),
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data=f"forceclose {query}|{user_id}",
            ),
            InlineKeyboardButton(
                text="▷",
                callback_data=f"slider F|{query_type}|{query}|{user_id}|{channel}|{fplay}",
            ),
        ],
    ]
    return buttons


def telegram_markup(_, chat_id):
    buttons = [
        [
            InlineKeyboardButton(
                text="ɴᴇxᴛ",
                callback_data=f"PanelMarkup None|{chat_id}",
            ),
            InlineKeyboardButton(text=_["CLOSEMENU_BUTTON"], callback_data="close"),
        ],
    ]
    return buttons


def queue_markup(_, videoid, chat_id):

    buttons = [
        [
            InlineKeyboardButton(
                text=_["S_B_3"],
                url=f"https://t.me/{app.username}?startgroup=true",
            ),
        ],
        [
            InlineKeyboardButton(
                text="II ᴘᴀᴜsᴇ",
                callback_data=f"ADMIN Pause|{chat_id}",
            ),
            InlineKeyboardButton(text="▢ sᴛᴏᴘ", callback_data=f"ADMIN Stop|{chat_id}"),
            InlineKeyboardButton(
                text="sᴋɪᴘ ‣‣I", callback_data=f"ADMIN Skip|{chat_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                text="▷ ʀᴇsᴜᴍᴇ", callback_data=f"ADMIN Resume|{chat_id}"
            ),
            InlineKeyboardButton(
                text="ʀᴇᴘʟᴀʏ ↺", callback_data=f"ADMIN Replay|{chat_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                text="ᴍᴏʀᴇ",
                callback_data=f"PanelMarkup None|{chat_id}",
            ),
        ],
    ]

    return buttons


def stream_markup2(_, chat_id):
    buttons = [
        [
            InlineKeyboardButton(
                text=_["S_B_3"],
                url=f"https://t.me/{app.username}?startgroup=true",
            ),
        ],
        [
            InlineKeyboardButton(text="▷", callback_data=f"ADMIN Resume|{chat_id}"),
            InlineKeyboardButton(text="II", callback_data=f"ADMIN Pause|{chat_id}"),
            InlineKeyboardButton(text="↻", callback_data=f"ADMIN Replay|{chat_id}"),
            InlineKeyboardButton(text="‣‣I", callback_data=f"ADMIN Skip|{chat_id}"),
            InlineKeyboardButton(text="▢", callback_data=f"ADMIN Stop|{chat_id}"),
        ],
        [
            InlineKeyboardButton(text="ᴍᴏʀᴇ", callback_data=f"PlayerMore|{chat_id}"),
            InlineKeyboardButton(text=_["CLOSEMENU_BUTTON"], callback_data="close"),
        ],
    ]
    return buttons


def stream_markup_timer2(_, chat_id, played, dur):
    played_sec = time_to_seconds(played)
    duration_sec = time_to_seconds(dur)
    percentage = (played_sec / duration_sec) * 100
    umm = math.floor(percentage)

    if 0 < umm <= 40:
        bar = "◉——————————"
    elif 10 < umm < 20:
        bar = "—◉—————————"
    elif 20 < umm < 30:
        bar = "——◉————————"
    elif 30 <= umm < 40:
        bar = "———◉———————"
    elif 40 <= umm < 50:
        bar = "————◉——————"
    elif 50 <= umm < 60:
        bar = "——————◉————"
    elif 50 <= umm < 70:
        bar = "———————◉———"
    else:
        bar = "——————————◉"

    buttons = [
        [
            InlineKeyboardButton(
                text=f"{played} {bar} {dur}",
                callback_data="GetTimer",
            )
        ],
        [
            InlineKeyboardButton(text="▷", callback_data=f"ADMIN Resume|{chat_id}"),
            InlineKeyboardButton(text="II", callback_data=f"ADMIN Pause|{chat_id}"),
            InlineKeyboardButton(text="↻", callback_data=f"ADMIN Replay|{chat_id}"),
            InlineKeyboardButton(text="‣‣I", callback_data=f"ADMIN Skip|{chat_id}"),
            InlineKeyboardButton(text="▢", callback_data=f"ADMIN Stop|{chat_id}"),
        ],
        [
            InlineKeyboardButton(text="ᴍᴏʀᴇ", callback_data=f"PlayerMore|{chat_id}"),
            InlineKeyboardButton(text=_["CLOSEMENU_BUTTON"], callback_data="close"),
        ],
    ]
    return buttons


def panel_markup_1(_, videoid, chat_id):
    buttons = [
        [
            InlineKeyboardButton(
                text=_["S_B_3"],
                url=f"https://t.me/{app.username}?startgroup=true",
            ),
        ],
        [
            InlineKeyboardButton(
                text="sᴜғғʟᴇ",
                callback_data=f"ADMIN Shuffle|{chat_id}",
            ),
            InlineKeyboardButton(text="ʟᴏᴏᴘ ↺", callback_data=f"ADMIN Loop|{chat_id}"),
        ],
        [
            InlineKeyboardButton(
                text="◁ 10 sᴇᴄ",
                callback_data=f"ADMIN 1|{chat_id}",
            ),
            InlineKeyboardButton(
                text="10 sᴇᴄ ▷",
                callback_data=f"ADMIN 2|{chat_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="ʜᴏᴍᴇ",
                callback_data=f"Pages Back|2|{videoid}|{chat_id}",
            ),
            InlineKeyboardButton(
                text="ɴᴇxᴛ",
                callback_data=f"Pages Forw|2|{videoid}|{chat_id}",
            ),
        ],
    ]
    return buttons


def panel_markup_2(_, videoid, chat_id):
    buttons = [
        [
            InlineKeyboardButton(
                text=_["S_B_3"],
                url=f"httpst.me/{app.username}?startgroup=true",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🕒 0.5x",
                callback_data=f"SpeedUP {chat_id}|0.5",
            ),
            InlineKeyboardButton(
                text="🕓 0.75x",
                callback_data=f"SpeedUP {chat_id}|0.75",
            ),
            InlineKeyboardButton(
                text="🕤 1.0x",
                callback_data=f"SpeedUP {chat_id}|1.0",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🕤 1.5x",
                callback_data=f"SpeedUP {chat_id}|1.5",
            ),
            InlineKeyboardButton(
                text="🕛 2.0x",
                callback_data=f"SpeedUP {chat_id}|2.0",
            ),
        ],
        [
            InlineKeyboardButton(
                text="ʙᴀᴄᴋ",
                callback_data=f"Pages Back|1|{videoid}|{chat_id}",
            ),
        ],
    ]
    return buttons


def panel_markup_5(_, videoid, chat_id):
    buttons = [
        [
            InlineKeyboardButton(
                text=_["S_B_3"],
                url=f"https:t.me/{app.username}?startgroup=true",
            ),
        ],
        [
            InlineKeyboardButton(text="ᴘᴀᴜsᴇ", callback_data=f"ADMIN Pause|{chat_id}"),
            InlineKeyboardButton(text="sᴛᴏᴘ", callback_data=f"ADMIN Stop|{chat_id}"),
            InlineKeyboardButton(text="sᴋɪᴘ", callback_data=f"ADMIN Skip|{chat_id}"),
        ],
        [
            InlineKeyboardButton(
                text="ʀᴇsᴜᴍᴇ", callback_data=f"ADMIN Resume|{chat_id}"
            ),
            InlineKeyboardButton(
                text="ʀᴇᴘʟᴀʏ", callback_data=f"ADMIN Replay|{chat_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                text="ʜᴏᴍᴇ",
                callback_data=f"MainMarkup {videoid}|{chat_id}",
            ),
            InlineKeyboardButton(
                text="ɴᴇxᴛ",
                callback_data=f"Pages Forw|1|{videoid}|{chat_id}",
            ),
        ],
    ]
    return buttons


def panel_markup_3(_, videoid, chat_id):
    buttons = [
        [
            InlineKeyboardButton(
                text="🕒 0.5x",
                callback_data=f"SpeedUP {chat_id}|0.5",
            ),
            InlineKeyboardButton(
                text="🕓 0.75x",
                callback_data=f"SpeedUP {chat_id}|0.75",
            ),
            InlineKeyboardButton(
                text="🕤 1.0x",
                callback_data=f"SpeedUP {chat_id}|1.0",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🕤 1.5x",
                callback_data=f"SpeedUP {chat_id}|1.5",
            ),
            InlineKeyboardButton(
                text="🕛 2.0x",
                callback_data=f"SpeedUP {chat_id}|2.0",
            ),
        ],
        [
            InlineKeyboardButton(
                text="ʙᴀᴄᴋ",
                callback_data=f"Pages Back|2|{videoid}|{chat_id}",
            ),
        ],
    ]
    return buttons


def panel_markup_4(_, vidid, chat_id, played, dur):
    played_sec = time_to_seconds(played)
    duration_sec = time_to_seconds(dur)
    percentage = (played_sec / duration_sec) * 100
    umm = math.floor(percentage)

    if 0 < umm <= 40:
        bar = "◉——————————"
    elif 10 < umm < 20:
        bar = "—◉—————————"
    elif 20 < umm < 30:
        bar = "——◉————————"
    elif 30 <= umm < 40:
        bar = "———◉———————"
    elif 40 <= umm < 50:
        bar = "————◉——————"
    elif 50 <= umm < 60:
        bar = "——————◉————"
    elif 50 <= umm < 70:
        bar = "———————◉———"
    else:
        bar = "——————————◉"

    buttons = [
        [
            InlineKeyboardButton(
                text=f"{played} {bar} {dur}",
                callback_data="GetTimer",
            )
        ],
        [
            InlineKeyboardButton(
                text="II ᴘᴀᴜsᴇ",
                callback_data=f"ADMIN Pause|{chat_id}",
            ),
            InlineKeyboardButton(
                text="▢ sᴛᴏᴘ ▢", callback_data=f"ADMIN Stop|{chat_id}"
            ),
            InlineKeyboardButton(
                text="sᴋɪᴘ ‣‣I", callback_data=f"ADMIN Skip|{chat_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                text="▷ ʀᴇsᴜᴍᴇ", callback_data=f"ADMIN Resume|{chat_id}"
            ),
            InlineKeyboardButton(
                text="ʀᴇᴘʟᴀʏ ↺", callback_data=f"ADMIN Replay|{chat_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                text="ʜᴏᴍᴇ",
                callback_data=f"MainMarkup {vidid}|{chat_id}",
            ),
        ],
    ]

    return buttons


def panel_markup_clone(_, vidid, chat_id):
    buttons = [
        [
            InlineKeyboardButton(text="▷", callback_data=f"ADMIN Resume|{chat_id}"),
            InlineKeyboardButton(text="II", callback_data=f"ADMIN Pause|{chat_id}"),
            InlineKeyboardButton(text="‣‣I", callback_data=f"ADMIN Skip|{chat_id}"),
            InlineKeyboardButton(text="▢", callback_data=f"ADMIN Stop|{chat_id}"),
        ],
        [
            InlineKeyboardButton(text=_["CLOSE_BUTTON"], callback_data="close")
        ],
    ]

    return buttons