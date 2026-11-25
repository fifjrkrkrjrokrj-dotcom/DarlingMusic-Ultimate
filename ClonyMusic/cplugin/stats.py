import platform
import random
from sys import version as pyver

import psutil
from pyrogram import __version__ as pyrover
from pyrogram import filters, Client
from pyrogram.errors import MessageIdInvalid
from pyrogram.types import InputMediaPhoto, Message
from pytgcalls.__version__ import __version__ as pytgver

import config
from ClonyMusic import app
from ClonyMusic.core.userbot import assistants
from ClonyMusic.misc import SUDOERS, mongodb
from ClonyMusic.plugins import ALL_MODULES
from ClonyMusic.utils.database import (
    get_served_chats_clone,
    get_served_users_clone,
    get_sudoers,
)
from ClonyMusic.utils.decorators.language import language, languageCB
from ClonyMusic.utils.inline.stats import back_stats_buttons, stats_buttons
from config import BANNED_USERS


# ✅ Helper to get Random Stats Image
def get_random_stats_img():
    if config.STATS_IMG_URL:
        if isinstance(config.STATS_IMG_URL, list):
            return random.choice(config.STATS_IMG_URL)
        return config.STATS_IMG_URL
    return "https://i.ibb.co/pBqPtFYn/statistics.jpg"


@Client.on_message(filters.command(["stats", "gstats"], prefixes=["/", "!", "%", ",", "", ".", "@", "#"]) & ~BANNED_USERS)
@language
async def stats_global(client: Client, message: Message, _):
    a = await client.get_me()
    bot_id = a.id

    upl = stats_buttons(_, True if message.from_user.id in SUDOERS else False)
    caption_text = _["gstats_2"].format(a.mention)
    img = get_random_stats_img()
    
    # ✅ Random Image + Spoiler (with text fallback)
    try:
        await message.reply_photo(
            photo=img,
            caption=caption_text,
            reply_markup=upl,
            has_spoiler=True
        )
    except Exception:
        await message.reply_text(
            text=caption_text,
            reply_markup=upl,
        )


@Client.on_callback_query(filters.regex("stats_back") & ~BANNED_USERS)
@languageCB
async def home_stats(client, CallbackQuery, _):
    a = await client.get_me()
    bot_id = a.id
    upl = stats_buttons(_, True if CallbackQuery.from_user.id in SUDOERS else False)
    caption_text = _["gstats_2"].format(a.mention)
    try:
        await CallbackQuery.edit_message_caption(
            caption=caption_text,
            reply_markup=upl,
        )
    except Exception:
        await CallbackQuery.edit_message_text(
            text=caption_text,
            reply_markup=upl,
        )


@Client.on_callback_query(filters.regex("TopOverall") & ~BANNED_USERS)
@languageCB
async def overall_stats(client, CallbackQuery, _):
    a = await client.get_me()
    bot_id = a.id
    try:
        await CallbackQuery.answer()
    except Exception:
        pass
    upl = back_stats_buttons(_)
    loading_text = _["gstats_1"].format(a.mention)
    try:
        await CallbackQuery.edit_message_caption(loading_text)
    except Exception:
        try:
            await CallbackQuery.edit_message_text(loading_text)
        except Exception:
            pass
    
    # Fetch Clone Stats
    try:
        served_chats = len(await get_served_chats_clone(bot_id))
    except Exception:
        served_chats = 0
    try:
        served_users = len(await get_served_users_clone(bot_id))
    except Exception:
        served_users = 0
    
    text = _["gstats_3"].format(
        a.mention,
        len(assistants),
        len(BANNED_USERS),
        served_chats,
        served_users,
        len(ALL_MODULES),
        len(SUDOERS),
        config.AUTO_LEAVING_ASSISTANT,
        config.DURATION_LIMIT_MIN,
    )
    img = get_random_stats_img()
    try:
        await CallbackQuery.edit_message_caption(caption=text, reply_markup=upl)
    except Exception:
        try:
            await CallbackQuery.edit_message_text(text=text, reply_markup=upl)
        except Exception:
            try:
                med = InputMediaPhoto(media=img, caption=text, has_spoiler=True)
                await CallbackQuery.edit_message_media(media=med, reply_markup=upl)
            except Exception:
                await CallbackQuery.message.reply_photo(
                    photo=img, caption=text, reply_markup=upl, has_spoiler=True
                )


@Client.on_callback_query(filters.regex("bot_stats_sudo"))
@languageCB
async def bot_stats(client, CallbackQuery, _):
    a = await client.get_me()
    bot_id = a.id
    if CallbackQuery.from_user.id not in SUDOERS:
        return await CallbackQuery.answer(_["gstats_4"], show_alert=True)
    upl = back_stats_buttons(_)
    try:
        await CallbackQuery.answer()
    except Exception:
        pass
        
    loading_text = _["gstats_1"].format(a.mention)
    try:
        await CallbackQuery.edit_message_caption(loading_text)
    except Exception:
        try:
            await CallbackQuery.edit_message_text(loading_text)
        except Exception:
            pass
    
    p_core = psutil.cpu_count(logical=False) or 1
    t_core = psutil.cpu_count(logical=True) or 1
    ram = str(round(psutil.virtual_memory().total / (1024.0**3))) + " GB"
    try:
        cpu_freq = psutil.cpu_freq().current
        if cpu_freq >= 1000:
            cpu_freq = f"{round(cpu_freq / 1000, 2)}GHz"
        else:
            cpu_freq = f"{round(cpu_freq, 2)}MHz"
    except Exception:
        cpu_freq = "Failed to fetch"
    
    try:
        hdd = psutil.disk_usage("/")
        total = hdd.total / (1024.0**3)
        used = hdd.used / (1024.0**3)
        free = hdd.free / (1024.0**3)
    except Exception:
        total, used, free = 0, 0, 0
    try:
        call = await mongodb.command("dbstats")
        datasize = call.get("dataSize", 0) / 1024
        storage = call.get("storageSize", 0) / 1024
        collections = call.get("collections", 0)
        objects = call.get("objects", 0)
    except Exception:
        datasize, storage, collections, objects = 0, 0, 0, 0
    
    # Fetch Clone Stats
    try:
        served_chats = len(await get_served_chats_clone(bot_id))
    except Exception:
        served_chats = 0
    try:
        served_users = len(await get_served_users_clone(bot_id))
    except Exception:
        served_users = 0
    
    text = _["gstats_5"].format(
        a.mention,
        len(ALL_MODULES),
        platform.system(),
        ram,
        p_core,
        t_core,
        cpu_freq,
        pyver.split()[0],
        pyrover,
        pytgver,
        str(total)[:4],
        str(used)[:4],
        str(free)[:4],
        served_chats,
        served_users,
        len(BANNED_USERS),
        len(await get_sudoers()),
        str(datasize)[:6],
        storage,
        collections,
        objects,
    )
    img = get_random_stats_img()
    try:
        await CallbackQuery.edit_message_caption(caption=text, reply_markup=upl)
    except Exception:
        try:
            await CallbackQuery.edit_message_text(text=text, reply_markup=upl)
        except Exception:
            try:
                med = InputMediaPhoto(media=img, caption=text, has_spoiler=True)
                await CallbackQuery.edit_message_media(media=med, reply_markup=upl)
            except Exception:
                await CallbackQuery.message.reply_photo(
                    photo=img, caption=text, reply_markup=upl, has_spoiler=True
                )