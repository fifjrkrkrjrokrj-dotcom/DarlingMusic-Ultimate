from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from ClonyMusic import LOGGER
from ClonyMusic.core.call import Lucky
from ClonyMusic.misc import db
from ClonyMusic.utils.database import is_nonadmin_chat
from ClonyMusic.utils.feature_flags import is_feature_enabled
from ClonyMusic.utils.player_extras import (
    build_playlist_ui,
    clear_user_playlist,
    fetch_lyrics,
    get_user_playlist,
    handle_voteskip,
    has_vc_admin_rights,
    play_saved_tracks,
    remove_user_track,
    save_track_for_user,
    toggle_247,
    toggle_autoplay,
    track_playlist_message,
)
from config import BANNED_USERS


@Client.on_message(filters.command(["myplaylist", "saved", "playlist"], prefixes=["/", "!", "%", ",", "", ".", "@", "#"]) & ~BANNED_USERS)
async def clone_my_playlist_cmd(client, message: Message):
    if not is_feature_enabled("save"):
        return await message.reply_text("<b>Disabled:</b> Saved Playlist is currently turned off by Admin.")
    if not message.from_user:
        return
    tracks = await get_user_playlist(message.from_user.id)
    text, markup = build_playlist_ui(message.from_user.id, tracks)
    photo = None
    if tracks and tracks[0].get("vidid"):
        photo = f"https://img.youtube.com/vi/{tracks[0]['vidid']}/hqdefault.jpg"
    if not photo:
        raw_pl = getattr(config, "PLAYLIST_IMG_URL", None)
        if raw_pl:
            photo = random.choice(raw_pl) if isinstance(raw_pl, list) else raw_pl
    sent = None
    if photo:
        try:
            sent = await message.reply_photo(photo=photo, caption=text, reply_markup=markup, has_spoiler=True)
        except Exception:
            pass
    if not sent:
        try:
            sent = await message.reply_text(text, reply_markup=markup)
        except Exception:
            pass
    if sent:
        track_playlist_message(sent, delay=300)
    return


@Client.on_message(filters.command(["247", "24x7"], prefixes=["/", "!", "%", ",", "", ".", "@", "#"]) & filters.group & ~BANNED_USERS)
async def clone_toggle_247_cmd(client, message: Message):
    if not is_feature_enabled("247"):
        return await message.reply_text("<b>Disabled:</b> 24/7 Mode is currently turned off by Admin.")
    state = toggle_247(message.chat.id)
    await message.reply_text(
        f"<b>24/7 VC Mode:</b> <code>{'ON (Assistant will stay in VC)' if state else 'OFF'}</code>"
    )


@Client.on_message(filters.command(["autoplay", "radio"], prefixes=["/", "!", "%", ",", "", ".", "@", "#"]) & filters.group & ~BANNED_USERS)
async def clone_toggle_autoplay_cmd(client, message: Message):
    if not is_feature_enabled("autoplay"):
        return await message.reply_text("<b>Disabled:</b> AutoPlay is currently turned off by Admin.")
    state = toggle_autoplay(message.chat.id)
    await message.reply_text(
        f"<b>AutoPlay Radio Mode:</b> <code>{'ON' if state else 'OFF'}</code>"
    )


@Client.on_message(filters.command(["lyrics"], prefixes=["/", "!", "%", ",", "", ".", "@", "#"]) & ~BANNED_USERS)
async def clone_lyrics_cmd(client, message: Message):
    if not is_feature_enabled("lyrics"):
        return await message.reply_text("<b>Disabled:</b> Lyrics feature is currently turned off by Admin.")
    query = message.text.split(None, 1)[1] if len(message.command) > 1 else None
    if not query and db.get(message.chat.id):
        query = db[message.chat.id][0].get("title")
    if not query:
        return await message.reply_text("Usage: `/lyrics <song name>`")
    msg = await message.reply_text(f"<b>Searching lyrics for:</b> <code>{query[:40]}</code>...")
    txt = await fetch_lyrics(query)
    if not txt:
        return await msg.edit_text("<b>Lyrics not found for this track.</b>")
    await msg.edit_text(
        f"<b>Lyrics — {query[:40]}</b>\n\n{txt}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close")]]),
    )


@Client.on_message(filters.command(["voteskip"], prefixes=["/", "!", "%", ",", "", ".", "@", "#"]) & filters.group & ~BANNED_USERS)
async def clone_voteskip_cmd(client, message: Message):
    if not message.from_user:
        return
    _ok, info = await handle_voteskip(client, message.chat.id, message.from_user.id, message)
    await message.reply_text(f"<b>{info}</b>")


@Client.on_callback_query(filters.regex(r"^(SaveTrack|AutoPlayToggle|GetLyrics|VoteSkip|ToggleAV)\|") & ~BANNED_USERS)
async def clone_player_extra_callbacks(client, cq: CallbackQuery):
    try:
        action, chat_str = cq.data.split("|", 1)
        chat_id = int(chat_str)

        if action == "ToggleAV":
            if not is_feature_enabled("av_switch"):
                return await cq.answer("Audio/Video switch is disabled by Admin.", show_alert=True)
            is_non_admin = await is_nonadmin_chat(chat_id)
            if not is_non_admin and not await has_vc_admin_rights(client, chat_id, cq.from_user.id):
                return await cq.answer("Only Group Admins can switch Audio/Video.", show_alert=True)
            playing = db.get(chat_id)
            if not playing:
                return await cq.answer("Nothing is playing right now.", show_alert=True)
            await cq.answer("Switching stream mode...", show_alert=False)
            new_mode = await Lucky.switch_av_stream(chat_id, playing[0])
            if not new_mode:
                return await cq.message.reply_text("<b>Failed to switch stream mode for this track.</b>")
            return await cq.message.reply_text(f"<b>Stream switched to {new_mode.upper()} mode.</b>")

        if action == "VoteSkip":
            _ok, info = await handle_voteskip(client, chat_id, cq.from_user.id, cq.message)
            return await cq.answer(info, show_alert=True)

        if action == "SaveTrack":
            if not is_feature_enabled("save"):
                return await cq.answer("Saved Playlist is disabled by Admin.", show_alert=True)
            playing = db.get(chat_id)
            if not playing:
                return await cq.answer("Nothing is playing right now.", show_alert=True)
            res = await save_track_for_user(cq.from_user.id, playing[0])
            if res == "exists":
                return await cq.answer("Already in your Saved Playlist.", show_alert=True)
            if res == "full":
                return await cq.answer("Playlist full (max 30 tracks).", show_alert=True)
            return await cq.answer("Saved to your playlist! Use /myplaylist to play.", show_alert=True)

        if action == "AutoPlayToggle":
            if not is_feature_enabled("autoplay"):
                return await cq.answer("AutoPlay is disabled by Admin.", show_alert=True)
            state = toggle_autoplay(chat_id)
            return await cq.answer(f"AutoPlay Radio: {'ON' if state else 'OFF'}", show_alert=True)

        if action == "GetLyrics":
            if not is_feature_enabled("lyrics"):
                return await cq.answer("Lyrics feature is disabled by Admin.", show_alert=True)
            playing = db.get(chat_id)
            if not playing:
                return await cq.answer("Nothing is playing right now.", show_alert=True)
            title = playing[0].get("title", "")
            await cq.answer("Fetching lyrics...", show_alert=False)
            txt = await fetch_lyrics(title)
            if not txt:
                return await cq.message.reply_text("<b>Lyrics not found for current song.</b>")
            await cq.message.reply_text(
                f"<b>Lyrics — {title[:40]}</b>\n\n{txt}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close")]]),
            )
    except Exception as e:
        LOGGER(__name__).error(f"clone player_extra_callbacks error ({cq.data}): {e}")
        await cq.answer(f"Action failed: {type(e).__name__}", show_alert=True)


@Client.on_callback_query(filters.regex(r"^(OpenMyPlaylist|UPL)") & ~BANNED_USERS)
async def clone_user_playlist_callbacks(client, cq: CallbackQuery):
    try:
        data = cq.data
        uid = cq.from_user.id

        if data == "OpenMyPlaylist":
            tracks = await get_user_playlist(uid)
            text, markup = build_playlist_ui(uid, tracks)
            await cq.answer()
            sent = await cq.message.reply_text(text, reply_markup=markup)
            if sent:
                track_playlist_message(sent, delay=300)
            return

        action, payload = data.split("|", 1) if "|" in data else (data, "")
        owner_uid = int(payload.split()[-1]) if " " in payload else int(payload)
        if uid != owner_uid:
            return await cq.answer("Yeh kisi aur ki playlist hai! Apna /myplaylist open karein.", show_alert=True)

        track_playlist_message(cq.message, delay=300)

        if data.startswith("UPLRefresh|"):
            tracks = await get_user_playlist(uid)
            text, markup = build_playlist_ui(uid, tracks)
            await cq.answer("Refreshed")
            return await cq.edit_message_text(text, reply_markup=markup)

        if data.startswith("UPLClear|"):
            await clear_user_playlist(uid)
            text, markup = build_playlist_ui(uid, [])
            await cq.answer("Playlist cleared!", show_alert=True)
            return await cq.edit_message_text(text, reply_markup=markup)

        if data.startswith("UPLDelOne "):
            idx = int(data.split(" ", 1)[1].split("|")[0])
            await remove_user_track(uid, idx)
            tracks = await get_user_playlist(uid)
            text, markup = build_playlist_ui(uid, tracks)
            await cq.answer("Removed track!")
            return await cq.edit_message_text(text, reply_markup=markup)

        tracks = await get_user_playlist(uid)
        if not tracks:
            return await cq.answer("Your playlist is empty!", show_alert=True)

        if data.startswith("UPLPlayAll "):
            kind = data.split(" ", 1)[1].split("|")[0]
            return await play_saved_tracks(client, cq, tracks, video=(kind == "v"), shuffle=False)

        if data.startswith("UPLShuffle|"):
            return await play_saved_tracks(client, cq, tracks, video=False, shuffle=True)

        if data.startswith("UPLPlayOne "):
            idx = int(data.split(" ", 1)[1].split("|")[0])
            if 0 <= idx < len(tracks):
                return await play_saved_tracks(client, cq, [tracks[idx]], video=False, shuffle=False)
    except Exception as e:
        LOGGER(__name__).error(f"clone user_playlist_callbacks error ({cq.data}): {e}")
        await cq.answer(f"Playlist error: {type(e).__name__}", show_alert=True)
