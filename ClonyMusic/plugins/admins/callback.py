import asyncio
import os
import random
from pyrogram.errors import MessageNotModified
from pyrogram.types import CallbackQuery, InputMediaVideo, InputMediaPhoto, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram import filters

from ClonyMusic import LOGGER, YouTube, app
from ClonyMusic.core.call import Lucky
from ClonyMusic.misc import SUDOERS, db
from ClonyMusic.utils.database import (
    get_active_chats, get_lang, get_upvote_count, is_active_chat,
    is_music_playing, is_nonadmin_chat, music_off, music_on, set_loop, get_assistant
)
from ClonyMusic.utils.decorators.language import languageCB
from ClonyMusic.utils.formatters import seconds_to_min
from ClonyMusic.utils.inline import close_markup, stream_markup, stream_markup_timer
from ClonyMusic.utils.inline.play import effects_markup, more_controls_markup, panel_markup_1
from ClonyMusic.utils.feature_flags import is_feature_enabled
from ClonyMusic.utils.player_extras import has_vc_admin_rights, is_player_menu_active, set_player_menu_active
from ClonyMusic.utils.stream.autoclear import auto_clean
from ClonyMusic.utils.thumbnails import get_thumb
import config
from config import (
    BANNED_USERS, SOUNCLOUD_IMG_URL, STREAM_IMG_URL, TELEGRAM_AUDIO_URL,
    TELEGRAM_VIDEO_URL, START_IMG_URL, adminlist, confirmer, votemode
)
from strings import get_string
from ClonyMusic.utils.inline.start import private_panel, support_panel

checker = {}
upvoters = {}

# --- BACK BUTTON HANDLER (Fix for Video/Photo + Random Image) ---
@app.on_callback_query(filters.regex("settingsback_helper") & ~BANNED_USERS)
@languageCB
async def settings_back_helper(client, CallbackQuery, _):
    try:
        await CallbackQuery.answer()
    except:
        pass
    
    # Agar START_IMG_URL list hai to random choice karega, nahi to direct string lega
    if isinstance(START_IMG_URL, list):
        img = random.choice(START_IMG_URL)
    else:
        img = START_IMG_URL

    await CallbackQuery.edit_message_media(
        media=InputMediaPhoto(
            media=img,
            caption=_["start_2"].format(CallbackQuery.from_user.mention, app.mention)
        ),
        reply_markup=InlineKeyboardMarkup(private_panel(_))
    )

# --- SUPPORT PAGE ---
@app.on_callback_query(filters.regex("support_page") & ~BANNED_USERS)
async def support_cb(client, callback_query):
    try:
        _ = get_string("en")
        await callback_query.answer()
        await callback_query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(support_panel(_))
        )
    except Exception as e:
        await callback_query.answer(f"Error: {e}", show_alert=True)

# --- CLONE PAGE ---
@app.on_callback_query(filters.regex("clone_page") & ~BANNED_USERS)
@languageCB
async def clone_page_cb(client, CallbackQuery, _):
    await CallbackQuery.answer()
    clone_text = (
        "**ᴍᴀᴋᴇ ʏᴏᴜʀ ᴏᴡɴ ᴍᴜsɪᴄ ʙᴏᴛ ᴡᴀᴛᴄʜɪɴɢ ᴛʜᴇ ᴠɪᴅᴇᴏ ᴄᴀʀᴇғᴜʟʟʏ.**\n\n"
        "<blockquote><b><u>ᴄʟᴏɴᴇ ᴄᴏᴍᴍᴀɴᴅs :</u></b>\n\n"
        "<b><u>ᴀʟʟ ᴜsᴇʀs :</u></b>\n"
        "/clone – <b>ᴄʟᴏɴᴇ ʏᴏᴜʀ ᴏᴡɴ ʙᴏᴛ ᴜsɪɴɢ ʙᴏᴛ ᴛᴏᴋᴇɴ ғʀᴏᴍ @BotFather.</b>\n"
        "<b>ᴇxᴀᴍᴘʟᴇ:</b> /clone <code>ᴘᴀsᴛᴇ_ᴛᴏᴋᴇɴ_ʜᴇʀᴇ</code>\n\n"
        "/rmbot – <b>ᴅᴇʟᴇᴛᴇ ʏᴏᴜʀ ᴄʟᴏɴᴇᴅ ʙᴏᴛ.</b>\n\n"
        "/mybot – <b>ᴄʜᴇᴄᴋ ᴛʜᴇ ʙᴏᴛs ʏᴏᴜ'ᴠᴇ ᴄʟᴏɴᴇᴅ.</b></blockquote>"
    )
    await CallbackQuery.edit_message_media(
        media=InputMediaVideo(
            media="https://files.catbox.moe/rxiwb3.mp4",
            caption=clone_text
        ),
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(text="⌯ ʙᴀᴄᴋ ⌯", callback_data="settingsback_helper")]
            ]
        )
    )

# --- SOURCE PAGE (Video + Owner + Back) ---
@app.on_callback_query(filters.regex("gib_source"))
async def gib_repo_callback(_, callback_query):
    await callback_query.edit_message_media(
        media=InputMediaVideo(
            "https://telegra.ph/file/b1367262cdfbcd0b2af07.mp4",
            caption="ʟᴜɴᴅ ʟᴇʟᴇ ᴍᴇʀᴀ ʀᴇᴘᴏ ᴋʏᴀ ᴋᴀʀᴇɢᴀ, ʟᴇɢᴀ ᴋʏᴀ ʙʜᴏsᴀᴅɪᴋᴇ"
        ),
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(text="• ʙᴀᴄᴋ •", callback_data="settingsback_helper"),
                    InlineKeyboardButton(text="• ᴄʟᴏsᴇ •", callback_data="close")
                ]
            ]
        ),
    )

# --- UNBAN ASSISTANT ---
@app.on_callback_query(filters.regex("unban_assistant"))
async def unban_assistant(_, callback: CallbackQuery):
    chat_id = callback.message.chat.id
    userbot = await get_assistant(chat_id)
    try:
        await app.unban_chat_member(chat_id, userbot.id)
        await callback.answer("Assistant Unbanned Successfully!", show_alert=True)
    except Exception:
        await callback.answer("Failed to unban. Give me Admin permissions.", show_alert=True)

# --- ADMIN COMMANDS ---
@app.on_callback_query(filters.regex("ADMIN") & ~BANNED_USERS)
@languageCB
async def del_back_playlist(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    callback_request = callback_data.split(None, 1)[1]
    command, chat = callback_request.split("|")
    if "_" in str(chat):
        bet = chat.split("_")
        chat = bet[0]
        counter = bet[1]
    chat_id = int(chat)
    if not await is_active_chat(chat_id):
        return await CallbackQuery.answer(_["general_5"], show_alert=True)
    mention = CallbackQuery.from_user.mention
    
    if command == "UpVote":
        if chat_id not in votemode: votemode[chat_id] = {}
        if chat_id not in upvoters: upvoters[chat_id] = {}
        
        voters = (upvoters[chat_id]).get(CallbackQuery.message.id)
        if not voters: upvoters[chat_id][CallbackQuery.message.id] = []
        
        vote = (votemode[chat_id]).get(CallbackQuery.message.id)
        if not vote: votemode[chat_id][CallbackQuery.message.id] = 0
        
        if CallbackQuery.from_user.id in upvoters[chat_id][CallbackQuery.message.id]:
            (upvoters[chat_id][CallbackQuery.message.id]).remove(CallbackQuery.from_user.id)
            votemode[chat_id][CallbackQuery.message.id] -= 1
        else:
            (upvoters[chat_id][CallbackQuery.message.id]).append(CallbackQuery.from_user.id)
            votemode[chat_id][CallbackQuery.message.id] += 1
            
        upvote = await get_upvote_count(chat_id)
        get_upvotes = int(votemode[chat_id][CallbackQuery.message.id])
        
        if get_upvotes >= upvote:
            votemode[chat_id][CallbackQuery.message.id] = upvote
            try:
                exists = confirmer[chat_id][CallbackQuery.message.id]
                current = db[chat_id][0]
                if current["vidid"] != exists["vidid"] or current["file"] != exists["file"]:
                    return await CallbackQuery.edit_message_text(_["admin_35"])
            except:
                return await CallbackQuery.edit_message_text(_["admin_36"])
            try:
                await CallbackQuery.edit_message_text(_["admin_37"].format(upvote))
            except:
                pass
            command = counter
            mention = "ᴜᴘᴠᴏᴛᴇs"
        else:
            if CallbackQuery.from_user.id in upvoters[chat_id][CallbackQuery.message.id]:
                await CallbackQuery.answer(_["admin_38"], show_alert=True)
            else:
                await CallbackQuery.answer(_["admin_39"], show_alert=True)
            upl = InlineKeyboardMarkup([[InlineKeyboardButton(text=f"👍 {get_upvotes}", callback_data=f"ADMIN  UpVote|{chat_id}_{counter}")]])
            await CallbackQuery.answer(_["admin_40"], show_alert=True)
            return await CallbackQuery.edit_message_reply_markup(reply_markup=upl)
    else:
        is_non_admin = await is_nonadmin_chat(CallbackQuery.message.chat.id)
        if not is_non_admin:
            if CallbackQuery.from_user.id not in SUDOERS:
                admins = adminlist.get(CallbackQuery.message.chat.id)
                if not admins or CallbackQuery.from_user.id not in admins:
                    return await CallbackQuery.answer(_["admin_14"], show_alert=True)
                    
    if command == "Pause":
        if not await is_music_playing(chat_id): return await CallbackQuery.answer(_["admin_1"], show_alert=True)
        await CallbackQuery.answer()
        await music_off(chat_id)
        await Lucky.pause_stream(chat_id)
        await CallbackQuery.message.reply_text(_["admin_2"].format(mention), reply_markup=close_markup(_))
    elif command == "Resume":
        if await is_music_playing(chat_id): return await CallbackQuery.answer(_["admin_3"], show_alert=True)
        await CallbackQuery.answer()
        await music_on(chat_id)
        await Lucky.resume_stream(chat_id)
        await CallbackQuery.message.reply_text(_["admin_4"].format(mention), reply_markup=close_markup(_))
    elif command == "Stop" or command == "End":
        await CallbackQuery.answer()
        await Lucky.stop_stream(chat_id)
        await set_loop(chat_id, 0)
        await CallbackQuery.message.reply_text(_["admin_5"].format(mention), reply_markup=close_markup(_))
        await CallbackQuery.message.delete()
    elif command == "Skip" or command == "Replay":
        check = db.get(chat_id)
        if command == "Skip":
            txt = f"➻ sᴛʀᴇᴀᴍ sᴋɪᴩᴩᴇᴅ 🎄\n│ \n└ʙʏ : {mention} 🥀"
            try:
                popped = check.pop(0)
                if popped: await auto_clean(popped)
                if not check:
                    await CallbackQuery.edit_message_text(txt)
                    await CallbackQuery.message.reply_text(_["admin_6"].format(mention, CallbackQuery.message.chat.title), reply_markup=close_markup(_))
                    return await Lucky.stop_stream(chat_id)
            except:
                return await Lucky.stop_stream(chat_id)
        else:
            txt = f"➻ sᴛʀᴇᴀᴍ ʀᴇ-ᴘʟᴀʏᴇᴅ 🎄\n│ \n└ʙʏ : {mention} 🥀"
        
        await CallbackQuery.answer()
        queued = check[0]["file"]
        title = (check[0]["title"]).title()
        user = check[0]["by"]
        duration = check[0]["dur"]
        streamtype = check[0]["streamtype"]
        videoid = check[0]["vidid"]
        status = True if str(streamtype) == "video" else None
        db[chat_id][0]["played"] = 0
        
        try:
            image = await YouTube.thumbnail(videoid, True)
        except:
            image = None
            
        try:
            if "live_" in queued:
                n, link = await YouTube.video(videoid, True)
                if n == 0:
                    return await CallbackQuery.message.reply_text(_["admin_7"].format(title))
                target_file = link
            elif "vid_" in queued:
                target_file, _direct = await YouTube.download(videoid, None, videoid=True, video=bool(status))
                if not target_file:
                    return await CallbackQuery.message.reply_text(_["call_6"])
            else:
                target_file = queued

            _, img = await asyncio.gather(
                Lucky.skip_stream(chat_id, target_file, video=status),
                get_thumb(videoid),
            )
        except Exception:
            return await CallbackQuery.message.reply_text(_["call_6"])

        button = stream_markup(_, chat_id)
        run = await CallbackQuery.message.reply_photo(
            photo=img if img else (random.choice(STREAM_IMG_URL) if isinstance(STREAM_IMG_URL, list) else STREAM_IMG_URL),
            caption=_["stream_1"].format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], duration, user),
            reply_markup=InlineKeyboardMarkup(button),
            has_spoiler=True,
        )
        db[chat_id][0]["mystic"] = run
        db[chat_id][0]["markup"] = "stream"
        await CallbackQuery.edit_message_text(txt, reply_markup=close_markup(_))


@app.on_callback_query(filters.regex(r"^GetTimer$") & ~BANNED_USERS)
async def main_get_timer_cb(client, CallbackQuery: CallbackQuery):
    chat_id = CallbackQuery.message.chat.id
    playing = db.get(chat_id)
    if playing:
        played = seconds_to_min(int(playing[0].get("played") or 0))
        dur = playing[0].get("dur") or "0:00"
        return await CallbackQuery.answer(f"Playing: {played} / {dur}", show_alert=False)
    return await CallbackQuery.answer("Live Playback Progress", show_alert=False)


@app.on_callback_query(filters.regex(r"^(PanelMarkup|MainMarkup|MusicMarkup)") & ~BANNED_USERS)
@languageCB
async def main_panel_switch_cb(client, CallbackQuery: CallbackQuery, _):
    try:
        await CallbackQuery.answer()
        data = CallbackQuery.data.strip()
        chat_id = CallbackQuery.message.chat.id
        if data.startswith("PanelMarkup"):
            videoid = data.split(None, 1)[1].split("|")[0]
            buttons = panel_markup_1(_, videoid, chat_id)
        else:
            buttons = stream_markup(_, chat_id)
        await CallbackQuery.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
    except MessageNotModified:
        pass
    except Exception as e:
        LOGGER(__name__).error(f"main_panel_switch_cb error: {e}")


@app.on_callback_query(filters.regex(r"^(PlayerMore|PlayerBack|AudioFXMenu|AudioFXBack)\|") & ~BANNED_USERS)
@languageCB
async def audio_fx_menu_cb(client, CallbackQuery: CallbackQuery, _):
    try:
        action, chat_str = CallbackQuery.data.split("|", 1)
        chat_id = int(chat_str)
        if action == "AudioFXMenu" and not is_feature_enabled("effects"):
            return await CallbackQuery.answer("Audio Effects are currently disabled by Admin.", show_alert=True)
        await CallbackQuery.answer()
        msg_id = CallbackQuery.message.id
        if action in ("PlayerMore", "AudioFXMenu"):
            set_player_menu_active(chat_id, True)
            checker.setdefault(chat_id, {})[msg_id] = False
        else:
            set_player_menu_active(chat_id, False)
            checker.setdefault(chat_id, {})[msg_id] = True

        if action == "AudioFXMenu":
            markup = effects_markup(_, chat_id)
        elif action == "PlayerMore":
            markup = more_controls_markup(_, chat_id)
        else:
            markup = stream_markup(_, chat_id)
        await CallbackQuery.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(markup))
    except MessageNotModified:
        pass
    except Exception as e:
        LOGGER(__name__).error(f"audio_fx_menu_cb error ({CallbackQuery.data}): {e}")
        await CallbackQuery.answer(f"Menu error: {type(e).__name__}", show_alert=True)


@app.on_callback_query(filters.regex(r"^AudioFX ") & ~BANNED_USERS)
@languageCB
async def audio_fx_apply_cb(client, CallbackQuery: CallbackQuery, _):
    try:
        if not is_feature_enabled("effects"):
            return await CallbackQuery.answer("Audio Effects are currently disabled by Admin.", show_alert=True)
        payload = CallbackQuery.data.split(" ", 1)[1]
        effect, chat_str = payload.split("|", 1)
        chat_id = int(chat_str)

        is_non_admin = await is_nonadmin_chat(chat_id)
        if not is_non_admin and not await has_vc_admin_rights(client, chat_id, CallbackQuery.from_user.id):
            return await CallbackQuery.answer(_["admin_14"], show_alert=True)

        playing = db.get(chat_id)
        if not playing:
            return await CallbackQuery.answer("Nothing is playing right now.", show_alert=True)

        file_path = playing[0].get("file")
        streamtype = playing[0].get("streamtype", "audio")
        if not file_path or "live_" in str(file_path):
            return await CallbackQuery.answer("Effects not available on live stream.", show_alert=True)
        if "vid_" in str(file_path):
            check_sp = playing[0].get("speed_path")
            if check_sp and os.path.exists(check_sp):
                file_path = check_sp
            else:
                n, file_path = await YouTube.video(playing[0]["vidid"], True)
                if n == 0 or not file_path:
                    return await CallbackQuery.answer("Cannot resolve stream for effect.", show_alert=True)
        elif playing[0].get("speed_path") and os.path.exists(playing[0].get("speed_path")):
            file_path = playing[0].get("speed_path")

        await CallbackQuery.answer(f"Applying {effect.upper()} effect...", show_alert=False)
        await Lucky.effect_stream(chat_id, file_path, effect, mode=str(streamtype))
        checker.setdefault(chat_id, {})[CallbackQuery.message.id] = True
        try:
            await CallbackQuery.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(stream_markup(_, chat_id)))
        except MessageNotModified:
            pass
    except Exception as e:
        LOGGER(__name__).error(f"audio_fx_apply_cb error: {e}")
        await CallbackQuery.answer(f"Effect error: {type(e).__name__}", show_alert=True)

async def markup_timer():
    while not await asyncio.sleep(7):
        active_chats = await get_active_chats()
        for chat_id in active_chats:
            try:
                if is_player_menu_active(chat_id):
                    continue
                if not await is_music_playing(chat_id):
                    continue
                playing = db.get(chat_id)
                if not playing or int(playing[0]["seconds"]) == 0:
                    continue
                mystic = playing[0]["mystic"]
                try:
                    if checker.get(chat_id, {}).get(mystic.id) is False:
                        continue
                except:
                    pass
                
                try:
                    language = await get_lang(chat_id)
                    _ = get_string(language)
                except: _ = get_string("en")
                
                try:
                    buttons = stream_markup_timer(_, chat_id, seconds_to_min(playing[0]["played"]), playing[0]["dur"])
                    await mystic.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
                except: continue
            except: continue

try:
    asyncio.create_task(markup_timer())
except Exception:
    pass
