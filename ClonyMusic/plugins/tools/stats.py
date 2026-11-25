import asyncio
import platform
import random
from sys import version as pyver

import psutil
from pyrogram import __version__ as pyrover
from pyrogram import filters
from pyrogram.errors import MessageIdInvalid
from pyrogram.types import InputMediaPhoto, Message
from pytgcalls.__version__ import __version__ as pytgver

import config
from ClonyMusic import app
from ClonyMusic.core.userbot import assistants
from ClonyMusic.misc import SUDOERS, mongodb
from ClonyMusic.plugins import ALL_MODULES
from ClonyMusic.utils.database import get_served_chats, get_served_users, get_sudoers
from ClonyMusic.utils.decorators.language import language, languageCB
from ClonyMusic.utils.inline.stats import back_stats_buttons, stats_buttons
from config import BANNED_USERS


def get_stats_img():
    if config.STATS_IMG_URL:
        if isinstance(config.STATS_IMG_URL, list):
            return random.choice(config.STATS_IMG_URL)
        return config.STATS_IMG_URL
    return "https://i.ibb.co/pBqPtFYn/statistics.jpg"


@app.on_message(filters.command(["stats", "gstats"], prefixes=["/", "!", "%", ",", "", ".", "@", "#"]) & ~BANNED_USERS)
@language
async def stats_global(client, message: Message, _):
    upl = stats_buttons(_, True if message.from_user.id in SUDOERS else False)
    caption_text = _["gstats_2"].format(app.mention)
    img = get_stats_img()
    try:
        await message.reply_photo(
            photo=img,
            caption=caption_text,
            reply_markup=upl,
            has_spoiler=True,
        )
    except Exception:
        await message.reply_text(
            text=caption_text,
            reply_markup=upl,
        )


@app.on_callback_query(filters.regex("stats_back") & ~BANNED_USERS)
@languageCB
async def home_stats(client, CallbackQuery, _):
    upl = stats_buttons(_, True if CallbackQuery.from_user.id in SUDOERS else False)
    caption_text = _["gstats_2"].format(app.mention)
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


@app.on_callback_query(filters.regex("TopOverall") & ~BANNED_USERS)
@languageCB
async def overall_stats(client, CallbackQuery, _):
    try:
        await CallbackQuery.answer()
    except Exception:
        pass
    upl = back_stats_buttons(_)
    loading_text = _["gstats_1"].format(app.mention)
    try:
        await CallbackQuery.edit_message_caption(loading_text)
    except Exception:
        try:
            await CallbackQuery.edit_message_text(loading_text)
        except Exception:
            pass

    try:
        served_chats = len(await get_served_chats())
    except Exception:
        served_chats = 0
    try:
        served_users = len(await get_served_users())
    except Exception:
        served_users = 0

    text = _["gstats_3"].format(
        app.mention,
        len(assistants),
        len(BANNED_USERS),
        served_chats,
        served_users,
        len(ALL_MODULES),
        len(SUDOERS),
        config.AUTO_LEAVING_ASSISTANT,
        config.DURATION_LIMIT_MIN,
    )
    img = get_stats_img()
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


@app.on_callback_query(filters.regex("bot_stats_sudo"))
@languageCB
async def bot_stats(client, CallbackQuery, _):
    if CallbackQuery.from_user.id not in SUDOERS:
        return await CallbackQuery.answer(_["gstats_4"], show_alert=True)
    upl = back_stats_buttons(_)
    try:
        await CallbackQuery.answer()
    except Exception:
        pass
    loading_text = _["gstats_1"].format(app.mention)
    try:
        await CallbackQuery.edit_message_caption(loading_text)
    except Exception:
        try:
            await CallbackQuery.edit_message_text(loading_text)
        except Exception:
            pass

    p_core = psutil.cpu_count(logical=False) or 1
    t_core = psutil.cpu_count(logical=True) or 1
    ram = str(round(psutil.virtual_memory().total / (1024.0**3))) + " ɢʙ"
    try:
        cpu_freq = psutil.cpu_freq().current
        if cpu_freq >= 1000:
            cpu_freq = f"{round(cpu_freq / 1000, 2)}ɢʜᴢ"
        else:
            cpu_freq = f"{round(cpu_freq, 2)}ᴍʜᴢ"
    except Exception:
        cpu_freq = "ғᴀɪʟᴇᴅ ᴛᴏ ғᴇᴛᴄʜ"
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

    try:
        served_chats = len(await get_served_chats())
    except Exception:
        served_chats = 0
    try:
        served_users = len(await get_served_users())
    except Exception:
        served_users = 0

    text = _["gstats_5"].format(
        app.mention,
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
    img = get_stats_img()
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


@app.on_message(filters.command(["cleandb", "cleanstats", "resetstats"]) & SUDOERS)
async def clean_database_handler(client, message: Message):
    msg = await message.reply_text("🔄 **Checking database stats...**")
    try:
        args = message.text.split()
        if len(args) > 1 and args[1].lower() in ["all", "reset", "clear"]:
            await mongodb.chats.drop()
            await mongodb.tgusersdb.drop()
            return await msg.edit_text(
                "✅ **MongoDB served chats & served users completely reset!**\n\n"
                "Ab purana kachra saaf ho gaya hai. Ab se sirf vahi groups aur users add honge jo bot ko actually use karenge."
            )

        served_chats = await get_served_chats()
        total_chats = len(served_chats)
        await msg.edit_text(f"🔍 **Scanning `{total_chats}` chats in database to remove dead/kicked groups...**")
        
        deleted = 0
        for c in served_chats:
            chat_id = c.get("chat_id")
            if not chat_id:
                continue
            try:
                await client.get_chat(chat_id)
            except Exception:
                await mongodb.chats.delete_one({"chat_id": chat_id})
                deleted += 1
                await asyncio.sleep(0.02)

        remaining = total_chats - deleted
        await msg.edit_text(
            f"✅ **Database Cleanup Complete!**\n\n"
            f"🗑 **Removed Inactive/Kicked Groups:** `{deleted}`\n"
            f"✨ **Active Groups Remaining:** `{remaining}`\n\n"
            f"💡 *Agar bilkul 0 se fresh reset karna hai toh send karein:* `/cleandb all`"
        )
    except Exception as e:
        await msg.edit_text(f"❌ **Error during cleanup:** `{e}`")

