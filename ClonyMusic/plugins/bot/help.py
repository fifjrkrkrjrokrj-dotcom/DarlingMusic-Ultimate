import random
from typing import Union
from pyrogram import enums, filters, types
from pyrogram.types import InlineKeyboardMarkup, Message, InlineKeyboardButton
from ClonyMusic import app
from ClonyMusic.utils import help_pannel
from ClonyMusic.utils.database import get_lang
from ClonyMusic.utils.decorators.language import LanguageStart, languageCB
from ClonyMusic.utils.inline.help import help_back_markup, private_help_panel
from config import BANNED_USERS, START_IMG_URL, SUPPORT_CHAT
from strings import get_string, helpers
from ClonyMusic.utils.stuffs.helper import Helper

# ✅ Helper to safe get Random Image
def get_random_start_img():
    if START_IMG_URL:
        if isinstance(START_IMG_URL, list):
            return random.choice(START_IMG_URL)
        return START_IMG_URL
    return "https://telegra.ph/file/2e3d368e77c449c287430.jpg" # Fallback

@app.on_message(filters.command(["help"], prefixes=["/", "!", "%", ",", "", ".", "@", "#"]) & filters.private & ~BANNED_USERS)
@app.on_callback_query(filters.regex("settings_back_helper") & ~BANNED_USERS)
async def helper_private(
    client: app, update: Union[types.Message, types.CallbackQuery]
):
    is_callback = isinstance(update, types.CallbackQuery)
    if is_callback:
        try:
            await update.answer()
        except:
            pass
        chat_id = update.message.chat.id
        language = await get_lang(chat_id)
        _ = get_string(language)
        keyboard = help_pannel(_, True)
        
        # Callback just edits text, no spoiler needed here
        await update.edit_message_text(
            _["help_1"].format(SUPPORT_CHAT), reply_markup=keyboard
        )
    else:
        try:
            await update.delete()
        except:
            pass
        language = await get_lang(update.chat.id)
        _ = get_string(language)
        keyboard = help_pannel(_)
        
        # ✅ Random Photo + Spoiler Logic
        try:
            await update.reply_photo(
                photo=get_random_start_img(),
                caption=_["help_1"].format(SUPPORT_CHAT),
                reply_markup=keyboard,
                has_spoiler=True # ✨ Spoiler Added
            )
        except Exception:
            await update.reply_text(
                _["help_1"].format(SUPPORT_CHAT),
                reply_markup=keyboard,
            )


@app.on_message(filters.command(["help"], prefixes=["/", "!", "%", ",", "", ".", "@", "#"]) & filters.group & ~BANNED_USERS)
@LanguageStart
async def help_com_group(client, message: Message, _):
    keyboard = private_help_panel(_)
    await message.reply_text(_["help_2"], reply_markup=InlineKeyboardMarkup(keyboard))


@app.on_callback_query(filters.regex("help_callback") & ~BANNED_USERS)
@languageCB
async def helper_cb(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    cb = callback_data.split(None, 1)[1]
    keyboard = help_back_markup(_)
    
    if cb == "hb1":
        await CallbackQuery.edit_message_text(helpers.HELP_1, reply_markup=keyboard)
    elif cb == "hb2":
        await CallbackQuery.edit_message_text(helpers.HELP_2, reply_markup=keyboard)
    elif cb == "hb3":
        await CallbackQuery.edit_message_text(helpers.HELP_3, reply_markup=keyboard)
    elif cb == "hb4":
        await CallbackQuery.edit_message_text(helpers.HELP_4, reply_markup=keyboard)
    elif cb == "hb5":
        await CallbackQuery.edit_message_text(helpers.HELP_5, reply_markup=keyboard)
    elif cb == "hb6":
        await CallbackQuery.edit_message_text(helpers.HELP_6, reply_markup=keyboard)
    elif cb == "hb7":
        await CallbackQuery.edit_message_text(helpers.HELP_7, reply_markup=keyboard)
    elif cb == "hb8":
        await CallbackQuery.edit_message_text(helpers.HELP_8, reply_markup=keyboard)
    elif cb == "hb9":
        await CallbackQuery.edit_message_text(helpers.HELP_9, reply_markup=keyboard)
    elif cb == "hb10":
        await CallbackQuery.edit_message_text(helpers.HELP_10, reply_markup=keyboard)
    elif cb == "hb11":
        await CallbackQuery.edit_message_text(helpers.HELP_11, reply_markup=keyboard)
    elif cb == "hb12":
        await CallbackQuery.edit_message_text(helpers.HELP_12, reply_markup=keyboard)
    elif cb == "hb13":
        await CallbackQuery.edit_message_text(helpers.HELP_13, reply_markup=keyboard)
    elif cb == "hb14":
        await CallbackQuery.edit_message_text(helpers.HELP_14, reply_markup=keyboard)
    elif cb == "hb15":
        await CallbackQuery.edit_message_text(helpers.HELP_15, reply_markup=keyboard)
    elif cb == "all_features":
        await CallbackQuery.edit_message_text(
            "<blockquote><b><u>All Music & Player Commands</u></b></blockquote>\n\n"
            "<b>Playback & Queue:</b>\n"
            "• `/play` / `/vplay` / `/playforce` / `/vplayforce`\n"
            "• `/queue` or `/q` — View queue + Group Admin Play Now\n"
            "• `More` on player — Audio Effects (8D, Bass, Nightcore, Vocal), Audio/Video Switch, Lyrics, AutoPlay, Shuffle\n"
            "• `/pause` `/resume` `/skip` `/stop` `/seek` `/speed` `/loop` `/shuffle`\n"
            "• `/voteskip` — Vote to skip playing track\n"
            "• `/247` — Toggle 24/7 VC mode\n\n"
            "<b>Saved Playlist & Utility:</b>\n"
            "• `/myplaylist` (`/saved`) — Access & play saved tracks\n"
            "• `/lyrics` `/song` `/ping` `/stats`\n\n"
            "<b>Clone System:</b>\n"
            "• `/clone <token>` — Clone your own music bot\n"
            "• `/mybots` — View your cloned bots\n"
            "• `/cpanel` (in Clone DM) — Clone Owner Panel",
            reply_markup=keyboard,
        )


@app.on_callback_query(filters.regex('managebot123'))
async def on_back_button(client, CallbackQuery):
    callback_data = CallbackQuery.data.strip()
    cb = callback_data.split(None, 1)[1]
    
    # We need to get language here to pass to help_pannel
    language = await get_lang(CallbackQuery.message.chat.id)
    _ = get_string(language)
    
    keyboard = help_pannel(_, True)
    if cb == "settings_back_helper":
        await CallbackQuery.edit_message_text(
            _["help_1"].format(SUPPORT_CHAT), reply_markup=keyboard
        )

@app.on_callback_query(filters.regex('mplus'))      
async def mb_plugin_button(client, CallbackQuery):
    callback_data = CallbackQuery.data.strip()
    cb = callback_data.split(None, 1)[1]
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("ʙᴀᴄᴋ", callback_data=f"mbot_cb")]])
    if cb == "Okieeeeee":
        await CallbackQuery.edit_message_text(f"`something errors`",reply_markup=keyboard,parse_mode=enums.ParseMode.MARKDOWN)
    else:
        await CallbackQuery.edit_message_text(getattr(Helper, cb), reply_markup=keyboard)