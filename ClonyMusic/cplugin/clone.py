import random
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

import config
from ClonyMusic import app
from ClonyMusic.utils.decorators.language import language

def get_random_start_img():
    if config.START_IMG_URL:
        if isinstance(config.START_IMG_URL, list):
            return random.choice(config.START_IMG_URL)
        return config.START_IMG_URL
    return "https://telegra.ph/file/2e3d368e77c449c287430.jpg"

@Client.on_message(filters.command("clone") & ~config.BANNED_USERS)
@language
async def ping_clone(client: Client, message: Message, _):
    host_username = app.username
    if not host_username:
        try:
            me = await app.get_me()
            host_username = me.username
        except Exception:
            host_username = "ClonyMusicBot"

    bot_link = f"https://t.me/{host_username}?start=clone"
    caption = _["NO_CLONE_MSG"].format(host_username)

    await message.reply_photo(
        photo=get_random_start_img(),
        caption=caption,
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("ɢᴏ ᴀɴᴅ ᴄʟᴏɴᴇ", url=bot_link)]
            ]
        ),
        has_spoiler=True
    )
