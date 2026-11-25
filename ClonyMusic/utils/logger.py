from pyrogram.enums import ParseMode

from ClonyMusic import app
from ClonyMusic.utils.database import is_on_off
from ClonyMusic.utils.feature_flags import should_log
from config import LOGGER_ID


async def play_logs(message, streamtype, bot_mention=None):
    if not should_log("play"):
        return
    if await is_on_off(2):
        try:
            query = message.text.split(None, 1)[1]
        except Exception:
            query = "Link/File or Reply"
        if len(query) > 40:
            query = query[:37] + "..."

        mention = bot_mention or app.mention
        chat_title = message.chat.title or "Private Chat"
        if len(chat_title) > 25:
            chat_title = chat_title[:22] + "..."

        logger_text = (
            f"🎵 <b>{mention} ᴘʟᴀʏ</b>\n"
            f"👤 {message.from_user.mention} • 💬 {chat_title}\n"
            f"🎧 <code>{query}</code>"
        )
        if message.chat.id != LOGGER_ID:
            try:
                await app.send_message(
                    chat_id=LOGGER_ID,
                    text=logger_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
            except Exception:
                pass
        return


async def clone_bot_logs(client, message, bot_mention, clone_logger_id, streamtype):
    try:
        query = message.text.split(None, 1)[1]
    except Exception:
        query = "Link/File or Reply"
    if len(query) > 40:
        query = query[:37] + "..."

    chat_title = message.chat.title or "Private Chat"
    if len(chat_title) > 25:
        chat_title = chat_title[:22] + "..."

    log_text = (
        f"🎵 <b>{bot_mention} ᴘʟᴀʏ</b>\n"
        f"👤 {message.from_user.mention} • 💬 {chat_title}\n"
        f"🎧 <code>{query}</code>"
    )

    # 1. Clone Bot Owner logger (if set)
    if clone_logger_id and message.chat.id != int(clone_logger_id):
        try:
            await client.send_message(
                chat_id=int(clone_logger_id),
                text=log_text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except Exception:
            pass

    # 2. Main Admin Logger (only if not already sent to the same ID and play logs enabled)
    if should_log("play") and LOGGER_ID and int(clone_logger_id or 0) != LOGGER_ID and message.chat.id != LOGGER_ID:
        try:
            await app.send_message(
                chat_id=LOGGER_ID,
                text=log_text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except Exception:
            pass
