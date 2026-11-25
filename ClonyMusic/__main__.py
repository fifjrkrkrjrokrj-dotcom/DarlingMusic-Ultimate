
import asyncio
import importlib

try:
    import uvloop
    uvloop.install()
except ImportError:
    pass

from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

import config
from ClonyMusic import LOGGER, app, userbot
from ClonyMusic.core.call import Lucky
from ClonyMusic.misc import sudo
from ClonyMusic.plugins import ALL_MODULES
from ClonyMusic.utils.database import get_banned_users, get_gbanned
from ClonyMusic.utils.button_style import (
    install_button_style_hook,
    load_bot_admins,
    load_button_style,
)
from ClonyMusic.utils.fsub import load_fsub_settings
from ClonyMusic.utils.feature_flags import load_feature_flags
from ClonyMusic.utils.player_extras import load_autoplay_chats, load_247_chats
from config import BANNED_USERS
from ClonyMusic.plugins.tools.clone import restart_bots


async def init():
    if not config.STRING1:
        LOGGER(__name__).error("String Session not filled, please Provide a valid session.")
        exit()
    install_button_style_hook()
    await sudo()
    await load_button_style()
    await load_bot_admins()
    await load_fsub_settings()
    await load_feature_flags()
    await load_autoplay_chats()
    await load_247_chats()
    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except:
        pass
    await app.start()
    for all_module in ALL_MODULES:
        importlib.import_module("ClonyMusic.plugins" + all_module)
    LOGGER("ClonyMusic.plugins").info("𝐀𝐥𝐥 𝐅𝐞𝐚𝐭𝐮𝐫𝐞𝐬 𝐋𝐨𝐚𝐝𝐞𝐝 𝐁𝐚𝐛𝐲🥳...")
    await userbot.start()
    await Lucky.start()
    try:
        await Lucky.stream_call("https://te.legra.ph/file/29f784eb49d230ab62e9e.mp4")
    except NoActiveGroupCall:
        LOGGER("ClonyMusic").error(
            "𝗣𝗹𝗭 𝗦𝗧𝗔𝗥𝗧 𝗬𝗢𝗨𝗥 𝗟𝗢𝗚 𝗚𝗥𝗢𝗨𝗣 𝗩𝗢𝗜𝗖𝗘𝗖𝗛𝗔𝗧\𝗖𝗛𝗔𝗡𝗡𝗘𝗟\n\n𝗠𝗨𝗦𝗜𝗖 𝗕𝗢𝗧 𝗦𝗧𝗢𝗣........"
        )
        exit()
    except:
        pass
    await Lucky.decorators()
    await restart_bots()
    LOGGER("ClonyMusic").info(f"✨ {config.BOT_NAME} Started Successfully!")
    await idle()
    await app.stop()
    await userbot.stop()
    LOGGER("ClonyMusic").info("𝗦𝗧𝗢𝗣 𝗠𝗨𝗦𝗜𝗖🎻 𝗕𝗢𝗧..")


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(init())
